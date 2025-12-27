"""
Password Reset Service - Passwort-Zuruecksetzung per E-Mail
"""
import os
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.password_reset_token import PasswordResetToken
from app.models.notification_settings import NotificationSettings
from app.auth.security import get_password_hash
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class PasswordResetService:
    """Service fuer Passwort-Zuruecksetzung"""

    def __init__(self, db: AsyncSession, notification_service: NotificationService):
        self.db = db
        self.notifications = notification_service

    async def _get_expiry_hours(self) -> int:
        """Laedt die Ablaufzeit aus den Einstellungen"""
        result = await self.db.execute(
            select(NotificationSettings).limit(1)
        )
        settings = result.scalar_one_or_none()
        if settings:
            return settings.password_reset_expiry_hours
        return 24  # Default

    async def _get_app_url(self) -> str:
        """Laedt die App-URL aus den Einstellungen"""
        result = await self.db.execute(
            select(NotificationSettings).limit(1)
        )
        settings = result.scalar_one_or_none()
        if settings and settings.app_url:
            return settings.app_url.rstrip('/')
        return os.getenv('APP_URL', 'http://localhost:8080').rstrip('/')

    async def _get_user_by_email(self, email: str) -> Optional[User]:
        """Findet Benutzer anhand der E-Mail"""
        result = await self.db.execute(
            select(User).where(
                and_(
                    User.email == email,
                    User.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()

    async def _invalidate_existing_tokens(self, user_id: int):
        """Invalidiert alle existierenden Tokens eines Benutzers"""
        await self.db.execute(
            update(PasswordResetToken).where(
                and_(
                    PasswordResetToken.user_id == user_id,
                    PasswordResetToken.used == False
                )
            ).values(used=True)
        )
        await self.db.commit()

    async def request_reset(self, email: str) -> bool:
        """
        Erstellt Reset-Token und sendet E-Mail.

        Aus Sicherheitsgruenden wird immer True zurueckgegeben,
        auch wenn die E-Mail nicht existiert.

        Args:
            email: E-Mail-Adresse des Benutzers

        Returns:
            True (immer, aus Sicherheitsgruenden)
        """
        # Benutzer finden
        user = await self._get_user_by_email(email)
        if not user:
            logger.info(f"Passwort-Reset angefordert fuer unbekannte E-Mail: {email[:3]}***")
            return True  # Sicherheit: Keine Rueckmeldung ob E-Mail existiert

        # Alte Tokens invalidieren
        await self._invalidate_existing_tokens(user.id)

        # Neuen Token erstellen
        token = secrets.token_urlsafe(48)
        expiry_hours = await self._get_expiry_hours()
        expires_at = datetime.utcnow() + timedelta(hours=expiry_hours)

        reset_token = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=expires_at
        )
        self.db.add(reset_token)
        await self.db.commit()

        # E-Mail senden
        app_url = await self._get_app_url()
        reset_url = f"{app_url}/reset-password?token={token}"

        plain_message = f"""Hallo {user.username},

Sie haben das Zuruecksetzen Ihres Passworts angefordert.

Klicken Sie auf folgenden Link (gueltig fuer {expiry_hours} Stunden):
{reset_url}

Falls Sie diese Anfrage nicht gestellt haben, ignorieren Sie diese E-Mail.
Ihr Passwort bleibt unveraendert.

Mit freundlichen Gruessen,
PVE Commander
"""

        html_message = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #1565C0; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: #ffffff; padding: 30px; border: 1px solid #e0e0e0; border-top: none; }}
        .footer {{ background: #f5f5f5; padding: 15px; text-align: center; font-size: 12px; color: #666; border-radius: 0 0 8px 8px; }}
        .button {{ display: inline-block; padding: 12px 24px; background: #1976D2; color: white !important; text-decoration: none; border-radius: 4px; margin: 20px 0; }}
        .warning {{ background: #fff3e0; border-left: 4px solid #ff9800; padding: 10px 15px; margin: 15px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0;">PVE Commander</h1>
        </div>
        <div class="content">
            <h2>Passwort zuruecksetzen</h2>
            <p>Hallo <strong>{user.username}</strong>,</p>
            <p>Sie haben das Zuruecksetzen Ihres Passworts angefordert.</p>
            <p>Klicken Sie auf den folgenden Button, um ein neues Passwort zu setzen:</p>
            <p style="text-align: center;">
                <a href="{reset_url}" class="button">Passwort zuruecksetzen</a>
            </p>
            <p style="font-size: 12px; color: #666;">
                Oder kopieren Sie diesen Link in Ihren Browser:<br>
                <a href="{reset_url}">{reset_url}</a>
            </p>
            <div class="warning">
                <strong>Wichtig:</strong> Dieser Link ist nur <strong>{expiry_hours} Stunden</strong> gueltig.
            </div>
            <p>Falls Sie diese Anfrage nicht gestellt haben, ignorieren Sie diese E-Mail. Ihr Passwort bleibt unveraendert.</p>
        </div>
        <div class="footer">
            Diese E-Mail wurde automatisch generiert.<br>
            &copy; {datetime.now().year} PVE Commander
        </div>
    </div>
</body>
</html>
"""

        await self.notifications.notify(
            event_type='password_reset',
            subject='Passwort zuruecksetzen - PVE Commander',
            message=plain_message,
            html_message=html_message,
            user_id=user.id
        )

        logger.info(f"Passwort-Reset Token erstellt fuer Benutzer: {user.username}")
        return True

    async def validate_token(self, token: str) -> Optional[dict]:
        """
        Prueft ob ein Token gueltig ist.

        Args:
            token: Der Reset-Token

        Returns:
            Dict mit user_id und expires_at oder None wenn ungueltig
        """
        result = await self.db.execute(
            select(PasswordResetToken).where(
                and_(
                    PasswordResetToken.token == token,
                    PasswordResetToken.used == False,
                    PasswordResetToken.expires_at > datetime.utcnow()
                )
            )
        )
        reset_token = result.scalar_one_or_none()

        if reset_token:
            return {
                'user_id': reset_token.user_id,
                'expires_at': reset_token.expires_at
            }
        return None

    async def reset_password(self, token: str, new_password: str) -> bool:
        """
        Setzt das Passwort zurueck mit einem gueltigen Token.

        Args:
            token: Der Reset-Token
            new_password: Das neue Passwort

        Returns:
            True bei Erfolg, False wenn Token ungueltig
        """
        validation = await self.validate_token(token)
        if not validation:
            logger.warning(f"Ungueltiger oder abgelaufener Reset-Token verwendet")
            return False

        user_id = validation['user_id']

        # Passwort aendern
        hashed = get_password_hash(new_password)
        await self.db.execute(
            update(User).where(User.id == user_id).values(
                password_hash=hashed
            )
        )

        # Token als verwendet markieren
        await self.db.execute(
            update(PasswordResetToken).where(
                PasswordResetToken.token == token
            ).values(used=True)
        )

        await self.db.commit()

        # Benutzer laden fuer Log
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            logger.info(f"Passwort zurueckgesetzt fuer Benutzer: {user.username}")

        return True


def get_password_reset_service(
    db: AsyncSession,
    notification_service: NotificationService
) -> PasswordResetService:
    """Factory-Funktion fuer PasswordResetService"""
    return PasswordResetService(db, notification_service)
