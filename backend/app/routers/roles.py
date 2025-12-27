"""
Roles Router - RBAC Rollen-Verwaltung

Endpoints:
- GET /api/roles - Alle Rollen auflisten
- GET /api/roles/{id} - Rollen-Details
- POST /api/roles - Rolle erstellen
- PUT /api/roles/{id} - Rolle aktualisieren
- DELETE /api/roles/{id} - Rolle loeschen
- GET /api/roles/{id}/permissions - Rollen-Berechtigungen
- PUT /api/roles/{id}/permissions - Berechtigungen setzen
- GET /api/roles/permissions/all - Alle verfuegbaren Permissions
"""
import json
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.auth.dependencies import get_current_active_user
from app.models.user import User
from app.models.role import Role
from app.models.permission import Permission
from app.models.role_permission import RolePermission
from app.models.user_role import UserRole
from app.services.rbac_service import RBACService
from app.services.audit_service import AuditService, ActionType, ResourceType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/roles", tags=["roles"])


# =============================================================================
# Schemas
# =============================================================================

class RoleCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    display_name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    parent_role_id: Optional[int] = None
    priority: int = 0
    allowed_os_types: Optional[List[str]] = None
    allowed_categories: Optional[List[str]] = None


class RoleUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    parent_role_id: Optional[int] = None
    priority: Optional[int] = None
    allowed_os_types: Optional[List[str]] = None
    allowed_categories: Optional[List[str]] = None


class RolePermissionItem(BaseModel):
    permission_id: int
    scope: Optional[Dict[str, Any]] = None
    is_deny: bool = False


class RolePermissionSet(BaseModel):
    permissions: List[RolePermissionItem]


class PermissionResponse(BaseModel):
    id: int
    name: str
    resource: str
    action: str
    description: Optional[str]
    is_system: bool

    class Config:
        from_attributes = True


class RolePermissionResponse(BaseModel):
    permission: PermissionResponse
    scope: Optional[Dict[str, Any]]
    is_deny: bool


class RoleResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str]
    parent_role_id: Optional[int]
    parent_role_name: Optional[str] = None
    priority: int
    is_system_role: bool
    is_super_admin: bool
    allowed_os_types: Optional[List[str]] = None
    allowed_categories: Optional[List[str]] = None
    created_at: Optional[str] = None
    permissions_count: int = 0
    users_count: int = 0

    class Config:
        from_attributes = True


# =============================================================================
# Helper Functions
# =============================================================================

def role_to_response(role: Role) -> RoleResponse:
    """Konvertiert Role Model zu Response."""
    return RoleResponse(
        id=role.id,
        name=role.name,
        display_name=role.display_name,
        description=role.description,
        parent_role_id=role.parent_role_id,
        parent_role_name=role.parent_role.name if role.parent_role else None,
        priority=role.priority,
        is_system_role=role.is_system_role,
        is_super_admin=role.is_super_admin,
        allowed_os_types=json.loads(role.allowed_os_types) if role.allowed_os_types else None,
        allowed_categories=json.loads(role.allowed_categories) if role.allowed_categories else None,
        created_at=role.created_at.isoformat() if role.created_at else None,
        permissions_count=len(role.permissions) if role.permissions else 0,
        users_count=len(role.user_roles) if role.user_roles else 0,
    )


