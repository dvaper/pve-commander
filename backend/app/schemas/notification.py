"""
Schemas fuer Benachrichtigungs-Feature
"""
from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, EmailStr, HttpUrl, Field


# ==================== Notification Settings (Global) ====================

class NotificationSettingsBase(BaseModel):
    """Basis-Schema fuer globale Benachrichtigungseinstellungen"""
    # SMTP
    smtp_enabled: bool = False
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_from_email: Optional[str] = None
    smtp_from_name: str = "PVE Commander"
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False

    # Gotify
    gotify_enabled: bool = False
    gotify_url: Optional[str] = None
    gotify_priority: int = Field(default=5, ge=1, le=10)

    # App
    app_url: str = "http://localhost:8080"
    password_reset_expiry_hours: int = Field(default=24, ge=1, le=168)


class NotificationSettingsUpdate(BaseModel):
    """Schema fuer Aktualisierung der Einstellungen"""
    # SMTP
    smtp_enabled: Optional[bool] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None  # Klartext, wird verschluesselt gespeichert
    smtp_from_email: Optional[str] = None
    smtp_from_name: Optional[str] = None
    smtp_use_tls: Optional[bool] = None
    smtp_use_ssl: Optional[bool] = None

    # Gotify
    gotify_enabled: Optional[bool] = None
    gotify_url: Optional[str] = None
    gotify_token: Optional[str] = None  # Klartext, wird verschluesselt gespeichert
    gotify_priority: Optional[int] = Field(default=None, ge=1, le=10)

    # App
    app_url: Optional[str] = None
    password_reset_expiry_hours: Optional[int] = Field(default=None, ge=1, le=168)


class NotificationSettingsResponse(NotificationSettingsBase):
    """Response-Schema (ohne sensible Daten)"""
    id: int
    smtp_password_set: bool = False  # Zeigt an, ob Passwort gesetzt ist
    gotify_token_set: bool = False  # Zeigt an, ob Token gesetzt ist
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ConnectionTestResponse(BaseModel):
    """Response fuer Verbindungstests"""
    success: bool
    message: str


# ==================== User Notification Preferences ====================

class UserNotificationPreferencesBase(BaseModel):
    """Basis-Schema fuer Benutzer-Benachrichtigungspraeferenzen"""
    # Kanaele
    email_enabled: bool = True
    gotify_enabled: bool = False

    # Ereignisse - VM
    notify_vm_created: bool = True
    notify_vm_deleted: bool = True
    notify_vm_state_change: bool = False

    # Ereignisse - Ansible
    notify_ansible_completed: bool = True
    notify_ansible_failed: bool = True

    # Ereignisse - System
    notify_system_alerts: bool = True


class UserNotificationPreferencesUpdate(BaseModel):
    """Schema fuer Aktualisierung der Benutzer-Praeferenzen"""
    email_enabled: Optional[bool] = None
    gotify_enabled: Optional[bool] = None
    gotify_user_token: Optional[str] = None  # Klartext, wird verschluesselt

    notify_vm_created: Optional[bool] = None
    notify_vm_deleted: Optional[bool] = None
    notify_vm_state_change: Optional[bool] = None
    notify_ansible_completed: Optional[bool] = None
    notify_ansible_failed: Optional[bool] = None
    notify_system_alerts: Optional[bool] = None


class UserNotificationPreferencesResponse(UserNotificationPreferencesBase):
    """Response-Schema"""
    id: int
    user_id: int
    gotify_user_token_set: bool = False
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== Webhooks ====================

EventType = Literal[
    "vm_created",
    "vm_deleted",
    "vm_state_change",
    "ansible_completed",
    "ansible_failed",
    "system_alert"
]


class WebhookBase(BaseModel):
    """Basis-Schema fuer Webhooks"""
    name: str = Field(..., min_length=1, max_length=100)
    url: str = Field(..., min_length=1, max_length=500)
    enabled: bool = True

    # Ereignisse
    on_vm_created: bool = False
    on_vm_deleted: bool = False
    on_vm_state_change: bool = False
    on_ansible_completed: bool = False
    on_ansible_failed: bool = False
    on_system_alert: bool = False


class WebhookCreate(WebhookBase):
    """Schema fuer Webhook-Erstellung"""
    secret: Optional[str] = None  # Fuer HMAC-Signatur


class WebhookUpdate(BaseModel):
    """Schema fuer Webhook-Aktualisierung"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    url: Optional[str] = Field(default=None, min_length=1, max_length=500)
    secret: Optional[str] = None
    enabled: Optional[bool] = None

    on_vm_created: Optional[bool] = None
    on_vm_deleted: Optional[bool] = None
    on_vm_state_change: Optional[bool] = None
    on_ansible_completed: Optional[bool] = None
    on_ansible_failed: Optional[bool] = None
    on_system_alert: Optional[bool] = None


class WebhookResponse(WebhookBase):
    """Response-Schema"""
    id: int
    secret_set: bool = False
    last_triggered_at: Optional[datetime] = None
    last_status: Optional[str] = None
    failure_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WebhookTestResponse(BaseModel):
    """Response fuer Webhook-Test"""
    success: bool
    status_code: Optional[int] = None
    message: str


# ==================== Password Reset ====================

class PasswordResetRequest(BaseModel):
    """Anfrage fuer Passwort-Reset"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Bestaetigung des Passwort-Resets"""
    token: str
    new_password: str = Field(..., min_length=8)


class PasswordResetValidate(BaseModel):
    """Token-Validierung"""
    valid: bool
    expires_at: Optional[datetime] = None


# ==================== Notification Log ====================

NotificationChannel = Literal["email", "gotify", "webhook"]
NotificationStatus = Literal["sent", "failed", "pending"]


class NotificationLogEntry(BaseModel):
    """Log-Eintrag"""
    id: int
    channel: NotificationChannel
    recipient: Optional[str] = None
    subject: Optional[str] = None
    event_type: str
    status: NotificationStatus
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationLogResponse(BaseModel):
    """Paginated Log Response"""
    items: List[NotificationLogEntry]
    total: int
    page: int
    per_page: int


# ==================== Notification Events ====================

class NotificationEvent(BaseModel):
    """Schema fuer interne Benachrichtigungs-Events"""
    event_type: EventType
    subject: str
    message: str
    html_message: Optional[str] = None
    user_id: Optional[int] = None  # Nur diesen Benutzer benachrichtigen
    payload: Optional[dict] = None  # Zusaetzliche Daten fuer Webhooks
