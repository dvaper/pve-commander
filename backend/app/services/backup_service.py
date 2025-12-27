"""
BackupService - Backup und Restore Funktionalitaet

Features:
- Selektives Backup (App-DB, NetBox-DB, Config, SSH, Playbooks, etc.)
- ZIP-Format mit Manifest
- PostgreSQL Backup via docker exec pg_dump
- Restore mit Validierung
"""
import asyncio
import gzip
import hashlib
import json
import logging
import os
import shutil
import subprocess
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.backup import BackupHistory, BackupSchedule

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Models
# =============================================================================

class BackupOptions(BaseModel):
    """Optionen fuer Backup-Erstellung"""
    include_app_db: bool = True
    include_netbox_db: bool = True
    include_terraform_state: bool = True
    include_ssh_keys: bool = True
    include_config: bool = True
    include_inventory: bool = True
    include_playbooks: bool = True
    include_terraform_modules: bool = True
    include_roles: bool = True
    include_netbox_media: bool = False


class BackupInfo(BaseModel):
    """Informationen ueber ein Backup"""
    id: str
    filename: str
    created_at: datetime
    size_bytes: int
    components: List[str]
    is_scheduled: bool
    status: str


class BackupResult(BaseModel):
    """Ergebnis einer Backup-Operation"""
    success: bool
    backup_id: Optional[str] = None
    filename: Optional[str] = None
    size_bytes: Optional[int] = None
    message: str
    components: List[str] = []


class RestoreResult(BaseModel):
    """Ergebnis einer Restore-Operation"""
    success: bool
    message: str
    restored_components: List[str] = []
    warnings: List[str] = []


class ScheduleInfo(BaseModel):
    """Informationen ueber den Backup-Zeitplan"""
    enabled: bool = False
    frequency: str = "daily"
    time: str = "02:00"
    retention_days: int = 7
    options: BackupOptions = BackupOptions()
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None


# =============================================================================
# BackupService
# =============================================================================

