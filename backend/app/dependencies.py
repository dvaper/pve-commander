"""
Dependency Injection - Zentrale Service-Dependencies fuer FastAPI

Dieses Modul stellt alle Service-Dependencies fuer FastAPI-Routen bereit.
Ermoeglicht einheitliche Injektion und einfacheres Testing.

Verwendung in Routern:
    from app.dependencies import (
        get_db,
        get_current_user,
        get_permission_service_dep,
        get_netbox_service_dep,
    )

    @router.get("/items")
    async def get_items(
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user),
        netbox: NetBoxService = Depends(get_netbox_service_dep),
    ):
        ...
"""

from typing import AsyncGenerator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt

from app.config import settings
from app.database import async_session
from app.models.user import User


# =============================================================================
# OAuth2 Schema
# =============================================================================

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# =============================================================================
# Database Dependency
# =============================================================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency fuer Datenbank-Session.

    Oeffnet eine neue Session und schliesst sie nach dem Request.
    """
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


# =============================================================================
# Auth Dependencies (re-export aus auth.dependencies)
# =============================================================================

# Import der existierenden Auth-Dependencies
from app.auth.dependencies import (
    get_current_user,
    get_current_active_user,
    get_current_admin_user,
    get_current_super_admin,
    get_optional_current_user,
)


# =============================================================================
# Service Dependencies
# =============================================================================

async def get_permission_service_dep(
    user: User = Depends(get_current_user),
):
    """Dependency fuer PermissionService."""
    from app.services.permission_service import get_permission_service
    return get_permission_service(user)


async def get_settings_service_dep(
    db: AsyncSession = Depends(get_db),
):
    """Dependency fuer SettingsService."""
    from app.services.settings_service import get_settings_service
    return get_settings_service(db)


async def get_notification_service_dep(
    db: AsyncSession = Depends(get_db),
):
    """Dependency fuer NotificationService."""
    from app.services.notification_service import get_notification_service
    return get_notification_service(db)


async def get_vm_template_service_dep(
    db: AsyncSession = Depends(get_db),
):
    """Dependency fuer VMTemplateService."""
    from app.services.vm_template_service import get_vm_template_service
    return get_vm_template_service(db)


async def get_cloud_init_settings_service_dep(
    db: AsyncSession = Depends(get_db),
):
    """Dependency fuer CloudInitSettingsService."""
    from app.services.cloud_init_settings_service import get_cloud_init_settings_service
    return get_cloud_init_settings_service(db)


async def get_rbac_service_dep(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Dependency fuer RBACService."""
    from app.services.rbac_service import get_rbac_service
    return get_rbac_service(db, user)


async def get_password_reset_service_dep(
    db: AsyncSession = Depends(get_db),
):
    """Dependency fuer PasswordResetService."""
    from app.services.password_reset_service import get_password_reset_service
    return get_password_reset_service(db)


# =============================================================================
# Singleton Service Dependencies (Stateless)
# =============================================================================

def get_proxmox_service_dep():
    """Dependency fuer ProxmoxService (Singleton)."""
    from app.services.proxmox_service import get_proxmox_service
    return get_proxmox_service()


def get_netbox_service_dep():
    """Dependency fuer NetBoxService (Singleton)."""
    from app.services.netbox_service import netbox_service
    return netbox_service


def get_terraform_service_dep():
    """Dependency fuer TerraformService."""
    from app.services.terraform_service import TerraformService
    return TerraformService()


def get_inventory_sync_service_dep():
    """Dependency fuer InventorySyncService (Singleton)."""
    from app.services.inventory_sync_service import get_sync_service
    return get_sync_service()


def get_ansible_inventory_service_dep():
    """Dependency fuer AnsibleInventoryService (Singleton)."""
    from app.services.ansible_inventory_service import ansible_inventory_service
    return ansible_inventory_service


def get_cloud_init_service_dep():
    """Dependency fuer CloudInitService (Singleton)."""
    from app.services.cloud_init_service import cloud_init_service
    return cloud_init_service


def get_ssh_service_dep():
    """Dependency fuer SSHService (Singleton)."""
    from app.services.ssh_service import get_ssh_service
    return get_ssh_service()


# =============================================================================
# Permission Check Dependencies
# =============================================================================

def require_permission(permission_key: str):
    """
    Factory fuer Permission-Check Dependency.

    Verwendung:
        @router.get("/vms")
        async def list_vms(
            _: None = Depends(require_permission("terraform.view")),
        ):
            ...
    """
    async def check_permission(
        user: User = Depends(get_current_user),
    ):
        from app.services.permission_service import get_permission_service
        perm_service = get_permission_service(user)

        if not perm_service.has_permission(permission_key):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Berechtigung '{permission_key}' erforderlich",
            )

    return check_permission


def require_admin():
    """Dependency die Admin-Rechte erfordert."""
    async def check_admin(user: User = Depends(get_current_user)):
        if not user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin-Rechte erforderlich",
            )
        return user
    return check_admin


def require_super_admin():
    """Dependency die Super-Admin-Rechte erfordert."""
    async def check_super_admin(user: User = Depends(get_current_user)):
        if not user.is_super_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Super-Admin-Rechte erforderlich",
            )
        return user
    return check_super_admin
