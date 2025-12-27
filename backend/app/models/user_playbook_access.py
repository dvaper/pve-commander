"""
UserPlaybookAccess Model - Zuordnung von Benutzern zu Playbooks
"""
from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class UserPlaybookAccess(Base):
    """Zuordnung eines Benutzers zu einem Playbook"""
    __tablename__ = "user_playbook_access"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    playbook_name = Column(String(255), nullable=False)  # Playbook-Name (ohne Pfad)

    # Relationship
    user = relationship("User", back_populates="playbook_access")

    __table_args__ = (
        UniqueConstraint('user_id', 'playbook_name', name='uq_user_playbook'),
    )

    def __repr__(self):
        return f"<UserPlaybookAccess(user_id={self.user_id}, playbook={self.playbook_name})>"
