"""
NetBox Router - VLANs und Prefixes verwalten, Import von Proxmox
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_active_user, get_current_admin_user
from app.models.user import User
from app.services.netbox_service import netbox_service
from app.services.proxmox_service import proxmox_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/netbox", tags=["netbox"])


# =============================================================================
# Status Endpoint
# =============================================================================

class NetBoxStatus(BaseModel):
    """NetBox Verbindungsstatus"""
    online: bool
    url: Optional[str] = None
    error: Optional[str] = None


@router.get("/status", response_model=NetBoxStatus)
async def get_netbox_status(
    current_user: User = Depends(get_current_active_user)
):
    """
    Prueft ob NetBox erreichbar ist.
    Wird vom Dashboard fuer den Alert-Banner genutzt.
    """
    try:
        # Versuche VLANs abzurufen als Verbindungstest
        await netbox_service.get_vlans()
        return NetBoxStatus(
            online=True,
            url=netbox_service.base_url if hasattr(netbox_service, 'base_url') else None
        )
    except Exception as e:
        logger.warning(f"NetBox Status-Check fehlgeschlagen: {e}")
        return NetBoxStatus(
            online=False,
            error=str(e)
        )


# =============================================================================
# Schemas
# =============================================================================

class VLANInfo(BaseModel):
    """VLAN-Information aus NetBox"""
    id: int
    name: str
    prefix: Optional[str] = None
    bridge: str


class PrefixInfo(BaseModel):
    """Prefix-Information aus NetBox"""
    prefix: str
    vlan: Optional[int] = None
    description: Optional[str] = None
    utilization: Optional[int] = None


class ProxmoxVLAN(BaseModel):
    """VLAN aus Proxmox-Scan"""
    vlan_id: int
    bridge: str
    nodes: list[str]
    vm_count: int
    exists_in_netbox: bool


class VLANImportItem(BaseModel):
    """Einzelnes VLAN zum Importieren"""
    vlan_id: int
    prefix: Optional[str] = None  # None = kein Prefix erstellen


class VLANImportRequest(BaseModel):
    """Import-Anfrage"""
    vlans: list[VLANImportItem]


class VLANImportResult(BaseModel):
    """Import-Ergebnis"""
    imported: list[int]
    skipped: list[int]
    errors: list[str]


class ProxmoxIP(BaseModel):
    """IP aus Proxmox-Scan"""
    vmid: int
    name: str
    node: str
    ip: str
    status: str
    source: str  # 'guest-agent' | 'cloud-init'
    exists_in_netbox: bool = False
    prefix: Optional[str] = None


class ReleasedIP(BaseModel):
    """Freigegebene IP"""
    ip: str
    description: str
    reason: str


class IPSyncResult(BaseModel):
    """IP-Sync Ergebnis"""
    scanned: int
    created: int
    skipped: int
    released: int = 0
    errors: list[str]
    ips: list[ProxmoxIP]
    released_ips: list[ReleasedIP] = []


class VMInfo(BaseModel):
    """VM-Information mit Sync-Status"""
    vmid: Optional[int] = None
    name: str
    node: Optional[str] = None
    ip_address: Optional[str] = None
    cores: Optional[int] = None
    memory_gb: Optional[float] = None
    disk_gb: Optional[int] = None
    status: str  # 'registered' | 'unregistered' | 'orphaned'
    netbox_vm_id: Optional[int] = None


class VMSyncRequest(BaseModel):
    """Sync-Anfrage für VMs"""
    vmids: list[int]


class VMSyncDetail(BaseModel):
    """Detail für eine synchronisierte VM"""
    vmid: int
    name: str
    status: str  # 'created' | 'updated' | 'error'
    error: Optional[str] = None


class VMSyncResult(BaseModel):
    """VM-Sync Ergebnis"""
    synced: int
    skipped: int
    errors: list[str]
    details: list[VMSyncDetail]


class VMDeleteResult(BaseModel):
    """VM-Lösch Ergebnis"""
    success: bool
    deleted_vm: Optional[str] = None
    released_ip: Optional[str] = None
    error: Optional[str] = None


class VMBatchDeleteRequest(BaseModel):
    """Batch-Delete Anfrage für verwaiste VMs"""
    vm_ids: list[int]


class VMBatchDeleteResult(BaseModel):
    """Batch-Delete Ergebnis"""
    deleted: int
    failed: int
    errors: list[str]
    details: list[VMDeleteResult]


class VMUpdateDetail(BaseModel):
    """Detail für eine aktualisierte VM"""
    vmid: int
    name: str
    status: str  # 'updated' | 'error'
    error: Optional[str] = None


class VMUpdateResult(BaseModel):
    """VM-Update Ergebnis"""
    updated: int
    errors: list[str]
    details: list[VMUpdateDetail]


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/vlans", response_model=list[VLANInfo])
async def get_vlans(
    current_user: User = Depends(get_current_active_user)
):
    """
    Alle VLANs aus NetBox abrufen.
    """
    try:
        vlans = await netbox_service.get_vlans()
        return [VLANInfo(**v) for v in vlans]
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der VLANs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prefixes", response_model=list[PrefixInfo])
async def get_prefixes(
    current_user: User = Depends(get_current_active_user)
):
    """
    Alle Prefixes aus NetBox abrufen.
    """
    try:
        prefixes = await netbox_service.get_prefixes_with_utilization()
        return [PrefixInfo(**p) for p in prefixes]
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der Prefixes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/proxmox-vlans", response_model=list[ProxmoxVLAN])
async def scan_proxmox_vlans(
    current_user: User = Depends(get_current_active_user)
):
    """
    Proxmox-Cluster nach VLANs scannen.

    Findet:
    - Bridges mit VLAN-Namen (vmbr60 -> VLAN 60)
    - VLAN-Tags in VM-Konfigurationen
    """
    try:
        # Proxmox scannen
        proxmox_vlans = await proxmox_service.scan_network_vlans()

        # NetBox VLANs abrufen zum Abgleich
        netbox_vlans = await netbox_service.get_vlans()
        netbox_vlan_ids = {v['id'] for v in netbox_vlans}

        # Ergebnis zusammenstellen
        result = []
        for vlan in proxmox_vlans:
            result.append(ProxmoxVLAN(
                vlan_id=vlan['vlan_id'],
                bridge=vlan['bridge'],
                nodes=vlan['nodes'],
                vm_count=vlan.get('vm_count', 0),
                exists_in_netbox=vlan['vlan_id'] in netbox_vlan_ids
            ))

        return sorted(result, key=lambda x: x.vlan_id)

    except Exception as e:
        logger.error(f"Fehler beim Scannen der Proxmox VLANs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import-vlans", response_model=VLANImportResult)
async def import_vlans(
    request: VLANImportRequest,
    current_user: User = Depends(get_current_admin_user)
):
    """
    VLANs nach NetBox importieren.

    Erfordert Admin-Rechte.
    """
    imported = []
    skipped = []
    errors = []

    for item in request.vlans:
        try:
            # Pruefen ob VLAN bereits existiert
            if await netbox_service.vlan_exists(item.vlan_id):
                skipped.append(item.vlan_id)
                continue

            # VLAN erstellen
            vlan_result = await netbox_service.create_vlan(
                vlan_id=item.vlan_id,
                name=f"VLAN{item.vlan_id}"
            )

            if not vlan_result:
                errors.append(f"VLAN {item.vlan_id}: Erstellung fehlgeschlagen")
                continue

            # Prefix erstellen (wenn angegeben)
            if item.prefix:
                prefix_result = await netbox_service.create_prefix_for_vlan(
                    vlan_id=item.vlan_id,
                    prefix=item.prefix
                )
                if not prefix_result:
                    errors.append(f"VLAN {item.vlan_id}: Prefix-Erstellung fehlgeschlagen")
                    # VLAN wurde trotzdem erstellt
                    imported.append(item.vlan_id)
                    continue

            imported.append(item.vlan_id)
            logger.info(f"VLAN {item.vlan_id} erfolgreich importiert")

        except Exception as e:
            errors.append(f"VLAN {item.vlan_id}: {str(e)}")
            logger.error(f"Fehler beim Import von VLAN {item.vlan_id}: {e}")

    return VLANImportResult(
        imported=imported,
        skipped=skipped,
        errors=errors
    )


@router.post("/sync-ips", response_model=IPSyncResult)
async def sync_ips_from_proxmox(
    current_user: User = Depends(get_current_admin_user)
):
    """
    Scannt Proxmox VMs und synchronisiert IPs nach NetBox.

    - Neue IPs werden in NetBox angelegt
    - Existierende IPs werden uebersprungen
    - Verwaiste IPs (in NetBox aktiv, aber keine VM) werden freigegeben
    - Erfordert Admin-Rechte
    """
    created = 0
    skipped = 0
    released = 0
    errors = []
    result_ips = []
    released_ips = []

    try:
        # 1. Proxmox VMs scannen
        proxmox_ips = await proxmox_service.scan_vm_ips()
        proxmox_ip_set = {vm_ip.get("ip") for vm_ip in proxmox_ips if vm_ip.get("ip")}

        # 2. Prefixes aus NetBox holen fuer Zuordnung
        prefixes = await netbox_service.get_prefixes_with_utilization()

        # 3. Alle aktiven IPs aus NetBox holen
        netbox_active_ips = await netbox_service.get_active_ips()

        # 4. Verwaiste IPs finden und freigeben
        for netbox_ip in netbox_active_ips:
            ip_addr = netbox_ip.get("address")
            if ip_addr and ip_addr not in proxmox_ip_set:
                # IP ist in NetBox aktiv, aber keine VM hat diese IP
                try:
                    await netbox_service.release_ip(ip_addr)
                    released += 1
                    released_ips.append(ReleasedIP(
                        ip=ip_addr,
                        description=netbox_ip.get("description", ""),
                        reason="Keine VM mit dieser IP in Proxmox gefunden",
                    ))
                    logger.info(f"Verwaiste IP {ip_addr} freigegeben")
                except Exception as e:
                    errors.append(f"Release {ip_addr}: {str(e)}")
                    logger.error(f"Fehler beim Freigeben von IP {ip_addr}: {e}")

        # 5. Proxmox IPs verarbeiten (neue anlegen)
        for vm_ip in proxmox_ips:
            ip = vm_ip.get("ip")
            if not ip:
                continue

            # Prefix fuer diese IP finden
            matching_prefix = None
            for prefix in prefixes:
                if _ip_in_prefix(ip, prefix.get("prefix", "")):
                    matching_prefix = prefix.get("prefix")
                    break

            # Pruefen ob IP bereits in NetBox existiert
            try:
                ip_exists = not await netbox_service.check_ip_available(ip)
            except Exception:
                ip_exists = False

            result_ips.append(ProxmoxIP(
                vmid=vm_ip.get("vmid"),
                name=vm_ip.get("name", ""),
                node=vm_ip.get("node", ""),
                ip=ip,
                status=vm_ip.get("status", "unknown"),
                source=vm_ip.get("source", "unknown"),
                exists_in_netbox=ip_exists,
                prefix=matching_prefix,
            ))

            if ip_exists:
                skipped += 1
                continue

            # IP in NetBox anlegen
            try:
                await netbox_service.reserve_ip(
                    ip_address=ip,
                    description=f"{vm_ip.get('name', '')} (VMID: {vm_ip.get('vmid')})",
                    dns_name=vm_ip.get("name", ""),
                )
                # Status auf active setzen (VM laeuft ja)
                if vm_ip.get("status") == "running":
                    await netbox_service.activate_ip(ip)
                created += 1
                logger.info(f"IP {ip} fuer VM {vm_ip.get('name')} in NetBox angelegt")
            except Exception as e:
                errors.append(f"{ip}: {str(e)}")
                logger.error(f"Fehler beim Anlegen von IP {ip}: {e}")

        return IPSyncResult(
            scanned=len(proxmox_ips),
            created=created,
            skipped=skipped,
            released=released,
            errors=errors,
            ips=result_ips,
            released_ips=released_ips,
        )

    except Exception as e:
        logger.error(f"Fehler beim IP-Sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _ip_in_prefix(ip: str, prefix: str) -> bool:
    """Prueft ob eine IP in einem Prefix liegt."""
    import ipaddress
    try:
        ip_obj = ipaddress.ip_address(ip)
        network = ipaddress.ip_network(prefix, strict=False)
        return ip_obj in network
    except Exception:
        return False


# =============================================================================
# VM Sync Endpoints
# =============================================================================

@router.get("/proxmox-vms", response_model=list[VMInfo])
async def scan_proxmox_vms(
    current_user: User = Depends(get_current_active_user)
):
    """
    Scannt Proxmox-Cluster nach VMs und vergleicht mit NetBox.

    Gibt für jede VM den Status zurück:
    - registered: VM in Proxmox UND NetBox
    - unregistered: VM in Proxmox, aber NICHT in NetBox
    - orphaned: VM in NetBox, aber NICHT mehr in Proxmox
    """
    try:
        # 1. Alle VMs aus Proxmox holen
        proxmox_vms = await proxmox_service.scan_vm_ips()

        # 2. Alle VMs aus NetBox holen
        netbox_vms = await netbox_service.get_all_vms()

        # NetBox VMs nach Name indizieren für schnellen Lookup
        netbox_by_name = {vm["name"]: vm for vm in netbox_vms}
        netbox_by_ip = {vm["ip_address"]: vm for vm in netbox_vms if vm.get("ip_address")}

        result = []
        proxmox_names = set()
        proxmox_ips = set()

        # 3. Proxmox VMs verarbeiten
        for pve_vm in proxmox_vms:
            name = pve_vm.get("name", "")
            ip = pve_vm.get("ip")
            proxmox_names.add(name)
            if ip:
                proxmox_ips.add(ip)

            # Prüfen ob VM in NetBox existiert (nach Name oder IP)
            netbox_vm = netbox_by_name.get(name) or (netbox_by_ip.get(ip) if ip else None)

            # Memory von MB zu GB konvertieren
            memory_mb = pve_vm.get("maxmem", 0)
            memory_gb = round(memory_mb / (1024 * 1024 * 1024), 1) if memory_mb else None

            # Disk von Bytes zu GB konvertieren
            disk_bytes = pve_vm.get("maxdisk", 0)
            disk_gb = round(disk_bytes / (1024 * 1024 * 1024)) if disk_bytes else None

            result.append(VMInfo(
                vmid=pve_vm.get("vmid"),
                name=name,
                node=pve_vm.get("node"),
                ip_address=ip,
                cores=pve_vm.get("cpus"),
                memory_gb=memory_gb,
                disk_gb=disk_gb,
                status="registered" if netbox_vm else "unregistered",
                netbox_vm_id=netbox_vm["id"] if netbox_vm else None,
            ))

        # 4. Verwaiste NetBox VMs finden (nicht mehr in Proxmox)
        for netbox_vm in netbox_vms:
            name = netbox_vm["name"]
            ip = netbox_vm.get("ip_address")

            # Prüfen ob in Proxmox vorhanden
            in_proxmox = name in proxmox_names or (ip and ip in proxmox_ips)

            if not in_proxmox:
                # Verwaiste VM
                memory_mb = netbox_vm.get("memory_mb")
                memory_gb = round(memory_mb / 1024, 1) if memory_mb else None

                result.append(VMInfo(
                    vmid=None,  # Nicht mehr in Proxmox
                    name=name,
                    node=None,
                    ip_address=ip,
                    cores=netbox_vm.get("vcpus"),
                    memory_gb=memory_gb,
                    disk_gb=netbox_vm.get("disk_gb"),
                    status="orphaned",
                    netbox_vm_id=netbox_vm["id"],
                ))

        # Nach VMID sortieren (None-Werte ans Ende)
        return sorted(result, key=lambda x: (x.vmid is None, x.vmid or 0))

    except Exception as e:
        logger.error(f"Fehler beim Scannen der Proxmox VMs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync-vms", response_model=VMSyncResult)
async def sync_vms_to_netbox(
    request: VMSyncRequest,
    current_user: User = Depends(get_current_admin_user)
):
    """
    Synchronisiert ausgewählte VMs nach NetBox.

    Erstellt VM-Devices in NetBox und verknüpft IPs.
    Erfordert Admin-Rechte.
    """
    synced = 0
    skipped = 0
    errors = []
    details = []

    try:
        # Alle Proxmox VMs holen für Details
        proxmox_vms = await proxmox_service.scan_vm_ips()
        pve_by_vmid = {vm.get("vmid"): vm for vm in proxmox_vms}

        for vmid in request.vmids:
            pve_vm = pve_by_vmid.get(vmid)

            if not pve_vm:
                errors.append(f"VMID {vmid}: Nicht in Proxmox gefunden")
                details.append(VMSyncDetail(
                    vmid=vmid,
                    name="unknown",
                    status="error",
                    error="Nicht in Proxmox gefunden",
                ))
                continue

            name = pve_vm.get("name", f"vm-{vmid}")
            ip = pve_vm.get("ip")
            node = pve_vm.get("node", "")

            if not ip:
                errors.append(f"VMID {vmid} ({name}): Keine IP-Adresse")
                details.append(VMSyncDetail(
                    vmid=vmid,
                    name=name,
                    status="error",
                    error="Keine IP-Adresse",
                ))
                continue

            # Memory und Disk konvertieren
            memory_mb = pve_vm.get("maxmem", 0)
            memory_mb_int = int(memory_mb / (1024 * 1024)) if memory_mb else 4096

            disk_bytes = pve_vm.get("maxdisk", 0)
            disk_gb = int(disk_bytes / (1024 * 1024 * 1024)) if disk_bytes else 32

            cores = pve_vm.get("cpus", 2)

            try:
                # VM in NetBox synchronisieren
                result = await netbox_service.sync_vm_from_proxmox(
                    name=name,
                    vmid=vmid,
                    ip_address=ip,
                    node=node,
                    vcpus=cores,
                    memory_mb=memory_mb_int,
                    disk_gb=disk_gb,
                )

                if result.get("success"):
                    synced += 1
                    details.append(VMSyncDetail(
                        vmid=vmid,
                        name=name,
                        status="created",
                    ))
                    logger.info(f"VM {name} (VMID: {vmid}) nach NetBox synchronisiert")
                else:
                    error_msg = result.get("error", "Unbekannter Fehler")
                    errors.append(f"VMID {vmid} ({name}): {error_msg}")
                    details.append(VMSyncDetail(
                        vmid=vmid,
                        name=name,
                        status="error",
                        error=error_msg,
                    ))

            except Exception as e:
                errors.append(f"VMID {vmid} ({name}): {str(e)}")
                details.append(VMSyncDetail(
                    vmid=vmid,
                    name=name,
                    status="error",
                    error=str(e),
                ))
                logger.error(f"Fehler beim Sync von VM {name}: {e}")

        return VMSyncResult(
            synced=synced,
            skipped=skipped,
            errors=errors,
            details=details,
        )

    except Exception as e:
        logger.error(f"Fehler beim VM-Sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/vms/{vm_id}", response_model=VMDeleteResult)
async def delete_orphaned_vm(
    vm_id: int,
    current_user: User = Depends(get_current_admin_user)
):
    """
    Löscht eine verwaiste VM aus NetBox.

    Gibt auch die verknüpfte IP-Adresse frei.
    Erfordert Admin-Rechte.
    """
    try:
        result = await netbox_service.delete_vm_by_id(vm_id)

        if result.get("success"):
            logger.info(f"Verwaiste VM {result.get('deleted_vm')} aus NetBox gelöscht")
        else:
            logger.warning(f"Löschen von VM {vm_id} fehlgeschlagen: {result.get('error')}")

        return VMDeleteResult(
            success=result.get("success", False),
            deleted_vm=result.get("deleted_vm"),
            released_ip=result.get("released_ip"),
            error=result.get("error"),
        )

    except Exception as e:
        logger.error(f"Fehler beim Löschen von VM {vm_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete-vms", response_model=VMBatchDeleteResult)
async def delete_orphaned_vms_batch(
    request: VMBatchDeleteRequest,
    current_user: User = Depends(get_current_admin_user)
):
    """
    Löscht mehrere verwaiste VMs aus NetBox.

    Gibt für jede VM das Ergebnis zurück.
    Erfordert Admin-Rechte.
    """
    deleted = 0
    failed = 0
    errors = []
    details = []

    for vm_id in request.vm_ids:
        try:
            result = await netbox_service.delete_vm_by_id(vm_id)

            if result.get("success"):
                deleted += 1
                logger.info(f"Verwaiste VM {result.get('deleted_vm')} gelöscht")
            else:
                failed += 1
                errors.append(f"VM {vm_id}: {result.get('error')}")

            details.append(VMDeleteResult(
                success=result.get("success", False),
                deleted_vm=result.get("deleted_vm"),
                released_ip=result.get("released_ip"),
                error=result.get("error"),
            ))

        except Exception as e:
            failed += 1
            errors.append(f"VM {vm_id}: {str(e)}")
            details.append(VMDeleteResult(
                success=False,
                error=str(e),
            ))
            logger.error(f"Fehler beim Löschen von VM {vm_id}: {e}")

    return VMBatchDeleteResult(
        deleted=deleted,
        failed=failed,
        errors=errors,
        details=details,
    )


@router.post("/update-vms", response_model=VMUpdateResult)
async def update_vms_in_netbox(
    request: VMSyncRequest,  # Gleiche Request-Struktur wie sync
    current_user: User = Depends(get_current_admin_user)
):
    """
    Aktualisiert bestehende VMs in NetBox mit aktuellen Proxmox-Specs.

    Holt CPU/RAM/Disk aus Proxmox und aktualisiert die NetBox-Einträge.
    Erfordert Admin-Rechte.
    """
    updated = 0
    errors = []
    details = []

    try:
        # Alle Proxmox VMs holen für Details
        proxmox_vms = await proxmox_service.scan_vm_ips()
        pve_by_vmid = {vm.get("vmid"): vm for vm in proxmox_vms}

        # NetBox VMs für ID-Lookup
        netbox_vms = await netbox_service.get_all_vms()
        netbox_by_name = {vm["name"]: vm for vm in netbox_vms}

        for vmid in request.vmids:
            pve_vm = pve_by_vmid.get(vmid)

            if not pve_vm:
                errors.append(f"VMID {vmid}: Nicht in Proxmox gefunden")
                details.append(VMUpdateDetail(
                    vmid=vmid,
                    name="unknown",
                    status="error",
                    error="Nicht in Proxmox gefunden",
                ))
                continue

            name = pve_vm.get("name", f"vm-{vmid}")

            # NetBox VM-ID finden
            netbox_vm = netbox_by_name.get(name)
            if not netbox_vm:
                errors.append(f"VMID {vmid} ({name}): Nicht in NetBox gefunden")
                details.append(VMUpdateDetail(
                    vmid=vmid,
                    name=name,
                    status="error",
                    error="Nicht in NetBox gefunden",
                ))
                continue

            netbox_vm_id = netbox_vm["id"]

            # Specs aus Proxmox extrahieren
            memory_bytes = pve_vm.get("maxmem", 0)
            memory_mb = int(memory_bytes / (1024 * 1024)) if memory_bytes else 4096

            disk_bytes = pve_vm.get("maxdisk", 0)
            disk_gb = int(disk_bytes / (1024 * 1024 * 1024)) if disk_bytes else 32

            cores = pve_vm.get("cpus", 2)

            try:
                result = await netbox_service.update_vm(
                    vm_id=netbox_vm_id,
                    vcpus=cores,
                    memory_mb=memory_mb,
                    disk_gb=disk_gb,
                )

                if result.get("success"):
                    updated += 1
                    details.append(VMUpdateDetail(
                        vmid=vmid,
                        name=name,
                        status="updated",
                    ))
                    logger.info(f"VM {name} in NetBox aktualisiert: {cores} vCPU, {memory_mb} MB, {disk_gb} GB")
                else:
                    error_msg = result.get("error", "Unbekannter Fehler")
                    errors.append(f"VMID {vmid} ({name}): {error_msg}")
                    details.append(VMUpdateDetail(
                        vmid=vmid,
                        name=name,
                        status="error",
                        error=error_msg,
                    ))

            except Exception as e:
                errors.append(f"VMID {vmid} ({name}): {str(e)}")
                details.append(VMUpdateDetail(
                    vmid=vmid,
                    name=name,
                    status="error",
                    error=str(e),
                ))
                logger.error(f"Fehler beim Update von VM {name}: {e}")

        return VMUpdateResult(
            updated=updated,
            errors=errors,
            details=details,
        )

    except Exception as e:
        logger.error(f"Fehler beim VM-Update: {e}")
        raise HTTPException(status_code=500, detail=str(e))
