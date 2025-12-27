"""
NotificationLog Model - Protokollierung aller Benachrichtigungen
"""
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func

from app.database import Base


class NotificationLog(Base):
    """Benachrichtigungs-Protokoll"""
    __tablename__ = "notification_log"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Kanal und Empfaenger
    channel = Column(String(20), nullable=False, index=True)  # 'email', 'gotify', 'webhook'
    recipient = Column(String(255), nullable=True)  # E-Mail-Adresse, Webhook-Name, etc.

    # Inhalt
    subject = Column(String(255), nullable=True)
    event_type = Column(String(50), nullable=False, index=True)  # 'vm_created', 'ansible_failed', etc.

    # Status
    status = Column(String(20), nullable=False, index=True)  # 'sent', 'failed', 'pending'
    error_message = Column(Text, nullable=True)

    # Zeitstempel
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
