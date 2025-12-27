"""
CloudInitSettingsService - Verwaltung der Cloud-Init Konfiguration

Dieser Service laedt und speichert Cloud-Init Einstellungen aus der Datenbank.
Er ersetzt die hardcodierten Werte in cloud_init_service.py.
"""
import json
import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cloud_init_settings import CloudInitSettings

logger = logging.getLogger(__name__)


class CloudInitSettingsService:
    """Service fuer Cloud-Init Settings"""

    # Fallback-Defaults (verwendet wenn DB nicht verfuegbar oder leer)
    DEFAULT_SSH_KEYS: List[str] = []
    DEFAULT_ADMIN_USERNAME = "ansible"
    DEFAULT_ADMIN_GECOS = "Homelab Admin"
    DEFAULT_PHONE_HOME_ENABLED = True

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_settings(self) -> CloudInitSettings:
        """
        Holt oder erstellt die Singleton-Einstellungen.

        Bei erster Verwendung werden Default-Werte angelegt.
        """
        result = await self.db.execute(select(CloudInitSettings))
        settings = result.scalar_one_or_none()

        if not settings:
            logger.info("Erstelle Cloud-Init Settings mit Defaults")
            settings = CloudInitSettings(
                ssh_authorized_keys=json.dumps(self.DEFAULT_SSH_KEYS),
                admin_username=self.DEFAULT_ADMIN_USERNAME,
                admin_gecos=self.DEFAULT_ADMIN_GECOS,
                phone_home_enabled=self.DEFAULT_PHONE_HOME_ENABLED,
            )
            self.db.add(settings)
            await self.db.commit()
            await self.db.refresh(settings)

        return settings

    async def get_ssh_keys(self) -> List[str]:
        """Gibt die konfigurierten SSH-Keys zurueck"""
        settings = await self.get_settings()
        if settings.ssh_authorized_keys:
            try:
                return json.loads(settings.ssh_authorized_keys)
            except json.JSONDecodeError:
                logger.warning("Ungueltige SSH-Keys JSON, verwende Default")
                return self.DEFAULT_SSH_KEYS
        return self.DEFAULT_SSH_KEYS

    async def add_ssh_key(self, key: str) -> List[str]:
        """
        Fuegt einen SSH-Key hinzu.

        Args:
            key: SSH Public Key (z.B. "ssh-ed25519 AAAA... user@host")

        Returns:
            Aktualisierte Liste aller Keys
        """
        key = key.strip()
        if not key:
            return await self.get_ssh_keys()

        keys = await self.get_ssh_keys()
        if key not in keys:
            keys.append(key)
            settings = await self.get_settings()
            settings.ssh_authorized_keys = json.dumps(keys)
            await self.db.commit()
            logger.info(f"SSH-Key hinzugefuegt: {key[:30]}...")
        return keys

    async def remove_ssh_key(self, key: str) -> List[str]:
        """
        Entfernt einen SSH-Key.

        Args:
            key: SSH Public Key zum Entfernen

        Returns:
            Aktualisierte Liste aller Keys
        """
        keys = await self.get_ssh_keys()
        if key in keys:
            keys.remove(key)
            settings = await self.get_settings()
            settings.ssh_authorized_keys = json.dumps(keys)
            await self.db.commit()
            logger.info(f"SSH-Key entfernt: {key[:30]}...")
        return keys

    async def set_ssh_keys(self, keys: List[str]) -> None:
        """
        Setzt alle SSH-Keys (ersetzt bestehende).

        Args:
            keys: Liste von SSH Public Keys
        """
        # Bereinige Keys (Leerzeichen, leere Eintraege)
        cleaned_keys = [k.strip() for k in keys if k.strip()]

        settings = await self.get_settings()
        settings.ssh_authorized_keys = json.dumps(cleaned_keys)
        await self.db.commit()
        logger.info(f"SSH-Keys gesetzt: {len(cleaned_keys)} Keys")

    async def get_phone_home_url(self, request_host: Optional[str] = None) -> Optional[str]:
        """
        Gibt die Phone-Home URL zurueck.

        Wenn nicht konfiguriert und request_host angegeben,
        wird die URL automatisch generiert.

        Args:
            request_host: Host aus dem HTTP-Request (z.B. "10.0.0.100:8080")

        Returns:
            Phone-Home URL oder None wenn deaktiviert
        """
        settings = await self.get_settings()

        if not settings.phone_home_enabled:
            return None

        if settings.phone_home_url:
            return settings.phone_home_url

        # Auto-generate aus Request-Host
        if request_host:
            # Entferne Port falls vorhanden
            host = request_host.split(":")[0] if ":" in request_host else request_host
            # Backend laeuft auf Port 8000
            return f"http://{host}:8000/api/cloud-init/callback"

        return None

    async def get_admin_username(self) -> str:
        """Gibt den Admin-Benutzernamen zurueck"""
        settings = await self.get_settings()
        return settings.admin_username or self.DEFAULT_ADMIN_USERNAME

    async def get_admin_gecos(self) -> str:
        """Gibt den Admin GECOS-String zurueck"""
        settings = await self.get_settings()
        return settings.admin_gecos or self.DEFAULT_ADMIN_GECOS

    async def get_nas_snippets_config(self) -> dict:
        """
        Gibt die NAS Snippets Konfiguration zurueck.

        Returns:
            Dict mit path, ref und enabled
        """
        settings = await self.get_settings()
        return {
            "path": settings.nas_snippets_path,
            "ref": settings.nas_snippets_ref,
            "enabled": bool(settings.nas_snippets_path),
        }

    async def update_settings(
        self,
        ssh_keys: Optional[List[str]] = None,
        phone_home_enabled: Optional[bool] = None,
        phone_home_url: Optional[str] = None,
        admin_username: Optional[str] = None,
        admin_gecos: Optional[str] = None,
        nas_snippets_path: Optional[str] = None,
        nas_snippets_ref: Optional[str] = None,
    ) -> CloudInitSettings:
        """
        Aktualisiert die Settings.

        Nur angegebene Parameter werden aktualisiert (nicht-None).

        Returns:
            Aktualisierte Settings
        """
        settings = await self.get_settings()

        if ssh_keys is not None:
            cleaned_keys = [k.strip() for k in ssh_keys if k.strip()]
            settings.ssh_authorized_keys = json.dumps(cleaned_keys)

        if phone_home_enabled is not None:
            settings.phone_home_enabled = phone_home_enabled

        if phone_home_url is not None:
            # Leerer String = None (auto-generate)
            settings.phone_home_url = phone_home_url if phone_home_url else None

        if admin_username is not None:
            settings.admin_username = admin_username.strip() or self.DEFAULT_ADMIN_USERNAME

        if admin_gecos is not None:
            settings.admin_gecos = admin_gecos.strip() or self.DEFAULT_ADMIN_GECOS

        if nas_snippets_path is not None:
            settings.nas_snippets_path = nas_snippets_path.strip() if nas_snippets_path else None

        if nas_snippets_ref is not None:
            settings.nas_snippets_ref = nas_snippets_ref.strip() if nas_snippets_ref else None

        await self.db.commit()
        await self.db.refresh(settings)

        logger.info("Cloud-Init Settings aktualisiert")
        return settings

    async def get_all_settings_dict(self) -> dict:
        """
        Gibt alle Settings als Dictionary zurueck.

        Nuetzlich fuer API-Responses und Debugging.
        """
        settings = await self.get_settings()
        return {
            "ssh_authorized_keys": await self.get_ssh_keys(),
            "phone_home_enabled": settings.phone_home_enabled,
            "phone_home_url": settings.phone_home_url,
            "admin_username": settings.admin_username,
            "admin_gecos": settings.admin_gecos,
            "nas_snippets_path": settings.nas_snippets_path,
            "nas_snippets_ref": settings.nas_snippets_ref,
        }


def get_cloud_init_settings_service(db: AsyncSession) -> CloudInitSettingsService:
    """Factory-Funktion fuer Dependency Injection"""
    return CloudInitSettingsService(db)
