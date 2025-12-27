"""
Audit Helper - Vereinfachte Audit-Logging Integration

Stellt Context-Manager und Decorator fuer einfache Integration
in bestehende Router bereit.
"""
import json
import logging
from typing import Dict, Any, Optional, Callable
from functools import wraps
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.audit_service import AuditService, ActionType, ResourceType

logger = logging.getLogger(__name__)


class AuditContext:
    """
    Context fuer Audit-Logging.

    Vereinfacht das Erfassen von Request-Kontext (IP, User-Agent).
    """

    def __init__(
        self,
        db: AsyncSession,
        request: Optional[Request] = None,
    ):
        self.db = db
        self.service = AuditService(db)
        self.request = request

    def _get_request_context(self) -> Dict[str, Any]:
        """Extrahiert Kontext aus dem Request."""
        if not self.request:
            return {}

        return {
            "ip_address": self._get_client_ip(),
            "user_agent": self.request.headers.get("user-agent", "")[:500],
            "correlation_id": self.request.headers.get("x-correlation-id"),
        }

    def _get_client_ip(self) -> Optional[str]:
        """Ermittelt die Client-IP (inkl. Proxy-Support)."""
        if not self.request:
            return None

        # Forwarded Header (Standard)
        forwarded = self.request.headers.get("forwarded")
        if forwarded:
            # Format: for=<ip>;host=...; proto=...
            for part in forwarded.split(";"):
                if part.strip().lower().startswith("for="):
                    ip = part.strip()[4:].strip('"')
                    return ip

        # X-Forwarded-For (non-standard aber weit verbreitet)
        x_forwarded = self.request.headers.get("x-forwarded-for")
        if x_forwarded:
            # Erstes Element ist die Original-IP
            return x_forwarded.split(",")[0].strip()

        # X-Real-IP (Nginx)
        real_ip = self.request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Direkter Client
        if self.request.client:
            return self.request.client.host

        return None

    async def log(
        self,
        action_type: str,
        resource_type: str,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        rollback_data: Optional[Dict[str, Any]] = None,
        is_rollbackable: bool = False,
    ):
        """
        Erstellt einen Audit-Log-Eintrag.

        Args:
            action_type: Typ der Aktion (CREATE, UPDATE, DELETE, ...)
            resource_type: Typ der Ressource (user, role, playbook, ...)
            user_id: ID des handelnden Users
            username: Name des handelnden Users
            resource_id: ID der betroffenen Ressource
            resource_name: Name/Bezeichnung der Ressource
            details: Zusaetzliche Details (old_value, new_value, ...)
            rollback_data: Daten fuer Rollback-Operation
            is_rollbackable: Kann diese Aktion rueckgaengig gemacht werden?
        """
        request_context = self._get_request_context()

        await self.service.log(
            action_type=action_type,
            resource_type=resource_type,
            user_id=user_id,
            username=username,
            resource_id=resource_id,
            resource_name=resource_name,
            details=details,
            rollback_data=rollback_data,
            is_rollbackable=is_rollbackable,
            request_context=request_context,
        )


async def audit_log(
    db: AsyncSession,
    action_type: str,
    resource_type: str,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    resource_id: Optional[str] = None,
    resource_name: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    rollback_data: Optional[Dict[str, Any]] = None,
    is_rollbackable: bool = False,
    request: Optional[Request] = None,
):
    """
    Convenience-Funktion fuer Audit-Logging.

    Kann direkt in Endpoints verwendet werden:

    ```python
    await audit_log(
        db=db,
        action_type=ActionType.CREATE,
        resource_type=ResourceType.USER,
        user_id=current_user.id,
        username=current_user.username,
        resource_id=str(new_user.id),
        resource_name=new_user.username,
        request=request,
    )
    ```
    """
    ctx = AuditContext(db, request)
    await ctx.log(
        action_type=action_type,
        resource_type=resource_type,
        user_id=user_id,
        username=username,
        resource_id=resource_id,
        resource_name=resource_name,
        details=details,
        rollback_data=rollback_data,
        is_rollbackable=is_rollbackable,
    )


