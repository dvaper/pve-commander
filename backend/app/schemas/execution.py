"""
Execution Schemas
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class ExecutionCreate(BaseModel):
    """Basis-Schema für Execution"""
    execution_type: str


class AnsibleExecutionCreate(BaseModel):
    """Schema für Ansible Execution"""
    playbook_name: str
    target_hosts: Optional[List[str]] = None
    target_groups: Optional[List[str]] = None
    extra_vars: Optional[dict] = None


class TerraformExecutionCreate(BaseModel):
    """Schema für Terraform Execution"""
    tf_action: str  # 'plan', 'apply', 'destroy'
    tf_module: Optional[str] = None
    tf_vars: Optional[dict] = None


class AnsibleBatchCreate(BaseModel):
    """Schema fuer Batch-Ausfuehrung mehrerer Playbooks"""
    playbooks: List[str]  # Liste von Playbook-Namen in Ausfuehrungsreihenfolge
    target_hosts: Optional[List[str]] = None
    target_groups: Optional[List[str]] = None
    extra_vars: Optional[dict] = None


class BatchExecutionResponse(BaseModel):
    """Response fuer Batch-Ausfuehrung"""
    batch_id: str
    executions: List["ExecutionResponse"]
    total: int


class ExecutionLogResponse(BaseModel):
    """Schema für Log-Einträge"""
    id: int
    timestamp: datetime
    log_type: str
    content: str
    sequence_num: int

    class Config:
        from_attributes = True


class ExecutionResponse(BaseModel):
    """Schema für Execution Response"""
    id: int
    execution_type: str
    status: str
    playbook_name: Optional[str] = None
    target_hosts: Optional[str] = None
    target_groups: Optional[str] = None
    extra_vars: Optional[str] = None
    tf_action: Optional[str] = None
    tf_module: Optional[str] = None
    tf_vars: Optional[str] = None
    user_id: int
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    duration_seconds: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ExecutionListResponse(BaseModel):
    """Schema für paginierte Execution-Liste"""
    items: List[ExecutionResponse]
    total: int
    page: int
    page_size: int
