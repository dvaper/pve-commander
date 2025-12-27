"""
NotificationSettings Model - Globale Benachrichtigungseinstellungen
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func

from app.database import Base


class NotificationSettings(Base):
    """Globale Benachrichtigungseinstellungen (Singleton)"""
    __tablename__ = "notification_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # SMTP Konfiguration
    smtp_enabled = Column(Boolean, default=False, nullable=False)
    smtp_host = Column(String(255), nullable=True)
    smtp_port = Column(Integer, default=587, nullable=False)
    smtp_user = Column(String(255), nullable=True)
    smtp_password_encrypted = Column(Text, nullable=True)  # Verschluesselt!
    smtp_from_email = Column(String(255), nullable=True)
    smtp_from_name = Column(String(100), default="PVE Commander", nullable=False)
    smtp_use_tls = Column(Boolean, default=True, nullable=False)
    smtp_use_ssl = Column(Boolean, default=False, nullable=False)

    # Gotify Konfiguration
    gotify_enabled = Column(Boolean, default=False, nullable=False)
    gotify_url = Column(String(255), nullable=True)
    gotify_token_encrypted = Column(Text, nullable=True)  # Verschluesselt!
    gotify_priority = Column(Integer, default=5, nullable=False)

    # App URL fuer Links in E-Mails
    app_url = Column(String(255), default="http://localhost:8080", nullable=False)

    # Passwort-Reset Einstellungen
    password_reset_expiry_hours = Column(Integer, default=24, nullable=False)

    # Zeitstempel
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
