"""
RBAC Service - Role-Based Access Control mit Hierarchie-Support

Permission Resolution Order:
1. Super-Admin Bypass (immer erlaubt)
2. Explicit DENY (gewinnt immer)
3. Rollen-Hierarchie (erbt von Parent-Rollen)
4. Scope-Restrictions (filtert nach Gruppen/Kategorien)
5. Default DENY (wenn keine passende Permission)
"""
import json
import logging
from typing import Set, Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.role import Role
from app.models.permission import Permission
from app.models.role_permission import RolePermission
from app.models.user_role import UserRole
from app.models.playbook_metadata import PlaybookMetadata

logger = logging.getLogger(__name__)


class RBACService:
    """
    Zentraler RBAC Service mit Caching und Hierarchie-Support.

    Usage:
        rbac = RBACService(db, user)

        # Einfache Permission-Pruefung
        if await rbac.has_permission("users.write"):
            ...

        # Permission mit Scope
        if await rbac.has_permission("playbooks.execute", {"group": "linux-servers"}):
            ...

        # Playbook-Ausfuehrung pruefen
        if await rbac.can_execute_playbook("update-system", ["web-servers"]):
            ...
    """

    def __init__(self, db: AsyncSession, user: User):
        self.db = db
        self.user = user
        self._permission_cache: Optional[Dict[str, Any]] = None
        self._role_cache: Optional[List[Role]] = None

    # =========================================================================
    # Core Permission Checks
    # =========================================================================

    async def has_permission(
        self,
        permission_name: str,
        scope: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Prueft ob der Benutzer eine bestimmte Permission hat.

        Args:
            permission_name: Permission zu pruefen (z.B. "users.write")
            scope: Optionale Scope-Restrictions zur Validierung
                   z.B. {"group": "linux-servers", "playbook": "custom-deploy"}

        Returns:
            True wenn Permission gewaehrt, sonst False
        """
        # Super-Admin Bypass
        if await self.is_super_admin():
            return True

        # Permissions laden falls nicht gecached
        if self._permission_cache is None:
            await self._load_permissions()

        # Zuerst Explicit Deny pruefen
        if self._has_deny(permission_name, scope):
            return False

        # Dann Allow pruefen
        return self._has_allow(permission_name, scope)

    async def has_any_permission(self, permission_names: List[str]) -> bool:
        """Prueft ob mindestens eine der Permissions vorhanden ist."""
        for perm in permission_names:
            if await self.has_permission(perm):
                return True
        return False

    async def has_all_permissions(self, permission_names: List[str]) -> bool:
        """Prueft ob alle Permissions vorhanden sind."""
        for perm in permission_names:
            if not await self.has_permission(perm):
                return False
        return True

    async def get_effective_permissions(self) -> Dict[str, Any]:
        """
        Gibt alle effektiven Permissions des Benutzers zurueck.

        Returns:
            {
                "permissions": ["users.read", "playbooks.execute", ...],
                "scoped_permissions": {
                    "playbooks.execute": [{"groups": ["linux-*"]}],
                    ...
                },
                "denied_permissions": ["users.delete"],
                "is_super_admin": False,
                "roles": ["linux-admin", "operator"]
            }
        """
        if self._permission_cache is None:
            await self._load_permissions()

        roles = await self._get_user_roles()

        return {
            "permissions": list(self._permission_cache.get("allowed", set())),
            "scoped_permissions": self._permission_cache.get("scopes", {}),
            "denied_permissions": list(self._permission_cache.get("denied", set())),
            "is_super_admin": await self.is_super_admin(),
            "roles": [r.name for r in roles],
            "role_details": [
                {
                    "name": r.name,
                    "display_name": r.display_name,
                    "priority": r.priority,
                }
                for r in roles
            ],
        }

    async def is_super_admin(self) -> bool:
        """Prueft ob der Benutzer Super-Admin ist."""
        # Legacy-Flag
        if self.user.is_super_admin:
            return True

        # Rollen pruefen
        roles = await self._get_user_roles()
        return any(r.is_super_admin for r in roles)

    async def is_active(self) -> bool:
        """Prueft ob der Benutzer aktiv ist."""
        return self.user.is_active

    # =========================================================================
    # Role Hierarchy
    # =========================================================================

    async def _get_user_roles(self) -> List[Role]:
        """Holt alle Rollen des Benutzers (inkl. vererbte)."""
        if self._role_cache is not None:
            return self._role_cache

        # Direkte Rollen-Zuweisungen laden
        result = await self.db.execute(
            select(UserRole)
            .options(selectinload(UserRole.role))
            .where(UserRole.user_id == self.user.id)
        )
        user_roles = result.scalars().all()

        # Alle Rollen inkl. Parents sammeln
        all_roles: List[Role] = []
        visited: Set[int] = set()

        for user_role in user_roles:
            await self._collect_role_hierarchy(user_role.role, all_roles, visited)

        self._role_cache = all_roles
        return all_roles

    async def _collect_role_hierarchy(
        self,
        role: Role,
        collected: List[Role],
        visited: Set[int]
    ):
        """Sammelt rekursiv Rolle und ihre Parents."""
        if role.id in visited:
            return

        visited.add(role.id)
        collected.append(role)

        # Parent-Rolle laden falls vorhanden
        if role.parent_role_id:
            result = await self.db.execute(
                select(Role).where(Role.id == role.parent_role_id)
            )
            parent = result.scalar_one_or_none()
            if parent:
                await self._collect_role_hierarchy(parent, collected, visited)

    async def _load_permissions(self):
        """Laedt alle Permissions aus Rollen in den Cache."""
        roles = await self._get_user_roles()

        allowed: Set[str] = set()
        denied: Set[str] = set()
        scopes: Dict[str, List[Dict]] = {}

        for role in roles:
            # Rollen-Permissions laden
            result = await self.db.execute(
                select(RolePermission)
                .options(selectinload(RolePermission.permission))
                .where(RolePermission.role_id == role.id)
            )
            role_perms = result.scalars().all()

            for rp in role_perms:
                perm_name = rp.permission.name

                if rp.is_deny:
                    denied.add(perm_name)
                else:
                    allowed.add(perm_name)
                    if rp.scope:
                        if perm_name not in scopes:
                            scopes[perm_name] = []
                        try:
                            scopes[perm_name].append(json.loads(rp.scope))
                        except json.JSONDecodeError:
                            logger.warning(f"Ungültiger Scope für {perm_name}: {rp.scope}")

        self._permission_cache = {
            "allowed": allowed,
            "denied": denied,
            "scopes": scopes,
        }

    def _has_deny(self, permission: str, scope: Optional[Dict]) -> bool:
        """Prueft auf Explicit Deny."""
        return permission in self._permission_cache.get("denied", set())

    def _has_allow(self, permission: str, scope: Optional[Dict]) -> bool:
        """Prueft auf Allow mit Scope-Validierung."""
        if permission not in self._permission_cache.get("allowed", set()):
            return False

        # Wenn kein Scope erforderlich, erlauben
        if scope is None:
            return True

        # Scope-Restrictions pruefen
        perm_scopes = self._permission_cache.get("scopes", {}).get(permission, [])
        if not perm_scopes:
            return True  # Keine Scope-Restrictions

        # Mindestens ein Scope muss matchen
        for perm_scope in perm_scopes:
            if self._scope_matches(perm_scope, scope):
                return True

        return False

    def _scope_matches(self, allowed_scope: Dict, requested_scope: Dict) -> bool:
        """Prueft ob angeforderter Scope mit erlaubtem Scope uebereinstimmt."""
        for key, value in requested_scope.items():
            if key not in allowed_scope:
                continue  # Keine Restriction auf diesem Key

            allowed_values = allowed_scope[key]
            if isinstance(allowed_values, list):
                # Wildcard-Patterns pruefen
                matched = False
                for pattern in allowed_values:
                    if isinstance(pattern, str):
                        if pattern.endswith("*"):
                            if value.startswith(pattern[:-1]):
                                matched = True
                                break
                        elif value == pattern:
                            matched = True
                            break
                if not matched:
                    return False
            elif isinstance(allowed_values, str):
                if allowed_values.endswith("*"):
                    if not value.startswith(allowed_values[:-1]):
                        return False
                elif value != allowed_values:
                    return False

        return True

    # =========================================================================
    # Playbook Access
    # =========================================================================

    async def can_access_playbook(self, playbook_name: str) -> bool:
        """Prueft ob Benutzer auf ein Playbook zugreifen kann."""
        if await self.is_super_admin():
            return True

        # playbooks.read Permission mit Scope pruefen
        return await self.has_permission(
            "playbooks.read",
            {"playbook": playbook_name}
        )

    async def can_execute_playbook(
        self,
        playbook_name: str,
        target_groups: List[str]
    ) -> bool:
        """Prueft ob Benutzer Playbook auf Zielgruppen ausfuehren kann."""
        if await self.is_super_admin():
            return True

        # Execution-Permission pruefen
        if not await self.has_permission("playbooks.execute"):
            return False

        # Playbook-Zugriff pruefen
        if not await self.can_access_playbook(playbook_name):
            return False

        # Gruppen-Zugriff pruefen
        for group in target_groups:
            if not await self.has_permission("inventory.read", {"group": group}):
                return False

        # OS-Type und Kategorie-Restrictions pruefen
        metadata = await self._get_playbook_metadata(playbook_name)
        if metadata:
            roles = await self._get_user_roles()
            for role in roles:
                # OS-Type Restriction
                if role.allowed_os_types:
                    try:
                        allowed = json.loads(role.allowed_os_types)
                        if metadata.os_type not in allowed and "all" not in allowed:
                            continue  # Diese Rolle erlaubt es nicht, naechste pruefen
                    except json.JSONDecodeError:
                        pass

                # Kategorie Restriction
                if role.allowed_categories:
                    try:
                        allowed = json.loads(role.allowed_categories)
                        if metadata.category not in allowed:
                            continue  # Diese Rolle erlaubt es nicht
                    except json.JSONDecodeError:
                        pass

                # Rolle erlaubt es
                return True

            # Keine Rolle hat es erlaubt
            return False

        return True

    async def _get_playbook_metadata(
        self,
        playbook_name: str
    ) -> Optional[PlaybookMetadata]:
        """Holt Playbook-Metadaten aus der Datenbank."""
        result = await self.db.execute(
            select(PlaybookMetadata)
            .where(PlaybookMetadata.playbook_name == playbook_name)
        )
        return result.scalar_one_or_none()

    # =========================================================================
    # Inventory Access
    # =========================================================================

    async def get_accessible_groups(self) -> Set[str]:
        """Gibt alle zugaenglichen Inventory-Gruppen zurueck."""
        if await self.is_super_admin():
            return set()  # Leeres Set = alle Gruppen

        # Gruppen aus Scope-Restrictions extrahieren
        if self._permission_cache is None:
            await self._load_permissions()

        groups: Set[str] = set()
        inventory_scopes = self._permission_cache.get("scopes", {}).get("inventory.read", [])

        for scope in inventory_scopes:
            if "groups" in scope:
                groups.update(scope["groups"])

        # Legacy: UserGroupAccess
        if hasattr(self.user, 'group_access') and self.user.group_access:
            for access in self.user.group_access:
                groups.add(access.group_name)

        return groups

    async def can_access_group(self, group_name: str) -> bool:
        """Prueft ob Benutzer auf eine Gruppe zugreifen kann."""
        if await self.is_super_admin():
            return True

        return await self.has_permission("inventory.read", {"group": group_name})

    # =========================================================================
    # Execution Access
    # =========================================================================

    async def can_view_execution(self, execution_user_id: int) -> bool:
        """Prueft ob Benutzer eine Execution sehen kann."""
        if await self.is_super_admin():
            return True

        # Alle Executions sehen?
        if await self.has_permission("executions.read_all"):
            return True

        # Eigene Executions?
        if await self.has_permission("executions.read"):
            return execution_user_id == self.user.id

        return False

    async def can_cancel_execution(self, execution_user_id: int) -> bool:
        """Prueft ob Benutzer eine Execution abbrechen kann."""
        if await self.is_super_admin():
            return True

        # Cancel-Permission vorhanden?
        if not await self.has_permission("executions.cancel"):
            return False

        # Alle oder nur eigene?
        if await self.has_permission("executions.read_all"):
            return True

        return execution_user_id == self.user.id

    # =========================================================================
    # User Management
    # =========================================================================

    async def can_manage_users(self) -> bool:
        """Prueft ob Benutzer andere Benutzer verwalten kann."""
        return await self.has_permission("users.admin") or await self.is_super_admin()

    async def can_manage_roles(self) -> bool:
        """Prueft ob Benutzer Rollen verwalten kann."""
        return await self.has_permission("roles.write") or await self.is_super_admin()

    async def can_manage_settings(self) -> bool:
        """Prueft ob Benutzer Einstellungen aendern kann."""
        return await self.has_permission("settings.write") or await self.is_super_admin()

    # =========================================================================
    # Access Summary
    # =========================================================================

    async def get_access_summary(self) -> Dict[str, Any]:
        """
        Gibt eine Zusammenfassung der Zugriffsrechte zurueck.
        Nützlich für die Frontend-Anzeige.
        """
        return {
            "is_super_admin": await self.is_super_admin(),
            "is_active": await self.is_active(),
            "can_manage_users": await self.can_manage_users(),
            "can_manage_roles": await self.can_manage_roles(),
            "can_manage_settings": await self.can_manage_settings(),
            "permissions": await self.get_effective_permissions(),
        }


# =============================================================================
# Factory Function
# =============================================================================

def get_rbac_service(db: AsyncSession, user: User) -> RBACService:
    """Factory-Funktion fuer RBACService."""
    return RBACService(db, user)
