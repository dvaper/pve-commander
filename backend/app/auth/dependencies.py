"""
Auth Dependencies für FastAPI

Verfuegbare Dependencies:
- get_current_user: Holt User aus JWT (Basis)
- get_current_active_user: Prueft ob User aktiv
- get_current_admin_user: Prueft Admin-Rechte (Legacy)
- get_current_super_admin: Prueft Super-Admin-Rechte
- get_permission_service_dep: Liefert PermissionService fuer aktuellen User
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.auth.security import decode_token
from app.models.user import User
from app.exceptions import (
    AuthenticationError,
    TokenExpiredError,
    PermissionDeniedError,
    SuperAdminRequiredError,
)
from app.services.permission_service import PermissionService, get_permission_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Holt den aktuellen User aus dem JWT Token.

    Lädt auch die group_access und playbook_access Relationships.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Ungültige Anmeldedaten",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_data = decode_token(token)
    if token_data is None or token_data.username is None:
        raise credentials_exception

    result = await db.execute(
        select(User)
        .options(
            selectinload(User.group_access),
            selectinload(User.playbook_access),
        )
        .where(User.username == token_data.username)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Prüft ob User aktiv ist"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Benutzer ist deaktiviert",
        )
    return current_user


async def get_current_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Prüft ob User Admin ist (Legacy - verwendet is_admin oder is_super_admin)"""
    if not current_user.is_admin and not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin-Berechtigung erforderlich",
        )
    return current_user


async def get_current_super_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Prüft ob User Super-Admin ist (Vollzugriff)"""
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super-Admin-Berechtigung erforderlich",
        )
    return current_user


# Alias fuer kuerzere Imports
get_current_super_admin = get_current_super_admin_user


# =============================================================================
# Permission Service Dependency
# =============================================================================

async def get_permission_service_dep(
    current_user: User = Depends(get_current_active_user),
) -> PermissionService:
    """
    Dependency die PermissionService fuer aktuellen User liefert.

    Verwendung:
        @router.get("/items")
        async def list_items(
            perm: PermissionService = Depends(get_permission_service_dep),
        ):
            if perm.is_super_admin:
                ...
            groups = perm.filter_groups(all_groups)
    """
    return get_permission_service(current_user)


async def require_permission(
    permission: str,
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Factory fuer Permissions-Check Dependencies.

    Verwendung:
        require_manage_users = lambda: Depends(lambda u=Depends(get_current_active_user): require_permission("manage_users", u))

    Hinweis: Fuer haeufige Checks wie Super-Admin ist get_current_super_admin besser geeignet.
    """
    perm_service = get_permission_service(current_user)

    permission_checks = {
        "manage_users": perm_service.can_manage_users,
        "manage_settings": perm_service.can_manage_settings,
        "super_admin": perm_service.is_super_admin,
    }

    if permission not in permission_checks:
        raise ValueError(f"Unbekannte Permission: {permission}")

    if not permission_checks[permission]:
        raise PermissionDeniedError(f"Permission '{permission}' erforderlich")

    return current_user
