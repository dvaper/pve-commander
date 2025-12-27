"""
Rollback Executors - Ressourcenspezifische Rollback-Logik

Jeder Executor implementiert die Logik zum Rueckgaengigmachen
einer bestimmten Aktion auf einer bestimmten Ressource.
"""
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.audit_rollback import AuditRollback
from app.services.audit_service import AuditService, ActionType, ResourceType

logger = logging.getLogger(__name__)


class RollbackExecutor(ABC):
    """Basis-Klasse fuer Rollback-Executors."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @abstractmethod
    async def execute(self, rollback_data: Dict[str, Any]) -> None:
        """Fuehrt die Rollback-Operation aus."""
        pass

    @abstractmethod
    def get_resource_type(self) -> str:
        """Gibt den Ressourcentyp zurueck."""
        pass


class UserRollbackExecutor(RollbackExecutor):
    """Rollback-Executor fuer User-Aenderungen."""

    def get_resource_type(self) -> str:
        return ResourceType.USER

    async def execute(self, rollback_data: Dict[str, Any]) -> None:
        from app.models.user import User
        from app.auth.security import get_password_hash

        action = rollback_data.get("action")

        if action == "restore_deleted":
            # Geloeschten User wiederherstellen
            user_data = rollback_data.get("user_data")
            if not user_data:
                raise ValueError("Keine User-Daten fuer Wiederherstellung")

            user = User(
                id=user_data.get("id"),
                username=user_data.get("username"),
                password_hash=user_data.get("password_hash"),
                email=user_data.get("email"),
                is_admin=user_data.get("is_admin", False),
                is_super_admin=user_data.get("is_super_admin", False),
                is_active=user_data.get("is_active", True),
                theme=user_data.get("theme", "blue"),
                dark_mode=user_data.get("dark_mode", "dark"),
            )
            self.db.add(user)
            logger.info(f"User wiederhergestellt: {user.username}")

        elif action == "revert_update":
            # User-Update rueckgaengig machen
            user_id = rollback_data.get("user_id")
            old_data = rollback_data.get("old_data")

            if not user_id or not old_data:
                raise ValueError("Unvollstaendige Rollback-Daten")

            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                raise ValueError(f"User {user_id} nicht gefunden")

            for key, value in old_data.items():
                if hasattr(user, key) and key != "id":
                    setattr(user, key, value)

            logger.info(f"User-Update rueckgaengig gemacht: {user.username}")

        elif action == "delete_created":
            # Erstellten User loeschen
            user_id = rollback_data.get("user_id")

            if not user_id:
                raise ValueError("Keine User-ID fuer Loeschung")

            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if user:
                await self.db.delete(user)
                logger.info(f"Erstellten User geloescht: {user.username}")

        else:
            raise ValueError(f"Unbekannte Rollback-Aktion: {action}")

        await self.db.commit()


class RoleRollbackExecutor(RollbackExecutor):
    """Rollback-Executor fuer Rollen-Aenderungen."""

    def get_resource_type(self) -> str:
        return ResourceType.ROLE

    async def execute(self, rollback_data: Dict[str, Any]) -> None:
        from app.models.role import Role
        from app.models.role_permission import RolePermission

        action = rollback_data.get("action")

        if action == "restore_deleted":
            # Geloeschte Rolle wiederherstellen
            role_data = rollback_data.get("role_data")
            permissions = rollback_data.get("permissions", [])

            if not role_data:
                raise ValueError("Keine Rollen-Daten fuer Wiederherstellung")

            role = Role(
                name=role_data.get("name"),
                display_name=role_data.get("display_name"),
                description=role_data.get("description"),
                parent_role_id=role_data.get("parent_role_id"),
                priority=role_data.get("priority", 0),
                is_system_role=role_data.get("is_system_role", False),
                is_super_admin=role_data.get("is_super_admin", False),
                allowed_os_types=role_data.get("allowed_os_types"),
                allowed_categories=role_data.get("allowed_categories"),
            )
            self.db.add(role)
            await self.db.flush()

            # Permissions wiederherstellen
            for perm in permissions:
                rp = RolePermission(
                    role_id=role.id,
                    permission_id=perm.get("permission_id"),
                    scope=perm.get("scope"),
                    is_deny=perm.get("is_deny", False),
                )
                self.db.add(rp)

            logger.info(f"Rolle wiederhergestellt: {role.name}")

        elif action == "revert_update":
            # Rollen-Update rueckgaengig machen
            role_id = rollback_data.get("role_id")
            old_data = rollback_data.get("old_data")

            if not role_id or not old_data:
                raise ValueError("Unvollstaendige Rollback-Daten")

            result = await self.db.execute(
                select(Role).where(Role.id == role_id)
            )
            role = result.scalar_one_or_none()

            if not role:
                raise ValueError(f"Rolle {role_id} nicht gefunden")

            for key, value in old_data.items():
                if hasattr(role, key) and key != "id":
                    setattr(role, key, value)

            logger.info(f"Rollen-Update rueckgaengig gemacht: {role.name}")

        elif action == "delete_created":
            # Erstellte Rolle loeschen
            role_id = rollback_data.get("role_id")

            if not role_id:
                raise ValueError("Keine Rollen-ID fuer Loeschung")

            result = await self.db.execute(
                select(Role).where(Role.id == role_id)
            )
            role = result.scalar_one_or_none()

            if role:
                await self.db.delete(role)
                logger.info(f"Erstellte Rolle geloescht: {role.name}")

        else:
            raise ValueError(f"Unbekannte Rollback-Aktion: {action}")

        await self.db.commit()


class SettingsRollbackExecutor(RollbackExecutor):
    """Rollback-Executor fuer Einstellungs-Aenderungen."""

    def get_resource_type(self) -> str:
        return ResourceType.SETTINGS

    async def execute(self, rollback_data: Dict[str, Any]) -> None:
        from app.models.app_settings import AppSettings

        action = rollback_data.get("action")

        if action == "revert_update":
            setting_key = rollback_data.get("key")
            old_value = rollback_data.get("old_value")

            if not setting_key:
                raise ValueError("Kein Settings-Key fuer Rollback")

            result = await self.db.execute(
                select(AppSettings).where(AppSettings.key == setting_key)
            )
            setting = result.scalar_one_or_none()

            if setting:
                setting.value = old_value
                logger.info(f"Setting rueckgaengig gemacht: {setting_key}")
            else:
                # Setting existiert nicht mehr, neu erstellen
                setting = AppSettings(key=setting_key, value=old_value)
                self.db.add(setting)
                logger.info(f"Setting wiederhergestellt: {setting_key}")

        else:
            raise ValueError(f"Unbekannte Rollback-Aktion: {action}")

        await self.db.commit()


class UserRoleRollbackExecutor(RollbackExecutor):
    """Rollback-Executor fuer User-Rollen-Zuweisungen."""

    def get_resource_type(self) -> str:
        return "user_role"

    async def execute(self, rollback_data: Dict[str, Any]) -> None:
        from app.models.user_role import UserRole

        action = rollback_data.get("action")

        if action == "remove_assigned":
            # Zugewiesene Rolle entfernen
            user_id = rollback_data.get("user_id")
            role_id = rollback_data.get("role_id")

            result = await self.db.execute(
                select(UserRole).where(
                    UserRole.user_id == user_id,
                    UserRole.role_id == role_id
                )
            )
            user_role = result.scalar_one_or_none()

            if user_role:
                await self.db.delete(user_role)
                logger.info(f"Rollen-Zuweisung entfernt: User {user_id}, Role {role_id}")

        elif action == "restore_removed":
            # Entfernte Rolle wiederherstellen
            user_role_data = rollback_data.get("user_role_data")

            if not user_role_data:
                raise ValueError("Keine User-Role-Daten fuer Wiederherstellung")

            user_role = UserRole(
                user_id=user_role_data.get("user_id"),
                role_id=user_role_data.get("role_id"),
            )
            self.db.add(user_role)
            logger.info(f"Rollen-Zuweisung wiederhergestellt")

        else:
            raise ValueError(f"Unbekannte Rollback-Aktion: {action}")

        await self.db.commit()


# =============================================================================
# Executor Registry
# =============================================================================

ROLLBACK_EXECUTORS = {
    ResourceType.USER: UserRollbackExecutor,
    ResourceType.ROLE: RoleRollbackExecutor,
    ResourceType.SETTINGS: SettingsRollbackExecutor,
    "user_role": UserRoleRollbackExecutor,
}


def get_rollback_executor(
    db: AsyncSession,
    resource_type: str
) -> Optional[RollbackExecutor]:
    """Holt den passenden Executor fuer einen Ressourcentyp."""
    executor_class = ROLLBACK_EXECUTORS.get(resource_type)
    if executor_class:
        return executor_class(db)
    return None


# =============================================================================
# Rollback Service
# =============================================================================

class RollbackService:
    """
    Service fuer die Ausfuehrung von Rollback-Operationen.

    Koordiniert zwischen AuditService und spezifischen Executors.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit_service = AuditService(db)

    async def execute_rollback(
        self,
        rollback_id: int,
        executor_user_id: int,
        executor_username: str,
    ) -> AuditRollback:
        """
        Fuehrt einen angeforderten Rollback aus.

        Args:
            rollback_id: ID des Rollback-Requests
            executor_user_id: ID des ausfuehrenden Users
            executor_username: Name des ausfuehrenden Users

        Returns:
            Aktualisierter AuditRollback Record
        """
        # Rollback-Request holen
        rollback = await self.audit_service.get_rollback_by_id(rollback_id)

        if not rollback:
            raise ValueError(f"Rollback-Request {rollback_id} nicht gefunden")

        if rollback.status != "pending":
            raise ValueError(f"Rollback {rollback_id} ist nicht ausstehend (Status: {rollback.status})")

        # Original Audit-Eintrag holen
        original = await self.audit_service.get_log_by_id(rollback.original_audit_id)

        if not original:
            raise ValueError(f"Original Audit-Eintrag nicht gefunden")

        # Status auf "executing" setzen
        rollback.status = "executing"
        await self.db.commit()

        try:
            # Rollback-Daten parsen
            rollback_data = json.loads(original.rollback_data) if original.rollback_data else {}

            # Executor holen
            executor = get_rollback_executor(self.db, original.resource_type)

            if not executor:
                raise ValueError(f"Kein Executor fuer Ressourcentyp: {original.resource_type}")

            # Rollback ausfuehren
            await executor.execute(rollback_data)

            # Status aktualisieren
            rollback.status = "completed"
            rollback.success = True
            rollback.executed_at = datetime.utcnow()

            # Original-Eintrag als rueckgerollt markieren
            original.rollback_executed = True

            # Audit-Eintrag fuer den Rollback erstellen
            rollback_audit = await self.audit_service.log(
                action_type=ActionType.ROLLBACK,
                resource_type=original.resource_type,
                user_id=executor_user_id,
                username=executor_username,
                resource_id=original.resource_id,
                resource_name=original.resource_name,
                details={
                    "original_audit_id": original.id,
                    "original_action": original.action_type,
                    "original_sequence": original.sequence,
                    "reason": rollback.reason,
                },
            )

            rollback.rollback_audit_id = rollback_audit.id
            original.rollback_by_entry_id = rollback_audit.id

            await self.db.commit()

            logger.info(f"Rollback {rollback_id} erfolgreich ausgefuehrt")

            return rollback

        except Exception as e:
            # Fehler dokumentieren
            rollback.status = "failed"
            rollback.success = False
            rollback.error_message = str(e)
            await self.db.commit()

            logger.error(f"Rollback {rollback_id} fehlgeschlagen: {e}")
            raise

    async def cancel_rollback(
        self,
        rollback_id: int,
        user_id: int,
        username: str,
    ) -> AuditRollback:
        """
        Bricht einen ausstehenden Rollback-Request ab.
        """
        rollback = await self.audit_service.get_rollback_by_id(rollback_id)

        if not rollback:
            raise ValueError(f"Rollback-Request {rollback_id} nicht gefunden")

        if rollback.status != "pending":
            raise ValueError(f"Nur ausstehende Rollbacks koennen abgebrochen werden")

        rollback.status = "cancelled"
        await self.db.commit()

        logger.info(f"Rollback {rollback_id} abgebrochen von {username}")

        return rollback
