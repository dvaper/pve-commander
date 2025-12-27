"""
Backup Router - Backup und Restore API-Endpunkte
"""
import logging
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse

from app.auth.dependencies import get_current_super_admin_user
from app.models.user import User
from app.services.backup_service import (
    backup_service,
    BackupOptions,
    BackupInfo,
    BackupResult,
    RestoreResult,
    ScheduleInfo,
)
from app.services.backup_scheduler import backup_scheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backup", tags=["backup"])


# =============================================================================
# Backup erstellen
# =============================================================================

@router.post("/create", response_model=BackupResult)
async def create_backup(
    options: Optional[BackupOptions] = None,
    current_user: User = Depends(get_current_super_admin_user),
):
    """
    Erstellt ein Backup mit den angegebenen Optionen.

    Wenn keine Optionen angegeben werden, werden Standardwerte verwendet.
    Alle Komponenten ausser NetBox-Media werden standardmaessig gesichert.
    """
    if options is None:
        options = BackupOptions()

    result = await backup_service.create_backup(options, is_scheduled=False)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.message
        )

    return result


# =============================================================================
# Backup herunterladen
# =============================================================================

@router.get("/download/{backup_id}")
async def download_backup(
    backup_id: str,
    current_user: User = Depends(get_current_super_admin_user),
):
    """
    Laesst ein Backup herunterladen.

    Gibt die Backup-ZIP-Datei zum Download zurueck.
    """
    backup_path = await backup_service.get_backup_path(backup_id)

    if not backup_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup nicht gefunden"
        )

    return FileResponse(
        path=backup_path,
        filename=backup_path.name,
        media_type="application/zip"
    )


# =============================================================================
# Backups auflisten
# =============================================================================

@router.get("/list", response_model=list[BackupInfo])
async def list_backups(
    current_user: User = Depends(get_current_super_admin_user),
):
    """
    Listet alle vorhandenen Backups auf.

    Sortiert nach Erstellungsdatum (neustes zuerst).
    """
    return await backup_service.list_backups()


# =============================================================================
# Backup loeschen
# =============================================================================

@router.delete("/{backup_id}")
async def delete_backup(
    backup_id: str,
    current_user: User = Depends(get_current_super_admin_user),
):
    """
    Loescht ein Backup.

    Entfernt sowohl die Backup-Datei als auch den Datenbank-Eintrag.
    """
    success = await backup_service.delete_backup(backup_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup nicht gefunden oder konnte nicht geloescht werden"
        )

    return {"success": True, "message": "Backup geloescht"}


# =============================================================================
# Backup wiederherstellen
# =============================================================================

@router.post("/restore", response_model=RestoreResult)
async def restore_backup(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_super_admin_user),
):
    """
    Stellt ein Backup aus einer hochgeladenen ZIP-Datei wieder her.

    ACHTUNG: Dies ueberschreibt die aktuellen Daten!
    Vor dem Wiederherstellen wird automatisch ein Backup der
    aktuellen Daten erstellt (.pre-restore Dateien).
    """
    if not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nur ZIP-Dateien werden unterstuetzt"
        )

    # Temporaere Datei erstellen
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        result = await backup_service.restore_backup(tmp_path)

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.message
            )

        return result

    finally:
        # Temp-Datei aufraeumen
        if tmp_path.exists():
            tmp_path.unlink()


@router.post("/restore/{backup_id}", response_model=RestoreResult)
async def restore_backup_by_id(
    backup_id: str,
    current_user: User = Depends(get_current_super_admin_user),
):
    """
    Stellt ein Backup anhand seiner ID wieder her.

    ACHTUNG: Dies ueberschreibt die aktuellen Daten!
    """
    backup_path = await backup_service.get_backup_path(backup_id)

    if not backup_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup nicht gefunden"
        )

    result = await backup_service.restore_backup(backup_path)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.message
        )

    return result


# =============================================================================
# Zeitplan
# =============================================================================

@router.get("/schedule", response_model=ScheduleInfo)
async def get_schedule(
    current_user: User = Depends(get_current_super_admin_user),
):
    """
    Gibt den aktuellen Backup-Zeitplan zurueck.
    """
    return await backup_service.get_schedule()


@router.put("/schedule", response_model=ScheduleInfo)
async def update_schedule(
    schedule: ScheduleInfo,
    current_user: User = Depends(get_current_super_admin_user),
):
    """
    Aktualisiert den Backup-Zeitplan.

    Frequenz-Optionen:
    - daily: Taegliches Backup
    - weekly: Woechentliches Backup (Sonntag)

    Zeit im Format HH:MM (24h).
    """
    success = await backup_service.update_schedule(schedule)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Zeitplan konnte nicht aktualisiert werden"
        )

    # Scheduler neu laden (aktualisiert next_run in der DB)
    await backup_scheduler.reload_schedule()

    # Aktualisierten Zeitplan aus DB zurueckladen (mit next_run)
    return await backup_service.get_schedule()


# =============================================================================
# Retention/Cleanup
# =============================================================================

@router.post("/cleanup")
async def cleanup_old_backups(
    retention_days: int = 7,
    current_user: User = Depends(get_current_super_admin_user),
):
    """
    Loescht alte geplante Backups basierend auf der Aufbewahrungsdauer.

    Nur geplante Backups (is_scheduled=True) werden geloescht.
    Manuell erstellte Backups bleiben erhalten.
    """
    deleted = await backup_service.cleanup_old_backups(retention_days)

    return {
        "success": True,
        "deleted_count": deleted,
        "message": f"{deleted} alte Backups geloescht"
    }
