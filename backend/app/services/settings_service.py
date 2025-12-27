"""
SettingsService - Verwaltung von App-Einstellungen.

Verwaltet Einstellungen wie:
- Default-Gruppen für neue Benutzer
- Default-Playbooks für neue Benutzer
"""

import json
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.app_settings import (
    AppSettings,
    SETTING_DEFAULT_GROUPS,
    SETTING_DEFAULT_PLAYBOOKS,
    SETTING_NETBOX_EXTERNAL_URL,
)


class SettingsService:
    """
    Service für App-Einstellungen.

    Bietet Methoden für:
    - Lesen und Speichern von Einstellungen
    - Default-Werte für neue Benutzer
    """

    def __init__(self, db: AsyncSession):
        """
        Initialisiert den Settings-Service.

        Args:
            db: Async-Datenbank-Session
        """
        self.db = db

    # ==================== Generische Methoden ====================

    async def get_setting(self, key: str) -> Optional[str]:
        """
        Holt einen Setting-Wert.

        Args:
            key: Setting-Key

        Returns:
            Setting-Wert oder None
        """
        result = await self.db.execute(
            select(AppSettings).where(AppSettings.key == key)
        )
        setting = result.scalar_one_or_none()
        return setting.value if setting else None

    async def set_setting(self, key: str, value: str, description: Optional[str] = None) -> AppSettings:
        """
        Setzt oder aktualisiert einen Setting-Wert.

        Args:
            key: Setting-Key
            value: Setting-Wert
            description: Optionale Beschreibung

        Returns:
            Das Setting-Objekt
        """
        result = await self.db.execute(
            select(AppSettings).where(AppSettings.key == key)
        )
        setting = result.scalar_one_or_none()

        if setting:
            setting.value = value
            if description:
                setting.description = description
        else:
            setting = AppSettings(key=key, value=value, description=description)
            self.db.add(setting)

        await self.db.commit()
        await self.db.refresh(setting)
        return setting

    async def get_all_settings(self) -> List[AppSettings]:
        """
        Holt alle Settings.

        Returns:
            Liste aller Settings
        """
        result = await self.db.execute(select(AppSettings))
        return list(result.scalars().all())

    # ==================== Default-Gruppen ====================

    async def get_default_groups(self) -> List[str]:
        """
        Holt die Default-Gruppen für neue Benutzer.

        Returns:
            Liste von Gruppen-Namen
        """
        value = await self.get_setting(SETTING_DEFAULT_GROUPS)
        if not value:
            return []
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return []

    async def set_default_groups(self, groups: List[str]) -> None:
        """
        Setzt die Default-Gruppen für neue Benutzer.

        Args:
            groups: Liste von Gruppen-Namen
        """
        await self.set_setting(
            SETTING_DEFAULT_GROUPS,
            json.dumps(groups),
            "Standard-Inventory-Gruppen für neue Benutzer"
        )

    # ==================== Default-Playbooks ====================

    async def get_default_playbooks(self) -> List[str]:
        """
        Holt die Default-Playbooks für neue Benutzer.

        Returns:
            Liste von Playbook-Namen
        """
        value = await self.get_setting(SETTING_DEFAULT_PLAYBOOKS)
        if not value:
            return []
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return []

    async def set_default_playbooks(self, playbooks: List[str]) -> None:
        """
        Setzt die Default-Playbooks für neue Benutzer.

        Args:
            playbooks: Liste von Playbook-Namen
        """
        await self.set_setting(
            SETTING_DEFAULT_PLAYBOOKS,
            json.dumps(playbooks),
            "Standard-Playbooks für neue Benutzer"
        )

    # ==================== NetBox External URL ====================

    async def get_netbox_external_url(self) -> Optional[str]:
        """
        Holt die externe NetBox URL.

        Returns:
            Externe NetBox URL oder None
        """
        return await self.get_setting(SETTING_NETBOX_EXTERNAL_URL)

    async def set_netbox_external_url(self, url: Optional[str]) -> None:
        """
        Setzt die externe NetBox URL.

        Args:
            url: Externe URL (z.B. https://netbox.example.com)
        """
        if url:
            await self.set_setting(
                SETTING_NETBOX_EXTERNAL_URL,
                url,
                "Externe URL fuer NetBox UI (fuer Browser-Zugriff)"
            )
        else:
            # URL loeschen wenn None oder leer
            result = await self.db.execute(
                select(AppSettings).where(AppSettings.key == SETTING_NETBOX_EXTERNAL_URL)
            )
            setting = result.scalar_one_or_none()
            if setting:
                await self.db.delete(setting)
                await self.db.commit()

    # ==================== Kombinierte Methoden ====================

    async def get_default_access(self) -> dict:
        """
        Holt alle Default-Zugriffseinstellungen.

        Returns:
            Dict mit 'default_groups' und 'default_playbooks'
        """
        return {
            "default_groups": await self.get_default_groups(),
            "default_playbooks": await self.get_default_playbooks(),
        }

    async def set_default_access(self, groups: List[str], playbooks: List[str]) -> None:
        """
        Setzt alle Default-Zugriffseinstellungen.

        Args:
            groups: Liste von Gruppen-Namen
            playbooks: Liste von Playbook-Namen
        """
        await self.set_default_groups(groups)
        await self.set_default_playbooks(playbooks)


# ==================== Factory-Funktion ====================

def get_settings_service(db: AsyncSession) -> SettingsService:
    """
    Factory-Funktion für SettingsService.

    Args:
        db: Async-Datenbank-Session

    Returns:
        Konfigurierter SettingsService
    """
    return SettingsService(db)
