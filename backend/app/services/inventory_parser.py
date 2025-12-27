"""
Inventory Parser - Parst hosts.yml in strukturierte Daten
"""
import yaml
from pathlib import Path
from typing import Dict, List, Optional
from app.schemas.inventory import HostInfo, GroupInfo, InventoryTree


class InventoryParser:
    """Parser für Ansible YAML Inventory"""

    def __init__(self, inventory_path: str):
        self.inventory_path = Path(inventory_path)
        self._data = None
        self._hosts: Dict[str, HostInfo] = {}
        self._groups: Dict[str, GroupInfo] = {}
        self._host_groups: Dict[str, List[str]] = {}
        self._last_modified: float = 0
        self._load()

    def _check_and_reload(self):
        """Prüft ob die Datei geändert wurde und lädt ggf. neu"""
        try:
            current_mtime = self.inventory_path.stat().st_mtime
            if current_mtime > self._last_modified:
                self._load()
        except Exception:
            pass

    def _load(self):
        """Lädt und parst das Inventory"""
        if not self.inventory_path.exists():
            raise FileNotFoundError(f"Inventory nicht gefunden: {self.inventory_path}")

        # Timestamp speichern
        self._last_modified = self.inventory_path.stat().st_mtime

        with open(self.inventory_path, "r") as f:
            self._data = yaml.safe_load(f)

        self._parse()

    def _parse(self):
        """Parst die Inventory-Struktur"""
        self._hosts = {}
        self._groups = {}
        self._host_groups = {}

        if not self._data:
            return

        # Parse all groups recursively
        self._parse_group("all", self._data.get("all", {}))

        # Berechne total_hosts_count für alle Gruppen (inkl. Children)
        self._calculate_total_hosts()

    def _parse_group(self, group_name: str, group_data: dict, parent_groups: List[str] = None):
        """Parst eine Gruppe rekursiv"""
        if parent_groups is None:
            parent_groups = []

        hosts = []
        children = []
        group_vars = {}

        if isinstance(group_data, dict):
            # Hosts in dieser Gruppe
            if "hosts" in group_data:
                for host_name, host_vars in (group_data["hosts"] or {}).items():
                    hosts.append(host_name)
                    self._add_host(host_name, host_vars or {}, [group_name] + parent_groups)

            # Variablen für die Gruppe
            if "vars" in group_data:
                group_vars = group_data["vars"] or {}

            # Kinder-Gruppen
            if "children" in group_data:
                for child_name, child_data in (group_data["children"] or {}).items():
                    children.append(child_name)
                    # Nur parsen wenn child_data Inhalt hat ODER die Gruppe noch nicht existiert
                    # (verhindert Überschreiben durch leere Referenzen in Meta-Gruppen)
                    if child_data or child_name not in self._groups:
                        self._parse_group(
                            child_name,
                            child_data or {},
                            [group_name] + parent_groups
                        )

        # Gruppe speichern (total_hosts_count wird später berechnet)
        self._groups[group_name] = GroupInfo(
            name=group_name,
            hosts=hosts,
            children=children,
            hosts_count=len(hosts),
            total_hosts_count=0,  # Wird in _calculate_total_hosts gesetzt
            vars=group_vars,
        )

    def _calculate_total_hosts(self):
        """Berechnet total_hosts_count für alle Gruppen (inkl. Children)"""
        # Cache für bereits berechnete Gruppen
        calculated: Dict[str, int] = {}

        def get_total(group_name: str) -> int:
            """Rekursive Berechnung der Gesamtzahl"""
            if group_name in calculated:
                return calculated[group_name]

            group = self._groups.get(group_name)
            if not group:
                return 0

            # Direkte Hosts dieser Gruppe
            total = group.hosts_count

            # Hosts aller Kinder-Gruppen hinzufügen
            for child_name in group.children:
                total += get_total(child_name)

            calculated[group_name] = total
            return total

        # Berechne für alle Gruppen
        for group_name, group in self._groups.items():
            group.total_hosts_count = get_total(group_name)

    def _add_host(self, host_name: str, host_vars: dict, groups: List[str]):
        """Fügt einen Host hinzu oder aktualisiert seine Gruppen"""
        if host_name in self._hosts:
            # Gruppen erweitern
            existing_groups = set(self._hosts[host_name].groups)
            existing_groups.update(groups)
            self._hosts[host_name].groups = list(existing_groups)
        else:
            self._hosts[host_name] = HostInfo(
                name=host_name,
                ansible_host=host_vars.get("ansible_host"),
                vmid=host_vars.get("vmid"),
                pve_node=host_vars.get("pve_node"),
                groups=groups,
                vars={k: str(v) for k, v in host_vars.items()},
            )

    def reload(self):
        """Lädt das Inventory neu"""
        self._load()

    def get_hosts(self) -> List[HostInfo]:
        """Gibt alle Hosts zurück"""
        self._check_and_reload()
        return list(self._hosts.values())

    def get_host(self, name: str) -> Optional[HostInfo]:
        """Gibt einen einzelnen Host zurück"""
        self._check_and_reload()
        return self._hosts.get(name)

    def get_groups(self) -> List[GroupInfo]:
        """Gibt alle Gruppen zurück (ohne 'all')"""
        self._check_and_reload()
        return [g for g in self._groups.values() if g.name != "all"]

    def get_group(self, name: str) -> Optional[GroupInfo]:
        """Gibt eine einzelne Gruppe zurück"""
        self._check_and_reload()
        return self._groups.get(name)

    def get_tree(self) -> InventoryTree:
        """Gibt die vollständige Inventory-Struktur zurück"""
        self._check_and_reload()
        return InventoryTree(
            groups=self._groups,
            hosts=self._hosts,
            all_hosts=list(self._hosts.keys()),
            all_groups=[g for g in self._groups.keys() if g != "all"],
        )
