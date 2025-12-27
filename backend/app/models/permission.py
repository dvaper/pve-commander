"""
Permission Model - Granulare Berechtigungen
"""
from sqlalchemy import Column, Integer, String, Text, Boolean
from sqlalchemy.orm import relationship

from app.database import Base


class Permission(Base):
    """
    Definiert verfuegbare Berechtigungen.

    Namenskonvention: {resource}.{action}
    Beispiele:
    - users.read, users.write, users.delete, users.admin
    - playbooks.read, playbooks.write, playbooks.execute
    - inventory.read, inventory.write
    - executions.read, executions.cancel
    - settings.read, settings.write
    - terraform.read, terraform.execute
    - roles.read, roles.write, roles.delete
    - audit.read, audit.rollback
    """
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Permission Identifier (z.B. "users.write")
    name = Column(String(100), unique=True, nullable=False, index=True)

    # Resource Type (z.B. "users", "playbooks", "inventory")
    resource = Column(String(50), nullable=False, index=True)

    # Action (z.B. "read", "write", "execute", "delete", "admin")
    action = Column(String(50), nullable=False)

    # Beschreibung
    description = Column(Text, nullable=True)

    # System-Permission (kann nicht geloescht werden)
    is_system = Column(Boolean, default=True)

    # Relationships
    role_permissions = relationship(
        "RolePermission",
        back_populates="permission",
        cascade="all, delete-orphan"
    )
