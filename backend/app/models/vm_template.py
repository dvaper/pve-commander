"""
VM Template Model - Wiederverwendbare VM-Konfigurationsvorlagen
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class VMTemplate(Base):
    """VM-Vorlage für schnelle VM-Erstellung"""
    __tablename__ = "vm_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(500), nullable=True)

    # VM-Konfiguration
    cores = Column(Integer, nullable=False, default=2)
    memory_gb = Column(Integer, nullable=False, default=2)
    disk_size_gb = Column(Integer, nullable=False, default=20)
    target_node = Column(String(50), nullable=True)  # Optional, sonst auswählbar
    storage = Column(String(50), nullable=False, default="local-ssd")
    template_vmid = Column(Integer, nullable=True)  # Proxmox Template VMID
    vlan = Column(Integer, nullable=False, default=60)

    # Ansible Integration
    ansible_group = Column(String(100), nullable=True)

    # Cloud-Init
    cloud_init_profile = Column(String(50), nullable=True)

    # Meta
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_default = Column(Boolean, default=False)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
