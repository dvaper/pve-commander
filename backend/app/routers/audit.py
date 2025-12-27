"""
Audit Router - Audit-Log Anzeige und Verifikation

Endpoints:
- GET /api/audit/logs - Audit-Logs auflisten (paginiert, filterbar)
- GET /api/audit/logs/{id} - Einzelner Log-Eintrag
- GET /api/audit/verify - Hash-Chain verifizieren
- GET /api/audit/export - Logs exportieren (JSON/CSV)
- GET /api/audit/stats - Audit-Statistiken

WICHTIG: Keine DELETE oder PUT Endpoints - Logs sind immutabel!
"""
import json
import logging
import csv
import io
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_active_user
from app.models.user import User
from app.services.rbac_service import RBACService
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit", tags=["audit"])


# =============================================================================
# Schemas
# =============================================================================

class AuditLogResponse(BaseModel):
    id: int
    sequence: int
    timestamp: str
    user_id: Optional[int]
    username: Optional[str]
    action_type: str
    resource_type: str
    resource_id: Optional[str]
    resource_name: Optional[str]
    details: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    user_agent: Optional[str]
    correlation_id: Optional[str]
    is_rollbackable: bool
    rollback_executed: bool
    entry_hash: str
    previous_hash: Optional[str]


class AuditLogListResponse(BaseModel):
    logs: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ChainVerificationResult(BaseModel):
    is_valid: bool
    entries_checked: int
    errors: List[Dict[str, Any]]
    verification_time_ms: float


class AuditStatsResponse(BaseModel):
    total_entries: int
    by_action_type: Dict[str, int]
    by_resource_type: Dict[str, int]
    rollbackable_count: int


# =============================================================================
# Helper Functions
# =============================================================================

def audit_log_to_response(log) -> AuditLogResponse:
    """Konvertiert AuditLog Model zu Response."""
    return AuditLogResponse(
        id=log.id,
        sequence=log.sequence,
        timestamp=log.timestamp.isoformat() if log.timestamp else None,
        user_id=log.user_id,
        username=log.username,
        action_type=log.action_type,
        resource_type=log.resource_type,
        resource_id=log.resource_id,
        resource_name=log.resource_name,
        details=json.loads(log.details) if log.details else None,
        ip_address=log.ip_address,
        user_agent=log.user_agent,
        correlation_id=log.correlation_id,
        is_rollbackable=log.is_rollbackable,
        rollback_executed=log.rollback_executed,
        entry_hash=log.entry_hash,
        previous_hash=log.previous_hash,
    )


async def check_audit_permission(db: AsyncSession, user: User) -> None:
    """Prueft ob User Audit-Logs lesen darf."""
    rbac = RBACService(db, user)
    if not await rbac.has_permission("audit.read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Keine Berechtigung zum Lesen der Audit-Logs"
        )


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=200),
    user_id: Optional[int] = None,
    action_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    correlation_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Listet Audit-Logs mit Filterung und Paginierung auf.

    Filter:
    - user_id: Nur Logs eines bestimmten Benutzers
    - action_type: CREATE, UPDATE, DELETE, EXECUTE, LOGIN, etc.
    - resource_type: user, role, playbook, execution, etc.
    - resource_id: ID der betroffenen Ressource
    - start_date, end_date: Zeitraum
    - correlation_id: Request-Correlation-ID
    """
    await check_audit_permission(db, current_user)

    audit = AuditService(db)
    logs, total = await audit.get_logs(
        page=page,
        page_size=page_size,
        user_id=user_id,
        action_type=action_type,
        resource_type=resource_type,
        resource_id=resource_id,
        start_date=start_date,
        end_date=end_date,
        correlation_id=correlation_id,
    )

    pages = (total + page_size - 1) // page_size

    return AuditLogListResponse(
        logs=[audit_log_to_response(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/logs/{audit_id}", response_model=AuditLogResponse)
async def get_audit_log(
    audit_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Gibt einen einzelnen Audit-Log-Eintrag zurueck."""
    await check_audit_permission(db, current_user)

    audit = AuditService(db)
    log = await audit.get_log_by_id(audit_id)

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit-Log nicht gefunden"
        )

    return audit_log_to_response(log)


