"""
VM Templates Router - API-Endpunkte für VM-Vorlagen
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.vm_template import (
    VMTemplateCreate,
    VMTemplateUpdate,
    VMTemplateResponse,
    VMTemplateListItem,
)
from app.auth.dependencies import get_current_active_user, get_current_admin_user
from app.services.vm_template_service import get_vm_template_service

router = APIRouter(prefix="/api/terraform/templates/presets", tags=["vm-templates"])


@router.get("", response_model=List[VMTemplateListItem])
async def list_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Alle VM-Vorlagen abrufen"""
    service = get_vm_template_service(db)
    templates = await service.list_templates()
    return [VMTemplateListItem.model_validate(t) for t in templates]


@router.get("/{template_id}", response_model=VMTemplateResponse)
async def get_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Einzelne VM-Vorlage abrufen"""
    service = get_vm_template_service(db)
    template = await service.get_template(template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vorlage nicht gefunden"
        )

    return service.template_to_response(template)


@router.post("", response_model=VMTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: VMTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """Neue VM-Vorlage erstellen (nur Admin)"""
    service = get_vm_template_service(db)
    template = await service.create_template(data, current_user.id)
    return service.template_to_response(template)


@router.put("/{template_id}", response_model=VMTemplateResponse)
async def update_template(
    template_id: int,
    data: VMTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """VM-Vorlage aktualisieren (nur Admin)"""
    service = get_vm_template_service(db)
    template = await service.update_template(template_id, data)
    return service.template_to_response(template)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """VM-Vorlage löschen (nur Admin)"""
    service = get_vm_template_service(db)
    await service.delete_template(template_id)
    return None
