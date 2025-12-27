"""
AuditRollback - Tracking von Rollback-Operationen
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.sql import func

from app.database import Base


class AuditRollback(Base):
    """
    Verfolgt Rollback-Requests und deren Ausfuehrungsstatus.

    Workflow:
    1. Benutzer fordert Rollback eines Audit-Eintrags an
    2. System validiert Rollback-Faehigkeit
    3. Rollback wird ausgefuehrt
    4. Neuer Audit-Eintrag dokumentiert den Rollback
    """
    __tablename__ = "audit_rollbacks"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Referenz auf urspruenglichen Audit-Eintrag
    original_audit_id = Column(Integer, nullable=False, index=True)
    original_sequence = Column(Integer, nullable=False)

    # Rollback-Request Informationen
    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    requested_by_user_id = Column(Integer, nullable=False)
    requested_by_username = Column(String(100), nullable=False)

    # Grund fuer Rollback
    reason = Column(Text, nullable=True)

    # Ausfuehrungsstatus
    status = Column(String(20), default="pending")
    # Werte: pending, executing, completed, failed, cancelled

    executed_at = Column(DateTime(timezone=True), nullable=True)

    # Ergebnis
    success = Column(Boolean, nullable=True)
    error_message = Column(Text, nullable=True)

    # Referenz auf neuen Audit-Eintrag der den Rollback dokumentiert
    rollback_audit_id = Column(Integer, nullable=True)

    # Daten-Snapshot vor Rollback (fuer doppelte Rollback-Verhinderung)
    pre_rollback_state = Column(Text, nullable=True)  # JSON
