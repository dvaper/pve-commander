"""
VM History Model - Änderungsverlauf für VMs
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class VMHistory(Base):
    """Modell für VM-Änderungsverlauf"""

    __tablename__ = "vm_history"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # VM-Identifikation
    vm_name = Column(String(100), nullable=False, index=True)

    # Aktion
    action = Column(
        String(50),
        nullable=False,
        index=True,
    )  # created, updated, deployed, destroyed, imported, config_changed

    # TF-Konfiguration vor/nach Änderung
    tf_config_before = Column(Text, nullable=True)
    tf_config_after = Column(Text, nullable=True)

    # Verknüpfung zur Execution (falls vorhanden)
    execution_id = Column(Integer, ForeignKey("executions.id"), nullable=True)

    # User der die Änderung durchgeführt hat
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Zeitstempel
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Zusätzliche Metadaten (IP, Node, VMID, etc.)
    extra_data = Column(JSON, nullable=True, default=dict)

    # Beziehungen
    user = relationship("User", foreign_keys=[user_id])
    execution = relationship("Execution", foreign_keys=[execution_id])

    def __repr__(self):
        return f"<VMHistory {self.id}: {self.vm_name} - {self.action}>"
