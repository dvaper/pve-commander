"""
User Model
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    """User für Authentication"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)

    # Rollen-Felder
    is_admin = Column(Boolean, default=False)  # Legacy, wird zu is_super_admin migriert
    is_super_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # NetBox Integration
    netbox_user_id = Column(Integer, nullable=True)  # Referenz auf NetBox User ID

    # Benutzer-Einstellungen
    theme = Column(String(20), default="blue", nullable=False)  # Farbschema (blue, orange, green, purple, teal)
    dark_mode = Column(String(10), default="dark", nullable=False)  # Modus (system, light, dark)
    sidebar_logo = Column(String(10), default="icon", nullable=False)  # Logo-Variante (icon, banner)
    ui_beta = Column(Boolean, default=False, nullable=False)  # Neues UI aktivieren (Feature-Flag)

    # Zeitstempel
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    group_access = relationship(
        "UserGroupAccess",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    playbook_access = relationship(
        "UserPlaybookAccess",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    host_access = relationship(
        "UserHostAccess",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    executions = relationship("Execution", back_populates="user")

    # Benachrichtigungs-Relationships
    notification_preferences = relationship(
        "UserNotificationPreferences",
        back_populates="user",
        uselist=False,  # One-to-One
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    password_reset_tokens = relationship(
        "PasswordResetToken",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    # RBAC Relationships
    roles = relationship(
        "UserRole",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
        foreign_keys="UserRole.user_id"
    )
