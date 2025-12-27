"""
Auth Router - Login, Profil, Passwort-Änderung

Security Features:
- Rate-Limiting gegen Brute-Force (CRIT-05)
- Timing-Attack-Schutz (CRIT-04)
"""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    UserResponse,
    UserResponseWithAccess,
    Token,
    PasswordChangeRequest,
    UserAccessSummary,
    UserPreferencesUpdate,
    UserPreferencesResponse,
)
from app.auth.security import verify_password, get_password_hash, create_access_token
from app.auth.dependencies import get_current_user, get_current_active_user
from app.services.permission_service import get_permission_service
from app.services.netbox_user_service import netbox_user_service
from app.services.audit_helper import audit_log, ActionType, ResourceType
from app.utils.rate_limit import (
    check_rate_limit,
    clear_rate_limit,
    RateLimitConfig,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# CRIT-04: Dummy-Hash fuer Timing-Attack-Schutz
# Wird verwendet wenn User nicht existiert, um konstante Antwortzeit zu gewaehrleisten
_DUMMY_PASSWORD_HASH = get_password_hash("dummy_password_for_timing_protection")


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Login und JWT Token erhalten.

    Security Features:
    - Rate-Limiting: Max 5 Versuche/Minute pro IP, 10 Versuche/5min pro Username
    - Timing-Attack-Schutz: Konstante Antwortzeit unabhaengig ob User existiert
    """
    # Client-IP fuer Rate-Limiting ermitteln
    client_ip = "unknown"
    if request:
        # X-Forwarded-For Header beruecksichtigen (Reverse Proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        elif request.client:
            client_ip = request.client.host

    # CRIT-05: Rate-Limiting pro IP
    rate_limit_key_ip = f"login:ip:{client_ip}"
    if not check_rate_limit(
        rate_limit_key_ip,
        limit=RateLimitConfig.LOGIN_LIMIT,
        window_seconds=RateLimitConfig.LOGIN_WINDOW
    ):
        logger.warning(f"Login Rate-Limit erreicht fuer IP {client_ip}")
        await audit_log(
            db=db,
            action_type=ActionType.LOGIN_FAILED,
            resource_type=ResourceType.SESSION,
            username=form_data.username,
            resource_name=form_data.username,
            details={"reason": "rate_limit_exceeded", "ip": client_ip},
            request=request,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Zu viele Login-Versuche. Bitte warten Sie eine Minute.",
            headers={"Retry-After": "60"},
        )

    # CRIT-05: Rate-Limiting pro Username (schuetzt auch gegen verteilte Angriffe)
    rate_limit_key_user = f"login:user:{form_data.username.lower()}"
    if not check_rate_limit(
        rate_limit_key_user,
        limit=RateLimitConfig.LOGIN_USER_LIMIT,
        window_seconds=RateLimitConfig.LOGIN_USER_WINDOW
    ):
        logger.warning(f"Login Rate-Limit erreicht fuer User {form_data.username}")
        await audit_log(
            db=db,
            action_type=ActionType.LOGIN_FAILED,
            resource_type=ResourceType.SESSION,
            username=form_data.username,
            resource_name=form_data.username,
            details={"reason": "rate_limit_exceeded_user", "ip": client_ip},
            request=request,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Zu viele Login-Versuche fuer diesen Benutzer. Bitte warten Sie 5 Minuten.",
            headers={"Retry-After": "300"},
        )

    # User suchen
    result = await db.execute(
        select(User).where(User.username == form_data.username)
    )
    user = result.scalar_one_or_none()

    # CRIT-04: Timing-Attack-Schutz
    # IMMER einen Passwort-Vergleich durchfuehren, auch wenn User nicht existiert
    # Dies verhindert Username-Enumeration durch Zeitmessung
    password_hash_to_check = user.password_hash if user else _DUMMY_PASSWORD_HASH
    password_valid = verify_password(form_data.password, password_hash_to_check)

    if not user or not password_valid:
        # Audit: Fehlgeschlagener Login
        await audit_log(
            db=db,
            action_type=ActionType.LOGIN_FAILED,
            resource_type=ResourceType.SESSION,
            username=form_data.username,
            resource_name=form_data.username,
            details={"reason": "invalid_credentials", "ip": client_ip},
            request=request,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falscher Benutzername oder Passwort",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Prüfen ob User aktiv ist
    if not user.is_active:
        # Audit: Fehlgeschlagener Login (deaktiviert)
        await audit_log(
            db=db,
            action_type=ActionType.LOGIN_FAILED,
            resource_type=ResourceType.SESSION,
            user_id=user.id,
            username=user.username,
            resource_id=str(user.id),
            resource_name=user.username,
            details={"reason": "user_disabled"},
            request=request,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Benutzer ist deaktiviert",
        )

    # Last Login aktualisieren
    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    # Rate-Limit zuruecksetzen nach erfolgreichem Login
    clear_rate_limit(rate_limit_key_ip)
    clear_rate_limit(rate_limit_key_user)

    # Audit: Erfolgreicher Login
    await audit_log(
        db=db,
        action_type=ActionType.LOGIN,
        resource_type=ResourceType.SESSION,
        user_id=user.id,
        username=user.username,
        resource_id=str(user.id),
        resource_name=user.username,
        request=request,
    )

    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id}
    )

    return Token(access_token=access_token)


@router.get("/me", response_model=UserResponseWithAccess)
async def get_me(current_user: User = Depends(get_current_active_user)):
    """
    Aktuellen User mit Berechtigungen abrufen.

    Gibt alle Details inkl. zugewiesener Gruppen und Playbooks zurück.
    """
    return UserResponseWithAccess(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_admin=current_user.is_admin,
        is_super_admin=current_user.is_super_admin,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
        group_access=current_user.group_access,
        playbook_access=current_user.playbook_access,
        accessible_groups=[g.group_name for g in current_user.group_access],
        accessible_playbooks=[p.playbook_name for p in current_user.playbook_access],
    )


@router.get("/me/access", response_model=UserAccessSummary)
async def get_my_access(current_user: User = Depends(get_current_active_user)):
    """
    Berechtigungsübersicht für den aktuellen User.

    Gibt eine Zusammenfassung zurück, was der User sehen/tun darf.
    """
    perm_service = get_permission_service(current_user)
    summary = perm_service.get_access_summary()

    return UserAccessSummary(
        is_super_admin=summary["is_super_admin"],
        is_active=summary["is_active"],
        accessible_groups=summary["accessible_groups"],
        accessible_playbooks=summary["accessible_playbooks"],
        can_manage_users=summary["can_manage_users"],
    )


@router.post("/change-password")
async def change_password(
    password_data: PasswordChangeRequest,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Eigenes Passwort ändern.

    Erfordert das aktuelle Passwort zur Bestätigung.
    Optional: Synchronisiert das Passwort auch nach NetBox.
    """
    # Aktuelles Passwort verifizieren
    if not verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aktuelles Passwort ist falsch",
        )

    # Neues Passwort setzen
    current_user.password_hash = get_password_hash(password_data.new_password)

    # NetBox-Passwort synchronisieren (wenn aktiviert und verknüpft)
    netbox_synced = False
    if password_data.sync_to_netbox and current_user.netbox_user_id:
        try:
            success = await netbox_user_service.change_password(
                current_user.netbox_user_id,
                password_data.new_password,
            )
            if success:
                netbox_synced = True
                logger.info(f"NetBox-Passwort für User '{current_user.username}' synchronisiert")
        except Exception as e:
            logger.warning(f"NetBox-Passwort-Sync fehlgeschlagen: {e}")

    await db.commit()

    # Audit: Passwort-Aenderung (nicht rollbackable aus Sicherheitsgruenden)
    await audit_log(
        db=db,
        action_type=ActionType.UPDATE,
        resource_type=ResourceType.USER,
        user_id=current_user.id,
        username=current_user.username,
        resource_id=str(current_user.id),
        resource_name=current_user.username,
        details={
            "field": "password",
            "netbox_synced": netbox_synced,
        },
        request=request,
    )

    message = "Passwort erfolgreich geändert"
    if password_data.sync_to_netbox:
        if netbox_synced:
            message += " (auch in NetBox)"
        elif current_user.netbox_user_id:
            message += " (NetBox-Sync fehlgeschlagen)"
        else:
            message += " (kein NetBox-User verknüpft)"

    return {"message": message, "netbox_synced": netbox_synced}


