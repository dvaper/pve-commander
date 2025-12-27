"""
Cloud-Init Router - API-Endpunkte fuer Cloud-Init Verwaltung und Callbacks
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.auth import get_current_user
from app.models.user import User
from app.schemas.cloud_init import (
    CloudInitProfile,
    CloudInitProfileInfo,
    CloudInitCallbackRequest,
    CloudInitCallbackResponse,
    CLOUD_INIT_PROFILES,
)
from app.services.cloud_init_service import cloud_init_service

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cloud-init", tags=["cloud-init"])

# In-Memory Storage fuer Callbacks (kann spaeter in DB verschoben werden)
_cloud_init_callbacks: List[dict] = []
MAX_CALLBACKS = 100  # Maximale Anzahl gespeicherter Callbacks


# ========== Profile Endpoints ==========

@router.get("/profiles", response_model=List[CloudInitProfileInfo])
async def list_profiles(
    current_user: User = Depends(get_current_user),
):
    """Liste aller verfuegbaren Cloud-Init Profile"""
    profiles = cloud_init_service.get_profiles()
    return [CloudInitProfileInfo(**p) for p in profiles]


@router.get("/profiles/{profile_id}", response_model=CloudInitProfileInfo)
async def get_profile(
    profile_id: str,
    current_user: User = Depends(get_current_user),
):
    """Details zu einem spezifischen Profil"""
    profile = cloud_init_service.get_profile_info(profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profil '{profile_id}' nicht gefunden"
        )
    return CloudInitProfileInfo(**profile)


@router.post("/generate")
async def generate_cloud_init(
    request: Request,
    hostname: str,
    profile: str = "basic",
    additional_packages: Optional[List[str]] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generiert Cloud-Init User-Data fuer ein Profil.

    Args:
        hostname: Hostname der VM
        profile: Profil-ID (default: basic)
        additional_packages: Zusaetzliche Pakete
    """
    try:
        profile_enum = CloudInitProfile(profile)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ungueltiges Profil: {profile}"
        )

    # Request-Host fuer auto-generierte Phone-Home URL
    request_host = request.headers.get("host")

    user_data = await cloud_init_service.generate_user_data(
        profile=profile_enum,
        hostname=hostname,
        db=db,
        request_host=request_host,
        additional_packages=additional_packages,
    )

    return {
        "hostname": hostname,
        "profile": profile,
        "user_data": user_data,
    }


# ========== Callback Endpoints ==========

@router.post("/callback", response_model=CloudInitCallbackResponse)
async def cloud_init_callback(
    request: Request,
    callback_data: CloudInitCallbackRequest,
):
    """
    Phone-Home Callback von Cloud-Init.

    Dieser Endpoint wird von VMs aufgerufen, wenn Cloud-Init abgeschlossen ist.
    Erfordert keine Authentifizierung (wird von VMs waehrend Boot aufgerufen).
    """
    global _cloud_init_callbacks

    # Client IP ermitteln
    client_ip = request.client.host if request.client else "unknown"

    # Callback-Daten speichern
    callback_entry = {
        "hostname": callback_data.hostname,
        "instance_id": callback_data.instance_id,
        "ip_address": callback_data.ip_address or client_ip,
        "fqdn": callback_data.fqdn,
        "status": callback_data.status,
        "timestamp": callback_data.timestamp or datetime.now().isoformat(),
        "received_at": datetime.now().isoformat(),
        "client_ip": client_ip,
        "pub_key_ecdsa": callback_data.pub_key_ecdsa,
        "pub_key_ed25519": callback_data.pub_key_ed25519,
    }

    # Zur Liste hinzufuegen (neueste zuerst)
    _cloud_init_callbacks.insert(0, callback_entry)

    # Alte Eintraege entfernen
    if len(_cloud_init_callbacks) > MAX_CALLBACKS:
        _cloud_init_callbacks = _cloud_init_callbacks[:MAX_CALLBACKS]

    logger.info(
        f"Cloud-Init callback received: hostname={callback_data.hostname}, "
        f"ip={callback_data.ip_address or client_ip}, status={callback_data.status}"
    )

    # VM-Name aus Hostname ableiten (falls FQDN)
    vm_name = callback_data.hostname.split(".")[0] if callback_data.hostname else None

    return CloudInitCallbackResponse(
        success=True,
        message=f"Callback fuer '{callback_data.hostname}' erfolgreich empfangen",
        vm_name=vm_name,
    )


@router.get("/callbacks")
async def list_callbacks(
    limit: int = 50,
    hostname: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """
    Liste aller empfangenen Cloud-Init Callbacks.

    Args:
        limit: Maximale Anzahl zurueckgegebener Eintraege
        hostname: Optional: Nach Hostname filtern
    """
    callbacks = _cloud_init_callbacks

    if hostname:
        callbacks = [c for c in callbacks if hostname.lower() in c.get("hostname", "").lower()]

    return {
        "total": len(_cloud_init_callbacks),
        "filtered": len(callbacks),
        "callbacks": callbacks[:limit],
    }


@router.get("/callbacks/latest/{hostname}")
async def get_latest_callback(
    hostname: str,
    current_user: User = Depends(get_current_user),
):
    """
    Holt den letzten Callback fuer einen bestimmten Hostname.

    Args:
        hostname: Hostname oder VM-Name
    """
    for callback in _cloud_init_callbacks:
        cb_hostname = callback.get("hostname", "")
        if hostname.lower() in cb_hostname.lower() or cb_hostname.lower().startswith(hostname.lower()):
            return callback

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Kein Callback fuer '{hostname}' gefunden"
    )


@router.delete("/callbacks")
async def clear_callbacks(
    current_user: User = Depends(get_current_user),
):
    """Loescht alle gespeicherten Callbacks (nur Super-Admin)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nur Super-Admin kann Callbacks loeschen"
        )

    global _cloud_init_callbacks
    count = len(_cloud_init_callbacks)
    _cloud_init_callbacks = []

    return {"message": f"{count} Callbacks geloescht"}


# ========== VM Ready Check ==========

@router.get("/vm-ready/{hostname}")
async def check_vm_ready(
    hostname: str,
    timeout_minutes: int = 10,
    current_user: User = Depends(get_current_user),
):
    """
    Prueft ob eine VM bereit ist (Cloud-Init abgeschlossen).

    Args:
        hostname: Hostname oder VM-Name
        timeout_minutes: Maximales Alter des Callbacks in Minuten

    Returns:
        ready: True wenn Callback vorhanden und nicht aelter als timeout_minutes
    """
    for callback in _cloud_init_callbacks:
        cb_hostname = callback.get("hostname", "")
        if hostname.lower() in cb_hostname.lower() or cb_hostname.lower().startswith(hostname.lower()):
            # Alter pruefen
            received_at = callback.get("received_at")
            if received_at:
                try:
                    received_time = datetime.fromisoformat(received_at)
                    age_minutes = (datetime.now() - received_time).total_seconds() / 60

                    return {
                        "ready": age_minutes <= timeout_minutes,
                        "hostname": cb_hostname,
                        "ip_address": callback.get("ip_address"),
                        "status": callback.get("status"),
                        "age_minutes": round(age_minutes, 1),
                        "received_at": received_at,
                    }
                except (ValueError, TypeError):
                    pass

            return {
                "ready": True,
                "hostname": cb_hostname,
                "ip_address": callback.get("ip_address"),
                "status": callback.get("status"),
                "received_at": received_at,
            }

    return {
        "ready": False,
        "hostname": hostname,
        "message": "Kein Callback empfangen",
    }
