"""
Cloud-Init Settings Router - Konfiguration der Cloud-Init Defaults

API-Endpunkte fuer die Verwaltung von Cloud-Init Einstellungen.
Nur fuer Super-Admins zugaenglich.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.auth.dependencies import get_current_super_admin_user
from app.services.cloud_init_settings_service import get_cloud_init_settings_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cloud-init/settings", tags=["cloud-init-settings"])


# ==================== Schemas ====================

class CloudInitSettingsRead(BaseModel):
    """Response-Schema fuer Cloud-Init Settings"""
    ssh_authorized_keys: List[str] = []
    phone_home_enabled: bool = True
    phone_home_url: Optional[str] = None
    admin_username: str = "ansible"
    admin_gecos: str = "Homelab Admin"
    nas_snippets_path: Optional[str] = None
    nas_snippets_ref: Optional[str] = None


class CloudInitSettingsUpdate(BaseModel):
    """Update-Schema fuer Cloud-Init Settings"""
    ssh_authorized_keys: Optional[List[str]] = None
    phone_home_enabled: Optional[bool] = None
    phone_home_url: Optional[str] = Field(
        default=None,
        description="Phone-Home URL. Leer lassen fuer Auto-Generierung aus Request-Host."
    )
    admin_username: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Admin-Benutzername fuer VMs (Default: ansible)"
    )
    admin_gecos: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Admin GECOS-String (z.B. 'Homelab Admin')"
    )
    nas_snippets_path: Optional[str] = Field(
        default=None,
        description="Pfad zum NAS Snippets Verzeichnis (z.B. /mnt/pve/nas/snippets)"
    )
    nas_snippets_ref: Optional[str] = Field(
        default=None,
        description="Proxmox Storage-Referenz (z.B. nas:snippets)"
    )


class SSHKeyAdd(BaseModel):
    """Schema zum Hinzufuegen eines SSH-Keys"""
    key: str = Field(
        ...,
        min_length=10,
        description="SSH Public Key (ssh-ed25519/ssh-rsa ...)"
    )


class SSHKeyRemove(BaseModel):
    """Schema zum Entfernen eines SSH-Keys"""
    key: str = Field(..., description="SSH Public Key zum Entfernen")


# ==================== Endpoints ====================

@router.get("", response_model=CloudInitSettingsRead)
async def get_cloud_init_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_super_admin_user),
):
    """
    Cloud-Init Settings abrufen.

    Nur fuer Super-Admins zugaenglich.
    """
    service = get_cloud_init_settings_service(db)
    settings_dict = await service.get_all_settings_dict()
    return CloudInitSettingsRead(**settings_dict)


@router.put("", response_model=CloudInitSettingsRead)
async def update_cloud_init_settings(
    update: CloudInitSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_super_admin_user),
):
    """
    Cloud-Init Settings aktualisieren.

    Nur angegebene Felder werden aktualisiert.
    Nur fuer Super-Admins zugaenglich.
    """
    service = get_cloud_init_settings_service(db)

    await service.update_settings(
        ssh_keys=update.ssh_authorized_keys,
        phone_home_enabled=update.phone_home_enabled,
        phone_home_url=update.phone_home_url,
        admin_username=update.admin_username,
        admin_gecos=update.admin_gecos,
        nas_snippets_path=update.nas_snippets_path,
        nas_snippets_ref=update.nas_snippets_ref,
    )

    settings_dict = await service.get_all_settings_dict()
    logger.info(f"Cloud-Init Settings aktualisiert von {current_user.username}")
    return CloudInitSettingsRead(**settings_dict)


@router.get("/ssh-keys", response_model=List[str])
async def get_ssh_keys(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_super_admin_user),
):
    """
    SSH Authorized Keys abrufen.

    Nur fuer Super-Admins zugaenglich.
    """
    service = get_cloud_init_settings_service(db)
    return await service.get_ssh_keys()


@router.post("/ssh-keys", response_model=List[str])
async def add_ssh_key(
    key_data: SSHKeyAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_super_admin_user),
):
    """
    SSH-Key hinzufuegen.

    Fuegt einen neuen SSH Public Key zur Liste hinzu.
    Nur fuer Super-Admins zugaenglich.
    """
    # Validierung: Muss mit ssh- beginnen
    key = key_data.key.strip()
    if not key.startswith("ssh-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ungueltiger SSH-Key. Muss mit 'ssh-' beginnen (z.B. ssh-ed25519, ssh-rsa)"
        )

    service = get_cloud_init_settings_service(db)
    keys = await service.add_ssh_key(key)
    logger.info(f"SSH-Key hinzugefuegt von {current_user.username}")
    return keys


@router.delete("/ssh-keys")
async def remove_ssh_key(
    key_data: SSHKeyRemove,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_super_admin_user),
):
    """
    SSH-Key entfernen.

    Entfernt einen SSH Public Key aus der Liste.
    Nur fuer Super-Admins zugaenglich.
    """
    service = get_cloud_init_settings_service(db)
    keys = await service.remove_ssh_key(key_data.key)
    logger.info(f"SSH-Key entfernt von {current_user.username}")
    return {"success": True, "remaining_keys": keys}


@router.get("/phone-home-url")
async def get_phone_home_url(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_super_admin_user),
):
    """
    Aktuelle Phone-Home URL abrufen.

    Zeigt die konfigurierte oder auto-generierte URL.
    """
    service = get_cloud_init_settings_service(db)
    settings = await service.get_settings()

    return {
        "enabled": settings.phone_home_enabled,
        "url": settings.phone_home_url,
        "auto_generate": settings.phone_home_url is None,
    }
