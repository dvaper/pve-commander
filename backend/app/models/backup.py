"""
Backup Models - Backup-Historie und Zeitplan
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, CheckConstraint
from sqlalchemy.sql import func

from app.database import Base


class BackupHistory(Base):
    """Backup-Historie - speichert Informationen ueber erstellte Backups"""
    __tablename__ = "backup_history"

    id = Column(String(36), primary_key=True)  # UUID
    filename = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    size_bytes = Column(Integer, nullable=True)
    components = Column(Text, nullable=True)  # JSON array
    is_scheduled = Column(Boolean, default=False, nullable=False)
    status = Column(String(50), default="completed", nullable=False)  # completed, failed, in_progress


class BackupSchedule(Base):
    """Backup-Zeitplan (Singleton)"""
    __tablename__ = "backup_schedule"
    __table_args__ = (
        CheckConstraint('id = 1', name='singleton_constraint'),
    )

    id = Column(Integer, primary_key=True, default=1)
    enabled = Column(Boolean, default=False, nullable=False)
    frequency = Column(String(20), default="daily", nullable=False)  # daily, weekly
    time = Column(String(5), default="02:00", nullable=False)  # HH:MM
    retention_days = Column(Integer, default=7, nullable=False)
    options = Column(Text, nullable=True)  # JSON BackupOptions
    last_run = Column(DateTime(timezone=True), nullable=True)
    next_run = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
