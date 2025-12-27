"""
Inventory Router - Hosts und Gruppen aus hosts.yml

Berechtigungsfilterung:
- Super-Admins sehen alle Gruppen und Hosts
- Reguläre User sehen nur zugewiesene Gruppen und deren Hosts

Schreiboperationen (nur Super-Admin):
- Gruppen erstellen/umbenennen/löschen
- Hosts zu Gruppen hinzufügen/entfernen
- Git-Historie und Rollback
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from app.auth.dependencies import get_current_active_user
from app.models.user import User
from app.schemas.inventory import (
    HostInfo,
    GroupInfo,
    InventoryTree,
    GroupCreate,
    GroupRename,
    HostGroupAssignment,
    ValidationResult,
    InventoryChange,
    InventoryHistoryResponse,
    InventoryOperationResponse,
)
from app.services.inventory_parser import InventoryParser
from app.services.inventory_editor import get_inventory_editor, InventoryEditor
from app.services.permission_service import get_permission_service
from app.config import settings

router = APIRouter(prefix="/api/inventory", tags=["inventory"])

# Parser als Singleton
_parser = None


def get_parser() -> InventoryParser:
    """Gibt den Inventory-Parser zurück"""
    global _parser
    if _parser is None:
        _parser = InventoryParser(settings.ansible_inventory_path)
    return _parser


@router.get("/hosts", response_model=List[HostInfo])
async def get_hosts(
    current_user: User = Depends(get_current_active_user),
    parser: InventoryParser = Depends(get_parser),
):
    """
    Alle Hosts aus dem Inventory.

    Gefiltert nach Berechtigungen:
    - Super-Admin: Alle Hosts
    - Regulärer User: Nur Hosts aus zugewiesenen Gruppen
    """
    perm_service = get_permission_service(current_user)
    all_hosts = parser.get_hosts()

    # Super-Admin sieht alles
    if perm_service.is_super_admin:
        return all_hosts

    # Nur Hosts aus zugänglichen Gruppen
    accessible_groups = perm_service.get_accessible_groups()
    return [
        host for host in all_hosts
        if any(group in accessible_groups for group in host.groups)
    ]


@router.get("/groups", response_model=List[GroupInfo])
async def get_groups(
    current_user: User = Depends(get_current_active_user),
    parser: InventoryParser = Depends(get_parser),
):
    """
    Alle Gruppen aus dem Inventory.

    Gefiltert nach Berechtigungen:
    - Super-Admin: Alle Gruppen
    - Regulärer User: Nur zugewiesene Gruppen
    """
    perm_service = get_permission_service(current_user)
    all_groups = parser.get_groups()

    # Super-Admin sieht alles
    if perm_service.is_super_admin:
        return all_groups

    # Nur zugängliche Gruppen
    accessible_groups = perm_service.get_accessible_groups()
    return [
        group for group in all_groups
        if group.name in accessible_groups
    ]


@router.get("/tree", response_model=InventoryTree)
async def get_tree(
    current_user: User = Depends(get_current_active_user),
    parser: InventoryParser = Depends(get_parser),
):
    """
    Hierarchische Inventory-Struktur.

    Gefiltert nach Berechtigungen.
    """
    perm_service = get_permission_service(current_user)
    tree = parser.get_tree()

    # Super-Admin sieht alles
    if perm_service.is_super_admin:
        return tree

    # Filtern: Nur zugängliche Gruppen
    accessible_groups = perm_service.get_accessible_groups()
    filtered_groups = [
        group for group in tree.groups
        if group.name in accessible_groups
    ]

    return InventoryTree(groups=filtered_groups)


@router.get("/hosts/{host_name}", response_model=HostInfo)
async def get_host(
    host_name: str,
    current_user: User = Depends(get_current_active_user),
    parser: InventoryParser = Depends(get_parser),
):
    """Einzelner Host (mit Berechtigungsprüfung)"""
    perm_service = get_permission_service(current_user)
    host = parser.get_host(host_name)

    if not host:
        raise HTTPException(status_code=404, detail=f"Host '{host_name}' nicht gefunden")

    # Berechtigungsprüfung (wenn nicht Super-Admin)
    if not perm_service.is_super_admin:
        if not perm_service.can_access_any_group(host.groups):
            raise HTTPException(status_code=403, detail="Keine Berechtigung für diesen Host")

    return host


@router.get("/groups/{group_name}", response_model=GroupInfo)
async def get_group(
    group_name: str,
    current_user: User = Depends(get_current_active_user),
    parser: InventoryParser = Depends(get_parser),
):
    """Einzelne Gruppe (mit Berechtigungsprüfung)"""
    perm_service = get_permission_service(current_user)
    group = parser.get_group(group_name)

    if not group:
        raise HTTPException(status_code=404, detail=f"Gruppe '{group_name}' nicht gefunden")

    # Berechtigungsprüfung (wenn nicht Super-Admin)
    if not perm_service.is_super_admin:
        if not perm_service.can_access_group(group_name):
            raise HTTPException(status_code=403, detail="Keine Berechtigung für diese Gruppe")

    return group


@router.post("/reload")
async def reload_inventory(
    current_user: User = Depends(get_current_active_user),
    parser: InventoryParser = Depends(get_parser),
):
    """Inventory neu laden"""
    parser.reload()
    return {"message": "Inventory neu geladen", "hosts_count": len(parser.get_hosts())}


# ========================================
# Schreib-Operationen (nur Super-Admin)
# ========================================

def require_super_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """Dependency: Nur Super-Admin erlaubt"""
    perm_service = get_permission_service(current_user)
    if not perm_service.is_super_admin:
        raise HTTPException(
            status_code=403,
            detail="Nur Super-Admins können das Inventory bearbeiten"
        )
    return current_user


def get_editor() -> InventoryEditor:
    """Gibt den Inventory-Editor zurück"""
    return get_inventory_editor(settings.ansible_inventory_path)


# ========================================
# Gruppen-Management
# ========================================

@router.post("/groups", response_model=InventoryOperationResponse)
async def create_group(
    data: GroupCreate,
    current_user: User = Depends(require_super_admin),
    editor: InventoryEditor = Depends(get_editor),
    parser: InventoryParser = Depends(get_parser),
):
    """
    Neue Gruppe erstellen.

    - Nur Super-Admin
    - Validierung und Git-Backup
    """
    # Gruppe erstellen
    success, message = editor.create_group(data.name, data.parent)
    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Speichern mit Git-Commit
    save_success, save_message = editor.save(
        commit_message=f"Gruppe '{data.name}' erstellt",
        username=current_user.username
    )
    if not save_success:
        raise HTTPException(status_code=500, detail=save_message)

    # Parser neu laden
    parser.reload()

    return InventoryOperationResponse(
        success=True,
        message=f"Gruppe '{data.name}' erstellt",
        details=save_message
    )


@router.put("/groups/{group_name}", response_model=InventoryOperationResponse)
async def rename_group(
    group_name: str,
    data: GroupRename,
    current_user: User = Depends(require_super_admin),
    editor: InventoryEditor = Depends(get_editor),
    parser: InventoryParser = Depends(get_parser),
):
    """
    Gruppe umbenennen.

    - Nur Super-Admin
    - Validierung und Git-Backup
    """
    # Gruppe umbenennen
    success, message = editor.rename_group(group_name, data.new_name)
    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Speichern mit Git-Commit
    save_success, save_message = editor.save(
        commit_message=f"Gruppe '{group_name}' in '{data.new_name}' umbenannt",
        username=current_user.username
    )
    if not save_success:
        raise HTTPException(status_code=500, detail=save_message)

    # Parser neu laden
    parser.reload()

    return InventoryOperationResponse(
        success=True,
        message=f"Gruppe '{group_name}' in '{data.new_name}' umbenannt",
        details=save_message
    )


@router.delete("/groups/{group_name}", response_model=InventoryOperationResponse)
async def delete_group(
    group_name: str,
    current_user: User = Depends(require_super_admin),
    editor: InventoryEditor = Depends(get_editor),
    parser: InventoryParser = Depends(get_parser),
):
    """
    Gruppe löschen.

    - Nur Super-Admin
    - Geschützte Gruppen können nicht gelöscht werden
    - Validierung und Git-Backup
    """
    # Gruppe löschen
    success, message = editor.delete_group(group_name)
    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Speichern mit Git-Commit
    save_success, save_message = editor.save(
        commit_message=f"Gruppe '{group_name}' gelöscht",
        username=current_user.username
    )
    if not save_success:
        raise HTTPException(status_code=500, detail=save_message)

    # Parser neu laden
    parser.reload()

    return InventoryOperationResponse(
        success=True,
        message=f"Gruppe '{group_name}' gelöscht",
        details=save_message
    )


# ========================================
# Host-Zuordnung
# ========================================

@router.post("/groups/{group_name}/hosts", response_model=InventoryOperationResponse)
async def add_host_to_group(
    group_name: str,
    data: HostGroupAssignment,
    current_user: User = Depends(require_super_admin),
    editor: InventoryEditor = Depends(get_editor),
    parser: InventoryParser = Depends(get_parser),
):
    """
    Host zu einer Gruppe hinzufügen.

    - Nur Super-Admin
    - Host muss bereits im Inventory existieren
    """
    # Host hinzufügen
    success, message = editor.add_host_to_group(data.host_name, group_name)
    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Speichern mit Git-Commit
    save_success, save_message = editor.save(
        commit_message=f"Host '{data.host_name}' zu Gruppe '{group_name}' hinzugefügt",
        username=current_user.username
    )
    if not save_success:
        raise HTTPException(status_code=500, detail=save_message)

    # Parser neu laden
    parser.reload()

    return InventoryOperationResponse(
        success=True,
        message=f"Host '{data.host_name}' zu Gruppe '{group_name}' hinzugefügt",
        details=save_message
    )


@router.delete("/groups/{group_name}/hosts/{host_name}", response_model=InventoryOperationResponse)
async def remove_host_from_group(
    group_name: str,
    host_name: str,
    current_user: User = Depends(require_super_admin),
    editor: InventoryEditor = Depends(get_editor),
    parser: InventoryParser = Depends(get_parser),
):
    """
    Host aus einer Gruppe entfernen.

    - Nur Super-Admin
    - Host bleibt im Inventory (in anderen Gruppen)
    """
    # Host entfernen
    success, message = editor.remove_host_from_group(host_name, group_name)
    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Speichern mit Git-Commit
    save_success, save_message = editor.save(
        commit_message=f"Host '{host_name}' aus Gruppe '{group_name}' entfernt",
        username=current_user.username
    )
    if not save_success:
        raise HTTPException(status_code=500, detail=save_message)

    # Parser neu laden
    parser.reload()

    return InventoryOperationResponse(
        success=True,
        message=f"Host '{host_name}' aus Gruppe '{group_name}' entfernt",
        details=save_message
    )


@router.get("/hosts/{host_name}/groups", response_model=List[str])
async def get_host_groups(
    host_name: str,
    current_user: User = Depends(get_current_active_user),
    editor: InventoryEditor = Depends(get_editor),
):
    """Gibt alle Gruppen zurück, in denen ein Host ist"""
    groups = editor.get_host_groups(host_name)
    if not groups:
        raise HTTPException(status_code=404, detail=f"Host '{host_name}' nicht gefunden")
    return groups


# ========================================
# Git-Historie und Rollback
# ========================================

@router.get("/history", response_model=InventoryHistoryResponse)
async def get_history(
    limit: int = 20,
    current_user: User = Depends(require_super_admin),
    editor: InventoryEditor = Depends(get_editor),
):
    """
    Git-Historie der Inventory-Änderungen.

    - Nur Super-Admin
    """
    commits = editor.get_git_history(limit=limit)
    return InventoryHistoryResponse(
        commits=[
            InventoryChange(
                commit_hash=c["commit_hash"],
                author=c["author"],
                email=c.get("email"),
                timestamp=c["timestamp"],
                message=c["message"],
            )
            for c in commits
        ],
        total=len(commits)
    )


@router.post("/rollback/{commit_hash}", response_model=InventoryOperationResponse)
async def rollback_to_commit(
    commit_hash: str,
    current_user: User = Depends(require_super_admin),
    editor: InventoryEditor = Depends(get_editor),
    parser: InventoryParser = Depends(get_parser),
):
    """
    Inventory auf eine bestimmte Version zurücksetzen.

    - Nur Super-Admin
    - Erstellt neuen Commit mit der wiederhergestellten Version
    """
    # Version wiederherstellen
    success, message = editor.git_restore_commit(commit_hash)
    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Speichern mit Git-Commit
    save_success, save_message = editor.save(
        commit_message=f"Rollback auf Version {commit_hash[:8]}",
        username=current_user.username
    )
    if not save_success:
        raise HTTPException(status_code=500, detail=save_message)

    # Parser neu laden
    parser.reload()

    return InventoryOperationResponse(
        success=True,
        message=f"Rollback auf Version {commit_hash[:8]} durchgeführt",
        details=save_message
    )


@router.post("/validate", response_model=ValidationResult)
async def validate_inventory(
    current_user: User = Depends(require_super_admin),
    editor: InventoryEditor = Depends(get_editor),
):
    """
    Aktuelles Inventory validieren.

    - YAML-Syntax prüfen
    - Ansible-Inventory-Check
    """
    errors = []
    warnings = []

    # YAML-Validierung
    yaml_valid, yaml_error = editor.validate_yaml()
    if not yaml_valid:
        errors.append(f"YAML: {yaml_error}")

    # Ansible-Validierung
    ansible_valid, ansible_error = editor.validate_ansible()
    if not ansible_valid:
        errors.append(f"Ansible: {ansible_error}")
    elif ansible_error:
        warnings.append(ansible_error)

    return ValidationResult(
        valid=yaml_valid and ansible_valid,
        yaml_valid=yaml_valid,
        ansible_valid=ansible_valid,
        errors=errors,
        warnings=warnings,
    )


@router.post("/sync", response_model=InventoryOperationResponse)
async def sync_inventory(
    current_user: User = Depends(require_super_admin),
    editor: InventoryEditor = Depends(get_editor),
    parser: InventoryParser = Depends(get_parser),
):
    """
    Synchronisiert das Inventory mit Proxmox-Nodes.

    - Erstellt Gruppen für jeden Proxmox-Node (pve_pve-node-01, pve_pve-node-02, etc.)
    - Weist Hosts basierend auf ihrem pve_node Attribut zu
    - Nur Super-Admin
    """
    # Inventory neu laden
    editor.load()

    # Sync durchführen
    success, message, details = editor.sync_proxmox_node_groups()
    if not success:
        raise HTTPException(status_code=500, detail=message)

    # Nur speichern wenn Änderungen vorhanden
    if details.get("created") or details.get("updated"):
        save_success, save_message = editor.save(
            commit_message=f"Sync: {message}",
            username=current_user.username
        )
        if not save_success:
            raise HTTPException(status_code=500, detail=save_message)

        # Parser neu laden
        parser.reload()

    return InventoryOperationResponse(
        success=True,
        message=message or "Inventory synchronisiert",
        details=str(details) if details else None
    )


@router.post("/sync-vms", response_model=InventoryOperationResponse)
async def sync_vms_from_proxmox(
    current_user: User = Depends(require_super_admin),
):
    """
    Synchronisiert VMs aus Proxmox in das Inventory.

    - Holt alle VMs aus dem Proxmox-Cluster
    - Fügt fehlende VMs zum Inventory hinzu (Gruppe: proxmox_discovered)
    - Extrahiert IP-Adressen aus Cloud-Init Konfiguration
    - Nur Super-Admin
    """
    import json
    import logging

    logger = logging.getLogger(__name__)

    try:
        from app.services.inventory_sync_service import get_sync_service

        sync_service = get_sync_service()
        success, message, details = await sync_service.sync_from_proxmox()

        if not success:
            raise HTTPException(status_code=500, detail=message)

        return InventoryOperationResponse(
            success=True,
            message=message,
            details=json.dumps(details) if details else None
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.exception("Fehler beim Proxmox-Sync")
        raise HTTPException(
            status_code=500,
            detail=f"Sync fehlgeschlagen: {str(e)}. Proxmox-Cluster moeglicherweise nicht vollstaendig verfuegbar."
        )


@router.get("/sync-status")
async def get_sync_status(
    current_user: User = Depends(require_super_admin),
):
    """
    Gibt den Status des Background-Sync zurück.

    - Zeigt ob Sync läuft
    - Letzter Sync-Zeitpunkt
    - Sync-Intervall
    """
    from app.services.inventory_sync_service import get_sync_service

    sync_service = get_sync_service()
    return sync_service.get_status()


@router.post("/sync-background/start")
async def start_background_sync(
    current_user: User = Depends(require_super_admin),
):
    """
    Startet den automatischen Background-Sync.

    - Synchronisiert Proxmox VMs periodisch ins Inventory
    - Intervall ist konfigurierbar
    - Nur Super-Admin
    """
    from app.services.inventory_sync_service import get_sync_service

    sync_service = get_sync_service()
    await sync_service.start_background_sync()
    return {
        "success": True,
        "message": f"Background-Sync gestartet (Intervall: {sync_service.sync_interval_seconds}s)",
        "status": sync_service.get_status()
    }


@router.post("/sync-background/stop")
async def stop_background_sync(
    current_user: User = Depends(require_super_admin),
):
    """
    Stoppt den automatischen Background-Sync.

    - Nur Super-Admin
    """
    from app.services.inventory_sync_service import get_sync_service

    sync_service = get_sync_service()
    await sync_service.stop_background_sync()
    return {
        "success": True,
        "message": "Background-Sync gestoppt",
        "status": sync_service.get_status()
    }


@router.patch("/sync-settings")
async def update_sync_settings(
    interval_seconds: int = 300,
    current_user: User = Depends(require_super_admin),
):
    """
    Konfiguriert die Sync-Einstellungen.

    - interval_seconds: Sync-Intervall in Sekunden (min. 60, max. 3600)
    - Nur Super-Admin
    """
    from app.services.inventory_sync_service import get_sync_service

    # Validierung
    if interval_seconds < 60:
        raise HTTPException(status_code=400, detail="Intervall muss mindestens 60 Sekunden sein")
    if interval_seconds > 3600:
        raise HTTPException(status_code=400, detail="Intervall darf maximal 3600 Sekunden (1 Stunde) sein")

    sync_service = get_sync_service()
    sync_service.sync_interval_seconds = interval_seconds

    return {
        "success": True,
        "message": f"Sync-Intervall auf {interval_seconds}s gesetzt",
        "status": sync_service.get_status()
    }


@router.get("/vm-status")
async def get_vm_status(
    current_user: User = Depends(get_current_active_user),
):
    """
    Holt den aktuellen Status aller VMs aus Proxmox.

    Gibt ein Dictionary zurück mit VMID als Key und Status-Info als Value.
    Kann mit dem Inventory abgeglichen werden über das vmid-Feld.
    """
    from app.services.proxmox_service import ProxmoxService

    proxmox = ProxmoxService()
    if not proxmox.is_configured():
        return {"configured": False, "vms": {}}

    try:
        vms = await proxmox.get_all_vms()
        # Dictionary mit vmid als Key für schnellen Lookup
        vm_status = {
            str(vm["vmid"]): {
                "status": vm.get("status", "unknown"),
                "name": vm.get("name", ""),
                "node": vm.get("node", ""),
            }
            for vm in vms
        }
        return {"configured": True, "vms": vm_status}
    except Exception as e:
        return {"configured": True, "error": str(e), "vms": {}}