async def check_roles_permission(db: AsyncSession, user: User) -> None:
    """Prueft ob User Rollen verwalten darf."""
    rbac = RBACService(db, user)
    if not await rbac.has_permission("roles.write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Keine Berechtigung zur Rollen-Verwaltung"
        )


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=List[RoleResponse])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Listet alle Rollen auf."""
    rbac = RBACService(db, current_user)

    if not await rbac.has_permission("roles.read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Keine Berechtigung zum Lesen der Rollen"
        )

    result = await db.execute(
        select(Role)
        .options(
            selectinload(Role.permissions),
            selectinload(Role.user_roles),
            selectinload(Role.parent_role),
        )
        .order_by(Role.priority.desc(), Role.name)
    )
    roles = result.scalars().all()

    return [role_to_response(r) for r in roles]


@router.get("/permissions/all", response_model=List[PermissionResponse])
async def list_all_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Listet alle verfuegbaren Permissions auf."""
    rbac = RBACService(db, current_user)

    if not await rbac.has_permission("roles.read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Keine Berechtigung"
        )

    result = await db.execute(
        select(Permission).order_by(Permission.resource, Permission.action)
    )
    permissions = result.scalars().all()

    return permissions


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Gibt Details einer Rolle zurueck."""
    rbac = RBACService(db, current_user)

    if not await rbac.has_permission("roles.read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Keine Berechtigung"
        )

    result = await db.execute(
        select(Role)
        .options(
            selectinload(Role.permissions).selectinload(RolePermission.permission),
            selectinload(Role.user_roles),
            selectinload(Role.parent_role),
        )
        .where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rolle nicht gefunden"
        )

    return role_to_response(role)


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    data: RoleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Erstellt eine neue Rolle."""
    await check_roles_permission(db, current_user)

    # Pruefen ob Name bereits existiert
    result = await db.execute(
        select(Role).where(Role.name == data.name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rollenname bereits vergeben"
        )

    # Parent-Rolle validieren
    if data.parent_role_id:
        result = await db.execute(
            select(Role).where(Role.id == data.parent_role_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent-Rolle nicht gefunden"
            )

    # Rolle erstellen
    role = Role(
        name=data.name,
        display_name=data.display_name,
        description=data.description,
        parent_role_id=data.parent_role_id,
        priority=data.priority,
        is_system_role=False,
        is_super_admin=False,
        allowed_os_types=json.dumps(data.allowed_os_types) if data.allowed_os_types else None,
        allowed_categories=json.dumps(data.allowed_categories) if data.allowed_categories else None,
        created_by=current_user.username,
    )

    db.add(role)
    await db.commit()
    await db.refresh(role)

    # Audit Log (vor dem Neuladen mit Relationships)
    role_id = role.id
    role_name = role.name
    audit = AuditService(db)
    await audit.log(
        action_type=ActionType.CREATE,
        resource_type=ResourceType.ROLE,
        user_id=current_user.id,
        username=current_user.username,
        resource_id=str(role_id),
        resource_name=role_name,
        details={"role_data": data.model_dump()},
        rollback_data={
            "action": "delete_created",
            "role_id": role_id,
        },
    )

    logger.info(f"Rolle erstellt: {role_name} von {current_user.username}")

    # Rolle mit Relationships neu laden fuer Response
    result = await db.execute(
        select(Role)
        .options(
            selectinload(Role.permissions),
            selectinload(Role.user_roles),
            selectinload(Role.parent_role),
        )
        .where(Role.id == role_id)
    )
    role = result.scalar_one()

    return role_to_response(role)


@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    data: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Aktualisiert eine Rolle."""
    await check_roles_permission(db, current_user)

    result = await db.execute(
        select(Role)
        .options(selectinload(Role.parent_role))
        .where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rolle nicht gefunden"
        )

    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System-Rollen koennen nicht bearbeitet werden"
        )

    # Alte Werte speichern
    old_data = {
        "display_name": role.display_name,
        "description": role.description,
        "parent_role_id": role.parent_role_id,
        "priority": role.priority,
        "allowed_os_types": role.allowed_os_types,
        "allowed_categories": role.allowed_categories,
    }

    # Aktualisieren
    if data.display_name is not None:
        role.display_name = data.display_name
    if data.description is not None:
        role.description = data.description
    if data.parent_role_id is not None:
        role.parent_role_id = data.parent_role_id
    if data.priority is not None:
        role.priority = data.priority
    if data.allowed_os_types is not None:
        role.allowed_os_types = json.dumps(data.allowed_os_types)
    if data.allowed_categories is not None:
        role.allowed_categories = json.dumps(data.allowed_categories)

    await db.commit()
    await db.refresh(role)

    # Audit Log (vor dem Neuladen mit Relationships)
    role_id_for_audit = role.id
    role_name_for_audit = role.name
    audit = AuditService(db)
    await audit.log(
        action_type=ActionType.UPDATE,
        resource_type=ResourceType.ROLE,
        user_id=current_user.id,
        username=current_user.username,
        resource_id=str(role_id_for_audit),
        resource_name=role_name_for_audit,
        details={
            "old_data": old_data,
            "new_data": data.model_dump(exclude_unset=True),
        },
        rollback_data={
            "action": "revert_update",
            "role_id": role_id_for_audit,
            "old_data": old_data,
        },
    )

    logger.info(f"Rolle aktualisiert: {role_name_for_audit} von {current_user.username}")

    # Rolle mit Relationships neu laden fuer Response
    result = await db.execute(
        select(Role)
        .options(
            selectinload(Role.permissions),
            selectinload(Role.user_roles),
            selectinload(Role.parent_role),
        )
        .where(Role.id == role_id_for_audit)
    )
    role = result.scalar_one()

    return role_to_response(role)


@router.delete("/{role_id}")
async def delete_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Loescht eine Rolle."""
    await check_roles_permission(db, current_user)

    rbac = RBACService(db, current_user)
    if not await rbac.has_permission("roles.delete"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Keine Berechtigung zum Loeschen"
        )

    result = await db.execute(
        select(Role)
        .options(
            selectinload(Role.permissions),
            selectinload(Role.user_roles),
        )
        .where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rolle nicht gefunden"
        )

    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System-Rollen koennen nicht geloescht werden"
        )

    if role.user_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rolle ist noch {len(role.user_roles)} Benutzern zugewiesen"
        )

    # Rolle-Daten fuer Rollback speichern
    role_data = {
        "name": role.name,
        "display_name": role.display_name,
        "description": role.description,
        "parent_role_id": role.parent_role_id,
        "priority": role.priority,
        "allowed_os_types": role.allowed_os_types,
        "allowed_categories": role.allowed_categories,
    }

    permissions_data = [
        {
            "permission_id": rp.permission_id,
            "scope": rp.scope,
            "is_deny": rp.is_deny,
        }
        for rp in role.permissions
    ]

    role_name = role.name
    await db.delete(role)
    await db.commit()

    # Audit Log
    audit = AuditService(db)
    await audit.log(
        action_type=ActionType.DELETE,
        resource_type=ResourceType.ROLE,
        user_id=current_user.id,
        username=current_user.username,
        resource_id=str(role_id),
        resource_name=role_name,
        details={"role_data": role_data},
        rollback_data={
            "action": "restore_deleted",
            "role_data": role_data,
            "permissions": permissions_data,
        },
    )

    logger.info(f"Rolle geloescht: {role_name} von {current_user.username}")

    return {"message": f"Rolle '{role_name}' geloescht"}


