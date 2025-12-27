"""
Notification Service - Zentrale Verwaltung aller Benachrichtigungen

Unterstuetzte Kanaele:
- E-Mail (SMTP)
- Gotify (Push-Benachrichtigungen)
- Webhooks (externe Systeme)
"""
import json
import hmac
import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Dict, Any

import httpx
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_settings import NotificationSettings
from app.models.user_notification_preferences import UserNotificationPreferences
from app.models.webhook import Webhook
from app.models.notification_log import NotificationLog
from app.models.user import User
from app.services.crypto_service import decrypt_value

logger = logging.getLogger(__name__)


# ==================== Abstrakte Basisklasse ====================

class NotificationChannel(ABC):
    """Abstrakte Basisklasse fuer Benachrichtigungskanaele"""

    @abstractmethod
    async def send(self, recipient: str, subject: str, message: str, **kwargs) -> bool:
        """Sendet eine Benachrichtigung"""
        pass

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """Testet die Verbindung"""
        pass


# ==================== E-Mail Kanal (SMTP) ====================

class EmailChannel(NotificationChannel):
    """SMTP E-Mail Kanal"""

    def __init__(self, config: dict):
        self.host = config.get('smtp_host')
        self.port = config.get('smtp_port', 587)
        self.user = config.get('smtp_user')
        self.password = config.get('smtp_password')  # Bereits entschluesselt
        self.from_email = config.get('smtp_from_email')
        self.from_name = config.get('smtp_from_name', 'PVE Commander')
        self.use_tls = config.get('smtp_use_tls', True)
        self.use_ssl = config.get('smtp_use_ssl', False)

    async def send(
        self,
        recipient: str,
        subject: str,
        message: str,
        html_message: Optional[str] = None,
        **kwargs
    ) -> bool:
        """Sendet eine E-Mail"""
        try:
            import aiosmtplib

            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = recipient

            # Text-Version (immer)
            msg.attach(MIMEText(message, 'plain', 'utf-8'))

            # HTML-Version (optional)
            if html_message:
                msg.attach(MIMEText(html_message, 'html', 'utf-8'))

            # SMTP-Verbindung
            if self.use_ssl:
                # SSL von Anfang an (Port 465)
                await aiosmtplib.send(
                    msg,
                    hostname=self.host,
                    port=self.port,
                    username=self.user,
                    password=self.password,
                    use_tls=True,
                )
            else:
                # STARTTLS (Port 587)
                await aiosmtplib.send(
                    msg,
                    hostname=self.host,
                    port=self.port,
                    username=self.user,
                    password=self.password,
                    start_tls=self.use_tls,
                )

            logger.info(f"E-Mail gesendet an {recipient}: {subject}")
            return True

        except ImportError:
            logger.error("aiosmtplib nicht installiert")
            return False
        except Exception as e:
            logger.error(f"E-Mail senden fehlgeschlagen an {recipient}: {e}")
            return False

    async def test_connection(self) -> tuple[bool, str]:
        """Testet die SMTP-Verbindung"""
        try:
            import aiosmtplib

            if self.use_ssl:
                smtp = aiosmtplib.SMTP(
                    hostname=self.host,
                    port=self.port,
                    use_tls=True,
                )
            else:
                smtp = aiosmtplib.SMTP(
                    hostname=self.host,
                    port=self.port,
                    start_tls=self.use_tls,
                )

            async with smtp:
                await smtp.login(self.user, self.password)
                return True, "SMTP-Verbindung erfolgreich"

        except ImportError:
            return False, "aiosmtplib nicht installiert"
        except Exception as e:
            return False, str(e)


# ==================== Gotify Kanal ====================

class GotifyChannel(NotificationChannel):
    """Gotify Push-Benachrichtigungen"""

    def __init__(self, config: dict):
        self.url = (config.get('gotify_url') or '').rstrip('/')
        self.token = config.get('gotify_token')  # Bereits entschluesselt
        self.priority = config.get('gotify_priority', 5)

    async def send(
        self,
        recipient: str,
        subject: str,
        message: str,
        priority: Optional[int] = None,
        **kwargs
    ) -> bool:
        """Sendet eine Gotify-Benachrichtigung"""
        if not self.url or not self.token:
            logger.warning("Gotify nicht konfiguriert")
            return False

        # recipient kann ein user-spezifischer Token sein
        token = recipient if recipient and recipient != 'default' else self.token

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.url}/message",
                    headers={"X-Gotify-Key": token},
                    json={
                        "title": subject,
                        "message": message,
                        "priority": priority or self.priority
                    }
                )

                if response.status_code == 200:
                    logger.info(f"Gotify-Nachricht gesendet: {subject}")
                    return True
                else:
                    logger.error(f"Gotify-Fehler: HTTP {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"Gotify senden fehlgeschlagen: {e}")
            return False

    async def test_connection(self) -> tuple[bool, str]:
        """Testet die Gotify-Verbindung durch Senden einer Test-Nachricht"""
        if not self.url or not self.token:
            return False, "URL oder Token nicht konfiguriert"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # App-Tokens koennen nur Messages senden, nicht /application abfragen
                # Daher testen wir mit einer echten (stillen) Test-Nachricht
                response = await client.post(
                    f"{self.url}/message",
                    headers={"X-Gotify-Key": self.token},
                    json={
                        "title": "Verbindungstest",
                        "message": "Gotify-Verbindung erfolgreich getestet.",
                        "priority": 1  # Niedrige Prioritaet fuer Test
                    }
                )

                if response.status_code == 200:
                    return True, "Gotify-Verbindung erfolgreich (Test-Nachricht gesendet)"
                elif response.status_code == 401:
                    return False, "Authentifizierung fehlgeschlagen (ungueltiger Token)"
                elif response.status_code == 403:
                    return False, "Keine Berechtigung (Token hat keine Schreibrechte)"
                else:
                    return False, f"HTTP {response.status_code}"

        except httpx.ConnectError:
            return False, f"Verbindung zu {self.url} fehlgeschlagen"
        except Exception as e:
            return False, str(e)


# ==================== Webhook Kanal ====================

class WebhookChannel(NotificationChannel):
    """Webhook-Benachrichtigungen"""

    def __init__(self, webhook_config: dict):
        self.url = webhook_config.get('url')
        self.secret = webhook_config.get('secret')  # Bereits entschluesselt
        self.name = webhook_config.get('name')
        self.webhook_id = webhook_config.get('id')

    async def send(
        self,
        recipient: str,
        subject: str,
        message: str,
        event_type: str = None,
        payload: dict = None,
        **kwargs
    ) -> bool:
        """Sendet eine Webhook-Benachrichtigung"""
        data = {
            "event": event_type,
            "title": subject,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "source": "pve-commander",
            **(payload or {})
        }

        headers = {"Content-Type": "application/json"}
        body = json.dumps(data)

        # HMAC-Signatur hinzufuegen wenn Secret konfiguriert
        if self.secret:
            signature = hmac.new(
                self.secret.encode(),
                body.encode(),
                hashlib.sha256
            ).hexdigest()
            headers["X-Signature-256"] = f"sha256={signature}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.url,
                    content=body,
                    headers=headers
                )

                success = response.status_code < 400
                if success:
                    logger.info(f"Webhook '{self.name}' erfolgreich: {event_type}")
                else:
                    logger.warning(f"Webhook '{self.name}' fehlgeschlagen: HTTP {response.status_code}")

                return success

        except Exception as e:
            logger.error(f"Webhook '{self.name}' Fehler: {e}")
            return False

    async def test_connection(self) -> tuple[bool, str]:
        """Testet den Webhook mit einem Test-Payload"""
        data = {
            "event": "test",
            "title": "PVE Commander Webhook Test",
            "message": "Dies ist ein Test der Webhook-Verbindung.",
            "timestamp": datetime.utcnow().isoformat(),
            "source": "pve-commander",
            "test": True
        }

        headers = {"Content-Type": "application/json"}
        body = json.dumps(data)

        if self.secret:
            signature = hmac.new(
                self.secret.encode(),
                body.encode(),
                hashlib.sha256
            ).hexdigest()
            headers["X-Signature-256"] = f"sha256={signature}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.url,
                    content=body,
                    headers=headers
                )

                if response.status_code < 400:
                    return True, f"Webhook erfolgreich (HTTP {response.status_code})"
                else:
                    return False, f"HTTP {response.status_code}: {response.text[:100]}"

        except httpx.ConnectError:
            return False, f"Verbindung zu {self.url} fehlgeschlagen"
        except Exception as e:
            return False, str(e)


# ==================== Notification Service ====================

