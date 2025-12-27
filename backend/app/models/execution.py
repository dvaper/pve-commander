"""
Execution Model - Ansible/Terraform Ausführungen
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class Execution(Base):
    """Execution History für Ansible/Terraform"""
    __tablename__ = "executions"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Typ: 'ansible' oder 'terraform'
    execution_type = Column(String(20), nullable=False)

    # Status: 'pending', 'running', 'success', 'failed', 'cancelled'
    status = Column(String(20), nullable=False, default="pending")

    # Ansible-spezifisch
    playbook_name = Column(String(255), nullable=True)
    target_hosts = Column(Text, nullable=True)  # JSON array
    target_groups = Column(Text, nullable=True)  # JSON array
    extra_vars = Column(Text, nullable=True)  # JSON object

    # Terraform-spezifisch
    tf_action = Column(String(20), nullable=True)  # 'plan', 'apply', 'destroy'
    tf_module = Column(String(100), nullable=True)
    tf_vars = Column(Text, nullable=True)  # JSON object

    # Common
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    exit_code = Column(Integer, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="executions")
    logs = relationship("ExecutionLog", back_populates="execution", cascade="all, delete-orphan")