@router.post("/init", response_model=UserResponse)
async def init_admin(
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Initialen Admin-User erstellen.
    Nur möglich wenn noch kein User existiert.
    """
    # Prüfen ob User existieren
    result = await db.execute(select(User))
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin-User existiert bereits. Verwende /api/auth/login",
        )

    # Admin-Credentials aus Settings oder generieren
    from app.config import settings
    import secrets

    admin_user = settings.app_admin_user or "admin"
    admin_email = settings.app_admin_email or "admin@local"

    if settings.app_admin_password:
        admin_password = settings.app_admin_password
    else:
        # Fallback: Generiertes Passwort (wird im Response nicht angezeigt!)
        admin_password = secrets.token_urlsafe(12)
        # Hinweis: Das generierte Passwort wird in den Container-Logs ausgegeben

    admin = User(
        username=admin_user,
        password_hash=get_password_hash(admin_password),
        email=admin_email,
        is_admin=True,  # Legacy
        is_super_admin=True,
        is_active=True,
    )

    db.add(admin)
    await db.commit()
    await db.refresh(admin)

    # Audit: Admin-User erstellt (System-Aktion)
    await audit_log(
        db=db,
        action_type=ActionType.CREATE,
        resource_type=ResourceType.USER,
        resource_id=str(admin.id),
        resource_name=admin.username,
        details={
            "event": "initial_admin_created",
            "is_super_admin": True,
        },
        request=request,
    )

    return admin


@router.get("/me/preferences", response_model=UserPreferencesResponse)
async def get_my_preferences(current_user: User = Depends(get_current_active_user)):
    """
    Benutzer-Einstellungen abrufen.

    Gibt aktuelle Theme- und Dark-Mode-Einstellungen zurueck.
    """
    return UserPreferencesResponse(
        theme=current_user.theme or "blue",
        dark_mode=getattr(current_user, 'dark_mode', None) or "dark",
        sidebar_logo=getattr(current_user, 'sidebar_logo', None) or "icon",
        ui_beta=getattr(current_user, 'ui_beta', False) or False,
    )


@router.patch("/me/preferences", response_model=UserPreferencesResponse)
async def update_my_preferences(
    preferences: UserPreferencesUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Benutzer-Einstellungen aktualisieren.

    Ermoeglicht das Aendern des Farbschemas, Dark-Mode und Sidebar-Logo.
    """
    changes = {}

    if preferences.theme is not None:
        changes["theme"] = {"old": current_user.theme, "new": preferences.theme}
        current_user.theme = preferences.theme

    if preferences.dark_mode is not None:
        changes["dark_mode"] = {"old": getattr(current_user, 'dark_mode', None), "new": preferences.dark_mode}
        current_user.dark_mode = preferences.dark_mode

    if preferences.sidebar_logo is not None:
        changes["sidebar_logo"] = {"old": getattr(current_user, 'sidebar_logo', None), "new": preferences.sidebar_logo}
        current_user.sidebar_logo = preferences.sidebar_logo

    if preferences.ui_beta is not None:
        changes["ui_beta"] = {"old": getattr(current_user, 'ui_beta', False), "new": preferences.ui_beta}
        current_user.ui_beta = preferences.ui_beta

    await db.commit()
    await db.refresh(current_user)

    # Audit: Preferences-Aenderung
    if changes:
        await audit_log(
            db=db,
            action_type=ActionType.UPDATE,
            resource_type=ResourceType.USER,
            user_id=current_user.id,
            username=current_user.username,
            resource_id=str(current_user.id),
            resource_name=current_user.username,
            details={"preferences_changed": changes},
            request=request,
        )

    return UserPreferencesResponse(
        theme=current_user.theme or "blue",
        dark_mode=getattr(current_user, 'dark_mode', None) or "dark",
        sidebar_logo=getattr(current_user, 'sidebar_logo', None) or "icon",
        ui_beta=getattr(current_user, 'ui_beta', False) or False,
    )
