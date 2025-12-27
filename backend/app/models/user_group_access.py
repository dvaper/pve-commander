"""
UserGroupAccess Model - Zuordnung von Benutzern zu Inventory-Gruppen
"""
from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class UserGroupAccess(Base):
    """Zuordnung eines Benutzers zu einer Inventory-Gruppe"""
    __tablename__ = "user_group_access"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    group_name = Column(String(100), nullable=False)  # Inventory-Gruppenname

    # Relationship
    user = relationship("User", back_populates="group_access")

    __table_args__ = (
        UniqueConstraint('user_id', 'group_name', name='uq_user_group'),
    )

    def __repr__(self):
        return f"<UserGroupAccess(user_id={self.user_id}, group={self.group_name})>"
