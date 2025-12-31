"""
VM Schemas - Pydantic Modelle für VM-Deployment
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum
import re

from app.schemas.cloud_init import CloudInitProfile


class VMStatus(str, Enum):
    """Status einer VM-Konfiguration"""
    # Deployment-Status
    PLANNED = "planned"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    FAILED = "failed"
    DESTROYING = "destroying"
    # Proxmox Live-Status (für deployed VMs)
    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"


class VMConfigCreate(BaseModel):
    """Request-Schema für VM-Erstellung"""

    # Basis
    name: str = Field(..., min_length=1, max_length=63, description="VM-Name (Hostname)")
    description: str = Field(default="", max_length=500, description="Beschreibung")
    target_node: str = Field(..., min_length=1, description="Proxmox-Node (dynamisch aus Cluster)")

    # Template & Storage (dynamisch aus Proxmox)
    template_id: Optional[int] = Field(default=None, description="Template VMID (dynamisch)")
    storage: Optional[str] = Field(default=None, description="Storage-Pool fuer VM-Disk (dynamisch)")

    # Ressourcen
    cores: int = Field(default=2, ge=1, le=32, description="CPU-Kerne")
    memory_gb: int = Field(default=2, ge=1, le=128, description="RAM in GB")
    disk_size_gb: int = Field(default=20, ge=10, le=1000, description="Disk-Größe in GB")

    # Netzwerk (dynamisch aus NetBox)
    vlan: Optional[int] = Field(default=None, description="VLAN-ID (dynamisch aus NetBox)")
    ip_address: Optional[str] = Field(default=None, description="IP-Adresse (None = automatisch)")
    auto_reserve_ip: bool = Field(default=True, description="IP in NetBox reservieren")

    # Ansible Integration
    ansible_group: str = Field(
        default="",
        description="Ansible-Inventar-Gruppe (leer = nicht ins Inventory aufnehmen)"
    )

    # Cloud-Init
    cloud_init_profile: CloudInitProfile = Field(
        default=CloudInitProfile.NONE,
        description="Cloud-Init Profil für automatische Konfiguration"
    )

    # Post-Deploy Provisioning
    post_deploy_playbook: Optional[str] = Field(
        default=None,
        description="Playbook das nach erfolgreichem Deploy ausgeführt wird"
    )
    post_deploy_extra_vars: Optional[dict] = Field(
        default=None,
        description="Extra-Variablen für das Post-Deploy Playbook"
    )
    wait_for_ssh: bool = Field(
        default=True,
        description="Vor Playbook-Ausführung auf SSH-Verbindung warten"
    )

    # Frontend-URL
    frontend_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="URL zur Web-Oberfläche der VM (z.B. https://app.example.com)"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        """Validiert VM-Namen (nur lowercase, Zahlen, Bindestriche)"""
        if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$", v):
            raise ValueError(
                "Name muss mit Buchstabe/Zahl beginnen und enden, "
                "nur Kleinbuchstaben, Zahlen und Bindestriche erlaubt"
            )
        return v

    @field_validator("ip_address")
    @classmethod
    def validate_ip(cls, v):
        """Validiert IP-Adresse falls angegeben"""
        if v is None:
            return v
        # Allgemeines IPv4-Format
        pattern = r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"
        if not re.match(pattern, v):
            raise ValueError("Ungültige IP-Adresse (Format: x.x.x.x)")
        # Oktetten-Werte prüfen (0-255)
        octets = [int(o) for o in v.split(".")]
        if not all(0 <= o <= 255 for o in octets):
            raise ValueError("IP-Adresse Oktetten müssen zwischen 0 und 255 liegen")
        return v


class VMConfigResponse(BaseModel):
    """Response-Schema für VM-Konfiguration"""
    name: str
    vmid: int
    ip_address: str
    target_node: str
    description: str
    cores: int
    memory_gb: int
    disk_size_gb: int
    vlan: int
    status: VMStatus
    tf_file: str
    execution_id: Optional[int] = None
    ansible_group: str = ""  # Ansible-Inventar-Gruppe
    frontend_url: Optional[str] = None  # URL zur Web-Oberfläche


class VMConfigListItem(BaseModel):
    """Kurzform für VM-Liste"""
    name: str
    vmid: int
    ip_address: str
    target_node: str
    cores: int
    memory_gb: int
    disk_size_gb: int
    status: VMStatus
    ansible_group: str = ""  # Ansible-Inventar-Gruppe
    frontend_url: Optional[str] = None  # URL zur Web-Oberfläche


class AvailableIP(BaseModel):
    """Schema für verfügbare IP-Adresse"""
    address: str
    vmid: int
    vlan: int


class VLANInfo(BaseModel):
    """Schema für VLAN-Information"""
    id: int
    name: str
    prefix: str


class UsedIP(BaseModel):
    """Schema für belegte IP-Adresse"""
    address: str
    description: str
    status: str
    dns_name: str


class NodeInfo(BaseModel):
    """Schema für Proxmox-Node Information (dynamisch aus Cluster)"""
    name: str
    cpus: int
    ram_gb: int
    status: str = "online"
    cpu_usage: float = 0.0
    memory_used_gb: float = 0.0


class VMValidationResult(BaseModel):
    """Ergebnis der VM-Konfigurationsvalidierung"""
    valid: bool
    errors: list[str] = []
    warnings: list[str] = []


class TerraformPreview(BaseModel):
    """Preview des generierten Terraform-Codes"""
    filename: str
    content: str
    vmid: int
    ip_address: str


def calculate_vmid(ip_address: str) -> int:
    """
    Berechnet VMID aus IP-Adresse

    192.168.60.198 → 60198
    192.168.30.42  → 30042
    """
    octets = ip_address.split(".")
    vlan = int(octets[2])
    last_octet = int(octets[3])
    return vlan * 1000 + last_octet


# ========== VM Migration Schemas ==========


class VMMigrateRequest(BaseModel):
    """Request-Schema für VM-Migration"""
    target_node: str = Field(..., min_length=1, description="Ziel-Node für die Migration")

    @field_validator("target_node")
    @classmethod
    def validate_target_node(cls, v):
        """Validiert Node-Namen (grundlegende Formatprüfung)"""
        if not v or not v.strip():
            raise ValueError("Ziel-Node darf nicht leer sein")
        # Node-Existenz wird zur Laufzeit gegen Proxmox API geprüft
        return v.strip()


class VMMigrateResult(BaseModel):
    """Response-Schema für VM-Migration"""
    success: bool
    message: str
    vm_name: str
    source_node: str
    target_node: str
    vmid: Optional[int] = None
    upid: Optional[str] = None
    was_running: Optional[bool] = None
    restarted: Optional[bool] = None
    tf_updated: Optional[bool] = None
    warning: Optional[str] = None


# ========== VM Frontend-URL Schemas ==========


class VMFrontendUrlUpdate(BaseModel):
    """Request-Schema für Frontend-URL Update"""
    frontend_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="URL zur Web-Oberfläche (None zum Entfernen)"
    )


class VMFrontendUrlResult(BaseModel):
    """Response-Schema für Frontend-URL Update"""
    success: bool
    message: str
    vm_name: str
    frontend_url: Optional[str] = None


# ========== VM Config Update Schemas ==========


class VMConfigUpdate(BaseModel):
    """Request-Schema für VM-Konfiguration Update"""
    cores: Optional[int] = Field(default=None, ge=1, le=32, description="CPU-Kerne")
    memory_gb: Optional[int] = Field(default=None, ge=1, le=128, description="RAM in GB")
    disk_size_gb: Optional[int] = Field(default=None, ge=10, le=1000, description="Disk-Größe in GB")
    description: Optional[str] = Field(default=None, max_length=500, description="Beschreibung")
    target_node: Optional[str] = Field(default=None, description="Ziel-Node")

    @field_validator("target_node")
    @classmethod
    def validate_target_node(cls, v):
        """Validiert Node-Namen (grundlegende Formatprüfung)"""
        if v is None:
            return v
        if not v.strip():
            raise ValueError("Ziel-Node darf nicht leer sein")
        # Node-Existenz wird zur Laufzeit gegen Proxmox API geprüft
        return v.strip()


class VMConfigUpdateResult(BaseModel):
    """Response-Schema für VM-Konfiguration Update"""
    success: bool
    message: str
    vm_name: str
    updated_fields: dict = {}
    needs_apply: bool = False  # True wenn VM deployed ist und apply nötig
