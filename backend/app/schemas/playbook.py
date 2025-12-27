"""
Playbook Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import re


class PlaybookInfo(BaseModel):
    """Schema für Playbook-Übersicht"""
    name: str
    path: str
    hosts_target: Optional[str] = None
    description: Optional[str] = None
    is_system: bool = False  # True = schreibgeschützt


class PlaybookDetail(BaseModel):
    """Schema für Playbook-Details"""
    name: str
    path: str
    hosts_target: Optional[str] = None
    description: Optional[str] = None
    content: str
    tasks: List[str] = []
    roles: List[str] = []
    vars: List[str] = []
    is_system: bool = False  # True = schreibgeschützt


class PlaybookCreate(BaseModel):
    """Schema für Playbook-Erstellung"""
    name: str = Field(
        ...,
        min_length=2,
        max_length=64,
        description="Playbook-Name (muss mit 'custom-' beginnen)"
    )
    content: str = Field(
        ...,
        min_length=10,
        description="YAML-Inhalt des Playbooks"
    )

    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validiert den Playbook-Namen"""
        if not v.startswith("custom-"):
            raise ValueError("Name muss mit 'custom-' beginnen")
        if not re.match(r'^[a-z0-9_-]+$', v):
            raise ValueError("Name darf nur Kleinbuchstaben, Zahlen, _ und - enthalten")
        return v


class PlaybookUpdate(BaseModel):
    """Schema für Playbook-Update"""
    content: str = Field(
        ...,
        min_length=10,
        description="Neuer YAML-Inhalt des Playbooks"
    )


class PlaybookValidationRequest(BaseModel):
    """Schema für Validierungsanfrage"""
    content: str = Field(..., description="YAML-Inhalt zum Validieren")


class PlaybookParsedInfo(BaseModel):
    """Schema für geparste Playbook-Informationen"""
    hosts: List[str] = []
    tasks: List[str] = []
    roles: List[str] = []
    vars: List[str] = []
    plays_count: int = 0


class PlaybookValidationResult(BaseModel):
    """Schema für Validierungsergebnis"""
    valid: bool
    yaml_valid: bool
    yaml_error: Optional[str] = None
    ansible_valid: bool
    ansible_error: Optional[str] = None
    warnings: List[str] = []
    parsed_info: Optional[PlaybookParsedInfo] = None


class PlaybookTemplate(BaseModel):
    """Schema für Playbook-Template"""
    id: str
    name: str
    description: str
    content: str


class PlaybookHistoryEntry(BaseModel):
    """Schema für Git-Historie-Eintrag"""
    commit_hash: str
    author: str
    email: Optional[str] = None
    timestamp: str
    message: str


class PlaybookOperationResponse(BaseModel):
    """Schema für Playbook-Operationen (Create/Update/Delete)"""
    success: bool
    message: str
    playbook: Optional[PlaybookDetail] = None


class PlaybookMetadataResponse(BaseModel):
    """Schema fuer Playbook-Metadaten Response"""
    playbook_name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    os_type: str = "all"
    category: str = "custom"
    tags: List[str] = []
    requires_confirmation: bool = False
    risk_level: str = "info"


class PlaybookMetadataUpdate(BaseModel):
    """Schema fuer Playbook-Metadaten Update"""
    display_name: Optional[str] = None
    description: Optional[str] = None
    os_type: str = "all"
    category: str = "custom"
    tags: List[str] = []
    requires_confirmation: bool = False
    risk_level: str = "info"
