"""
Webhook Model - Konfiguration fuer externe Webhook-Benachrichtigungen
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func

from app.database import Base


class Webhook(Base):
    """Webhook-Konfiguration"""
    __tablename__ = "webhooks"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Basis-Konfiguration
    name = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    secret_encrypted = Column(Text, nullable=True)  # Fuer HMAC-Signatur, verschluesselt
    enabled = Column(Boolean, default=True, nullable=False)

    # Ereignisse - VM
    on_vm_created = Column(Boolean, default=False, nullable=False)
    on_vm_deleted = Column(Boolean, default=False, nullable=False)
    on_vm_state_change = Column(Boolean, default=False, nullable=False)

    # Ereignisse - Ansible
    on_ansible_completed = Column(Boolean, default=False, nullable=False)
    on_ansible_failed = Column(Boolean, default=False, nullable=False)

    # Ereignisse - System
    on_system_alert = Column(Boolean, default=False, nullable=False)

    # Status-Tracking
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    last_status = Column(String(20), nullable=True)  # 'success', 'failed'
    failure_count = Column(Integer, default=0, nullable=False)

    # Zeitstempel
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
