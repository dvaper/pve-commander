"""
VM Template Service - Verwaltung von VM-Vorlagen
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.vm_template import VMTemplate
from app.models.user import User
from app.schemas.vm_template import VMTemplateCreate, VMTemplateUpdate, VMTemplateResponse


class VMTemplateService:
    """Service für VM-Vorlagen-Verwaltung"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_templates(self) -> List[VMTemplate]:
        """Alle Vorlagen abrufen"""
        result = await self.db.execute(
            select(VMTemplate)
            .options(selectinload(VMTemplate.creator))
            .order_by(VMTemplate.is_default.desc(), VMTemplate.name)
        )
        return list(result.scalars().all())

    async def get_template(self, template_id: int) -> Optional[VMTemplate]:
        """Einzelne Vorlage abrufen"""
        result = await self.db.execute(
            select(VMTemplate)
            .options(selectinload(VMTemplate.creator))
            .where(VMTemplate.id == template_id)
        )
        return result.scalar_one_or_none()

    async def get_template_by_name(self, name: str) -> Optional[VMTemplate]:
        """Vorlage nach Namen suchen"""
        result = await self.db.execute(
            select(VMTemplate).where(VMTemplate.name == name)
        )
        return result.scalar_one_or_none()

    async def create_template(
        self,
        data: VMTemplateCreate,
        user_id: int
    ) -> VMTemplate:
        """Neue Vorlage erstellen"""
        # Prüfen ob Name bereits existiert
        existing = await self.get_template_by_name(data.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vorlage mit Namen '{data.name}' existiert bereits"
            )

        # Wenn is_default=True, andere Default-Vorlagen zurücksetzen
        if data.is_default:
            await self._clear_default_flags()

        template = VMTemplate(
            name=data.name,
            description=data.description,
            cores=data.cores,
            memory_gb=data.memory_gb,
            disk_size_gb=data.disk_size_gb,
            target_node=data.target_node,
            storage=data.storage,
            template_vmid=data.template_vmid,
            vlan=data.vlan,
            ansible_group=data.ansible_group,
            cloud_init_profile=data.cloud_init_profile,
            is_default=data.is_default,
            created_by=user_id,
        )

        self.db.add(template)
        await self.db.commit()
        await self.db.refresh(template)

        # Creator laden für Response
        result = await self.db.execute(
            select(VMTemplate)
            .options(selectinload(VMTemplate.creator))
            .where(VMTemplate.id == template.id)
        )
        return result.scalar_one()

    async def update_template(
        self,
        template_id: int,
        data: VMTemplateUpdate
    ) -> VMTemplate:
        """Vorlage aktualisieren"""
        template = await self.get_template(template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vorlage nicht gefunden"
            )

        # Prüfen ob neuer Name bereits existiert
        if data.name and data.name != template.name:
            existing = await self.get_template_by_name(data.name)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Vorlage mit Namen '{data.name}' existiert bereits"
                )

        # Wenn is_default=True, andere Default-Vorlagen zurücksetzen
        if data.is_default:
            await self._clear_default_flags(exclude_id=template_id)

        # Update nur gesetzte Felder
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(template, key, value)

        await self.db.commit()
        await self.db.refresh(template)

        # Creator neu laden
        result = await self.db.execute(
            select(VMTemplate)
            .options(selectinload(VMTemplate.creator))
            .where(VMTemplate.id == template.id)
        )
        return result.scalar_one()

    async def delete_template(self, template_id: int) -> bool:
        """Vorlage löschen"""
        template = await self.get_template(template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vorlage nicht gefunden"
            )

        await self.db.delete(template)
        await self.db.commit()
        return True

    async def _clear_default_flags(self, exclude_id: Optional[int] = None) -> None:
        """Alle Default-Flags zurücksetzen"""
        result = await self.db.execute(
            select(VMTemplate).where(VMTemplate.is_default == True)
        )
        templates = result.scalars().all()

        for template in templates:
            if exclude_id is None or template.id != exclude_id:
                template.is_default = False

        await self.db.commit()

    def template_to_response(self, template: VMTemplate) -> VMTemplateResponse:
        """Konvertiert VMTemplate zu Response-Schema"""
        return VMTemplateResponse(
            id=template.id,
            name=template.name,
            description=template.description,
            cores=template.cores,
            memory_gb=template.memory_gb,
            disk_size_gb=template.disk_size_gb,
            target_node=template.target_node,
            storage=template.storage,
            template_vmid=template.template_vmid,
            vlan=template.vlan,
            ansible_group=template.ansible_group,
            cloud_init_profile=template.cloud_init_profile,
            is_default=template.is_default,
            created_by=template.created_by,
            created_at=template.created_at,
            updated_at=template.updated_at,
            creator_name=template.creator.username if template.creator else None,
        )


def get_vm_template_service(db: AsyncSession) -> VMTemplateService:
    """Factory-Funktion für VMTemplateService"""
    return VMTemplateService(db)
