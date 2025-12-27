"""
PermissionService - Zentraler Service für Berechtigungsprüfungen.

Berechtigungskonzept:
- Super-Admins: Globaler Vollzugriff auf alle Gruppen, Playbooks und Executions
- Reguläre User: Zugriff nur auf zugewiesene Gruppen und Playbooks
- Execution-History: User sehen nur eigene Executions (Super-Admins alle)
"""

from typing import Set, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.user_group_access import UserGroupAccess
from app.models.user_playbook_access import UserPlaybookAccess


class PermissionService:
    """
    Zentraler Service für Berechtigungsprüfungen.

    Bietet einheitliche Methoden für:
    - Gruppen-Berechtigungen (Inventory-Gruppen)
    - Playbook-Berechtigungen
    - Execution-Berechtigungen
    - Benutzer-Verwaltungsrechte
    """

    def __init__(self, user: User):
        """
        Initialisiert den Permission-Service.

        Args:
            user: Aktueller Benutzer
        """
        self.user = user
        self._accessible_groups: Optional[Set[str]] = None
        self._accessible_playbooks: Optional[Set[str]] = None

    # ==================== Basis-Eigenschaften ====================

    @property
    def is_super_admin(self) -> bool:
        """Prüft ob der User Super-Admin ist (globaler Vollzugriff)."""
        return self.user is not None and self.user.is_super_admin

    @property
    def is_active(self) -> bool:
        """Prüft ob der User aktiv ist."""
        return self.user is not None and self.user.is_active

    @property
    def can_manage_users(self) -> bool:
        """Prüft ob der User Benutzer verwalten darf (nur Super-Admins)."""
        return self.is_super_admin

    @property
    def can_manage_settings(self) -> bool:
        """Prüft ob der User App-Einstellungen verwalten darf (nur Super-Admins)."""
        return self.is_super_admin

    # ==================== Gruppen-Berechtigungen ====================

    def get_accessible_groups(self) -> Set[str]:
        """
        Gibt alle Gruppen-Namen zurück, auf die der User Zugriff hat.

        - Super-Admins: Leeres Set (bedeutet: alle Gruppen)
        - Reguläre User: Zugewiesene Gruppen

        Returns:
            Set von Gruppen-Namen (leer bei Super-Admin = alle)
        """
        if self._accessible_groups is not None:
            return self._accessible_groups

        if self.is_super_admin:
            self._accessible_groups = set()  # Leer = alle
            return self._accessible_groups

        # Gruppen aus der Relationship laden
        self._accessible_groups = {
            access.group_name for access in self.user.group_access
        }
        return self._accessible_groups

    def can_access_group(self, group_name: str) -> bool:
        """
        Prüft ob der User auf eine bestimmte Gruppe zugreifen darf.

        Args:
            group_name: Name der Inventory-Gruppe

        Returns:
            True wenn Zugriff erlaubt
        """
        if self.is_super_admin:
            return True
        return group_name in self.get_accessible_groups()

    def can_access_any_group(self, group_names: List[str]) -> bool:
        """
        Prüft ob der User auf mindestens eine der Gruppen zugreifen darf.

        Args:
            group_names: Liste von Gruppen-Namen

        Returns:
            True wenn Zugriff auf mindestens eine Gruppe erlaubt
        """
        if self.is_super_admin:
            return True
        accessible = self.get_accessible_groups()
        return any(group in accessible for group in group_names)

    def filter_groups(self, all_groups: List[str]) -> List[str]:
        """
        Filtert eine Liste von Gruppen auf die zugänglichen.

        Args:
            all_groups: Liste aller Gruppen

        Returns:
            Liste der zugänglichen Gruppen
        """
        if self.is_super_admin:
            return all_groups
        accessible = self.get_accessible_groups()
        return [g for g in all_groups if g in accessible]

    # ==================== Playbook-Berechtigungen ====================

    def get_accessible_playbooks(self) -> Set[str]:
        """
        Gibt alle Playbook-Namen zurück, auf die der User Zugriff hat.

        - Super-Admins: Leeres Set (bedeutet: alle Playbooks)
        - Reguläre User: Zugewiesene Playbooks

        Returns:
            Set von Playbook-Namen (leer bei Super-Admin = alle)
        """
        if self._accessible_playbooks is not None:
            return self._accessible_playbooks

        if self.is_super_admin:
            self._accessible_playbooks = set()  # Leer = alle
            return self._accessible_playbooks

        # Playbooks aus der Relationship laden
        self._accessible_playbooks = {
            access.playbook_name for access in self.user.playbook_access
        }
        return self._accessible_playbooks

    def can_access_playbook(self, playbook_name: str) -> bool:
        """
        Prüft ob der User auf ein bestimmtes Playbook zugreifen darf.

        Args:
            playbook_name: Name des Playbooks

        Returns:
            True wenn Zugriff erlaubt
        """
        if self.is_super_admin:
            return True
        return playbook_name in self.get_accessible_playbooks()

    def filter_playbooks(self, all_playbooks: List[dict]) -> List[dict]:
        """
        Filtert eine Liste von Playbooks auf die zugänglichen.

        Args:
            all_playbooks: Liste aller Playbooks (als dict mit 'name'-Key)

        Returns:
            Liste der zugänglichen Playbooks
        """
        if self.is_super_admin:
            return all_playbooks
        accessible = self.get_accessible_playbooks()
        return [p for p in all_playbooks if p.get("name") in accessible]

    # ==================== Execution-Berechtigungen ====================

    def can_view_execution(self, execution_user_id: int) -> bool:
        """
        Prüft ob der User eine bestimmte Execution sehen darf.

        - Super-Admins: Alle Executions
        - Reguläre User: Nur eigene Executions

        Args:
            execution_user_id: User-ID des Execution-Erstellers

        Returns:
            True wenn Ansicht erlaubt
        """
        if self.is_super_admin:
            return True
        return self.user.id == execution_user_id

    def can_cancel_execution(self, execution_user_id: int) -> bool:
        """
        Prüft ob der User eine Execution abbrechen darf.

        Args:
            execution_user_id: User-ID des Execution-Erstellers

        Returns:
            True wenn Abbruch erlaubt
        """
        if self.is_super_admin:
            return True
        return self.user.id == execution_user_id

    def get_execution_filter_user_id(self) -> Optional[int]:
        """
        Gibt die User-ID für Execution-Filterung zurück.

        - Super-Admins: None (keine Filterung)
        - Reguläre User: Eigene User-ID

        Returns:
            User-ID für Filterung oder None
        """
        if self.is_super_admin:
            return None
        return self.user.id

    # ==================== Ansible-Ausführung ====================

    def can_execute_playbook(self, playbook_name: str, target_groups: List[str]) -> bool:
        """
        Prüft ob der User ein Playbook auf bestimmten Gruppen ausführen darf.

        Args:
            playbook_name: Name des Playbooks
            target_groups: Ziel-Gruppen für die Ausführung

        Returns:
            True wenn Ausführung erlaubt
        """
        if self.is_super_admin:
            return True

        # Playbook-Zugriff prüfen
        if not self.can_access_playbook(playbook_name):
            return False

        # Gruppen-Zugriff prüfen (alle Ziel-Gruppen müssen zugänglich sein)
        accessible_groups = self.get_accessible_groups()
        return all(group in accessible_groups for group in target_groups)

    # ==================== Zusammenfassung ====================

    def get_access_summary(self) -> dict:
        """
        Gibt eine Zusammenfassung der Berechtigungen zurück.

        Nützlich für Frontend und Debugging.
        """
        return {
            "is_super_admin": self.is_super_admin,
            "is_active": self.is_active,
            "can_manage_users": self.can_manage_users,
            "can_manage_settings": self.can_manage_settings,
            "accessible_groups": list(self.get_accessible_groups()),
            "accessible_playbooks": list(self.get_accessible_playbooks()),
        }


# ==================== Factory-Funktion ====================

def get_permission_service(user: User) -> PermissionService:
    """
    Factory-Funktion für PermissionService.

    Args:
        user: Aktueller Benutzer

    Returns:
        Konfigurierter PermissionService
    """
    return PermissionService(user)