def prepare_user_rollback_data(user, action: str = "restore_deleted") -> Dict[str, Any]:
    """
    Bereitet Rollback-Daten fuer User-Operationen vor.

    Args:
        user: User-Objekt
        action: Art der Rollback-Aktion

    Returns:
        Dict mit Rollback-Daten
    """
    if action == "restore_deleted":
        return {
            "action": "restore_deleted",
            "user_data": {
                "id": user.id,
                "username": user.username,
                "password_hash": user.password_hash,
                "email": user.email,
                "is_admin": user.is_admin,
                "is_super_admin": user.is_super_admin,
                "is_active": user.is_active,
                "theme": user.theme,
                "dark_mode": getattr(user, 'dark_mode', 'dark'),
            }
        }
    elif action == "delete_created":
        return {
            "action": "delete_created",
            "user_id": user.id,
        }
    elif action == "revert_update":
        return {
            "action": "revert_update",
            "user_id": user.id,
            "old_data": {},  # Muss vom Aufrufer gefuellt werden
        }
    else:
        return {"action": action}


def prepare_role_rollback_data(role, permissions=None, action: str = "restore_deleted") -> Dict[str, Any]:
    """
    Bereitet Rollback-Daten fuer Rollen-Operationen vor.

    Args:
        role: Role-Objekt
        permissions: Liste der Rollen-Permissions
        action: Art der Rollback-Aktion

    Returns:
        Dict mit Rollback-Daten
    """
    if action == "restore_deleted":
        return {
            "action": "restore_deleted",
            "role_data": {
                "name": role.name,
                "display_name": role.display_name,
                "description": role.description,
                "parent_role_id": role.parent_role_id,
                "priority": role.priority,
                "is_system_role": role.is_system_role,
                "is_super_admin": role.is_super_admin,
                "allowed_os_types": role.allowed_os_types,
                "allowed_categories": role.allowed_categories,
            },
            "permissions": permissions or [],
        }
    elif action == "delete_created":
        return {
            "action": "delete_created",
            "role_id": role.id,
        }
    elif action == "revert_update":
        return {
            "action": "revert_update",
            "role_id": role.id,
            "old_data": {},  # Muss vom Aufrufer gefuellt werden
        }
    else:
        return {"action": action}


def prepare_settings_rollback_data(key: str, old_value: Any) -> Dict[str, Any]:
    """
    Bereitet Rollback-Daten fuer Settings-Aenderungen vor.

    Args:
        key: Settings-Key
        old_value: Alter Wert vor der Aenderung

    Returns:
        Dict mit Rollback-Daten
    """
    return {
        "action": "revert_update",
        "key": key,
        "old_value": old_value,
    }


def prepare_user_role_rollback_data(user_id: int, role_id: int, action: str) -> Dict[str, Any]:
    """
    Bereitet Rollback-Daten fuer User-Role-Zuweisungen vor.

    Args:
        user_id: ID des Users
        role_id: ID der Rolle
        action: Art der Rollback-Aktion

    Returns:
        Dict mit Rollback-Daten
    """
    if action == "remove_assigned":
        return {
            "action": "remove_assigned",
            "user_id": user_id,
            "role_id": role_id,
        }
    elif action == "restore_removed":
        return {
            "action": "restore_removed",
            "user_role_data": {
                "user_id": user_id,
                "role_id": role_id,
            }
        }
    else:
        return {"action": action}


# Re-export ActionType und ResourceType fuer einfachen Import
__all__ = [
    "AuditContext",
    "audit_log",
    "prepare_user_rollback_data",
    "prepare_role_rollback_data",
    "prepare_settings_rollback_data",
    "prepare_user_role_rollback_data",
    "ActionType",
    "ResourceType",
]
