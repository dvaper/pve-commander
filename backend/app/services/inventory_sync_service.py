"""
Inventory Sync Service - Synchronisiert Inventory mit Proxmox

Funktionen:
- Periodische Synchronisation (Background-Task)
- Erkennung neuer VMs aus Proxmox
- Hinzufügen fehlender Hosts zum Inventory
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from app.services.proxmox_service import ProxmoxService
from app.services.inventory_editor import InventoryEditor
from app.services.inventory_parser import InventoryParser
from app.config import settings

logger = logging.getLogger(__name__)


class InventorySyncService:
    """Service für Inventory-Synchronisation mit Proxmox"""

    def __init__(self):
        self.proxmox = ProxmoxService()
        self.last_sync: Optional[datetime] = None
        self.sync_interval_seconds: int = 300  # 5 Minuten
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def sync_from_proxmox(self) -> Tuple[bool, str, dict]:
        """
        Synchronisiert das Inventory mit Proxmox VMs.

        - Holt alle VMs aus Proxmox
        - Vergleicht mit bestehendem Inventory
        - Fügt fehlende VMs hinzu (mit IP aus Proxmox-Config)

        Returns:
            Tuple[bool, str, dict]: (Erfolg, Nachricht, Details)
        """
        details = {
            "proxmox_vms": 0,
            "inventory_hosts": 0,
            "added": [],
            "updated": [],
            "removed": [],
            "skipped": [],
            "errors": []
        }

        # Prüfen ob Proxmox konfiguriert ist
        if not self.proxmox.is_configured():
            return False, "Proxmox API nicht konfiguriert", details

        try:
            # Alle VMs aus Proxmox holen
            proxmox_vms = await self.proxmox.get_all_vms()
            details["proxmox_vms"] = len(proxmox_vms)

            if not proxmox_vms:
                return True, "Keine VMs in Proxmox gefunden", details

            # Inventory laden (erstellen falls nicht vorhanden)
            inventory_path = Path(settings.ansible_inventory_path)
            if not inventory_path.exists():
                logger.info(f"Erstelle initiales Inventory: {inventory_path}")
                inventory_path.parent.mkdir(parents=True, exist_ok=True)
                inventory_path.write_text("---\nall:\n  children:\n    proxmox_discovered:\n      hosts: {}\n")

            editor = InventoryEditor(inventory_path)
            editor.load()

            parser = InventoryParser(settings.ansible_inventory_path)
            existing_hosts = parser.get_hosts()
            existing_hostnames = {h.name for h in existing_hosts}
            # Mapping von Hostname zu aktuellem pve_node
            existing_host_nodes = {h.name: h.pve_node for h in existing_hosts if h.pve_node}
            details["inventory_hosts"] = len(existing_hostnames)

            # VMs vergleichen und fehlende hinzufügen
            for vm in proxmox_vms:
                vm_name = vm.get("name")
                vm_node = vm.get("node")
                vmid = vm.get("vmid")
                vm_status = vm.get("status", "unknown")

                if not vm_name:
                    continue

                # Templates überspringen (VMID >= 900000)
                if vmid and vmid >= 900000:
                    details["skipped"].append({
                        "name": vm_name,
                        "reason": "Template",
                        "vmid": vmid
                    })
                    continue

                # Gestoppte VMs überspringen
                if vm_status != "running":
                    details["skipped"].append({
                        "name": vm_name,
                        "reason": f"Status: {vm_status}",
                        "vmid": vmid
                    })
                    continue

                # Prüfen ob Host bereits existiert
                if vm_name in existing_hostnames:
                    # Pruefen ob pve_node aktualisiert werden muss
                    current_node = existing_host_nodes.get(vm_name)
                    if current_node and current_node != vm_node:
                        # Node hat sich geaendert (VM wurde migriert)
                        success, msg = editor.update_host_var(vm_name, "pve_node", vm_node)
                        if success:
                            details["updated"].append({
                                "name": vm_name,
                                "old_node": current_node,
                                "new_node": vm_node,
                                "vmid": vmid
                            })
                            logger.info(f"VM '{vm_name}' wurde von {current_node} nach {vm_node} migriert - Inventory aktualisiert")
                        else:
                            details["errors"].append(f"{vm_name}: Node-Update fehlgeschlagen: {msg}")
                    else:
                        details["skipped"].append(vm_name)
                    continue

                # IP-Adresse ermitteln (verschiedene Methoden)
                try:
                    ip_address = None
                    ip_source = None

                    # 1. Versuch: QEMU Guest Agent (beste Methode für laufende VMs)
                    if vm_status == "running":
                        agent_result = await self.proxmox.get_vm_agent_network(vmid, vm_node)
                        if agent_result.get("success") and agent_result.get("primary_ip"):
                            ip_address = agent_result["primary_ip"]
                            ip_source = "guest-agent"

                    # 2. Fallback: Cloud-Init Config parsen
                    if not ip_address:
                        vm_config = await self.proxmox.get_vm_config(vmid, vm_node)
                        if vm_config.get("success"):
                            config = vm_config.get("config", {})
                            ip_address = self._extract_ip_from_config(config)
                            if ip_address:
                                ip_source = "cloud-init"

                    # VMs ohne IP überspringen
                    if not ip_address:
                        details["skipped"].append({
                            "name": vm_name,
                            "reason": "Keine IP erkannt (kein Guest Agent / Cloud-Init)",
                            "vmid": vmid,
                            "node": vm_node
                        })
                        continue

                    # Host mit IP hinzufügen
                    host_vars = {
                        "ansible_host": ip_address,
                        "vmid": vmid,
                        "pve_node": vm_node,
                        "ip_source": ip_source,
                    }

                    # In "proxmox_discovered" Gruppe einfügen
                    success, msg = editor.add_host(
                        hostname=vm_name,
                        group="proxmox_discovered",
                        host_vars=host_vars
                    )

                    if success:
                        details["added"].append({
                            "name": vm_name,
                            "ip": ip_address,
                            "ip_source": ip_source,
                            "node": vm_node,
                            "vmid": vmid
                        })
                    else:
                        details["errors"].append(f"{vm_name}: {msg}")

                except Exception as e:
                    details["errors"].append(f"{vm_name}: {str(e)}")

            # Verwaiste Hosts entfernen (in proxmox_discovered aber keine VM mehr)
            proxmox_vm_names = {vm.get("name") for vm in proxmox_vms if vm.get("name")}
            discovered_group = editor._find_group("proxmox_discovered")
            if discovered_group and discovered_group.get("hosts"):
                discovered_hosts = list(discovered_group["hosts"].keys())
                for host_name in discovered_hosts:
                    if host_name not in proxmox_vm_names:
                        # Host ist in Inventory aber VM existiert nicht mehr
                        success, msg = editor.remove_host_from_group(host_name, "proxmox_discovered")
                        if success:
                            details["removed"].append({
                                "name": host_name,
                                "reason": "VM nicht mehr in Proxmox vorhanden"
                            })
                            logger.info(f"Verwaister Host '{host_name}' aus Inventory entfernt")
                        else:
                            details["errors"].append(f"{host_name}: Entfernen fehlgeschlagen: {msg}")

            # Speichern wenn Änderungen vorhanden
            has_changes = details["added"] or details["updated"] or details["removed"]
            if has_changes:
                # Gruppe "proxmox_discovered" erstellen falls nicht vorhanden (nur bei neuen Hosts)
                if details["added"] and not editor._find_group("proxmox_discovered"):
                    editor.create_group("proxmox_discovered", parent="all")

                # Commit-Message erstellen
                commit_parts = []
                if details["added"]:
                    commit_parts.append(f"{len(details['added'])} VM(s) hinzugefuegt")
                if details["updated"]:
                    commit_parts.append(f"{len(details['updated'])} VM(s) migriert")
                if details["removed"]:
                    commit_parts.append(f"{len(details['removed'])} Host(s) entfernt")

                success, msg = editor.save(
                    commit_message=f"Auto-Sync: {', '.join(commit_parts)}",
                    username="system"
                )
                if not success:
                    return False, f"Speichern fehlgeschlagen: {msg}", details

                # Nach Aenderungen auch die Node-Gruppen aktualisieren
                if details["updated"]:
                    editor.load()  # Neu laden nach save
                    sync_success, sync_msg, sync_details = editor.sync_proxmox_node_groups()
                    if sync_success and (sync_details.get("removed") or sync_details.get("updated")):
                        editor.save(
                            commit_message=f"Auto-Sync: Node-Gruppen aktualisiert nach VM-Migration",
                            username="system"
                        )
                        logger.info(f"Node-Gruppen aktualisiert: {sync_msg}")

            self.last_sync = datetime.now()

            # Zusammenfassung erstellen
            msg_parts = []
            if details["added"]:
                msg_parts.append(f"{len(details['added'])} hinzugefuegt")
            if details["updated"]:
                msg_parts.append(f"{len(details['updated'])} migriert")
            if details["removed"]:
                msg_parts.append(f"{len(details['removed'])} entfernt")
            if details["skipped"]:
                msg_parts.append(f"{len(details['skipped'])} uebersprungen")
            if details["errors"]:
                msg_parts.append(f"{len(details['errors'])} Fehler")

            message = ", ".join(msg_parts) if msg_parts else "Keine Aenderungen"
            return True, message, details

        except Exception as e:
            logger.exception("Fehler bei Proxmox-Sync")
            return False, str(e), details

    def _extract_ip_from_config(self, config: dict) -> Optional[str]:
        """
        Extrahiert die IP-Adresse aus einer VM-Konfiguration.

        Sucht in:
        - ipconfig0-9 (Cloud-Init)
        - Notizen/Beschreibung
        """
        # Cloud-Init ipconfig (ipconfig0 bis ipconfig9)
        for i in range(10):
            ipconfig = config.get(f"ipconfig{i}", "")
            if ipconfig and "ip=" in ipconfig:
                # Format: ip=10.0.0.100/24,gw=10.0.0.1
                try:
                    ip_part = ipconfig.split("ip=")[1].split(",")[0]
                    ip_address = ip_part.split("/")[0]  # CIDR entfernen
                    if ip_address and ip_address != "dhcp":
                        return ip_address
                except (IndexError, ValueError):
                    pass

        # Fallback: Versuche IP aus net0 zu parsen (manche Configs haben das)
        for i in range(10):
            net = config.get(f"net{i}", "")
            if net:
                # Manchmal ist die IP im Kommentar/Tag
                import re
                ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', str(net))
                if ip_match:
                    return ip_match.group(1)

        return None

    async def start_background_sync(self):
        """Startet den periodischen Background-Sync"""
        if self._running:
            logger.info("Background-Sync läuft bereits")
            return

        self._running = True
        self._task = asyncio.create_task(self._sync_loop())
        logger.info(f"Background-Sync gestartet (Intervall: {self.sync_interval_seconds}s)")

    async def stop_background_sync(self):
        """Stoppt den periodischen Background-Sync"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Background-Sync gestoppt")

    async def _sync_loop(self):
        """Hauptschleife für periodischen Sync"""
        while self._running:
            try:
                # Warten vor erstem Sync (gibt App Zeit zum Starten)
                await asyncio.sleep(60)  # 1 Minute nach Start

                while self._running:
                    logger.info("Starte automatischen Inventory-Sync...")
                    success, message, details = await self.sync_from_proxmox()

                    if success:
                        if details.get("added"):
                            logger.info(f"Sync erfolgreich: {message}")
                        else:
                            logger.debug(f"Sync: {message}")
                    else:
                        logger.warning(f"Sync fehlgeschlagen: {message}")

                    await asyncio.sleep(self.sync_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Fehler im Sync-Loop: {e}")
                await asyncio.sleep(60)  # Bei Fehler 1 Minute warten

    def get_status(self) -> dict:
        """Gibt den aktuellen Sync-Status zurück"""
        return {
            "running": self._running,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "interval_seconds": self.sync_interval_seconds,
            "proxmox_configured": self.proxmox.is_configured()
        }


# Singleton-Instanz
_sync_service: Optional[InventorySyncService] = None


def get_sync_service() -> InventorySyncService:
    """Gibt die Singleton-Instanz des Sync-Service zurück"""
    global _sync_service
    if _sync_service is None:
        _sync_service = InventorySyncService()
    return _sync_service
