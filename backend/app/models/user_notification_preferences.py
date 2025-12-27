"""
UserNotificationPreferences Model - Benutzer-spezifische Benachrichtigungspraeferenzen
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class UserNotificationPreferences(Base):
    """Benutzer-Benachrichtigungspraeferenzen"""
    __tablename__ = "user_notification_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    # Kanaele aktivieren
    email_enabled = Column(Boolean, default=True, nullable=False)
    gotify_enabled = Column(Boolean, default=False, nullable=False)
    gotify_user_token_encrypted = Column(Text, nullable=True)  # Optionaler User-spezifischer Token

    # Ereignistypen - VM
    notify_vm_created = Column(Boolean, default=True, nullable=False)
    notify_vm_deleted = Column(Boolean, default=True, nullable=False)
    notify_vm_state_change = Column(Boolean, default=False, nullable=False)

    # Ereignistypen - Ansible
    notify_ansible_completed = Column(Boolean, default=True, nullable=False)
    notify_ansible_failed = Column(Boolean, default=True, nullable=False)

    # Ereignistypen - System
    notify_system_alerts = Column(Boolean, default=True, nullable=False)

    # Zeitstempel
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship
    user = relationship("User", back_populates="notification_preferences")
