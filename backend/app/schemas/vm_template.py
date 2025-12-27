"""
VM Template Schemas - Pydantic Modelle für VM-Vorlagen
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class VMTemplateBase(BaseModel):
    """Basis-Schema für VM-Vorlagen"""
    name: str = Field(..., min_length=1, max_length=100, description="Vorlagen-Name")
    description: Optional[str] = Field(default=None, max_length=500, description="Beschreibung")

    # VM-Konfiguration
    cores: int = Field(default=2, ge=1, le=32, description="CPU-Kerne")
    memory_gb: int = Field(default=2, ge=1, le=128, description="RAM in GB")
    disk_size_gb: int = Field(default=20, ge=10, le=1000, description="Disk-Größe in GB")
    target_node: Optional[str] = Field(default=None, description="Proxmox-Node (optional)")
    storage: str = Field(default="local-ssd", description="Storage-Pool")
    template_vmid: Optional[int] = Field(default=None, description="Proxmox Template VMID")
    vlan: int = Field(default=60, description="VLAN-ID")

    # Ansible Integration
    ansible_group: Optional[str] = Field(default=None, description="Ansible-Inventar-Gruppe")

    # Cloud-Init
    cloud_init_profile: Optional[str] = Field(default=None, description="Cloud-Init Profil")

    # Meta
    is_default: bool = Field(default=False, description="Standard-Vorlage")


class VMTemplateCreate(VMTemplateBase):
    """Schema für Vorlage-Erstellung"""
    pass


class VMTemplateUpdate(BaseModel):
    """Schema für Vorlage-Aktualisierung (alle Felder optional)"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    cores: Optional[int] = Field(default=None, ge=1, le=32)
    memory_gb: Optional[int] = Field(default=None, ge=1, le=128)
    disk_size_gb: Optional[int] = Field(default=None, ge=10, le=1000)
    target_node: Optional[str] = None
    storage: Optional[str] = None
    template_vmid: Optional[int] = None
    vlan: Optional[int] = None
    ansible_group: Optional[str] = None
    cloud_init_profile: Optional[str] = None
    is_default: Optional[bool] = None


class VMTemplateResponse(VMTemplateBase):
    """Response-Schema für VM-Vorlage"""
    id: int
    created_by: int
    created_at: datetime
    updated_at: datetime
    creator_name: Optional[str] = None

    class Config:
        from_attributes = True


class VMTemplateListItem(BaseModel):
    """Kurzform für Vorlagen-Liste"""
    id: int
    name: str
    description: Optional[str]
    cores: int
    memory_gb: int
    disk_size_gb: int
    vlan: int
    is_default: bool
    target_node: Optional[str]
    ansible_group: Optional[str]

    class Config:
        from_attributes = True