@router.get("/verify", response_model=ChainVerificationResult)
async def verify_audit_chain(
    start_sequence: Optional[int] = None,
    end_sequence: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Verifiziert die Integritaet der Audit-Log-Chain.

    Prueft:
    - Hash-Verkettung (previous_hash stimmt)
    - Entry-Hash (Inhalt nicht manipuliert)

    Bei Erfolg: is_valid=True, errors=[]
    Bei Fehler: is_valid=False, errors=[{sequence, error, ...}]
    """
    await check_audit_permission(db, current_user)

    rbac = RBACService(db, current_user)
    if not await rbac.has_permission("audit.verify"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Keine Berechtigung zur Chain-Verifikation"
        )

    audit = AuditService(db)

    start_time = datetime.utcnow()
    is_valid, errors, entries_checked = await audit.verify_chain(
        start_sequence=start_sequence,
        end_sequence=end_sequence,
    )
    end_time = datetime.utcnow()

    duration_ms = (end_time - start_time).total_seconds() * 1000

    return ChainVerificationResult(
        is_valid=is_valid,
        entries_checked=entries_checked,
        errors=errors,
        verification_time_ms=round(duration_ms, 2),
    )


@router.get("/export")
async def export_audit_logs(
    format: str = Query("json", regex="^(json|csv)$"),
    user_id: Optional[int] = None,
    action_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Exportiert Audit-Logs als JSON oder CSV.

    Achtung: Kann grosse Datenmengen produzieren!
    Verwende Filter um die Datenmenge zu begrenzen.
    """
    await check_audit_permission(db, current_user)

    rbac = RBACService(db, current_user)
    if not await rbac.has_permission("audit.export"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Keine Berechtigung zum Exportieren"
        )

    audit = AuditService(db)

    # Alle passenden Logs holen (max 10000)
    logs, _ = await audit.get_logs(
        page=1,
        page_size=10000,
        user_id=user_id,
        action_type=action_type,
        resource_type=resource_type,
        start_date=start_date,
        end_date=end_date,
    )

    if format == "json":
        # JSON Export
        data = [audit_log_to_response(log).model_dump() for log in logs]
        content = json.dumps(data, indent=2, default=str)

        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=audit_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            }
        )

    else:
        # CSV Export
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "id", "sequence", "timestamp", "user_id", "username",
            "action_type", "resource_type", "resource_id", "resource_name",
            "ip_address", "is_rollbackable", "rollback_executed",
        ])

        # Daten
        for log in logs:
            writer.writerow([
                log.id, log.sequence, log.timestamp.isoformat() if log.timestamp else "",
                log.user_id, log.username,
                log.action_type, log.resource_type, log.resource_id, log.resource_name,
                log.ip_address, log.is_rollbackable, log.rollback_executed,
            ])

        content = output.getvalue()

        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=audit_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )


@router.get("/stats", response_model=AuditStatsResponse)
async def get_audit_stats(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Gibt Audit-Statistiken zurueck."""
    await check_audit_permission(db, current_user)

    audit = AuditService(db)
    stats = await audit.get_stats(
        start_date=start_date,
        end_date=end_date,
    )

    return AuditStatsResponse(**stats)


@router.get("/action-types")
async def get_action_types(
    current_user: User = Depends(get_current_active_user),
):
    """Gibt alle moeglichen Action-Types zurueck."""
    from app.services.audit_service import ActionType

    return {
        "action_types": [
            {"value": ActionType.CREATE, "label": "Erstellen"},
            {"value": ActionType.READ, "label": "Lesen"},
            {"value": ActionType.UPDATE, "label": "Aktualisieren"},
            {"value": ActionType.DELETE, "label": "Loeschen"},
            {"value": ActionType.EXECUTE, "label": "Ausfuehren"},
            {"value": ActionType.LOGIN, "label": "Anmeldung"},
            {"value": ActionType.LOGOUT, "label": "Abmeldung"},
            {"value": ActionType.LOGIN_FAILED, "label": "Anmeldung fehlgeschlagen"},
            {"value": ActionType.PERMISSION_CHANGE, "label": "Berechtigungsaenderung"},
            {"value": ActionType.ROLE_CHANGE, "label": "Rollenaenderung"},
            {"value": ActionType.ROLLBACK, "label": "Rollback"},
            {"value": ActionType.SETTINGS_CHANGE, "label": "Einstellungsaenderung"},
            {"value": ActionType.BACKUP, "label": "Backup"},
            {"value": ActionType.RESTORE, "label": "Wiederherstellung"},
        ]
    }


@router.get("/resource-types")
async def get_resource_types(
    current_user: User = Depends(get_current_active_user),
):
    """Gibt alle moeglichen Resource-Types zurueck."""
    from app.services.audit_service import ResourceType

    return {
        "resource_types": [
            {"value": ResourceType.USER, "label": "Benutzer"},
            {"value": ResourceType.ROLE, "label": "Rolle"},
            {"value": ResourceType.PERMISSION, "label": "Berechtigung"},
            {"value": ResourceType.PLAYBOOK, "label": "Playbook"},
            {"value": ResourceType.EXECUTION, "label": "Ausfuehrung"},
            {"value": ResourceType.INVENTORY, "label": "Inventory"},
            {"value": ResourceType.SETTINGS, "label": "Einstellungen"},
            {"value": ResourceType.TERRAFORM, "label": "Terraform"},
            {"value": ResourceType.VM, "label": "VM"},
            {"value": ResourceType.BACKUP, "label": "Backup"},
            {"value": ResourceType.NOTIFICATION, "label": "Benachrichtigung"},
            {"value": ResourceType.SESSION, "label": "Session"},
            {"value": ResourceType.NETBOX, "label": "NetBox"},
        ]
    }
