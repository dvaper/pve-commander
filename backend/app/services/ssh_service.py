"""
SSH Service - Verwaltung von SSH-Keys und Verbindungstests

Dieser Service bietet Funktionen fuer:
- Auflisten verfuegbarer SSH-Keys (aus gemounteten Host-Verzeichnis)
- Import/Upload/Generierung von SSH-Keys
- Testen von SSH-Verbindungen
- Lesen/Aktualisieren der SSH-Konfiguration

Security Features:
- CRIT-03: Groessenbegrenzung und Validierung fuer SSH-Key-Uploads
"""
import asyncio
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel

from app.config import settings, reload_settings

logger = logging.getLogger(__name__)

# CRIT-03: Sicherheitslimits fuer SSH-Key-Uploads
MAX_SSH_KEY_SIZE = 16 * 1024  # 16 KB - ausreichend fuer RSA 4096
MAX_SSH_KEY_LINES = 100  # Maximale Zeilenanzahl


# =============================================================================
# Schemas
# =============================================================================

class SSHKeyInfo(BaseModel):
    """Information ueber einen SSH-Key"""
    id: Optional[str] = None  # Eindeutige ID fuer gespeicherte Keys
    name: str  # z.B. "id_ed25519", "id_rsa", "mein-key"
    path: str  # Vollstaendiger Pfad
    type: str  # "ed25519", "rsa", "ecdsa", "dsa"
    has_public: bool  # Ob .pub Datei existiert
    fingerprint: Optional[str] = None
    is_active: bool = False  # Ob dieser Key aktuell aktiv ist
    created_at: Optional[str] = None  # Erstellungsdatum


class SSHKeyListResponse(BaseModel):
    """Liste verfuegbarer SSH-Keys"""
    available: bool  # Ob das SSH-Verzeichnis gemountet ist
    keys: List[SSHKeyInfo] = []  # Keys aus Host-SSH (zum Import)
    stored_keys: List[SSHKeyInfo] = []  # Gespeicherte Keys
    current_key: Optional[SSHKeyInfo] = None  # Aktuell aktiver Key
    default_user: str  # Aktueller/empfohlener Benutzer


class SSHKeyImportRequest(BaseModel):
    """Request zum Importieren eines SSH-Keys"""
    source_path: str  # z.B. "/host-ssh/id_ed25519"
    key_name: Optional[str] = None  # Optionaler Name fuer den Key


class SSHKeyImportResponse(BaseModel):
    """Ergebnis des Imports"""
    success: bool
    message: str
    key_id: Optional[str] = None
    target_path: Optional[str] = None
    public_key: Optional[str] = None


class SSHKeyUploadRequest(BaseModel):
    """Request zum Hochladen eines SSH-Keys"""
    private_key: str  # PEM-formatierter Private Key
    public_key: Optional[str] = None  # Optional: Public Key
    key_name: Optional[str] = None  # Optionaler Name fuer den Key


class SSHKeyUploadResponse(BaseModel):
    """Ergebnis des Uploads"""
    success: bool
    message: str
    key_id: Optional[str] = None
    key_type: Optional[str] = None
    fingerprint: Optional[str] = None
    public_key: Optional[str] = None


class SSHKeyGenerateRequest(BaseModel):
    """Request zum Generieren eines neuen SSH-Keys"""
    key_type: str = "ed25519"  # "ed25519" oder "rsa"
    comment: str = ""  # Optionaler Kommentar
    key_name: Optional[str] = None  # Optionaler Name fuer den Key


class SSHKeyGenerateResponse(BaseModel):
    """Ergebnis der Generierung"""
    success: bool
    message: str
    key_id: Optional[str] = None
    public_key: Optional[str] = None  # Zur Anzeige fuer den Benutzer
    fingerprint: Optional[str] = None


# Key-Management Schemas
class SSHKeyActivateRequest(BaseModel):
    """Request zum Aktivieren eines Keys"""
    key_id: str


class SSHKeyActivateResponse(BaseModel):
    """Ergebnis der Aktivierung"""
    success: bool
    message: str
    active_key: Optional[SSHKeyInfo] = None


class SSHKeyDeleteRequest(BaseModel):
    """Request zum Loeschen eines Keys"""
    key_id: str


