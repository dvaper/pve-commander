"""
Ansible Inventory Service - Verwaltet das Ansible Inventory

Fügt neue VMs nach erfolgreichem Deploy zum Inventory hinzu.
"""
import yaml
from pathlib import Path
from typing import Optional

from app.config import settings


class AnsibleInventoryService:
    """Service für Ansible-Inventory-Management"""

    def __init__(self):
        self.inventory_path = Path(settings.ansible_inventory_path)

    def _load_inventory(self) -> dict:
        """Lädt das Inventory aus der YAML-Datei"""
        if not self.inventory_path.exists():
            raise FileNotFoundError(f"Inventory-Datei nicht gefunden: {self.inventory_path}")

        with open(self.inventory_path, "r") as f:
            return yaml.safe_load(f)

    def _save_inventory(self, inventory: dict) -> None:
        """Speichert das Inventory in die YAML-Datei"""
        # Backup erstellen
        backup_path = self.inventory_path.with_suffix(".yml.bak")
        if self.inventory_path.exists():
            import shutil
            shutil.copy(self.inventory_path, backup_path)

        with open(self.inventory_path, "w") as f:
            yaml.dump(
                inventory,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                indent=2,
            )

    def get_groups(self) -> list[str]:
        """Gibt alle verfügbaren Gruppen zurück"""
        try:
            inventory = self._load_inventory()
            groups = []

            # children enthält die Gruppen
            if "all" in inventory and "children" in inventory["all"]:
                for group_name in inventory["all"]["children"].keys():
                    # Meta-Gruppen ausschließen
                    if group_name not in ["linux", "debian_trixie", "proxmox"]:
                        groups.append(group_name)

            return sorted(groups)
        except Exception:
            return []

    def host_exists(self, hostname: str) -> bool:
        """Prüft ob ein Host bereits im Inventory existiert"""
        try:
            inventory = self._load_inventory()

            # Alle Gruppen durchsuchen
            if "all" in inventory and "children" in inventory["all"]:
                for group_data in inventory["all"]["children"].values():
                    if "hosts" in group_data and hostname in group_data["hosts"]:
                        return True

            return False
        except Exception:
            return False

    def add_host(
        self,
        hostname: str,
        ip_address: str,
        group: str,
        vmid: int,
        pve_node: str,
        ansible_port: Optional[int] = None,
    ) -> bool:
        """
        Fügt einen neuen Host zum Inventory hinzu.

        Args:
            hostname: Name des Hosts (z.B. "test-vm")
            ip_address: IP-Adresse (z.B. "10.0.0.120")
            group: Ansible-Gruppe (z.B. "docker_hosts")
            vmid: Proxmox VMID (z.B. 60120)
            pve_node: Proxmox Node (z.B. "pve-node-01")
            ansible_port: Optional SSH-Port wenn nicht 22

        Returns:
            True bei Erfolg, False bei Fehler
        """
        try:
            inventory = self._load_inventory()

            # Prüfen ob Gruppe existiert
            if "all" not in inventory or "children" not in inventory["all"]:
                return False

            if group not in inventory["all"]["children"]:
                # Gruppe erstellen falls nicht vorhanden
                inventory["all"]["children"][group] = {"hosts": {}}

            group_data = inventory["all"]["children"][group]

            if "hosts" not in group_data:
                group_data["hosts"] = {}

            # Host hinzufügen
            host_entry = {
                "ansible_host": ip_address,
                "vmid": vmid,
                "pve_node": pve_node,
            }

            if ansible_port and ansible_port != 22:
                host_entry["ansible_port"] = ansible_port

            group_data["hosts"][hostname] = host_entry

            # Inventory speichern
            self._save_inventory(inventory)

            return True
        except Exception as e:
            print(f"Fehler beim Hinzufügen des Hosts: {e}")
            return False

    def remove_host(self, hostname: str) -> bool:
        """
        Entfernt einen Host aus dem Inventory.

        Args:
            hostname: Name des Hosts

        Returns:
            True bei Erfolg, False wenn Host nicht gefunden
        """
        try:
            inventory = self._load_inventory()
            removed = False

            # Alle Gruppen durchsuchen
            if "all" in inventory and "children" in inventory["all"]:
                for group_data in inventory["all"]["children"].values():
                    if "hosts" in group_data and hostname in group_data["hosts"]:
                        del group_data["hosts"][hostname]
                        removed = True

            if removed:
                self._save_inventory(inventory)

            return removed
        except Exception:
            return False


# Singleton-Instanz
ansible_inventory_service = AnsibleInventoryService()
