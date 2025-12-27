"""
ExecutionLog Model - Output Logs für Executions
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class ExecutionLog(Base):
    """Log-Einträge für Execution Output"""
    __tablename__ = "execution_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(Integer, ForeignKey("executions.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    log_type = Column(String(10), nullable=False)  # 'stdout', 'stderr'
    content = Column(Text, nullable=False)
    sequence_num = Column(Integer, nullable=False)

    # Relationship
    execution = relationship("Execution", back_populates="logs")
