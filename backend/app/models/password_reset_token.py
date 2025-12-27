"""
PasswordResetToken Model - Tokens fuer Passwort-Zuruecksetzung
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class PasswordResetToken(Base):
    """Passwort-Reset Tokens"""
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Token (sicher generiert, 48 Bytes URL-safe)
    token = Column(String(64), unique=True, nullable=False, index=True)

    # Gueltigkeit
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False, nullable=False)

    # Zeitstempel
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    user = relationship("User", back_populates="password_reset_tokens")