class NotificationService:
    """
    Zentrale Verwaltung aller Benachrichtigungen.

    Koordiniert das Senden von Benachrichtigungen ueber verschiedene Kanaele
    basierend auf globalen Einstellungen und Benutzer-Praeferenzen.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._settings_cache: Optional[dict] = None
        self._settings_cache_time: Optional[datetime] = None

    async def get_settings(self, force_refresh: bool = False) -> dict:
        """
        Laedt globale Benachrichtigungseinstellungen (mit Cache).

        Returns:
            Dict mit Einstellungen
        """
        # Cache fuer 60 Sekunden
        if (
            not force_refresh
            and self._settings_cache
            and self._settings_cache_time
            and (datetime.utcnow() - self._settings_cache_time).seconds < 60
        ):
            return self._settings_cache

        result = await self.db.execute(
            select(NotificationSettings).limit(1)
        )
        settings = result.scalar_one_or_none()

        if settings:
            self._settings_cache = {
                'smtp_enabled': settings.smtp_enabled,
                'smtp_host': settings.smtp_host,
                'smtp_port': settings.smtp_port,
                'smtp_user': settings.smtp_user,
                'smtp_password': decrypt_value(settings.smtp_password_encrypted) if settings.smtp_password_encrypted else None,
                'smtp_from_email': settings.smtp_from_email,
                'smtp_from_name': settings.smtp_from_name,
                'smtp_use_tls': settings.smtp_use_tls,
                'smtp_use_ssl': settings.smtp_use_ssl,
                'gotify_enabled': settings.gotify_enabled,
                'gotify_url': settings.gotify_url,
                'gotify_token': decrypt_value(settings.gotify_token_encrypted) if settings.gotify_token_encrypted else None,
                'gotify_priority': settings.gotify_priority,
                'app_url': settings.app_url,
                'password_reset_expiry_hours': settings.password_reset_expiry_hours,
            }
        else:
            self._settings_cache = {}

        self._settings_cache_time = datetime.utcnow()
        return self._settings_cache

    async def _get_user_preferences(self, user_id: int) -> Optional[UserNotificationPreferences]:
        """Laedt Benutzer-Praeferenzen"""
        result = await self.db.execute(
            select(UserNotificationPreferences).where(
                UserNotificationPreferences.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def _get_subscribed_users(
        self,
        event_type: str,
        specific_user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Findet alle Benutzer, die fuer einen bestimmten Event-Typ benachrichtigt werden sollen.

        Args:
            event_type: z.B. 'vm_created', 'ansible_failed'
            specific_user_id: Nur diesen Benutzer beruecksichtigen

        Returns:
            Liste von Dicts mit Benutzer-Info und Praeferenzen
        """
        # Event-Typ zu Praeferenz-Feld mappen
        pref_field_map = {
            'vm_created': 'notify_vm_created',
            'vm_deleted': 'notify_vm_deleted',
            'vm_state_change': 'notify_vm_state_change',
            'ansible_completed': 'notify_ansible_completed',
            'ansible_failed': 'notify_ansible_failed',
            'system_alert': 'notify_system_alerts',
            'password_reset': None,  # Immer senden
        }

        pref_field = pref_field_map.get(event_type)

        # Benutzer mit Praeferenzen laden
        query = select(User, UserNotificationPreferences).outerjoin(
            UserNotificationPreferences,
            User.id == UserNotificationPreferences.user_id
        ).where(User.is_active == True)

        if specific_user_id:
            query = query.where(User.id == specific_user_id)

        result = await self.db.execute(query)
        rows = result.all()

        subscribed = []
        for user, prefs in rows:
            # Wenn keine Praeferenzen existieren, Defaults verwenden
            if prefs is None:
                # Fuer password_reset oder system_alert immer inkludieren
                if event_type in ('password_reset', 'system_alert'):
                    subscribed.append({
                        'user': user,
                        'email_enabled': True,
                        'gotify_enabled': False,
                        'gotify_token': None,
                    })
                continue

            # Praeferenz pruefen
            if pref_field and not getattr(prefs, pref_field, False):
                continue

            subscribed.append({
                'user': user,
                'email_enabled': prefs.email_enabled,
                'gotify_enabled': prefs.gotify_enabled,
                'gotify_token': decrypt_value(prefs.gotify_user_token_encrypted) if prefs.gotify_user_token_encrypted else None,
            })

        return subscribed

    async def _get_webhooks_for_event(self, event_type: str) -> List[dict]:
        """Findet alle aktiven Webhooks fuer einen Event-Typ"""
        # Event-Typ zu Webhook-Feld mappen
        field_map = {
            'vm_created': Webhook.on_vm_created,
            'vm_deleted': Webhook.on_vm_deleted,
            'vm_state_change': Webhook.on_vm_state_change,
            'ansible_completed': Webhook.on_ansible_completed,
            'ansible_failed': Webhook.on_ansible_failed,
            'system_alert': Webhook.on_system_alert,
        }

        field = field_map.get(event_type)
        if not field:
            return []

        result = await self.db.execute(
            select(Webhook).where(
                and_(
                    Webhook.enabled == True,
                    field == True
                )
            )
        )
        webhooks = result.scalars().all()

        return [
            {
                'id': w.id,
                'name': w.name,
                'url': w.url,
                'secret': decrypt_value(w.secret_encrypted) if w.secret_encrypted else None,
            }
            for w in webhooks
        ]

    async def _log_notification(
        self,
        channel: str,
        recipient: str,
        subject: str,
        event_type: str,
        status: str,
        error_message: Optional[str] = None
    ):
        """Protokolliert eine Benachrichtigung"""
        log_entry = NotificationLog(
            channel=channel,
            recipient=recipient,
            subject=subject,
            event_type=event_type,
            status=status,
            error_message=error_message
        )
        self.db.add(log_entry)
        await self.db.commit()

    async def notify(
        self,
        event_type: str,
        subject: str,
        message: str,
        html_message: Optional[str] = None,
        user_id: Optional[int] = None,
        payload: Optional[dict] = None
    ) -> Dict[str, Any]:
        """
        Sendet Benachrichtigungen an alle konfigurierten Kanaele.

        Args:
            event_type: z.B. 'vm_created', 'ansible_failed'
            subject: Betreff/Titel
            message: Nachrichtentext (Plain Text)
            html_message: Optionaler HTML-Nachrichtentext
            user_id: Nur diesen Benutzer benachrichtigen (sonst alle)
            payload: Zusaetzliche Daten fuer Webhooks

        Returns:
            Dict mit Statistiken (sent, failed, etc.)
        """
        settings = await self.get_settings()
        stats = {
            'email_sent': 0,
            'email_failed': 0,
            'gotify_sent': 0,
            'gotify_failed': 0,
            'webhook_sent': 0,
            'webhook_failed': 0,
        }

        # Benutzer mit aktivierten Benachrichtigungen fuer diesen Event-Typ
        users = await self._get_subscribed_users(event_type, user_id)

        # E-Mail senden
        if settings.get('smtp_enabled'):
            email_channel = EmailChannel(settings)
            for user_info in users:
                user = user_info['user']
                if user.email and user_info['email_enabled']:
                    success = await email_channel.send(
                        recipient=user.email,
                        subject=subject,
                        message=message,
                        html_message=html_message
                    )
                    if success:
                        stats['email_sent'] += 1
                    else:
                        stats['email_failed'] += 1

                    await self._log_notification(
                        channel='email',
                        recipient=user.email,
                        subject=subject,
                        event_type=event_type,
                        status='sent' if success else 'failed'
                    )

        # Gotify senden
        if settings.get('gotify_enabled'):
            gotify_channel = GotifyChannel(settings)
            for user_info in users:
                user = user_info['user']
                if user_info['gotify_enabled']:
                    token = user_info['gotify_token'] or 'default'
                    success = await gotify_channel.send(
                        recipient=token,
                        subject=subject,
                        message=message,
                        priority=self._get_priority_for_event(event_type)
                    )
                    if success:
                        stats['gotify_sent'] += 1
                    else:
                        stats['gotify_failed'] += 1

                    await self._log_notification(
                        channel='gotify',
                        recipient=user.username,
                        subject=subject,
                        event_type=event_type,
                        status='sent' if success else 'failed'
                    )

        # Webhooks triggern
        webhooks = await self._get_webhooks_for_event(event_type)
        for webhook in webhooks:
            channel = WebhookChannel(webhook)
            success = await channel.send(
                recipient=webhook['url'],
                subject=subject,
                message=message,
                event_type=event_type,
                payload=payload
            )

            # Webhook-Status aktualisieren
            await self.db.execute(
                Webhook.__table__.update().where(Webhook.id == webhook['id']).values(
                    last_triggered_at=datetime.utcnow(),
                    last_status='success' if success else 'failed',
                    failure_count=0 if success else Webhook.failure_count + 1
                )
            )
            await self.db.commit()

            if success:
                stats['webhook_sent'] += 1
            else:
                stats['webhook_failed'] += 1

            await self._log_notification(
                channel='webhook',
                recipient=webhook['name'],
                subject=subject,
                event_type=event_type,
                status='sent' if success else 'failed'
            )

        logger.info(f"Benachrichtigung '{event_type}': {stats}")
        return stats

    def _get_priority_for_event(self, event_type: str) -> int:
        """Bestimmt die Gotify-Prioritaet basierend auf Event-Typ"""
        priority_map = {
            'ansible_failed': 8,
            'system_alert': 9,
            'vm_deleted': 6,
            'vm_created': 5,
            'ansible_completed': 4,
            'vm_state_change': 3,
        }
        return priority_map.get(event_type, 5)


# ==================== Factory Function ====================

def get_notification_service(db: AsyncSession) -> NotificationService:
    """Factory-Funktion fuer NotificationService"""
    return NotificationService(db)