class BackupService:
    """Service fuer Backup und Restore Operationen"""

    def __init__(self):
        self.data_dir = Path(settings.data_dir)
        self.backup_dir = self.data_dir / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # Backup erstellen
    # -------------------------------------------------------------------------

    async def create_backup(self, options: BackupOptions, is_scheduled: bool = False) -> BackupResult:
        """
        Erstellt ein Backup mit den angegebenen Optionen.

        Args:
            options: BackupOptions mit den zu sichernden Komponenten
            is_scheduled: True wenn vom Scheduler aufgerufen

        Returns:
            BackupResult mit Erfolg/Fehler und Details
        """
        backup_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"backup_{timestamp}.zip"
        backup_path = self.backup_dir / filename
        temp_dir = self.backup_dir / f"temp_{backup_id}"

        try:
            # Temp-Verzeichnis erstellen
            temp_dir.mkdir(parents=True, exist_ok=True)
            components = []
            checksums = {}

            # Komponenten sichern
            if options.include_app_db:
                if await self._backup_sqlite(temp_dir):
                    components.append("app_db")
                    checksums["commander.db"] = self._calc_checksum(temp_dir / "commander.db")

            if options.include_netbox_db:
                if await self._backup_postgres(temp_dir):
                    components.append("netbox_db")
                    checksums["netbox.sql.gz"] = self._calc_checksum(temp_dir / "netbox.sql.gz")

            if options.include_config:
                if self._backup_config(temp_dir):
                    components.append("config")

            if options.include_ssh_keys:
                if self._backup_ssh(temp_dir):
                    components.append("ssh")

            if options.include_inventory:
                if self._backup_directory(self.data_dir / "inventory", temp_dir / "inventory"):
                    components.append("inventory")

            if options.include_playbooks:
                if self._backup_directory(self.data_dir / "playbooks", temp_dir / "playbooks"):
                    components.append("playbooks")

            if options.include_terraform_state:
                if self._backup_terraform_state(temp_dir):
                    components.append("terraform_state")

            if options.include_terraform_modules:
                if self._backup_directory(
                    self.data_dir / "terraform" / "modules",
                    temp_dir / "terraform" / "modules"
                ):
                    components.append("terraform_modules")

            if options.include_roles:
                if self._backup_directory(self.data_dir / "roles", temp_dir / "roles"):
                    components.append("roles")

            if options.include_netbox_media:
                if self._backup_directory(
                    self.data_dir / "netbox" / "media",
                    temp_dir / "netbox" / "media"
                ):
                    components.append("netbox_media")

            # Manifest erstellen
            manifest = {
                "version": "1.0",
                "app_version": os.getenv("VERSION", "unknown"),
                "created_at": datetime.now().isoformat(),
                "components": components,
                "checksums": checksums,
                "options": options.model_dump()
            }

            with open(temp_dir / "manifest.json", "w") as f:
                json.dump(manifest, f, indent=2)

            # ZIP erstellen
            with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(temp_dir)
                        zf.write(file_path, arcname)

            # Groesse ermitteln
            size_bytes = backup_path.stat().st_size

            # In Datenbank speichern
            await self._save_backup_history(
                backup_id=backup_id,
                filename=filename,
                size_bytes=size_bytes,
                components=components,
                is_scheduled=is_scheduled
            )

            logger.info(f"Backup erstellt: {filename} ({size_bytes} bytes, {len(components)} Komponenten)")

            return BackupResult(
                success=True,
                backup_id=backup_id,
                filename=filename,
                size_bytes=size_bytes,
                message=f"Backup erfolgreich erstellt",
                components=components
            )

        except Exception as e:
            logger.error(f"Backup fehlgeschlagen: {e}")
            return BackupResult(
                success=False,
                message=f"Backup fehlgeschlagen: {str(e)}"
            )

        finally:
            # Temp-Verzeichnis aufraeumen
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    # -------------------------------------------------------------------------
    # Einzelne Komponenten sichern
    # -------------------------------------------------------------------------

    async def _backup_sqlite(self, temp_dir: Path) -> bool:
        """Sichert die SQLite App-Datenbank"""
        try:
            src = self.data_dir / "db" / "commander.db"
            if not src.exists():
                logger.warning("SQLite-Datenbank nicht gefunden")
                return False

            dst = temp_dir / "commander.db"
            shutil.copy2(src, dst)
            logger.debug(f"SQLite gesichert: {dst}")
            return True

        except Exception as e:
            logger.error(f"SQLite-Backup fehlgeschlagen: {e}")
            return False

    async def _backup_postgres(self, temp_dir: Path) -> bool:
        """Sichert die PostgreSQL NetBox-Datenbank via docker exec"""
        try:
            # pg_dump via docker exec
            cmd = [
                "docker", "exec", "pve-commander-postgres",
                "pg_dump", "-U", "netbox", "netbox"
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 Minuten Timeout
            )

            if result.returncode != 0:
                logger.error(f"pg_dump fehlgeschlagen: {result.stderr}")
                return False

            # Komprimieren und speichern
            dst = temp_dir / "netbox.sql.gz"
            with gzip.open(dst, "wt", encoding="utf-8") as f:
                f.write(result.stdout)

            logger.debug(f"PostgreSQL gesichert: {dst}")
            return True

        except subprocess.TimeoutExpired:
            logger.error("PostgreSQL-Backup: Timeout")
            return False
        except Exception as e:
            logger.error(f"PostgreSQL-Backup fehlgeschlagen: {e}")
            return False

    def _backup_config(self, temp_dir: Path) -> bool:
        """Sichert die Konfigurationsdatei"""
        try:
            src = self.data_dir / "config" / ".env"
            if not src.exists():
                logger.warning("Config-Datei nicht gefunden")
                return False

            dst_dir = temp_dir / "config"
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst_dir / ".env")
            logger.debug(f"Config gesichert")
            return True

        except Exception as e:
            logger.error(f"Config-Backup fehlgeschlagen: {e}")
            return False

    def _backup_ssh(self, temp_dir: Path) -> bool:
        """Sichert SSH-Keys"""
        try:
            src_dir = self.data_dir / "ssh"
            if not src_dir.exists():
                logger.warning("SSH-Verzeichnis nicht gefunden")
                return False

            dst_dir = temp_dir / "ssh"
            dst_dir.mkdir(parents=True, exist_ok=True)

            for key_file in ["id_ed25519", "id_ed25519.pub", "known_hosts"]:
                src = src_dir / key_file
                if src.exists():
                    shutil.copy2(src, dst_dir / key_file)

            logger.debug(f"SSH-Keys gesichert")
            return True

        except Exception as e:
            logger.error(f"SSH-Backup fehlgeschlagen: {e}")
            return False

    def _backup_terraform_state(self, temp_dir: Path) -> bool:
        """Sichert Terraform State-Dateien"""
        try:
            src_dir = self.data_dir / "terraform"
            if not src_dir.exists():
                return False

            dst_dir = temp_dir / "terraform"
            dst_dir.mkdir(parents=True, exist_ok=True)

            for state_file in ["terraform.tfstate", "terraform.tfstate.backup"]:
                src = src_dir / state_file
                if src.exists():
                    shutil.copy2(src, dst_dir / state_file)

            logger.debug(f"Terraform State gesichert")
            return True

        except Exception as e:
            logger.error(f"Terraform-State-Backup fehlgeschlagen: {e}")
            return False

    def _backup_directory(self, src_dir: Path, dst_dir: Path) -> bool:
        """Sichert ein komplettes Verzeichnis"""
        try:
            if not src_dir.exists():
                return False

            shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
            logger.debug(f"Verzeichnis gesichert: {src_dir.name}")
            return True

        except Exception as e:
            logger.error(f"Verzeichnis-Backup fehlgeschlagen ({src_dir}): {e}")
            return False

    # -------------------------------------------------------------------------
    # Restore
    # -------------------------------------------------------------------------

    async def restore_backup(self, backup_path: Path) -> RestoreResult:
        """
        Stellt ein Backup wieder her.

        Args:
            backup_path: Pfad zur Backup-ZIP-Datei

        Returns:
            RestoreResult mit Details
        """
        temp_dir = self.backup_dir / f"restore_{uuid.uuid4()}"
        warnings = []
        restored = []

        try:
            # ZIP entpacken
            with zipfile.ZipFile(backup_path, "r") as zf:
                zf.extractall(temp_dir)

            # Manifest lesen
            manifest_path = temp_dir / "manifest.json"
            if not manifest_path.exists():
                return RestoreResult(
                    success=False,
                    message="Ungueltige Backup-Datei: manifest.json fehlt"
                )

            with open(manifest_path) as f:
                manifest = json.load(f)

            components = manifest.get("components", [])
            checksums = manifest.get("checksums", {})

            # Checksums validieren
            for filename, expected_checksum in checksums.items():
                file_path = temp_dir / filename
                if file_path.exists():
                    actual_checksum = self._calc_checksum(file_path)
                    if actual_checksum != expected_checksum:
                        warnings.append(f"Checksum-Mismatch: {filename}")

            # Komponenten wiederherstellen
            if "app_db" in components:
                if await self._restore_sqlite(temp_dir):
                    restored.append("app_db")
                else:
                    warnings.append("App-Datenbank konnte nicht wiederhergestellt werden")

            if "netbox_db" in components:
                if await self._restore_postgres(temp_dir):
                    restored.append("netbox_db")
                else:
                    warnings.append("NetBox-Datenbank konnte nicht wiederhergestellt werden")

            if "config" in components:
                if self._restore_config(temp_dir):
                    restored.append("config")

            if "ssh" in components:
                if self._restore_ssh(temp_dir):
                    restored.append("ssh")

            if "inventory" in components:
                if self._restore_directory(temp_dir / "inventory", self.data_dir / "inventory"):
                    restored.append("inventory")

            if "playbooks" in components:
                if self._restore_directory(temp_dir / "playbooks", self.data_dir / "playbooks"):
                    restored.append("playbooks")

            if "terraform_state" in components:
                if self._restore_terraform_state(temp_dir):
                    restored.append("terraform_state")

            if "terraform_modules" in components:
                if self._restore_directory(
                    temp_dir / "terraform" / "modules",
                    self.data_dir / "terraform" / "modules"
                ):
                    restored.append("terraform_modules")

            if "roles" in components:
                if self._restore_directory(temp_dir / "roles", self.data_dir / "roles"):
                    restored.append("roles")

            if "netbox_media" in components:
                if self._restore_directory(
                    temp_dir / "netbox" / "media",
                    self.data_dir / "netbox" / "media"
                ):
                    restored.append("netbox_media")

            logger.info(f"Restore abgeschlossen: {len(restored)} Komponenten wiederhergestellt")

            return RestoreResult(
                success=True,
                message=f"{len(restored)} Komponenten wiederhergestellt",
                restored_components=restored,
                warnings=warnings
            )

        except Exception as e:
            logger.error(f"Restore fehlgeschlagen: {e}")
            return RestoreResult(
                success=False,
                message=f"Restore fehlgeschlagen: {str(e)}",
                warnings=warnings
            )

        finally:
            # Temp-Verzeichnis aufraeumen
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    async def _restore_sqlite(self, temp_dir: Path) -> bool:
        """Stellt SQLite-Datenbank wieder her"""
        try:
            src = temp_dir / "commander.db"
            if not src.exists():
                return False

            dst = self.data_dir / "db" / "commander.db"
            dst.parent.mkdir(parents=True, exist_ok=True)

            # Backup der aktuellen DB
            if dst.exists():
                shutil.copy2(dst, dst.with_suffix(".db.pre-restore"))

            shutil.copy2(src, dst)
            logger.info("SQLite-Datenbank wiederhergestellt")
            return True

        except Exception as e:
            logger.error(f"SQLite-Restore fehlgeschlagen: {e}")
            return False

    async def _restore_postgres(self, temp_dir: Path) -> bool:
        """Stellt PostgreSQL-Datenbank wieder her"""
        try:
            src = temp_dir / "netbox.sql.gz"
            if not src.exists():
                return False

            # Dekomprimieren
            with gzip.open(src, "rt", encoding="utf-8") as f:
                sql_content = f.read()

            # psql via docker exec
            cmd = [
                "docker", "exec", "-i", "pve-commander-postgres",
                "psql", "-U", "netbox", "netbox"
            ]

            result = subprocess.run(
                cmd,
                input=sql_content,
                capture_output=True,
                text=True,
                timeout=600  # 10 Minuten Timeout
            )

            if result.returncode != 0:
                logger.error(f"psql fehlgeschlagen: {result.stderr}")
                return False

            logger.info("PostgreSQL-Datenbank wiederhergestellt")
            return True

        except Exception as e:
            logger.error(f"PostgreSQL-Restore fehlgeschlagen: {e}")
            return False

    def _restore_config(self, temp_dir: Path) -> bool:
        """Stellt Konfiguration wieder her"""
        try:
            src = temp_dir / "config" / ".env"
            if not src.exists():
                return False

            dst = self.data_dir / "config" / ".env"
            dst.parent.mkdir(parents=True, exist_ok=True)

            if dst.exists():
                shutil.copy2(dst, dst.with_suffix(".env.pre-restore"))

            shutil.copy2(src, dst)
            logger.info("Konfiguration wiederhergestellt")
            return True

        except Exception as e:
            logger.error(f"Config-Restore fehlgeschlagen: {e}")
            return False

    def _restore_ssh(self, temp_dir: Path) -> bool:
        """Stellt SSH-Keys wieder her"""
        try:
            src_dir = temp_dir / "ssh"
            if not src_dir.exists():
                return False

            dst_dir = self.data_dir / "ssh"
            dst_dir.mkdir(parents=True, exist_ok=True)

            for key_file in ["id_ed25519", "id_ed25519.pub", "known_hosts"]:
                src = src_dir / key_file
                if src.exists():
                    dst = dst_dir / key_file
                    shutil.copy2(src, dst)
                    # Berechtigungen fuer Private Key setzen
                    if key_file == "id_ed25519":
                        os.chmod(dst, 0o600)

            logger.info("SSH-Keys wiederhergestellt")
            return True

        except Exception as e:
            logger.error(f"SSH-Restore fehlgeschlagen: {e}")
            return False

    def _restore_terraform_state(self, temp_dir: Path) -> bool:
        """Stellt Terraform State wieder her"""
        try:
            src_dir = temp_dir / "terraform"
            if not src_dir.exists():
                return False

            dst_dir = self.data_dir / "terraform"
            dst_dir.mkdir(parents=True, exist_ok=True)

            for state_file in ["terraform.tfstate", "terraform.tfstate.backup"]:
                src = src_dir / state_file
                if src.exists():
                    shutil.copy2(src, dst_dir / state_file)

            logger.info("Terraform State wiederhergestellt")
            return True

        except Exception as e:
            logger.error(f"Terraform-Restore fehlgeschlagen: {e}")
            return False

    def _restore_directory(self, src_dir: Path, dst_dir: Path) -> bool:
        """Stellt ein Verzeichnis wieder her"""
        try:
            if not src_dir.exists():
                return False

            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
            logger.info(f"Verzeichnis wiederhergestellt: {dst_dir.name}")
            return True

        except Exception as e:
            logger.error(f"Verzeichnis-Restore fehlgeschlagen: {e}")
            return False

    # -------------------------------------------------------------------------
    # Backup-Verwaltung
    # -------------------------------------------------------------------------

    async def list_backups(self) -> List[BackupInfo]:
        """Listet alle vorhandenen Backups"""
        async with async_session() as session:
            result = await session.execute(
                select(BackupHistory).order_by(BackupHistory.created_at.desc())
            )
            backups = result.scalars().all()

            return [
                BackupInfo(
                    id=b.id,
                    filename=b.filename,
                    created_at=b.created_at,
                    size_bytes=b.size_bytes or 0,
                    components=json.loads(b.components) if b.components else [],
                    is_scheduled=b.is_scheduled,
                    status=b.status
                )
                for b in backups
            ]

    async def get_backup_path(self, backup_id: str) -> Optional[Path]:
        """Gibt den Pfad zu einem Backup zurueck"""
        async with async_session() as session:
            result = await session.execute(
                select(BackupHistory).where(BackupHistory.id == backup_id)
            )
            backup = result.scalar_one_or_none()

            if backup:
                path = self.backup_dir / backup.filename
                if path.exists():
                    return path

            return None

    async def delete_backup(self, backup_id: str) -> bool:
        """Loescht ein Backup"""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(BackupHistory).where(BackupHistory.id == backup_id)
                )
                backup = result.scalar_one_or_none()

                if not backup:
                    return False

                # Datei loeschen
                backup_path = self.backup_dir / backup.filename
                if backup_path.exists():
                    backup_path.unlink()

                # DB-Eintrag loeschen
                await session.execute(
                    delete(BackupHistory).where(BackupHistory.id == backup_id)
                )
                await session.commit()

                logger.info(f"Backup geloescht: {backup.filename}")
                return True

        except Exception as e:
            logger.error(f"Backup-Loeschung fehlgeschlagen: {e}")
            return False

    async def cleanup_old_backups(self, retention_days: int) -> int:
        """Loescht alte Backups basierend auf Retention"""
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=retention_days)
        deleted = 0

        async with async_session() as session:
            result = await session.execute(
                select(BackupHistory).where(
                    BackupHistory.created_at < cutoff,
                    BackupHistory.is_scheduled == True
                )
            )
            old_backups = result.scalars().all()

            for backup in old_backups:
                backup_path = self.backup_dir / backup.filename
                if backup_path.exists():
                    backup_path.unlink()

                await session.execute(
                    delete(BackupHistory).where(BackupHistory.id == backup.id)
                )
                deleted += 1

            await session.commit()

        if deleted > 0:
            logger.info(f"{deleted} alte Backups geloescht (Retention: {retention_days} Tage)")

        return deleted

    # -------------------------------------------------------------------------
    # Zeitplan
    # -------------------------------------------------------------------------

    async def get_schedule(self) -> ScheduleInfo:
        """Gibt den aktuellen Backup-Zeitplan zurueck"""
        async with async_session() as session:
            result = await session.execute(
                select(BackupSchedule).where(BackupSchedule.id == 1)
            )
            schedule = result.scalar_one_or_none()

            if schedule:
                options = BackupOptions(**json.loads(schedule.options)) if schedule.options else BackupOptions()
                return ScheduleInfo(
                    enabled=schedule.enabled,
                    frequency=schedule.frequency,
                    time=schedule.time,
                    retention_days=schedule.retention_days,
                    options=options,
                    last_run=schedule.last_run,
                    next_run=schedule.next_run
                )

            return ScheduleInfo()

    async def update_schedule(self, schedule_info: ScheduleInfo) -> bool:
        """Aktualisiert den Backup-Zeitplan"""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(BackupSchedule).where(BackupSchedule.id == 1)
                )
                schedule = result.scalar_one_or_none()

                if schedule:
                    schedule.enabled = schedule_info.enabled
                    schedule.frequency = schedule_info.frequency
                    schedule.time = schedule_info.time
                    schedule.retention_days = schedule_info.retention_days
                    schedule.options = json.dumps(schedule_info.options.model_dump())
                else:
                    schedule = BackupSchedule(
                        id=1,
                        enabled=schedule_info.enabled,
                        frequency=schedule_info.frequency,
                        time=schedule_info.time,
                        retention_days=schedule_info.retention_days,
                        options=json.dumps(schedule_info.options.model_dump())
                    )
                    session.add(schedule)

                await session.commit()
                logger.info(f"Backup-Zeitplan aktualisiert: {schedule_info.frequency} um {schedule_info.time}")
                return True

        except Exception as e:
            logger.error(f"Zeitplan-Update fehlgeschlagen: {e}")
            return False

    # -------------------------------------------------------------------------
    # Hilfsfunktionen
    # -------------------------------------------------------------------------

    def _calc_checksum(self, file_path: Path) -> str:
        """Berechnet SHA256-Checksum einer Datei"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return f"sha256:{sha256.hexdigest()}"

    async def _save_backup_history(
        self,
        backup_id: str,
        filename: str,
        size_bytes: int,
        components: List[str],
        is_scheduled: bool
    ):
        """Speichert Backup in der Historie"""
        async with async_session() as session:
            history = BackupHistory(
                id=backup_id,
                filename=filename,
                created_at=datetime.now(),  # Explizit Lokalzeit setzen
                size_bytes=size_bytes,
                components=json.dumps(components),
                is_scheduled=is_scheduled,
                status="completed"
            )
            session.add(history)
            await session.commit()


# Singleton-Instanz
backup_service = BackupService()
