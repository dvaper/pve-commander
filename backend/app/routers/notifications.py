"""
Notifications Router - API-Endpunkte fuer Benachrichtigungen
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user, get_current_super_admin
from app.models.user import User
from app.models.notification_settings import NotificationSettings
from app.models.user_notification_preferences import UserNotificationPreferences
from app.models.webhook import Webhook
from app.models.notification_log import NotificationLog
from app.schemas.notification import (
    NotificationSettingsResponse,
    NotificationSettingsUpdate,
    ConnectionTestResponse,
    UserNotificationPreferencesResponse,
    UserNotificationPreferencesUpdate,
    WebhookCreate,
    WebhookUpdate,
    WebhookResponse,
    WebhookTestResponse,
    NotificationLogEntry,
    NotificationLogResponse,
)
from app.services.notification_service import (
    NotificationService,
    EmailChannel,
    GotifyChannel,
    WebhookChannel,
)
from app.services.crypto_service import encrypt_value, decrypt_value

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


# ==================== Globale Einstellungen (Admin) ====================

@router.get("/settings", response_model=NotificationSettingsResponse)
async def get_notification_settings(
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Globale Benachrichtigungseinstellungen abrufen"""
    result = await db.execute(select(NotificationSettings).limit(1))
    settings = result.scalar_one_or_none()

    if not settings:
        # Erstelle Default-Einstellungen
        settings = NotificationSettings()
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

    return NotificationSettingsResponse(
        id=settings.id,
        smtp_enabled=settings.smtp_enabled,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_user=settings.smtp_user,
        smtp_from_email=settings.smtp_from_email,
        smtp_from_name=settings.smtp_from_name,
        smtp_use_tls=settings.smtp_use_tls,
        smtp_use_ssl=settings.smtp_use_ssl,
        smtp_password_set=bool(settings.smtp_password_encrypted),
        gotify_enabled=settings.gotify_enabled,
        gotify_url=settings.gotify_url,
        gotify_priority=settings.gotify_priority,
        gotify_token_set=bool(settings.gotify_token_encrypted),
        app_url=settings.app_url,
        password_reset_expiry_hours=settings.password_reset_expiry_hours,
        updated_at=settings.updated_at,
    )


@router.put("/settings", response_model=NotificationSettingsResponse)
async def update_notification_settings(
    data: NotificationSettingsUpdate,
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Globale Einstellungen aktualisieren"""
    result = await db.execute(select(NotificationSettings).limit(1))
    settings = result.scalar_one_or_none()

    if not settings:
        settings = NotificationSettings()
        db.add(settings)

    # Felder aktualisieren (nur wenn gesetzt)
    update_fields = data.model_dump(exclude_unset=True)

    # Passwort verschluesseln
    if 'smtp_password' in update_fields:
        password = update_fields.pop('smtp_password')
        if password:  # Nur setzen wenn nicht leer
            settings.smtp_password_encrypted = encrypt_value(password)

    # Gotify Token verschluesseln
    if 'gotify_token' in update_fields:
        token = update_fields.pop('gotify_token')
        if token:  # Nur setzen wenn nicht leer
            settings.gotify_token_encrypted = encrypt_value(token)

    # Restliche Felder
    for field, value in update_fields.items():
        if hasattr(settings, field):
            setattr(settings, field, value)

    await db.commit()
    await db.refresh(settings)

    logger.info(f"Benachrichtigungseinstellungen aktualisiert von {current_user.username}")

    return NotificationSettingsResponse(
        id=settings.id,
        smtp_enabled=settings.smtp_enabled,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_user=settings.smtp_user,
        smtp_from_email=settings.smtp_from_email,
        smtp_from_name=settings.smtp_from_name,
        smtp_use_tls=settings.smtp_use_tls,
        smtp_use_ssl=settings.smtp_use_ssl,
        smtp_password_set=bool(settings.smtp_password_encrypted),
        gotify_enabled=settings.gotify_enabled,
        gotify_url=settings.gotify_url,
        gotify_priority=settings.gotify_priority,
        gotify_token_set=bool(settings.gotify_token_encrypted),
        app_url=settings.app_url,
        password_reset_expiry_hours=settings.password_reset_expiry_hours,
        updated_at=settings.updated_at,
    )


@router.post("/settings/test-smtp", response_model=ConnectionTestResponse)
async def test_smtp_connection(
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """SMTP-Verbindung testen (nur Login-Test, keine Mail)"""
    result = await db.execute(select(NotificationSettings).limit(1))
    settings = result.scalar_one_or_none()

    if not settings or not settings.smtp_host:
        raise HTTPException(400, "SMTP nicht konfiguriert")

    config = {
        'smtp_host': settings.smtp_host,
        'smtp_port': settings.smtp_port,
        'smtp_user': settings.smtp_user,
        'smtp_password': decrypt_value(settings.smtp_password_encrypted) if settings.smtp_password_encrypted else None,
        'smtp_use_tls': settings.smtp_use_tls,
        'smtp_use_ssl': settings.smtp_use_ssl,
    }

    channel = EmailChannel(config)
    success, message = await channel.test_connection()

    return ConnectionTestResponse(success=success, message=message)


@router.post("/settings/send-test-email", response_model=ConnectionTestResponse)
async def send_test_email(
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Test-E-Mail an den aktuellen Benutzer senden"""
    if not current_user.email:
        raise HTTPException(400, "Keine E-Mail-Adresse fuer Ihren Account hinterlegt")

    result = await db.execute(select(NotificationSettings).limit(1))
    settings = result.scalar_one_or_none()

    if not settings or not settings.smtp_host:
        raise HTTPException(400, "SMTP nicht konfiguriert")

    if not settings.smtp_from_email:
        raise HTTPException(400, "Absender-Adresse (From) nicht konfiguriert")

    config = {
        'smtp_host': settings.smtp_host,
        'smtp_port': settings.smtp_port,
        'smtp_user': settings.smtp_user,
        'smtp_password': decrypt_value(settings.smtp_password_encrypted) if settings.smtp_password_encrypted else None,
        'smtp_from_email': settings.smtp_from_email,
        'smtp_from_name': settings.smtp_from_name or 'PVE Commander',
        'smtp_use_tls': settings.smtp_use_tls,
        'smtp_use_ssl': settings.smtp_use_ssl,
    }

    channel = EmailChannel(config)

    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    subject = "PVE Commander - Test-E-Mail"
    message = f"""Hallo {current_user.username},

dies ist eine Test-E-Mail von PVE Commander.

Wenn Sie diese E-Mail erhalten, funktioniert die SMTP-Konfiguration korrekt.

Zeitstempel: {timestamp}
Empfaenger: {current_user.email}
Server: {settings.smtp_host}:{settings.smtp_port}

Mit freundlichen Gruessen,
PVE Commander
"""

    html_message = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <h2 style="color: #1976D2;">PVE Commander - Test-E-Mail</h2>
    <p>Hallo <strong>{current_user.username}</strong>,</p>
    <p>dies ist eine Test-E-Mail von PVE Commander.</p>
    <p style="background: #e8f5e9; padding: 10px; border-left: 4px solid #4CAF50;">
        Wenn Sie diese E-Mail erhalten, funktioniert die SMTP-Konfiguration korrekt.
    </p>
    <table style="margin-top: 20px; border-collapse: collapse;">
        <tr><td style="padding: 5px 15px 5px 0; color: #666;">Zeitstempel:</td><td>{timestamp}</td></tr>
        <tr><td style="padding: 5px 15px 5px 0; color: #666;">Empfaenger:</td><td>{current_user.email}</td></tr>
        <tr><td style="padding: 5px 15px 5px 0; color: #666;">Server:</td><td>{settings.smtp_host}:{settings.smtp_port}</td></tr>
    </table>
    <p style="margin-top: 30px; color: #666; font-size: 0.9em;">
        Mit freundlichen Gruessen,<br/>
        <strong>PVE Commander</strong>
    </p>
</body>
</html>
"""

    try:
        success = await channel.send(
            recipient=current_user.email,
            subject=subject,
            message=message,
            html_message=html_message
        )

        if success:
            logger.info(f"Test-E-Mail gesendet an {current_user.email}")
            return ConnectionTestResponse(
                success=True,
                message=f"Test-E-Mail erfolgreich an {current_user.email} gesendet"
            )
        else:
            return ConnectionTestResponse(
                success=False,
                message="E-Mail-Versand fehlgeschlagen (siehe Server-Logs)"
            )

    except Exception as e:
        logger.error(f"Test-E-Mail fehlgeschlagen: {e}")
        return ConnectionTestResponse(success=False, message=str(e))


@router.post("/settings/test-gotify", response_model=ConnectionTestResponse)
async def test_gotify_connection(
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Gotify-Verbindung testen"""
    result = await db.execute(select(NotificationSettings).limit(1))
    settings = result.scalar_one_or_none()

    if not settings or not settings.gotify_url:
        raise HTTPException(400, "Gotify-URL nicht konfiguriert")

    if not settings.gotify_token_encrypted:
        raise HTTPException(400, "Gotify-Token nicht gespeichert. Bitte zuerst Token eingeben und speichern.")

    config = {
        'gotify_url': settings.gotify_url,
        'gotify_token': decrypt_value(settings.gotify_token_encrypted),
    }

    channel = GotifyChannel(config)
    success, message = await channel.test_connection()

    return ConnectionTestResponse(success=success, message=message)


@router.post("/settings/send-test-gotify", response_model=ConnectionTestResponse)
async def send_test_gotify_notification(
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Test-Benachrichtigung an Gotify senden"""
    result = await db.execute(select(NotificationSettings).limit(1))
    settings = result.scalar_one_or_none()

    if not settings or not settings.gotify_url:
        raise HTTPException(400, "Gotify-URL nicht konfiguriert")

    if not settings.gotify_token_encrypted:
        raise HTTPException(400, "Gotify-Token nicht gespeichert. Bitte zuerst Token eingeben und speichern.")

    config = {
        'gotify_url': settings.gotify_url,
        'gotify_token': decrypt_value(settings.gotify_token_encrypted),
        'gotify_priority': settings.gotify_priority or 5,
    }

    channel = GotifyChannel(config)

    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        success = await channel.send(
            recipient='default',
            subject="PVE Commander - Test",
            message=f"Dies ist eine Test-Benachrichtigung.\n\nZeitstempel: {timestamp}\nBenutzer: {current_user.username}",
            priority=settings.gotify_priority or 5
        )

        if success:
            logger.info(f"Gotify Test-Nachricht gesendet von {current_user.username}")
            return ConnectionTestResponse(
                success=True,
                message="Test-Benachrichtigung erfolgreich an Gotify gesendet"
            )
        else:
            return ConnectionTestResponse(
                success=False,
                message="Senden fehlgeschlagen (siehe Server-Logs)"
            )

    except Exception as e:
        logger.error(f"Gotify Test-Nachricht fehlgeschlagen: {e}")
        return ConnectionTestResponse(success=False, message=str(e))


# ==================== Webhooks (Admin) ====================

@router.get("/webhooks", response_model=list[WebhookResponse])
async def list_webhooks(
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Alle Webhooks auflisten"""
    result = await db.execute(select(Webhook).order_by(Webhook.created_at.desc()))
    webhooks = result.scalars().all()

    return [
        WebhookResponse(
            id=w.id,
            name=w.name,
            url=w.url,
            enabled=w.enabled,
            secret_set=bool(w.secret_encrypted),
            on_vm_created=w.on_vm_created,
            on_vm_deleted=w.on_vm_deleted,
            on_vm_state_change=w.on_vm_state_change,
            on_ansible_completed=w.on_ansible_completed,
            on_ansible_failed=w.on_ansible_failed,
            on_system_alert=w.on_system_alert,
            last_triggered_at=w.last_triggered_at,
            last_status=w.last_status,
            failure_count=w.failure_count,
            created_at=w.created_at,
            updated_at=w.updated_at,
        )
        for w in webhooks
    ]


@router.post("/webhooks", response_model=WebhookResponse)
async def create_webhook(
    data: WebhookCreate,
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Neuen Webhook erstellen"""
    webhook = Webhook(
        name=data.name,
        url=data.url,
        enabled=data.enabled,
        secret_encrypted=encrypt_value(data.secret) if data.secret else None,
        on_vm_created=data.on_vm_created,
        on_vm_deleted=data.on_vm_deleted,
        on_vm_state_change=data.on_vm_state_change,
        on_ansible_completed=data.on_ansible_completed,
        on_ansible_failed=data.on_ansible_failed,
        on_system_alert=data.on_system_alert,
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)

    logger.info(f"Webhook '{data.name}' erstellt von {current_user.username}")

    return WebhookResponse(
        id=webhook.id,
        name=webhook.name,
        url=webhook.url,
        enabled=webhook.enabled,
        secret_set=bool(webhook.secret_encrypted),
        on_vm_created=webhook.on_vm_created,
        on_vm_deleted=webhook.on_vm_deleted,
        on_vm_state_change=webhook.on_vm_state_change,
        on_ansible_completed=webhook.on_ansible_completed,
        on_ansible_failed=webhook.on_ansible_failed,
        on_system_alert=webhook.on_system_alert,
        last_triggered_at=webhook.last_triggered_at,
        last_status=webhook.last_status,
        failure_count=webhook.failure_count,
        created_at=webhook.created_at,
        updated_at=webhook.updated_at,
    )


@router.put("/webhooks/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: int,
    data: WebhookUpdate,
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Webhook aktualisieren"""
    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(404, "Webhook nicht gefunden")

    update_fields = data.model_dump(exclude_unset=True)

    # Secret verschluesseln
    if 'secret' in update_fields:
        secret = update_fields.pop('secret')
        if secret:
            webhook.secret_encrypted = encrypt_value(secret)

    for field, value in update_fields.items():
        if hasattr(webhook, field):
            setattr(webhook, field, value)

    await db.commit()
    await db.refresh(webhook)

    logger.info(f"Webhook '{webhook.name}' aktualisiert von {current_user.username}")

    return WebhookResponse(
        id=webhook.id,
        name=webhook.name,
        url=webhook.url,
        enabled=webhook.enabled,
        secret_set=bool(webhook.secret_encrypted),
        on_vm_created=webhook.on_vm_created,
        on_vm_deleted=webhook.on_vm_deleted,
        on_vm_state_change=webhook.on_vm_state_change,
        on_ansible_completed=webhook.on_ansible_completed,
        on_ansible_failed=webhook.on_ansible_failed,
        on_system_alert=webhook.on_system_alert,
        last_triggered_at=webhook.last_triggered_at,
        last_status=webhook.last_status,
        failure_count=webhook.failure_count,
        created_at=webhook.created_at,
        updated_at=webhook.updated_at,
    )


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(
    webhook_id: int,
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Webhook loeschen"""
    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(404, "Webhook nicht gefunden")

    webhook_name = webhook.name
    await db.execute(delete(Webhook).where(Webhook.id == webhook_id))
    await db.commit()

    logger.info(f"Webhook '{webhook_name}' geloescht von {current_user.username}")

    return {"message": f"Webhook '{webhook_name}' geloescht"}


@router.post("/webhooks/{webhook_id}/test", response_model=WebhookTestResponse)
async def test_webhook(
    webhook_id: int,
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Webhook mit Test-Payload ausloesen"""
    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(404, "Webhook nicht gefunden")

    config = {
        'id': webhook.id,
        'name': webhook.name,
        'url': webhook.url,
        'secret': decrypt_value(webhook.secret_encrypted) if webhook.secret_encrypted else None,
    }

    channel = WebhookChannel(config)
    success, message = await channel.test_connection()

    return WebhookTestResponse(
        success=success,
        status_code=200 if success else None,
        message=message
    )


# ==================== Benutzer-Praeferenzen ====================

@router.get("/preferences", response_model=UserNotificationPreferencesResponse)
async def get_my_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Eigene Benachrichtigungspraeferenzen abrufen"""
    result = await db.execute(
        select(UserNotificationPreferences).where(
            UserNotificationPreferences.user_id == current_user.id
        )
    )
    prefs = result.scalar_one_or_none()

    if not prefs:
        # Erstelle Default-Praeferenzen
        prefs = UserNotificationPreferences(user_id=current_user.id)
        db.add(prefs)
        await db.commit()
        await db.refresh(prefs)

    return UserNotificationPreferencesResponse(
        id=prefs.id,
        user_id=prefs.user_id,
        email_enabled=prefs.email_enabled,
        gotify_enabled=prefs.gotify_enabled,
        gotify_user_token_set=bool(prefs.gotify_user_token_encrypted),
        notify_vm_created=prefs.notify_vm_created,
        notify_vm_deleted=prefs.notify_vm_deleted,
        notify_vm_state_change=prefs.notify_vm_state_change,
        notify_ansible_completed=prefs.notify_ansible_completed,
        notify_ansible_failed=prefs.notify_ansible_failed,
        notify_system_alerts=prefs.notify_system_alerts,
        updated_at=prefs.updated_at,
    )


@router.put("/preferences", response_model=UserNotificationPreferencesResponse)
async def update_my_preferences(
    data: UserNotificationPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Eigene Praeferenzen aktualisieren"""
    result = await db.execute(
        select(UserNotificationPreferences).where(
            UserNotificationPreferences.user_id == current_user.id
        )
    )
    prefs = result.scalar_one_or_none()

    if not prefs:
        prefs = UserNotificationPreferences(user_id=current_user.id)
        db.add(prefs)

    update_fields = data.model_dump(exclude_unset=True)

    # Gotify Token verschluesseln
    if 'gotify_user_token' in update_fields:
        token = update_fields.pop('gotify_user_token')
        if token:
            prefs.gotify_user_token_encrypted = encrypt_value(token)

    for field, value in update_fields.items():
        if hasattr(prefs, field):
            setattr(prefs, field, value)

    await db.commit()
    await db.refresh(prefs)

    logger.info(f"Benachrichtigungspraeferenzen aktualisiert fuer {current_user.username}")

    return UserNotificationPreferencesResponse(
        id=prefs.id,
        user_id=prefs.user_id,
        email_enabled=prefs.email_enabled,
        gotify_enabled=prefs.gotify_enabled,
        gotify_user_token_set=bool(prefs.gotify_user_token_encrypted),
        notify_vm_created=prefs.notify_vm_created,
        notify_vm_deleted=prefs.notify_vm_deleted,
        notify_vm_state_change=prefs.notify_vm_state_change,
        notify_ansible_completed=prefs.notify_ansible_completed,
        notify_ansible_failed=prefs.notify_ansible_failed,
        notify_system_alerts=prefs.notify_system_alerts,
        updated_at=prefs.updated_at,
    )


# ==================== Benachrichtigungs-Log (Admin) ====================

@router.get("/log", response_model=NotificationLogResponse)
async def get_notification_log(
    channel: Optional[str] = Query(None, description="Filter nach Kanal (email, gotify, webhook)"),
    status: Optional[str] = Query(None, description="Filter nach Status (sent, failed)"),
    event_type: Optional[str] = Query(None, description="Filter nach Event-Typ"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Benachrichtigungs-Log abrufen"""
    query = select(NotificationLog)

    if channel:
        query = query.where(NotificationLog.channel == channel)
    if status:
        query = query.where(NotificationLog.status == status)
    if event_type:
        query = query.where(NotificationLog.event_type == event_type)

    # Total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Pagination
    query = query.order_by(NotificationLog.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    logs = result.scalars().all()

    return NotificationLogResponse(
        items=[
            NotificationLogEntry(
                id=log.id,
                channel=log.channel,
                recipient=log.recipient,
                subject=log.subject,
                event_type=log.event_type,
                status=log.status,
                error_message=log.error_message,
                created_at=log.created_at,
            )
            for log in logs
        ],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.delete("/log")
async def clear_notification_log(
    older_than_days: int = Query(30, ge=1, description="Loesche Eintraege aelter als X Tage"),
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Alte Log-Eintraege loeschen"""
    from datetime import datetime, timedelta

    cutoff = datetime.utcnow() - timedelta(days=older_than_days)

    result = await db.execute(
        delete(NotificationLog).where(NotificationLog.created_at < cutoff)
    )
    await db.commit()

    deleted = result.rowcount
    logger.info(f"{deleted} Log-Eintraege geloescht (aelter als {older_than_days} Tage)")

    return {"message": f"{deleted} Eintraege geloescht"}
