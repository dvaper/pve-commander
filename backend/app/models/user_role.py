"""
UserRole - Junction Table fuer User-Role Beziehung
"""
from sqlalchemy import Column, Integer, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class UserRole(Base):
    """
    Verknuepft Benutzer mit Rollen.

    Unterstuetzt:
    - Mehrere Rollen pro Benutzer
    - Optionale Ablaufzeit
    - Tracking wer die Rolle zugewiesen hat
    """
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, autoincrement=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    role_id = Column(
        Integer,
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False
    )

    # Zuweisungs-Tracking
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Optionales Ablaufdatum
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship(
        "User",
        back_populates="roles",
        foreign_keys=[user_id]
    )
    role = relationship("Role", back_populates="user_roles")
    assigner = relationship("User", foreign_keys=[assigned_by])

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )
