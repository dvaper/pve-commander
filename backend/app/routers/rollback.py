"""
Rollback Router - Rueckgaengigmachen von protokollierten Aktionen

Endpoints:
- GET /api/rollback - Rollback-Requests auflisten
- POST /api/rollback - Rollback anfordern
- GET /api/rollback/{id} - Rollback-Status
- POST /api/rollback/{id}/execute - Rollback ausfuehren
- POST /api/rollback/{id}/cancel - Rollback abbrechen
"""
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_active_user
from app.models.user import User
from app.services.rbac_service import RBACService
from app.services.audit_service import AuditService
from app.services.rollback_executors import RollbackService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rollback", tags=["rollback"])


# =============================================================================
# Schemas
# =============================================================================

class RollbackRequest(BaseModel):
    audit_id: int
    reason: Optional[str] = None


class RollbackResponse(BaseModel):
    id: int
    original_audit_id: int
    original_sequence: int
    status: str
    requested_at: str
    requested_by_user_id: int
    requested_by_username: str
    reason: Optional[str]
    executed_at: Optional[str]
    success: Optional[bool]
    error_message: Optional[str]
    rollback_audit_id: Optional[int]


class RollbackListResponse(BaseModel):
    rollbacks: List[RollbackResponse]
    total: int


# =============================================================================
# Helper Functions
# =============================================================================

def rollback_to_response(rollback) -> RollbackResponse:
    """Konvertiert AuditRollback Model zu Response."""
    return RollbackResponse(
        id=rollback.id,
        original_audit_id=rollback.original_audit_id,
        original_sequence=rollback.original_sequence,
        status=rollback.status,
        requested_at=rollback.requested_at.isoformat() if rollback.requested_at else None,
        requested_by_user_id=rollback.requested_by_user_id,
        requested_by_username=rollback.requested_by_username,
        reason=rollback.reason,
        executed_at=rollback.executed_at.isoformat() if rollback.executed_at else None,
        success=rollback.success,
        error_message=rollback.error_message,
        rollback_audit_id=rollback.rollback_audit_id,
    )


async def check_rollback_permission(db: AsyncSession, user: User) -> None:
    """Prueft ob User Rollbacks ausfuehren darf."""
    rbac = RBACService(db, user)
    if not await rbac.has_permission("audit.rollback"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Keine Berechtigung fuer Rollback-Operationen"
        )


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=RollbackListResponse)
async def list_rollbacks(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Listet alle Rollback-Requests auf.

    Filter:
    - status: pending, executing, completed, failed, cancelled
    """
    await check_rollback_permission(db, current_user)

    audit = AuditService(db)
    rollbacks = await audit.get_rollback_requests(status=status_filter)

    return RollbackListResponse(
        rollbacks=[rollback_to_response(r) for r in rollbacks],
        total=len(rollbacks),
    )


@router.post("", response_model=RollbackResponse, status_code=status.HTTP_201_CREATED)
async def request_rollback(
    data: RollbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Fordert einen Rollback fuer einen Audit-Log-Eintrag an.

    Voraussetzungen:
    - Audit-Eintrag muss existieren
    - Audit-Eintrag muss rollback-faehig sein (is_rollbackable=True)
    - Audit-Eintrag darf noch nicht zurueckgerollt sein
    """
    await check_rollback_permission(db, current_user)

    audit = AuditService(db)

    try:
        rollback = await audit.request_rollback(
            audit_id=data.audit_id,
            user_id=current_user.id,
            username=current_user.username,
            reason=data.reason,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    logger.info(
        f"Rollback angefordert: Audit #{data.audit_id} von {current_user.username}"
    )

    return rollback_to_response(rollback)


@router.get("/{rollback_id}", response_model=RollbackResponse)
async def get_rollback(
    rollback_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Gibt den Status eines Rollback-Requests zurueck."""
    await check_rollback_permission(db, current_user)

    audit = AuditService(db)
    rollback = await audit.get_rollback_by_id(rollback_id)

    if not rollback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rollback-Request nicht gefunden"
        )

    return rollback_to_response(rollback)


@router.post("/{rollback_id}/execute", response_model=RollbackResponse)
async def execute_rollback(
    rollback_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Fuehrt einen angeforderten Rollback aus.

    Voraussetzungen:
    - Rollback-Request muss existieren
    - Status muss "pending" sein
    - Passender Executor muss vorhanden sein
    """
    await check_rollback_permission(db, current_user)

    rollback_service = RollbackService(db)

    try:
        rollback = await rollback_service.execute_rollback(
            rollback_id=rollback_id,
            executor_user_id=current_user.id,
            executor_username=current_user.username,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Rollback {rollback_id} fehlgeschlagen: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rollback fehlgeschlagen: {str(e)}"
        )

    logger.info(
        f"Rollback ausgefuehrt: #{rollback_id} von {current_user.username}"
    )

    return rollback_to_response(rollback)


@router.post("/{rollback_id}/cancel", response_model=RollbackResponse)
async def cancel_rollback(
    rollback_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Bricht einen ausstehenden Rollback-Request ab.

    Nur moeglich wenn Status "pending" ist.
    """
    await check_rollback_permission(db, current_user)

    rollback_service = RollbackService(db)

    try:
        rollback = await rollback_service.cancel_rollback(
            rollback_id=rollback_id,
            user_id=current_user.id,
            username=current_user.username,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    logger.info(
        f"Rollback abgebrochen: #{rollback_id} von {current_user.username}"
    )

    return rollback_to_response(rollback)


@router.get("/audit/{audit_id}/can-rollback")
async def can_rollback(
    audit_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Prueft ob ein Audit-Eintrag rueckgaengig gemacht werden kann.

    Returns:
    - can_rollback: true/false
    - reason: Grund falls nicht moeglich
    """
    await check_rollback_permission(db, current_user)

    audit = AuditService(db)
    log = await audit.get_log_by_id(audit_id)

    if not log:
        return {
            "can_rollback": False,
            "reason": "Audit-Eintrag nicht gefunden"
        }

    if not log.is_rollbackable:
        return {
            "can_rollback": False,
            "reason": "Aktion ist nicht rueckgaengig machbar"
        }

    if log.rollback_executed:
        return {
            "can_rollback": False,
            "reason": "Wurde bereits zurueckgerollt"
        }

    if not log.rollback_data:
        return {
            "can_rollback": False,
            "reason": "Keine Rollback-Daten vorhanden"
        }

    return {
        "can_rollback": True,
        "reason": None,
        "action_type": log.action_type,
        "resource_type": log.resource_type,
        "resource_name": log.resource_name,
    }