class SSHKeyDeleteResponse(BaseModel):
    """Ergebnis des Loeschens"""
    success: bool
    message: str


class SSHTestRequest(BaseModel):
    """Request fuer SSH-Verbindungstest"""
    host: str  # IP oder Hostname
    user: Optional[str] = None  # SSH-Benutzer (Default: aus Config)
    port: int = 22


class SSHTestResponse(BaseModel):
    """Ergebnis des SSH-Tests"""
    success: bool
    message: str
    host_reachable: bool = False
    auth_successful: bool = False
    remote_hostname: Optional[str] = None
    error_details: Optional[str] = None


class SSHConfigResponse(BaseModel):
    """Aktuelle SSH-Konfiguration"""
    ssh_user: str  # Aktueller SSH-Benutzer
    has_key: bool  # Ob ein SSH-Key konfiguriert ist
    key_type: Optional[str] = None  # "ed25519", "rsa", etc.
    key_fingerprint: Optional[str] = None
    public_key: Optional[str] = None  # Fuer Anzeige


class SSHConfigUpdateRequest(BaseModel):
    """Request zum Aktualisieren der SSH-Konfiguration"""
    ssh_user: str  # Neuer SSH-Benutzer


# =============================================================================
# SSH Service
# =============================================================================

class SSHService:
    """Service fuer SSH-Operationen"""

    # Pfad zum gemounteten Host-SSH-Verzeichnis
    HOST_SSH_DIR = "/host-ssh"

    # Zielverzeichnis fuer SSH-Keys
    SSH_KEY_DIR = Path("/data/ssh")

    # Unterverzeichnis fuer gespeicherte Keys
    KEYS_SUBDIR = "keys"

    # Metadaten-Datei
    METADATA_FILE = "keys.json"

    # Unterstuetzte Key-Typen
    KEY_TYPES = {
        "ssh-ed25519": "ed25519",
        "ssh-rsa": "rsa",
        "ecdsa-sha2": "ecdsa",
        "ssh-dss": "dsa",
    }

    def __init__(self):
        pass

    @property
    def keys_dir(self) -> Path:
        """Verzeichnis fuer gespeicherte Keys"""
        return self.SSH_KEY_DIR / self.KEYS_SUBDIR

    @property
    def metadata_path(self) -> Path:
        """Pfad zur Metadaten-Datei"""
        return self.SSH_KEY_DIR / self.METADATA_FILE

    def _load_metadata(self) -> dict:
        """Laedt Key-Metadaten aus JSON-Datei"""
        import json
        if self.metadata_path.exists():
            try:
                with open(self.metadata_path) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Metadaten konnten nicht geladen werden: {e}")
        return {"keys": {}, "active_key_id": None}

    def _save_metadata(self, metadata: dict) -> None:
        """Speichert Key-Metadaten in JSON-Datei"""
        import json
        self.SSH_KEY_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

    def _generate_key_id(self) -> str:
        """Generiert eine eindeutige Key-ID"""
        import uuid
        return str(uuid.uuid4())[:8]

    # =========================================================================
    # Key Discovery
    # =========================================================================

    async def list_available_keys(self) -> SSHKeyListResponse:
        """
        Listet verfuegbare SSH-Keys auf.

        Prueft das gemountete Host-SSH-Verzeichnis und listet alle
        verfuegbaren Private Keys auf. Zeigt auch gespeicherte Keys.
        """
        host_ssh_path = Path(self.HOST_SSH_DIR)
        available = host_ssh_path.exists() and host_ssh_path.is_dir()

        keys = []
        if available:
            # Finde alle Private Keys (ohne .pub Suffix)
            for item in host_ssh_path.iterdir():
                if item.is_file() and not item.name.endswith(".pub"):
                    # Pruefe ob es ein SSH Private Key ist
                    key_info = await self._analyze_key_file(item)
                    if key_info:
                        keys.append(key_info)

        # Gespeicherte Keys laden
        stored_keys = await self._list_stored_keys()

        # Aktuell aktiven Key pruefen
        current_key = await self._get_current_key_info()

        # Default-User ermitteln
        default_user = await self._get_default_user()

        return SSHKeyListResponse(
            available=available,
            keys=keys,
            stored_keys=stored_keys,
            current_key=current_key,
            default_user=default_user,
        )

    async def _list_stored_keys(self) -> List[SSHKeyInfo]:
        """Listet alle gespeicherten Keys auf"""
        from datetime import datetime

        metadata = self._load_metadata()
        active_key_id = metadata.get("active_key_id")
        stored_keys = []

        for key_id, key_data in metadata.get("keys", {}).items():
            key_path = self.keys_dir / key_data.get("filename", "")
            if not key_path.exists():
                continue

            # Fingerprint berechnen
            fingerprint = await self._get_key_fingerprint(key_path)

            stored_keys.append(SSHKeyInfo(
                id=key_id,
                name=key_data.get("name", key_id),
                path=str(key_path),
                type=key_data.get("type", "unknown"),
                has_public=(key_path.with_suffix(key_path.suffix + ".pub")).exists() or Path(str(key_path) + ".pub").exists(),
                fingerprint=fingerprint,
                is_active=(key_id == active_key_id),
                created_at=key_data.get("created_at"),
            ))

        return stored_keys

    async def _store_key(
        self,
        private_key: str,
        public_key: Optional[str],
        key_type: str,
        key_name: Optional[str] = None,
        activate: bool = True,
    ) -> tuple[str, Path, str]:
        """
        Speichert einen Key im keys/ Verzeichnis mit Metadaten.

        Returns: (key_id, key_path, public_key)
        """
        from datetime import datetime

        # Verzeichnis erstellen
        self.keys_dir.mkdir(parents=True, exist_ok=True)

        # Key-ID generieren
        key_id = self._generate_key_id()

        # Dateiname
        filename = f"{key_id}_{key_type}"
        key_path = self.keys_dir / filename

        # Private Key schreiben
        key_path.write_text(private_key.strip() + "\n")
        os.chmod(key_path, 0o600)

        # Public Key verarbeiten
        if public_key:
            pub_path = Path(str(key_path) + ".pub")
            pub_path.write_text(public_key.strip() + "\n")
            os.chmod(pub_path, 0o644)
        else:
            # Public Key aus Private Key generieren
            public_key = await self._generate_public_from_private(key_path)
            if public_key:
                pub_path = Path(str(key_path) + ".pub")
                pub_path.write_text(public_key + "\n")
                os.chmod(pub_path, 0o644)

        # Genaueren Key-Typ ermitteln
        actual_type = await self._get_actual_key_type(key_path) or key_type

        # Metadaten aktualisieren
        metadata = self._load_metadata()
        metadata["keys"][key_id] = {
            "name": key_name or f"{actual_type.upper()}-Key ({key_id})",
            "filename": filename,
            "type": actual_type,
            "created_at": datetime.now().isoformat(),
        }

        # Optional: Key aktivieren
        if activate:
            metadata["active_key_id"] = key_id
            await self._create_active_symlink(key_path, actual_type)

        self._save_metadata(metadata)

        logger.info(f"SSH-Key gespeichert: {key_path} (ID: {key_id})")

        return key_id, key_path, public_key or ""

    async def _create_active_symlink(self, source_path: Path, key_type: str) -> None:
        """Erstellt Symlink zum aktiven Key"""
        # Ziel-Symlink-Name
        if key_type in ["rsa"]:
            link_name = "id_rsa"
        else:
            link_name = "id_ed25519"

        link_path = self.SSH_KEY_DIR / link_name
        pub_link_path = Path(str(link_path) + ".pub")

        # Alte Links/Dateien entfernen
        if link_path.exists() or link_path.is_symlink():
            link_path.unlink()
        if pub_link_path.exists() or pub_link_path.is_symlink():
            pub_link_path.unlink()

        # Neue Symlinks erstellen (relativ)
        rel_source = source_path.relative_to(self.SSH_KEY_DIR)
        link_path.symlink_to(rel_source)

        # Public Key Symlink
        source_pub = Path(str(source_path) + ".pub")
        if source_pub.exists():
            rel_source_pub = source_pub.relative_to(self.SSH_KEY_DIR)
            pub_link_path.symlink_to(rel_source_pub)

        logger.info(f"Aktiver Key-Symlink erstellt: {link_path} -> {rel_source}")

    async def activate_key(self, request: SSHKeyActivateRequest) -> SSHKeyActivateResponse:
        """Aktiviert einen gespeicherten Key"""
        key_id = request.key_id

        metadata = self._load_metadata()
        if key_id not in metadata.get("keys", {}):
            return SSHKeyActivateResponse(
                success=False,
                message=f"Key mit ID '{key_id}' nicht gefunden",
            )

        key_data = metadata["keys"][key_id]
        key_path = self.keys_dir / key_data["filename"]

        if not key_path.exists():
            return SSHKeyActivateResponse(
                success=False,
                message="Key-Datei nicht gefunden",
            )

        # Symlink erstellen
        await self._create_active_symlink(key_path, key_data.get("type", "ed25519"))

        # Metadaten aktualisieren
        metadata["active_key_id"] = key_id
        self._save_metadata(metadata)

        # Key-Info zurueckgeben
        fingerprint = await self._get_key_fingerprint(key_path)
        active_key = SSHKeyInfo(
            id=key_id,
            name=key_data.get("name", key_id),
            path=str(key_path),
            type=key_data.get("type", "unknown"),
            has_public=Path(str(key_path) + ".pub").exists(),
            fingerprint=fingerprint,
            is_active=True,
            created_at=key_data.get("created_at"),
        )

        return SSHKeyActivateResponse(
            success=True,
            message=f"Key '{key_data.get('name')}' aktiviert",
            active_key=active_key,
        )

    async def delete_key(self, request: SSHKeyDeleteRequest) -> SSHKeyDeleteResponse:
        """Loescht einen gespeicherten Key"""
        key_id = request.key_id

        metadata = self._load_metadata()
        if key_id not in metadata.get("keys", {}):
            return SSHKeyDeleteResponse(
                success=False,
                message=f"Key mit ID '{key_id}' nicht gefunden",
            )

        # Pruefen ob der Key aktiv ist
        if metadata.get("active_key_id") == key_id:
            return SSHKeyDeleteResponse(
                success=False,
                message="Aktiver Key kann nicht gelöscht werden. Bitte zuerst anderen Key aktivieren.",
            )

        key_data = metadata["keys"][key_id]
        key_path = self.keys_dir / key_data["filename"]

        # Dateien loeschen
        try:
            if key_path.exists():
                key_path.unlink()
            pub_path = Path(str(key_path) + ".pub")
            if pub_path.exists():
                pub_path.unlink()
        except Exception as e:
            logger.error(f"Fehler beim Loeschen der Key-Dateien: {e}")

        # Aus Metadaten entfernen
        del metadata["keys"][key_id]
        self._save_metadata(metadata)

        return SSHKeyDeleteResponse(
            success=True,
            message=f"Key '{key_data.get('name')}' gelöscht",
        )

    async def _analyze_key_file(self, path: Path) -> Optional[SSHKeyInfo]:
        """Analysiert eine Key-Datei und gibt Infos zurueck"""
        try:
            content = path.read_text().strip()

            # Pruefe auf Private Key Header
            if not content.startswith("-----BEGIN"):
                return None

            # Bestimme Key-Typ
            key_type = self._detect_private_key_type(content)
            if not key_type:
                return None

            # Pruefe ob Public Key existiert
            pub_path = path.with_suffix(path.suffix + ".pub") if path.suffix else Path(str(path) + ".pub")
            has_public = pub_path.exists()

            # Fingerprint berechnen
            fingerprint = await self._get_key_fingerprint(path)

            return SSHKeyInfo(
                name=path.name,
                path=str(path),
                type=key_type,
                has_public=has_public,
                fingerprint=fingerprint,
            )
        except Exception as e:
            logger.debug(f"Konnte Key-Datei nicht analysieren: {path} - {e}")
            return None

    def _detect_private_key_type(self, content: str) -> Optional[str]:
        """Erkennt den Typ eines Private Keys anhand des Headers"""
        if "BEGIN OPENSSH PRIVATE KEY" in content:
            # OpenSSH Format - kann ed25519, rsa, ecdsa sein
            # Genauere Erkennung durch ssh-keygen -l
            return "openssh"
        elif "BEGIN RSA PRIVATE KEY" in content:
            return "rsa"
        elif "BEGIN DSA PRIVATE KEY" in content:
            return "dsa"
        elif "BEGIN EC PRIVATE KEY" in content:
            return "ecdsa"
        return None

    async def _get_key_fingerprint(self, key_path: Path) -> Optional[str]:
        """Berechnet den Fingerprint eines Keys"""
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["ssh-keygen", "-lf", str(key_path)],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Format: "256 SHA256:xxxx user@host (ED25519)"
                parts = result.stdout.strip().split()
                if len(parts) >= 2:
                    return parts[1]  # SHA256:xxxx
            return None
        except Exception as e:
            logger.debug(f"Konnte Fingerprint nicht berechnen: {e}")
            return None

    async def _get_current_key_info(self) -> Optional[SSHKeyInfo]:
        """Gibt Infos zum aktuell konfigurierten Key zurueck"""
        key_path = Path(settings.ssh_key_path)
        if key_path.exists():
            return await self._analyze_key_file(key_path)
        return None

    async def _get_default_user(self) -> str:
        """Ermittelt den empfohlenen Default-User"""
        # Zuerst: Konfigurierter User
        if settings.ansible_remote_user and settings.ansible_remote_user != "ansible":
            return settings.ansible_remote_user

        # Dann: System-User aus Umgebung (falls verfuegbar)
        env_user = os.environ.get("USER") or os.environ.get("LOGNAME")
        if env_user and env_user not in ["root", "nobody"]:
            return env_user

        # Fallback
        return settings.ansible_remote_user or "ansible"

    # =========================================================================
    # Key Import
    # =========================================================================

    async def import_key(self, request: SSHKeyImportRequest) -> SSHKeyImportResponse:
        """
        Importiert einen Key aus dem gemounteten Host-SSH-Verzeichnis.
        Unterstuetzt Multi-Key-Speicherung.
        """
        source_path = Path(request.source_path)

        # Sicherheitspruefung: Nur aus /host-ssh erlaubt
        try:
            source_path.resolve().relative_to(Path(self.HOST_SSH_DIR).resolve())
        except ValueError:
            return SSHKeyImportResponse(
                success=False,
                message="Ungültiger Pfad: Import nur aus /host-ssh erlaubt",
            )

        if not source_path.exists():
            return SSHKeyImportResponse(
                success=False,
                message=f"Key-Datei nicht gefunden: {source_path}",
            )

        try:
            # Key-Inhalt lesen
            private_key = source_path.read_text()
            key_type = self._detect_private_key_type(private_key)

            if not key_type:
                return SSHKeyImportResponse(
                    success=False,
                    message="Unbekannter Key-Typ",
                )

            # Public Key lesen falls vorhanden
            public_key = None
            source_pub = Path(str(source_path) + ".pub")
            if source_pub.exists():
                public_key = source_pub.read_text().strip()

            # Key-Name generieren
            key_name = request.key_name or f"Import: {source_path.name}"

            # Key mit Multi-Key-Support speichern
            key_id, target_path, public_key = await self._store_key(
                private_key=private_key,
                public_key=public_key,
                key_type=key_type,
                key_name=key_name,
                activate=True,
            )

            logger.info(f"SSH-Key importiert: {source_path} -> {target_path} (ID: {key_id})")

            return SSHKeyImportResponse(
                success=True,
                message="SSH-Key erfolgreich importiert und aktiviert",
                key_id=key_id,
                target_path=str(target_path),
                public_key=public_key,
            )

        except Exception as e:
            logger.error(f"Fehler beim Key-Import: {e}")
            return SSHKeyImportResponse(
                success=False,
                message=f"Import fehlgeschlagen: {str(e)}",
            )

    # =========================================================================
    # Key Upload
    # =========================================================================

    async def upload_key(self, request: SSHKeyUploadRequest) -> SSHKeyUploadResponse:
        """
        Speichert einen per Copy/Paste uebermittelten Key.

        Security (CRIT-03):
        - Groessenbegrenzung (max 16KB)
        - Format-Validierung
        - Zeilenzahl-Begrenzung
        """
        private_key = request.private_key.strip()

        # CRIT-03: Groessenpruefung
        if len(private_key) > MAX_SSH_KEY_SIZE:
            logger.warning(f"SSH-Key Upload abgelehnt: Zu gross ({len(private_key)} bytes)")
            return SSHKeyUploadResponse(
                success=False,
                message=f"SSH-Key zu gross. Maximale Groesse: {MAX_SSH_KEY_SIZE // 1024} KB",
            )

        # CRIT-03: Zeilenzahl-Pruefung (verhindert Speicherprobleme)
        line_count = private_key.count('\n') + 1
        if line_count > MAX_SSH_KEY_LINES:
            logger.warning(f"SSH-Key Upload abgelehnt: Zu viele Zeilen ({line_count})")
            return SSHKeyUploadResponse(
                success=False,
                message=f"SSH-Key hat zu viele Zeilen. Maximum: {MAX_SSH_KEY_LINES}",
            )

        # Validiere Private Key Format
        if not private_key.startswith("-----BEGIN"):
            return SSHKeyUploadResponse(
                success=False,
                message="Ungültiges Key-Format: Muss mit '-----BEGIN' beginnen",
            )

        # CRIT-03: Pruefe auf gueltigen Key-Header und -Footer
        valid_headers = [
            "-----BEGIN OPENSSH PRIVATE KEY-----",
            "-----BEGIN RSA PRIVATE KEY-----",
            "-----BEGIN DSA PRIVATE KEY-----",
            "-----BEGIN EC PRIVATE KEY-----",
        ]
        has_valid_header = any(h in private_key for h in valid_headers)
        has_end_marker = "-----END" in private_key and "PRIVATE KEY-----" in private_key

        if not has_valid_header or not has_end_marker:
            return SSHKeyUploadResponse(
                success=False,
                message="Ungültiges SSH-Key-Format: Ungueltiger Header oder Footer",
            )

        key_type = self._detect_private_key_type(private_key)
        if not key_type:
            return SSHKeyUploadResponse(
                success=False,
                message="Unbekannter Key-Typ",
            )

        # CRIT-03: Public Key ebenfalls validieren falls angegeben
        if request.public_key:
            pub_key = request.public_key.strip()
            if len(pub_key) > MAX_SSH_KEY_SIZE:
                return SSHKeyUploadResponse(
                    success=False,
                    message="Public Key zu gross",
                )
            # Public Key sollte mit ssh- beginnen
            valid_pub_prefixes = ["ssh-ed25519", "ssh-rsa", "ecdsa-sha2", "ssh-dss"]
            if not any(pub_key.startswith(p) for p in valid_pub_prefixes):
                return SSHKeyUploadResponse(
                    success=False,
                    message="Ungültiges Public-Key-Format",
                )

        try:
            # Key speichern mit Multi-Key-Support
            key_id, key_path, public_key = await self._store_key(
                private_key=private_key,
                public_key=request.public_key,
                key_type=key_type,
                key_name=request.key_name,
                activate=True,
            )

            # Fingerprint berechnen
            fingerprint = await self._get_key_fingerprint(key_path)

            # Key-Typ genauer bestimmen
            actual_type = await self._get_actual_key_type(key_path)

            return SSHKeyUploadResponse(
                success=True,
                message="SSH-Key erfolgreich gespeichert und aktiviert",
                key_id=key_id,
                key_type=actual_type or key_type,
                fingerprint=fingerprint,
                public_key=public_key,
            )

        except Exception as e:
            logger.error(f"Fehler beim Key-Upload: {e}")
            return SSHKeyUploadResponse(
                success=False,
                message=f"Upload fehlgeschlagen: {str(e)}",
            )

    async def _generate_public_from_private(self, private_key_path: Path) -> Optional[str]:
        """Generiert Public Key aus Private Key"""
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["ssh-keygen", "-y", "-f", str(private_key_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception as e:
            logger.warning(f"Konnte Public Key nicht generieren: {e}")
            return None

    async def _get_actual_key_type(self, key_path: Path) -> Optional[str]:
        """Bestimmt den genauen Key-Typ via ssh-keygen"""
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["ssh-keygen", "-lf", str(key_path)],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Format: "256 SHA256:xxxx user@host (ED25519)"
                match = re.search(r"\(([A-Z0-9]+)\)$", result.stdout.strip())
                if match:
                    return match.group(1).lower()
            return None
        except Exception:
            return None

    # =========================================================================
    # Key Generation
    # =========================================================================

    async def generate_key(self, request: SSHKeyGenerateRequest) -> SSHKeyGenerateResponse:
        """
        Generiert ein neues SSH-Schluesselpaar.
        """
        import tempfile
        from datetime import datetime

        key_type = request.key_type.lower()
        if key_type not in ["ed25519", "rsa"]:
            return SSHKeyGenerateResponse(
                success=False,
                message=f"Ungültiger Key-Typ: {key_type}. Erlaubt: ed25519, rsa",
            )

        try:
            # Key-ID und Verzeichnis vorbereiten
            key_id = self._generate_key_id()
            self.keys_dir.mkdir(parents=True, exist_ok=True)

            # Zieldateiname im keys/ Verzeichnis
            filename = f"{key_id}_{key_type}"
            target_path = self.keys_dir / filename
            pub_path = Path(str(target_path) + ".pub")

            # ssh-keygen ausfuehren
            cmd = [
                "ssh-keygen",
                "-t", key_type,
                "-f", str(target_path),
                "-N", "",  # Kein Passwort
                "-C", request.comment or f"pve-commander@{key_type}",
            ]

            if key_type == "rsa":
                cmd.extend(["-b", "4096"])

            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return SSHKeyGenerateResponse(
                    success=False,
                    message=f"Key-Generierung fehlgeschlagen: {result.stderr}",
                )

            # Berechtigungen setzen
            os.chmod(target_path, 0o600)
            os.chmod(pub_path, 0o644)

            # Public Key lesen
            public_key = pub_path.read_text().strip()

            # Fingerprint berechnen
            fingerprint = await self._get_key_fingerprint(target_path)

            # Metadaten speichern
            metadata = self._load_metadata()
            key_name = request.key_name or f"{key_type.upper()}-Key ({key_id})"
            metadata["keys"][key_id] = {
                "name": key_name,
                "filename": filename,
                "type": key_type,
                "created_at": datetime.now().isoformat(),
            }

            # Key aktivieren
            metadata["active_key_id"] = key_id
            await self._create_active_symlink(target_path, key_type)
            self._save_metadata(metadata)

            logger.info(f"SSH-Key generiert: {target_path} (ID: {key_id})")

            return SSHKeyGenerateResponse(
                success=True,
                message=f"SSH-Key ({key_type.upper()}) erfolgreich generiert und aktiviert",
                key_id=key_id,
                public_key=public_key,
                fingerprint=fingerprint,
            )

        except Exception as e:
            logger.error(f"Fehler bei Key-Generierung: {e}")
            return SSHKeyGenerateResponse(
                success=False,
                message=f"Generierung fehlgeschlagen: {str(e)}",
            )

    # =========================================================================
    # Connection Test
    # =========================================================================

    async def test_connection(self, request: SSHTestRequest) -> SSHTestResponse:
        """
        Testet die SSH-Verbindung zu einem Host.
        """
        host = request.host.strip()
        user = request.user or settings.ansible_remote_user
        port = request.port

        if not host:
            return SSHTestResponse(
                success=False,
                message="Kein Host angegeben",
            )

        # Pruefe ob Key existiert
        key_path = Path(settings.ssh_key_path)
        if not key_path.exists():
            return SSHTestResponse(
                success=False,
                message="Kein SSH-Key konfiguriert",
                error_details=f"Key nicht gefunden: {key_path}",
            )

        # Schritt 1: Port-Check
        host_reachable = await self._check_port(host, port)

        if not host_reachable:
            return SSHTestResponse(
                success=False,
                message=f"Host nicht erreichbar auf Port {port}",
                host_reachable=False,
            )

        # Schritt 2: SSH-Verbindung testen
        try:
            cmd = [
                "ssh",
                "-i", str(key_path),
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "BatchMode=yes",
                "-o", "ConnectTimeout=10",
                "-p", str(port),
                f"{user}@{host}",
                "hostname",
            ]

            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
            )

            if result.returncode == 0:
                remote_hostname = result.stdout.strip()
                return SSHTestResponse(
                    success=True,
                    message=f"Verbindung erfolgreich!",
                    host_reachable=True,
                    auth_successful=True,
                    remote_hostname=remote_hostname,
                )
            else:
                error = result.stderr.strip()
                # Fehleranalyse
                if "Permission denied" in error:
                    error_msg = "Authentifizierung fehlgeschlagen"
                    error_details = f"User '{user}' hat keinen Zugriff. Ist der Public Key auf dem Ziel-Host hinterlegt?"
                elif "Connection refused" in error:
                    error_msg = "Verbindung abgelehnt"
                    error_details = "SSH-Dienst antwortet nicht"
                elif "No route to host" in error:
                    error_msg = "Host nicht erreichbar"
                    error_details = "Netzwerkfehler"
                else:
                    error_msg = "SSH-Verbindung fehlgeschlagen"
                    error_details = error

                return SSHTestResponse(
                    success=False,
                    message=error_msg,
                    host_reachable=True,
                    auth_successful=False,
                    error_details=error_details,
                )

        except asyncio.TimeoutError:
            return SSHTestResponse(
                success=False,
                message="Zeitüberschreitung",
                host_reachable=True,
                error_details="SSH-Verbindung hat zu lange gedauert (15 Sekunden)",
            )
        except Exception as e:
            return SSHTestResponse(
                success=False,
                message="Unbekannter Fehler",
                host_reachable=host_reachable,
                error_details=str(e),
            )

    async def _check_port(self, host: str, port: int, timeout: int = 5) -> bool:
        """Prueft ob ein Port erreichbar ist"""
        import socket
        try:
            def check():
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                result = sock.connect_ex((host, port))
                sock.close()
                return result == 0

            return await asyncio.to_thread(check)
        except Exception:
            return False

    # =========================================================================
    # Configuration
    # =========================================================================

    async def get_config(self) -> SSHConfigResponse:
        """
        Gibt die aktuelle SSH-Konfiguration zurueck.
        """
        key_path = Path(settings.ssh_key_path)
        has_key = key_path.exists()

        key_type = None
        fingerprint = None
        public_key = None

        if has_key:
            key_info = await self._analyze_key_file(key_path)
            if key_info:
                key_type = key_info.type
                fingerprint = key_info.fingerprint

            # Public Key lesen
            pub_path = Path(str(key_path) + ".pub")
            if pub_path.exists():
                public_key = pub_path.read_text().strip()

            # Genaueren Key-Typ ermitteln
            actual_type = await self._get_actual_key_type(key_path)
            if actual_type:
                key_type = actual_type

        return SSHConfigResponse(
            ssh_user=settings.ansible_remote_user,
            has_key=has_key,
            key_type=key_type,
            key_fingerprint=fingerprint,
            public_key=public_key,
        )

    async def update_config(self, request: SSHConfigUpdateRequest) -> SSHConfigResponse:
        """
        Aktualisiert die SSH-Konfiguration.

        Aendert den SSH-Benutzer in der .env Datei.
        """
        new_user = request.ssh_user.strip()

        if not new_user:
            raise ValueError("SSH-Benutzer darf nicht leer sein")

        # .env Datei aktualisieren
        from app.routers.setup import get_env_file_path, quote_env_value

        env_path = get_env_file_path()

        if env_path.exists():
            content = env_path.read_text()
            lines = content.split("\n")
            new_lines = []
            found_user = False
            found_default = False

            for line in lines:
                if line.startswith("ANSIBLE_REMOTE_USER="):
                    new_lines.append(f"ANSIBLE_REMOTE_USER={quote_env_value(new_user)}")
                    found_user = True
                elif line.startswith("DEFAULT_SSH_USER="):
                    new_lines.append(f"DEFAULT_SSH_USER={quote_env_value(new_user)}")
                    found_default = True
                else:
                    new_lines.append(line)

            if not found_user:
                new_lines.append(f"ANSIBLE_REMOTE_USER={quote_env_value(new_user)}")
            if not found_default:
                new_lines.append(f"DEFAULT_SSH_USER={quote_env_value(new_user)}")

            env_path.write_text("\n".join(new_lines))

            # Settings neu laden
            reload_settings(str(env_path))

            logger.info(f"SSH-User aktualisiert: {new_user}")

        return await self.get_config()


# =============================================================================
# Factory-Funktion
# =============================================================================

def get_ssh_service() -> SSHService:
    """Factory-Funktion fuer Dependency Injection"""
    return SSHService()
