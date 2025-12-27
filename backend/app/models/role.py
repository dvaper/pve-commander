"""
Role Model - Dynamische Rollen mit Hierarchie
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Role(Base):
    """
    Dynamische Rolle mit optionaler Hierarchie.

    Hierarchie wird ueber parent_role_id implementiert:
    - Junior-Admin (kein Parent)
    - Senior-Admin (Parent = Junior-Admin) erbt alle Junior-Berechtigungen
    - Super-Admin Flag umgeht alle Berechtigungspruefungen
    """
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Identifikation
    name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # Hierarchie: Parent Role (erbt Berechtigungen vom Parent)
    parent_role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)

    # Prioritaet fuer Konfliktaufloesung (hoeher = mehr Vorrang)
    priority = Column(Integer, default=0)

    # System-Rolle (kann nicht geloescht/modifiziert werden)
    is_system_role = Column(Boolean, default=False)

    # Super-Admin Flag (umgeht alle Berechtigungspruefungen)
    is_super_admin = Column(Boolean, default=False)

    # OS-Type Einschraenkungen (JSON Array: ["linux", "windows", "all"])
    allowed_os_types = Column(Text, nullable=True)

    # Kategorie-Einschraenkungen (JSON Array)
    allowed_categories = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(String(100), nullable=True)

    # Self-referential Relationship fuer Hierarchie
    parent_role = relationship(
        "Role",
        remote_side=[id],
        backref="child_roles",
        foreign_keys=[parent_role_id]
    )

    # Relationships
    permissions = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    user_roles = relationship(
        "UserRole",
        back_populates="role",
        cascade="all, delete-orphan"
    )
