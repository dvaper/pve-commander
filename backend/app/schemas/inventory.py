"""
Inventory Schemas
"""
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List, Dict


class HostInfo(BaseModel):
    """Schema für Host-Information"""
    name: str
    ansible_host: Optional[str] = None
    vmid: Optional[int] = None
    pve_node: Optional[str] = None
    groups: List[str] = []
    vars: Dict[str, str] = {}


class GroupInfo(BaseModel):
    """Schema für Gruppen-Information"""
    name: str
    hosts: List[str] = []
    children: List[str] = []
    hosts_count: int = 0  # Direkte Hosts in dieser Gruppe
    total_hosts_count: int = 0  # Alle Hosts inkl. Kinder-Gruppen
    vars: Dict[str, str] = {}


class InventoryTree(BaseModel):
    """Schema für hierarchische Inventory-Struktur"""
    groups: Dict[str, GroupInfo]
    hosts: Dict[str, HostInfo]
    all_hosts: List[str]
    all_groups: List[str]


# ========================================
# Inventory-Editor Schemas
# ========================================

class GroupCreate(BaseModel):
    """Schema zum Erstellen einer neuen Gruppe"""
    name: str = Field(..., min_length=1, max_length=64, description="Name der Gruppe")
    parent: str = Field(default="all", description="Parent-Gruppe (default: all)")


class GroupRename(BaseModel):
    """Schema zum Umbenennen einer Gruppe"""
    new_name: str = Field(..., min_length=1, max_length=64, description="Neuer Name der Gruppe")


class HostGroupAssignment(BaseModel):
    """Schema zum Zuweisen eines Hosts zu einer Gruppe"""
    host_name: str = Field(..., min_length=1, description="Name des Hosts")


class ValidationResult(BaseModel):
    """Ergebnis der Inventory-Validierung"""
    valid: bool
    yaml_valid: bool
    ansible_valid: bool
    errors: List[str] = []
    warnings: List[str] = []


class InventoryChange(BaseModel):
    """Schema für einen Eintrag in der Git-Historie"""
    commit_hash: str
    author: str
    email: Optional[str] = None
    timestamp: datetime
    message: str


class InventoryHistoryResponse(BaseModel):
    """Response für Git-Historie"""
    commits: List[InventoryChange]
    total: int


class InventoryOperationResponse(BaseModel):
    """Standard-Response für Inventory-Operationen"""
    success: bool
    message: str
    details: Optional[str] = None
