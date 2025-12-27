"""
UserHostAccess Model - Zuordnung von Benutzern zu einzelnen Inventory-Hosts
"""
from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class UserHostAccess(Base):
    """Zuordnung eines Benutzers zu einem einzelnen Inventory-Host"""
    __tablename__ = "user_host_access"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    host_name = Column(String(255), nullable=False)  # Inventory-Hostname

    # Relationship
    user = relationship("User", back_populates="host_access")

    __table_args__ = (
        UniqueConstraint('user_id', 'host_name', name='uq_user_host'),
    )

    def __repr__(self):
        return f"<UserHostAccess(user_id={self.user_id}, host={self.host_name})>"
