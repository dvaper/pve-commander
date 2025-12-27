"""
Password Reset Router - API-Endpunkte fuer Passwort-Zuruecksetzung

MED-01: Verwendet zentrales Rate-Limiting aus app.utils.rate_limit
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.notification import (
    PasswordResetRequest,
    PasswordResetConfirm,
    PasswordResetValidate,
)
from app.services.notification_service import NotificationService
from app.services.password_reset_service import PasswordResetService
from app.utils.rate_limit import check_rate_limit, RateLimitConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/forgot-password")
async def forgot_password(
    data: PasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Passwort-Reset anfordern.

    Sendet eine E-Mail mit einem Reset-Link, falls die E-Mail existiert.
    Aus Sicherheitsgruenden wird immer eine Erfolgsmeldung zurueckgegeben.
    """
    # MED-01: Zentrales Rate-Limiting verwenden
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"pwd_reset:{client_ip}"
    if not check_rate_limit(
        rate_key,
        limit=RateLimitConfig.PASSWORD_RESET_LIMIT,
        window_seconds=RateLimitConfig.PASSWORD_RESET_WINDOW
    ):
        logger.warning(f"Rate-Limit erreicht fuer Passwort-Reset von {client_ip}")
        raise HTTPException(
            429,
            "Zu viele Anfragen. Bitte versuchen Sie es in einer Minute erneut."
        )

    # Service erstellen
    notification_service = NotificationService(db)
    password_reset_service = PasswordResetService(db, notification_service)

    # Reset anfordern
    await password_reset_service.request_reset(data.email)

    # Immer Erfolg zurueckmelden (Sicherheit)
    return {
        "message": "Falls die E-Mail-Adresse existiert, wurde ein Reset-Link gesendet."
    }


@router.get("/validate-reset-token", response_model=PasswordResetValidate)
async def validate_reset_token(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Prueft ob ein Reset-Token gueltig ist.

    Wird vom Frontend verwendet, um zu pruefen ob der Token noch gueltig ist,
    bevor das Passwort-Formular angezeigt wird.
    """
    notification_service = NotificationService(db)
    password_reset_service = PasswordResetService(db, notification_service)

    validation = await password_reset_service.validate_token(token)

    if validation:
        return PasswordResetValidate(
            valid=True,
            expires_at=validation['expires_at']
        )
    else:
        return PasswordResetValidate(valid=False)


@router.post("/reset-password")
async def reset_password(
    data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db)
):
    """
    Passwort mit Token zuruecksetzen.

    Setzt das Passwort zurueck, wenn der Token gueltig ist.
    """
    notification_service = NotificationService(db)
    password_reset_service = PasswordResetService(db, notification_service)

    success = await password_reset_service.reset_password(
        token=data.token,
        new_password=data.new_password
    )

    if not success:
        raise HTTPException(
            400,
            "Ungueltiger oder abgelaufener Token. Bitte fordern Sie einen neuen Reset-Link an."
        )

    return {"message": "Passwort erfolgreich geaendert. Sie koennen sich jetzt einloggen."}
