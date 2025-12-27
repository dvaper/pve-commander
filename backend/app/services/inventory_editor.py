"""
Inventory Editor - Bearbeitet die hosts.yml mit Kommentar-Erhalt

Features:
- ruamel.yaml für Kommentar- und Formatierungserhalt
- Git-Backup vor jeder Änderung
- YAML-Syntax und Ansible-Validierung
- Atomare Schreibvorgänge
"""
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List, Dict

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq


class InventoryEditor:
    """Service zum Bearbeiten der Ansible Inventory-Datei"""

    def __init__(self, inventory_path: str):
        self.inventory_path = Path(inventory_path)
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.indent(mapping=2, sequence=4, offset=2)
        self.yaml.width = 4096  # Keine automatischen Zeilenumbrüche
        self._data: Optional[CommentedMap] = None

    def load(self) -> CommentedMap:
        """Lädt Inventory mit ruamel.yaml (erhält Kommentare)"""
        if not self.inventory_path.exists():
            # Leere Inventory-Struktur erstellen
            self._create_empty_inventory()

        with open(self.inventory_path, "r") as f:
            self._data = self.yaml.load(f)

        return self._data

    def _create_empty_inventory(self):
        """Erstellt eine leere Inventory-Datei mit Basis-Struktur"""
        # Verzeichnis erstellen falls nicht vorhanden
        self.inventory_path.parent.mkdir(parents=True, exist_ok=True)

        # Basis-Struktur fuer Ansible Inventory
        empty_inventory = CommentedMap()
        all_group = CommentedMap()
        all_group["children"] = CommentedMap()
        all_group["hosts"] = CommentedMap()
        empty_inventory["all"] = all_group

        # Datei schreiben
        with open(self.inventory_path, "w") as f:
            self.yaml.dump(empty_inventory, f)

    def save(self, commit_message: str, username: str = "system") -> Tuple[bool, str]:
        """
        Speichert das Inventory mit Validierung und Git-Backup.

        Returns:
            Tuple[bool, str]: (Erfolg, Nachricht)
        """
        if self._data is None:
            return False, "Keine Daten geladen"

        # 1. YAML-Syntax validieren
        valid, error = self.validate_yaml()
        if not valid:
            return False, f"YAML-Validierung fehlgeschlagen: {error}"

        # 2. Git-Backup erstellen (vor der Änderung)
        backup_success = self.git_commit(f"[Backup] Vor Änderung: {commit_message}", username)
        if not backup_success:
            # Warnung, aber fortfahren
            pass

        # 3. Atomares Schreiben (temp-Datei → rename)
        try:
            # Temp-Datei im gleichen Verzeichnis erstellen
            fd, temp_path = tempfile.mkstemp(
                suffix=".yml",
                prefix=".hosts_",
                dir=self.inventory_path.parent
            )
            try:
                with os.fdopen(fd, "w") as f:
                    self.yaml.dump(self._data, f)

                # Datei ersetzen (atomare Operation auf Unix)
                os.replace(temp_path, self.inventory_path)

                # Berechtigungen explizit setzen (0644 = rw-r--r--)
                os.chmod(self.inventory_path, 0o644)
            except Exception:
                # Temp-Datei aufräumen bei Fehler
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise
        except Exception as e:
            return False, f"Schreiben fehlgeschlagen: {str(e)}"

        # 4. Ansible-Validierung
        valid, error = self.validate_ansible()
        if not valid:
            # Bei Fehler: Rollback per Git
            self.git_rollback()
            return False, f"Ansible-Validierung fehlgeschlagen: {error}"

        # 5. Git-Commit erstellen
        self.git_commit(f"[Ansible Commander] {commit_message} (User: {username})", username)

        return True, "Änderung erfolgreich gespeichert"

    def validate_yaml(self) -> Tuple[bool, str]:
        """
        Prüft YAML-Syntax.

        Returns:
            Tuple[bool, str]: (Gültig, Fehlermeldung)
        """
        if self._data is None:
            return False, "Keine Daten geladen"

        try:
            # Versuche in String zu dumpen
            from io import StringIO
            stream = StringIO()
            self.yaml.dump(self._data, stream)
            return True, ""
        except Exception as e:
            return False, str(e)

    def validate_ansible(self) -> Tuple[bool, str]:
        """
        Prüft mit ansible-inventory --list.

        Returns:
            Tuple[bool, str]: (Gültig, Fehlermeldung)
        """
        try:
            result = subprocess.run(
                ["ansible-inventory", "-i", str(self.inventory_path), "--list"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                return False, result.stderr
            return True, ""
        except subprocess.TimeoutExpired:
            return False, "Ansible-Inventory Timeout"
        except FileNotFoundError:
            # ansible-inventory nicht installiert - Skip
            return True, "ansible-inventory nicht verfügbar (übersprungen)"
        except Exception as e:
            return False, str(e)

    def git_commit(self, message: str, username: str = "system") -> bool:
        """
        Erstellt Git-Commit im Inventory-Verzeichnis.

        Returns:
            bool: Erfolg
        """
        inventory_dir = self.inventory_path.parent

        try:
            # Git-Repository vorhanden?
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=inventory_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                return False

            # Datei zum Staging hinzufügen
            subprocess.run(
                ["git", "add", str(self.inventory_path)],
                cwd=inventory_dir,
                capture_output=True,
                timeout=10
            )

            # Commit erstellen
            result = subprocess.run(
                ["git", "commit", "-m", message, "--author", f"{username} <{username}@ansible-commander>"],
                cwd=inventory_dir,
                capture_output=True,
                text=True,
                timeout=10
            )

            return result.returncode == 0

        except Exception:
            return False

    def git_rollback(self) -> bool:
        """
        Setzt auf den letzten Commit zurück.

        Returns:
            bool: Erfolg
        """
        inventory_dir = self.inventory_path.parent

        try:
            subprocess.run(
                ["git", "checkout", "--", str(self.inventory_path)],
                cwd=inventory_dir,
                capture_output=True,
                timeout=10
            )
            # Daten neu laden
            self.load()
            return True
        except Exception:
            return False

    def get_git_history(self, limit: int = 20) -> List[dict]:
        """
        Gibt die Git-Historie für hosts.yml zurück.

        Returns:
            List[dict]: Liste von Commits
        """
        inventory_dir = self.inventory_path.parent

        try:
            result = subprocess.run(
                [
                    "git", "log", f"-{limit}",
                    "--pretty=format:%H|%an|%ae|%at|%s",
                    "--follow",
                    str(self.inventory_path)
                ],
                cwd=inventory_dir,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return []

            commits = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|", 4)
                if len(parts) == 5:
                    commits.append({
                        "commit_hash": parts[0],
                        "author": parts[1],
                        "email": parts[2],
                        "timestamp": datetime.fromtimestamp(int(parts[3])),
                        "message": parts[4],
                    })
            return commits

        except Exception:
            return []

    def git_restore_commit(self, commit_hash: str) -> Tuple[bool, str]:
        """
        Stellt eine bestimmte Version wieder her.

        Args:
            commit_hash: Git-Commit-Hash

        Returns:
            Tuple[bool, str]: (Erfolg, Nachricht)
        """
        inventory_dir = self.inventory_path.parent

        try:
            # Prüfen ob Commit existiert
            result = subprocess.run(
                ["git", "cat-file", "-t", commit_hash],
                cwd=inventory_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                return False, f"Commit '{commit_hash}' nicht gefunden"

            # Datei aus Commit wiederherstellen
            result = subprocess.run(
                ["git", "checkout", commit_hash, "--", str(self.inventory_path)],
                cwd=inventory_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                return False, f"Wiederherstellung fehlgeschlagen: {result.stderr}"

            # Daten neu laden
            self.load()

            return True, f"Version {commit_hash[:8]} wiederhergestellt"

        except Exception as e:
            return False, str(e)

    # ========================================
    # Gruppen-Operationen
    # ========================================

    def create_group(self, group_name: str, parent: str = "all") -> Tuple[bool, str]:
        """
        Erstellt eine neue Gruppe.

        Args:
            group_name: Name der neuen Gruppe
            parent: Parent-Gruppe (default: all)

        Returns:
            Tuple[bool, str]: (Erfolg, Nachricht)
        """
        if self._data is None:
            self.load()

        # Validierung des Gruppennamens
        if not group_name or not group_name.replace("_", "").replace("-", "").isalnum():
            return False, "Ungültiger Gruppenname (nur Buchstaben, Zahlen, _ und - erlaubt)"

        # Prüfen ob Gruppe bereits existiert
        if self._group_exists(group_name):
            return False, f"Gruppe '{group_name}' existiert bereits"

        # Parent-Gruppe finden
        parent_group = self._find_group(parent)
        if parent_group is None:
            return False, f"Parent-Gruppe '{parent}' nicht gefunden"

        # children-Sektion erstellen falls nicht vorhanden
        if "children" not in parent_group:
            parent_group["children"] = CommentedMap()

        # Neue Gruppe erstellen mit leerer hosts-Sektion
        new_group = CommentedMap()
        new_group["hosts"] = CommentedMap()

        parent_group["children"][group_name] = new_group

        return True, f"Gruppe '{group_name}' erstellt"

    def delete_group(self, group_name: str) -> Tuple[bool, str]:
        """
        Löscht eine Gruppe.

        Args:
            group_name: Name der zu löschenden Gruppe

        Returns:
            Tuple[bool, str]: (Erfolg, Nachricht)
        """
        if self._data is None:
            self.load()

        # Schutz für spezielle Gruppen
        protected_groups = ["all", "ungrouped", "linux", "windows"]
        if group_name in protected_groups:
            return False, f"Gruppe '{group_name}' ist geschützt und kann nicht gelöscht werden"

        # Gruppe finden und Parent ermitteln
        parent_name, deleted = self._delete_group_recursive("all", self._data.get("all", {}), group_name)

        if not deleted:
            return False, f"Gruppe '{group_name}' nicht gefunden"

        return True, f"Gruppe '{group_name}' gelöscht"

    def rename_group(self, old_name: str, new_name: str) -> Tuple[bool, str]:
        """
        Benennt eine Gruppe um.

        Args:
            old_name: Aktueller Name
            new_name: Neuer Name

        Returns:
            Tuple[bool, str]: (Erfolg, Nachricht)
        """
        if self._data is None:
            self.load()

        # Validierung
        if not new_name or not new_name.replace("_", "").replace("-", "").isalnum():
            return False, "Ungültiger neuer Gruppenname"

        if self._group_exists(new_name):
            return False, f"Gruppe '{new_name}' existiert bereits"

        # Gruppe finden
        parent_group, group_key = self._find_group_with_parent(old_name)
        if parent_group is None:
            return False, f"Gruppe '{old_name}' nicht gefunden"

        # Umbenennen (Reihenfolge erhalten)
        if "children" in parent_group:
            # Wert speichern
            group_data = parent_group["children"][group_key]

            # Neue OrderedDict mit neuer Reihenfolge erstellen
            new_children = CommentedMap()
            for key in parent_group["children"]:
                if key == group_key:
                    new_children[new_name] = group_data
                else:
                    new_children[key] = parent_group["children"][key]

            parent_group["children"] = new_children

        return True, f"Gruppe '{old_name}' in '{new_name}' umbenannt"

    # ========================================
    # Host-Operationen
    # ========================================

    def add_host(
        self,
        hostname: str,
        group: str,
        host_vars: Optional[Dict[str, any]] = None
    ) -> Tuple[bool, str]:
        """
        Erstellt einen neuen Host im Inventory.

        Args:
            hostname: Name des neuen Hosts
            group: Gruppe in die der Host eingefügt wird
            host_vars: Variablen für den Host (z.B. ansible_host, vmid, pve_node)

        Returns:
            Tuple[bool, str]: (Erfolg, Nachricht)
        """
        if self._data is None:
            self.load()

        # Prüfen ob Host bereits existiert
        if self._host_exists(hostname):
            return False, f"Host '{hostname}' existiert bereits"

        # Gruppe finden oder erstellen
        target_group = self._find_group(group)
        if target_group is None:
            # Gruppe erstellen
            success, msg = self.create_group(group, parent="all")
            if not success:
                return False, f"Konnte Gruppe '{group}' nicht erstellen: {msg}"
            target_group = self._find_group(group)

        # hosts-Sektion erstellen falls nicht vorhanden
        if "hosts" not in target_group:
            target_group["hosts"] = CommentedMap()
        elif target_group["hosts"] is None:
            target_group["hosts"] = CommentedMap()

        # Host mit Variablen hinzufügen
        if host_vars:
            host_data = CommentedMap()
            for key, value in host_vars.items():
                host_data[key] = value
            target_group["hosts"][hostname] = host_data
        else:
            target_group["hosts"][hostname] = None

        return True, f"Host '{hostname}' in Gruppe '{group}' erstellt"

    def add_host_to_group(self, host_name: str, group_name: str) -> Tuple[bool, str]:
        """
        Fügt einen Host zu einer Gruppe hinzu.

        Args:
            host_name: Name des Hosts
            group_name: Name der Gruppe

        Returns:
            Tuple[bool, str]: (Erfolg, Nachricht)
        """
        if self._data is None:
            self.load()

        # Prüfen ob Host existiert
        if not self._host_exists(host_name):
            return False, f"Host '{host_name}' existiert nicht im Inventory"

        # Gruppe finden
        group = self._find_group(group_name)
        if group is None:
            return False, f"Gruppe '{group_name}' nicht gefunden"

        # hosts-Sektion erstellen falls nicht vorhanden
        if "hosts" not in group:
            group["hosts"] = CommentedMap()
        elif group["hosts"] is None:
            group["hosts"] = CommentedMap()

        # Prüfen ob Host bereits in Gruppe
        if host_name in group["hosts"]:
            return False, f"Host '{host_name}' ist bereits in Gruppe '{group_name}'"

        # Host hinzufügen (ohne Attribute - nur Referenz)
        group["hosts"][host_name] = None

        return True, f"Host '{host_name}' zu Gruppe '{group_name}' hinzugefügt"

    def remove_host_from_group(self, host_name: str, group_name: str) -> Tuple[bool, str]:
        """
        Entfernt einen Host aus einer Gruppe.

        Args:
            host_name: Name des Hosts
            group_name: Name der Gruppe

        Returns:
            Tuple[bool, str]: (Erfolg, Nachricht)
        """
        if self._data is None:
            self.load()

        # Gruppe finden
        group = self._find_group(group_name)
        if group is None:
            return False, f"Gruppe '{group_name}' nicht gefunden"

        # Prüfen ob Host in Gruppe
        if "hosts" not in group or group["hosts"] is None or host_name not in group["hosts"]:
            return False, f"Host '{host_name}' ist nicht in Gruppe '{group_name}'"

        # Host entfernen
        del group["hosts"][host_name]

        return True, f"Host '{host_name}' aus Gruppe '{group_name}' entfernt"

    def update_host_var(self, host_name: str, var_name: str, var_value: any) -> Tuple[bool, str]:
        """
        Aktualisiert eine Variable eines Hosts.

        Sucht den Host in allen Gruppen und aktualisiert die Variable
        dort, wo der Host mit Variablen definiert ist (nicht nur Referenz).

        Args:
            host_name: Name des Hosts
            var_name: Name der Variable (z.B. pve_node)
            var_value: Neuer Wert der Variable

        Returns:
            Tuple[bool, str]: (Erfolg, Nachricht)
        """
        if self._data is None:
            self.load()

        # Host mit Variablen finden
        host_data = self._find_host_with_vars(host_name)
        if host_data is None:
            return False, f"Host '{host_name}' nicht gefunden oder hat keine Variablen"

        old_value = host_data.get(var_name)
        host_data[var_name] = var_value

        return True, f"Host '{host_name}': {var_name} aktualisiert ({old_value} -> {var_value})"

    def _find_host_with_vars(self, host_name: str, current: dict = None) -> Optional[dict]:
        """
        Findet einen Host und gibt dessen Variablen-Dict zurueck.

        Sucht nur Hosts, die mit Variablen definiert sind (nicht nur Referenzen).
        """
        if current is None:
            current = self._data.get("all", {})

        if isinstance(current, dict):
            # Hosts in dieser Gruppe pruefen
            if "hosts" in current and current["hosts"]:
                if host_name in current["hosts"]:
                    host_data = current["hosts"][host_name]
                    # Nur wenn es ein Dict ist (hat Variablen)
                    if isinstance(host_data, dict):
                        return host_data

            # Rekursiv in Children suchen
            if "children" in current and current["children"]:
                for child_data in current["children"].values():
                    result = self._find_host_with_vars(host_name, child_data or {})
                    if result is not None:
                        return result

        return None

    def get_host_groups(self, host_name: str) -> List[str]:
        """
        Gibt alle Gruppen zurück, in denen ein Host ist.

        Args:
            host_name: Name des Hosts

        Returns:
            List[str]: Liste der Gruppennamen
        """
        if self._data is None:
            self.load()

        groups = []
        self._find_host_groups_recursive("all", self._data.get("all", {}), host_name, groups)
        return groups

    # ========================================
    # Private Hilfsmethoden
    # ========================================

    def _group_exists(self, group_name: str) -> bool:
        """Prüft ob eine Gruppe existiert"""
        return self._find_group(group_name) is not None

    def _host_exists(self, host_name: str) -> bool:
        """Prüft ob ein Host existiert"""
        return self._find_host_in_any_group(host_name)

    def _find_group(self, group_name: str, current_name: str = "all", current: dict = None) -> Optional[dict]:
        """Findet eine Gruppe im Inventory"""
        if current is None:
            current = self._data.get("all", {})

        if current_name == group_name:
            return current

        if isinstance(current, dict) and "children" in current:
            for child_name, child_data in (current["children"] or {}).items():
                result = self._find_group(group_name, child_name, child_data or {})
                if result is not None:
                    return result

        return None

    def _find_group_with_parent(self, group_name: str, parent: dict = None, parent_name: str = "all") -> Tuple[Optional[dict], Optional[str]]:
        """Findet eine Gruppe und gibt auch den Parent zurück"""
        if parent is None:
            parent = self._data.get("all", {})

        if isinstance(parent, dict) and "children" in parent and parent["children"]:
            for child_name, child_data in parent["children"].items():
                if child_name == group_name:
                    return parent, child_name

                result, key = self._find_group_with_parent(group_name, child_data or {}, child_name)
                if result is not None:
                    return result, key

        return None, None

    def _delete_group_recursive(self, parent_name: str, parent: dict, target_name: str) -> Tuple[Optional[str], bool]:
        """Löscht eine Gruppe rekursiv"""
        if isinstance(parent, dict) and "children" in parent and parent["children"]:
            if target_name in parent["children"]:
                del parent["children"][target_name]
                return parent_name, True

            for child_name, child_data in list(parent["children"].items()):
                result, deleted = self._delete_group_recursive(child_name, child_data or {}, target_name)
                if deleted:
                    return result, True

        return None, False

    def _find_host_in_any_group(self, host_name: str, current: dict = None) -> bool:
        """Prüft ob ein Host in irgendeiner Gruppe existiert"""
        if current is None:
            current = self._data.get("all", {})

        if isinstance(current, dict):
            # Hosts in dieser Gruppe prüfen
            if "hosts" in current and current["hosts"]:
                if host_name in current["hosts"]:
                    return True

            # Rekursiv in Children suchen
            if "children" in current and current["children"]:
                for child_data in current["children"].values():
                    if self._find_host_in_any_group(host_name, child_data or {}):
                        return True

        return False

    def _find_host_groups_recursive(self, group_name: str, group_data: dict, host_name: str, result: List[str]):
        """Sammelt alle Gruppen, in denen ein Host ist"""
        if isinstance(group_data, dict):
            # Host in dieser Gruppe?
            if "hosts" in group_data and group_data["hosts"]:
                if host_name in group_data["hosts"]:
                    result.append(group_name)

            # Rekursiv in Children suchen
            if "children" in group_data and group_data["children"]:
                for child_name, child_data in group_data["children"].items():
                    self._find_host_groups_recursive(child_name, child_data or {}, host_name, result)


    # ========================================
    # Sync-Funktionen
    # ========================================

    def sync_proxmox_node_groups(self) -> Tuple[bool, str, dict]:
        """
        Synchronisiert Gruppen basierend auf Proxmox-Nodes.

        Erstellt/aktualisiert Gruppen wie pve_<node-name> fuer jeden Proxmox-Node.
        und weist Hosts basierend auf ihrem pve_node Attribut zu.
        Entfernt auch Hosts aus Node-Gruppen, wenn sie migriert wurden.

        Returns:
            Tuple[bool, str, dict]: (Erfolg, Nachricht, Details)
        """
        if self._data is None:
            self.load()

        # Alle Hosts mit ihren pve_nodes sammeln
        node_hosts: Dict[str, List[str]] = {}
        self._collect_hosts_by_node("all", self._data.get("all", {}), node_hosts)

        if not node_hosts:
            return True, "Keine Hosts mit pve_node Attribut gefunden", {"created": [], "updated": [], "removed": []}

        created_groups = []
        updated_groups = []
        removed_from_groups = []

        # Alle pve_* Gruppen sammeln
        all_pve_groups = self._find_all_pve_groups()

        # Für jeden Node eine Gruppe erstellen/aktualisieren
        for node_name, host_list in node_hosts.items():
            group_name = f"pve_{node_name}"

            # Prüfen ob Gruppe existiert
            group = self._find_group(group_name)

            if group is None:
                # Neue Gruppe erstellen
                success, msg = self.create_group(group_name, parent="all")
                if success:
                    created_groups.append(group_name)
                    group = self._find_group(group_name)

            if group is not None:
                # Hosts zur Gruppe hinzufügen (nur die, die noch nicht drin sind)
                if "hosts" not in group or group["hosts"] is None:
                    group["hosts"] = CommentedMap()

                hosts_added = False
                for host_name in host_list:
                    if host_name not in group["hosts"]:
                        group["hosts"][host_name] = None
                        hosts_added = True

                if hosts_added and group_name not in created_groups:
                    updated_groups.append(group_name)

        # Hosts aus falschen Node-Gruppen entfernen (nach Migration)
        all_hosts_with_nodes = {}
        for node_name, host_list in node_hosts.items():
            for host_name in host_list:
                all_hosts_with_nodes[host_name] = node_name

        for pve_group_name in all_pve_groups:
            group = self._find_group(pve_group_name)
            if group is None or "hosts" not in group or group["hosts"] is None:
                continue

            # Node-Name aus Gruppenname extrahieren (pve_<node> -> <node>)
            expected_node = pve_group_name[4:]  # Entfernt "pve_"

            # Hosts pruefen und falsche entfernen
            hosts_to_remove = []
            for host_name in list(group["hosts"].keys()):
                actual_node = all_hosts_with_nodes.get(host_name)
                if actual_node and actual_node != expected_node:
                    hosts_to_remove.append(host_name)

            for host_name in hosts_to_remove:
                del group["hosts"][host_name]
                removed_from_groups.append({
                    "host": host_name,
                    "old_group": pve_group_name,
                    "new_group": f"pve_{all_hosts_with_nodes[host_name]}"
                })

        details = {
            "created": created_groups,
            "updated": updated_groups,
            "removed": removed_from_groups,
            "node_hosts": {k: len(v) for k, v in node_hosts.items()}
        }

        message_parts = []
        if created_groups:
            message_parts.append(f"{len(created_groups)} Gruppe(n) erstellt")
        if updated_groups:
            message_parts.append(f"{len(updated_groups)} Gruppe(n) aktualisiert")
        if removed_from_groups:
            message_parts.append(f"{len(removed_from_groups)} Host(s) umgezogen")

        return True, ", ".join(message_parts) if message_parts else "Keine Aenderungen", details

    def _find_all_pve_groups(self) -> List[str]:
        """Findet alle Gruppen die mit 'pve_' beginnen"""
        pve_groups = []
        self._collect_pve_groups("all", self._data.get("all", {}), pve_groups)
        return pve_groups

    def _collect_pve_groups(self, group_name: str, group_data: dict, result: List[str]):
        """Sammelt alle pve_* Gruppen rekursiv"""
        if not isinstance(group_data, dict):
            return

        if group_name.startswith("pve_"):
            result.append(group_name)

        if "children" in group_data and group_data["children"]:
            for child_name, child_data in group_data["children"].items():
                self._collect_pve_groups(child_name, child_data or {}, result)

    def _collect_hosts_by_node(self, group_name: str, group_data: dict, result: Dict[str, List[str]]):
        """Sammelt Hosts gruppiert nach pve_node"""
        if not isinstance(group_data, dict):
            return

        # Hosts in dieser Gruppe prüfen
        if "hosts" in group_data and group_data["hosts"]:
            for host_name, host_vars in group_data["hosts"].items():
                if host_vars and isinstance(host_vars, dict):
                    pve_node = host_vars.get("pve_node")
                    if pve_node:
                        if pve_node not in result:
                            result[pve_node] = []
                        if host_name not in result[pve_node]:
                            result[pve_node].append(host_name)

        # Rekursiv in Children suchen
        if "children" in group_data and group_data["children"]:
            for child_name, child_data in group_data["children"].items():
                self._collect_hosts_by_node(child_name, child_data or {}, result)


# Singleton-Instanz
_editor: Optional[InventoryEditor] = None


def get_inventory_editor(inventory_path: str = None) -> InventoryEditor:
    """Gibt den Inventory-Editor zurück (Singleton)"""
    global _editor
    if _editor is None:
        from app.config import settings
        path = inventory_path or settings.ansible_inventory_path
        _editor = InventoryEditor(path)
    return _editor


def reset_inventory_editor():
    """Setzt den Editor zurück (für Tests)"""
    global _editor
    _editor = None
