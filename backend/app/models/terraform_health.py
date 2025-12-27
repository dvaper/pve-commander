"""
Terraform Health Model - Speichert den letzten Health-Check Status

Singleton-Tabelle zur Persistierung des Terraform State Health-Status.
Wird vom TerraformHealthService aktualisiert.
"""
from sqlalchemy import Column, Integer, Boolean, DateTime, CheckConstraint
from sqlalchemy.sql import func

from app.database import Base
from app.models.types import JSONList


class TerraformHealthStatus(Base):
    """
    Terraform Health Status (Singleton)

    Speichert den Status des letzten Health-Checks:
    - healthy: True wenn keine verwaisten VMs gefunden wurden
    - total_vms: Anzahl der VMs im Terraform State
    - orphaned_count: Anzahl der verwaisten VMs
    - orphaned_vms: JSON-Liste der verwaisten VMs mit Details
    - last_check: Zeitpunkt des letzten Checks
    - next_check: Geplanter Zeitpunkt des naechsten Checks
    """
    __tablename__ = "terraform_health_status"
    __table_args__ = (
        CheckConstraint('id = 1', name='terraform_health_singleton_constraint'),
    )

    id = Column(Integer, primary_key=True, default=1)
    healthy = Column(Boolean, default=True, nullable=False)
    total_vms = Column(Integer, default=0, nullable=False)
    orphaned_count = Column(Integer, default=0, nullable=False)
    orphaned_vms = Column(JSONList, default=[], nullable=False)  # Automatische JSON-Serialisierung
    last_check = Column(DateTime(timezone=True), nullable=True)
    next_check = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