@router.get("/{role_id}/permissions", response_model=List[RolePermissionResponse])
async def get_role_permissions(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Gibt die Berechtigungen einer Rolle zurueck."""
    rbac = RBACService(db, current_user)

    if not await rbac.has_permission("roles.read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Keine Berechtigung"
        )

    result = await db.execute(
        select(RolePermission)
        .options(selectinload(RolePermission.permission))
        .where(RolePermission.role_id == role_id)
    )
    role_perms = result.scalars().all()

    return [
        RolePermissionResponse(
            permission=PermissionResponse.model_validate(rp.permission),
            scope=json.loads(rp.scope) if rp.scope else None,
            is_deny=rp.is_deny,
        )
        for rp in role_perms
    ]


@router.put("/{role_id}/permissions")
async def set_role_permissions(
    role_id: int,
    data: RolePermissionSet,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Setzt die Berechtigungen einer Rolle."""
    await check_roles_permission(db, current_user)

    result = await db.execute(
        select(Role).where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rolle nicht gefunden"
        )

    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System-Rollen-Berechtigungen koennen nicht geaendert werden"
        )

    # Alte Permissions holen
    result = await db.execute(
        select(RolePermission).where(RolePermission.role_id == role_id)
    )
    old_perms = result.scalars().all()
    old_perms_data = [
        {
            "permission_id": rp.permission_id,
            "scope": rp.scope,
            "is_deny": rp.is_deny,
        }
        for rp in old_perms
    ]

    # Alte Permissions loeschen
    for old_perm in old_perms:
        await db.delete(old_perm)

    # Neue Permissions setzen
    for perm_item in data.permissions:
        # Permission existiert?
        result = await db.execute(
            select(Permission).where(Permission.id == perm_item.permission_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Permission {perm_item.permission_id} nicht gefunden"
            )

        role_perm = RolePermission(
            role_id=role_id,
            permission_id=perm_item.permission_id,
            scope=json.dumps(perm_item.scope) if perm_item.scope else None,
            is_deny=perm_item.is_deny,
        )
        db.add(role_perm)

    await db.commit()

    # Audit Log
    audit = AuditService(db)
    await audit.log(
        action_type=ActionType.PERMISSION_CHANGE,
        resource_type=ResourceType.ROLE,
        user_id=current_user.id,
        username=current_user.username,
        resource_id=str(role_id),
        resource_name=role.name,
        details={
            "old_permissions": old_perms_data,
            "new_permissions": [p.model_dump() for p in data.permissions],
        },
        rollback_data={
            "action": "revert_permissions",
            "role_id": role_id,
            "old_permissions": old_perms_data,
        },
    )

    logger.info(f"Rollen-Berechtigungen aktualisiert: {role.name} von {current_user.username}")

    return {"message": f"Berechtigungen fuer '{role.name}' aktualisiert"}
