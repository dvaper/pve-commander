"""
RolePermission - Junction Table fuer Role-Permission Beziehung
"""
from sqlalchemy import Column, Integer, ForeignKey, Boolean, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class RolePermission(Base):
    """
    Verknuepft Rollen mit Berechtigungen, optional mit Scope-Einschraenkungen.

    Scope-Beispiele:
    - {"groups": ["linux-servers", "web-servers"]}
    - {"playbooks": ["custom-*"]}
    - {"os_types": ["linux"]}
    """
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)

    role_id = Column(
        Integer,
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False
    )

    permission_id = Column(
        Integer,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False
    )

    # Optionale Scope-Einschraenkungen (JSON)
    # z.B. {"groups": ["linux-*"], "categories": ["maintenance"]}
    scope = Column(Text, nullable=True)

    # Deny-Flag (explizites Deny ueberschreibt Allow)
    is_deny = Column(Boolean, default=False)

    # Relationships
    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission", back_populates="role_permissions")

    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )
