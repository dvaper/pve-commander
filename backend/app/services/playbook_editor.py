"""
Playbook Editor Service - Erstellen und Bearbeiten von Playbooks

Features:
- YAML-Validierung mit detaillierten Fehlermeldungen
- Ansible-Syntax-Check
- Git-Versionierung
- System-Playbook-Schutz
"""
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

import yaml

from app.config import settings


# System-Playbooks die nicht bearbeitet/gelöscht werden können
SYSTEM_PLAYBOOKS = [
    "ping", "update", "apt-upgrade", "apt-check", "apt-reboot",
    "hardening", "docker-install", "dns-fix", "ssh-cleanup",
    "setup-zsh", "locale"
]

# Prefix für benutzerdefinierte Playbooks
CUSTOM_PREFIX = "custom-"


class PlaybookEditor:
    """Service für Playbook-Erstellung und -Bearbeitung"""

    def __init__(self, playbook_dir: str):
        self.playbook_dir = Path(playbook_dir)

    def is_system_playbook(self, name: str) -> bool:
        """Prüft ob ein Playbook schreibgeschützt ist (System-Playbook)"""
        # Ohne custom- Prefix oder in der System-Liste
        if name in SYSTEM_PLAYBOOKS:
            return True
        if not name.startswith(CUSTOM_PREFIX):
            # Playbook existiert bereits und hat kein custom- Prefix
            playbook_path = self.playbook_dir / f"{name}.yml"
            if playbook_path.exists():
                return True
            playbook_path = self.playbook_dir / f"{name}.yaml"
            if playbook_path.exists():
                return True
        return False

    def playbook_exists(self, name: str) -> bool:
        """Prüft ob ein Playbook existiert"""
        yml_path = self.playbook_dir / f"{name}.yml"
        yaml_path = self.playbook_dir / f"{name}.yaml"
        return yml_path.exists() or yaml_path.exists()

    def get_playbook_path(self, name: str) -> Optional[Path]:
        """Gibt den Pfad eines Playbooks zurück"""
        yml_path = self.playbook_dir / f"{name}.yml"
        if yml_path.exists():
            return yml_path
        yaml_path = self.playbook_dir / f"{name}.yaml"
        if yaml_path.exists():
            return yaml_path
        return None

    def validate_yaml(self, content: str) -> Tuple[bool, Optional[str], Optional[List]]:
        """
        YAML-Validierung mit detaillierten Fehlerinformationen.

        Returns:
            (valid, error_message, parsed_data)
        """
        try:
            # 1. Basis YAML-Parsing
            data = yaml.safe_load(content)

            # 2. Playbook-Struktur prüfen
            if data is None:
                return False, "Playbook ist leer", None

            if not isinstance(data, list):
                return False, "Playbook muss eine Liste von Plays sein (beginnt mit '- name:')", None

            if len(data) == 0:
                return False, "Playbook enthält keine Plays", None

            # 3. Jedes Play prüfen
            for i, play in enumerate(data):
                if not isinstance(play, dict):
                    return False, f"Play {i+1} ist kein gültiges Dictionary", None

                # 'hosts' ist Pflichtfeld
                if 'hosts' not in play:
                    return False, f"Play {i+1}: 'hosts' fehlt (Pflichtfeld)", None

                # Mindestens tasks, roles oder import_playbook
                has_work = any(key in play for key in [
                    'tasks', 'roles', 'import_playbook', 'include_role',
                    'pre_tasks', 'post_tasks', 'handlers'
                ])
                if not has_work:
                    return False, f"Play {i+1}: Keine tasks, roles oder imports definiert", None

            return True, None, data

        except yaml.YAMLError as e:
            # Detaillierte Fehlermeldung mit Zeilennummer
            if hasattr(e, 'problem_mark'):
                mark = e.problem_mark
                return False, f"YAML-Fehler in Zeile {mark.line + 1}, Spalte {mark.column + 1}: {e.problem}", None
            return False, f"YAML-Fehler: {str(e)}", None

    def validate_ansible(self, content: str) -> Tuple[bool, Optional[str]]:
        """
        Ansible-Syntax-Check mit ansible-playbook --syntax-check.

        Erstellt temporäre Datei und führt Check aus.
        """
        # Temporäre Datei erstellen
        fd, temp_path = tempfile.mkstemp(suffix='.yml', prefix='playbook_check_')
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(content)

            # Ansible-Syntax-Check ausführen
            result = subprocess.run(
                [
                    'ansible-playbook',
                    '--syntax-check',
                    '-i', 'localhost,',  # Dummy-Inventory
                    temp_path
                ],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.playbook_dir.parent)  # Damit relative Imports funktionieren
            )

            if result.returncode == 0:
                return True, None
            else:
                # Fehlermeldung bereinigen
                error = result.stderr or result.stdout
                # Temporären Pfad aus Fehlermeldung entfernen
                error = error.replace(temp_path, "<playbook>")
                return False, error.strip()

        except subprocess.TimeoutExpired:
            return False, "Ansible-Validierung Timeout (> 30s)"
        except FileNotFoundError:
            return False, "ansible-playbook nicht gefunden"
        except Exception as e:
            return False, f"Validierungsfehler: {str(e)}"
        finally:
            # Temporäre Datei löschen
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    def validate_full(self, content: str) -> Dict[str, Any]:
        """
        Vollständige Validierung (YAML + Ansible).

        Returns:
            {
                "valid": bool,
                "yaml_valid": bool,
                "yaml_error": str | None,
                "ansible_valid": bool,
                "ansible_error": str | None,
                "warnings": [],
                "parsed_info": { hosts, tasks, roles, vars } | None
            }
        """
        result = {
            "valid": False,
            "yaml_valid": False,
            "yaml_error": None,
            "ansible_valid": False,
            "ansible_error": None,
            "warnings": [],
            "parsed_info": None
        }

        # 1. YAML-Validierung
        yaml_valid, yaml_error, parsed_data = self.validate_yaml(content)
        result["yaml_valid"] = yaml_valid
        result["yaml_error"] = yaml_error

        if not yaml_valid:
            return result

        # 2. Parsed Info extrahieren
        result["parsed_info"] = self._extract_playbook_info(parsed_data)

        # 3. Ansible-Validierung
        ansible_valid, ansible_error = self.validate_ansible(content)
        result["ansible_valid"] = ansible_valid
        result["ansible_error"] = ansible_error

        # 4. Warnungen generieren
        warnings = self._generate_warnings(parsed_data)
        result["warnings"] = warnings

        # Gesamt-Validität
        result["valid"] = yaml_valid and ansible_valid

        return result

    def _extract_playbook_info(self, parsed_data: List) -> Dict[str, Any]:
        """Extrahiert Informationen aus geparsten Playbook-Daten"""
        info = {
            "hosts": [],
            "tasks": [],
            "roles": [],
            "vars": [],
            "plays_count": len(parsed_data)
        }

        for play in parsed_data:
            # Hosts
            hosts = play.get("hosts", "all")
            if hosts not in info["hosts"]:
                info["hosts"].append(hosts)

            # Tasks
            for task_key in ["tasks", "pre_tasks", "post_tasks"]:
                if task_key in play:
                    for task in play[task_key]:
                        task_name = task.get("name", "Unnamed task")
                        info["tasks"].append(task_name)

            # Roles
            if "roles" in play:
                for role in play["roles"]:
                    if isinstance(role, str):
                        info["roles"].append(role)
                    elif isinstance(role, dict):
                        role_name = role.get("role", role.get("name", "unknown"))
                        info["roles"].append(role_name)

            # Variablen
            if "vars" in play:
                info["vars"].extend(list(play["vars"].keys()))

        return info

    def _generate_warnings(self, parsed_data: List) -> List[str]:
        """Generiert Warnungen für potenzielle Probleme"""
        warnings = []

        for i, play in enumerate(parsed_data):
            # Warnung: gather_facts nicht explizit gesetzt
            if "gather_facts" not in play:
                pass  # Kein Warning, Standard ist True

            # Warnung: become ohne become_user
            if play.get("become") and not play.get("become_user"):
                warnings.append(f"Play {i+1}: 'become: true' ohne 'become_user' (Standard: root)")

            # Warnung: Keine Tags definiert
            if "tags" not in play and len(parsed_data) > 1:
                warnings.append(f"Play {i+1}: Keine Tags definiert (empfohlen bei mehreren Plays)")

        return warnings

    def create_playbook(
        self,
        name: str,
        content: str,
        username: str = "system"
    ) -> Tuple[bool, str]:
        """
        Erstellt ein neues Playbook.

        Args:
            name: Playbook-Name (ohne .yml)
            content: YAML-Inhalt
            username: Benutzername für Git-Commit

        Returns:
            (success, message)
        """
        # Name muss mit custom- beginnen
        if not name.startswith(CUSTOM_PREFIX):
            return False, f"Playbook-Name muss mit '{CUSTOM_PREFIX}' beginnen"

        # Prüfen ob bereits existiert
        if self.playbook_exists(name):
            return False, f"Playbook '{name}' existiert bereits"

        # Validierung
        validation = self.validate_full(content)
        if not validation["valid"]:
            if validation["yaml_error"]:
                return False, f"YAML-Fehler: {validation['yaml_error']}"
            if validation["ansible_error"]:
                return False, f"Ansible-Fehler: {validation['ansible_error']}"
            return False, "Validierung fehlgeschlagen"

        # Datei schreiben
        playbook_path = self.playbook_dir / f"{name}.yml"
        try:
            with open(playbook_path, "w") as f:
                f.write(content)
        except Exception as e:
            return False, f"Schreiben fehlgeschlagen: {str(e)}"

        # Git-Commit
        self._git_commit(
            f"[Ansible Commander] Playbook '{name}' erstellt (User: {username})",
            [playbook_path]
        )

        return True, f"Playbook '{name}' erstellt"

    def update_playbook(
        self,
        name: str,
        content: str,
        username: str = "system"
    ) -> Tuple[bool, str]:
        """
        Aktualisiert ein bestehendes Playbook.

        Args:
            name: Playbook-Name (ohne .yml)
            content: Neuer YAML-Inhalt
            username: Benutzername für Git-Commit

        Returns:
            (success, message)
        """
        # System-Playbooks sind geschützt
        if self.is_system_playbook(name):
            return False, f"System-Playbook '{name}' kann nicht bearbeitet werden"

        # Prüfen ob existiert
        playbook_path = self.get_playbook_path(name)
        if not playbook_path:
            return False, f"Playbook '{name}' nicht gefunden"

        # Validierung
        validation = self.validate_full(content)
        if not validation["valid"]:
            if validation["yaml_error"]:
                return False, f"YAML-Fehler: {validation['yaml_error']}"
            if validation["ansible_error"]:
                return False, f"Ansible-Fehler: {validation['ansible_error']}"
            return False, "Validierung fehlgeschlagen"

        # Backup erstellen (Git)
        self._git_commit(
            f"[Backup] Vor Änderung an '{name}'",
            [playbook_path]
        )

        # Datei aktualisieren
        try:
            with open(playbook_path, "w") as f:
                f.write(content)
        except Exception as e:
            return False, f"Schreiben fehlgeschlagen: {str(e)}"

        # Git-Commit
        self._git_commit(
            f"[Ansible Commander] Playbook '{name}' aktualisiert (User: {username})",
            [playbook_path]
        )

        return True, f"Playbook '{name}' aktualisiert"

    def delete_playbook(self, name: str, username: str = "system") -> Tuple[bool, str]:
        """
        Löscht ein Playbook.

        Args:
            name: Playbook-Name (ohne .yml)
            username: Benutzername für Git-Commit

        Returns:
            (success, message)
        """
        # System-Playbooks sind geschützt
        if self.is_system_playbook(name):
            return False, f"System-Playbook '{name}' kann nicht gelöscht werden"

        # Prüfen ob existiert
        playbook_path = self.get_playbook_path(name)
        if not playbook_path:
            return False, f"Playbook '{name}' nicht gefunden"

        # Löschen
        try:
            playbook_path.unlink()
        except Exception as e:
            return False, f"Löschen fehlgeschlagen: {str(e)}"

        # Git-Commit
        self._git_commit(
            f"[Ansible Commander] Playbook '{name}' gelöscht (User: {username})",
            [playbook_path],
            deleted=True
        )

        return True, f"Playbook '{name}' gelöscht"

    def get_history(self, name: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Gibt die Git-Historie eines Playbooks zurück.

        Returns:
            Liste von Commits mit hash, author, timestamp, message
        """
        playbook_path = self.get_playbook_path(name)
        if not playbook_path:
            return []

        try:
            result = subprocess.run(
                [
                    "git", "log",
                    f"-{limit}",
                    "--format=%H|%an|%ae|%at|%s",
                    "--follow",
                    "--", str(playbook_path)
                ],
                capture_output=True,
                text=True,
                cwd=str(self.playbook_dir)
            )

            if result.returncode != 0:
                return []

            commits = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|", 4)
                if len(parts) >= 5:
                    commits.append({
                        "commit_hash": parts[0],
                        "author": parts[1],
                        "email": parts[2],
                        "timestamp": datetime.fromtimestamp(int(parts[3])).isoformat(),
                        "message": parts[4]
                    })

            return commits
        except Exception:
            return []

    def restore_version(
        self,
        name: str,
        commit_hash: str,
        username: str = "system"
    ) -> Tuple[bool, str]:
        """
        Stellt eine frühere Version eines Playbooks wieder her.

        Args:
            name: Playbook-Name
            commit_hash: Git-Commit-Hash
            username: Benutzername für Git-Commit

        Returns:
            (success, message)
        """
        # System-Playbooks sind geschützt
        if self.is_system_playbook(name):
            return False, f"System-Playbook '{name}' kann nicht bearbeitet werden"

        playbook_path = self.get_playbook_path(name)
        if not playbook_path:
            return False, f"Playbook '{name}' nicht gefunden"

        try:
            # Alte Version abrufen
            result = subprocess.run(
                ["git", "show", f"{commit_hash}:{playbook_path.name}"],
                capture_output=True,
                text=True,
                cwd=str(self.playbook_dir)
            )

            if result.returncode != 0:
                return False, f"Version {commit_hash[:8]} nicht gefunden"

            old_content = result.stdout

            # Validierung der alten Version
            validation = self.validate_full(old_content)
            if not validation["valid"]:
                return False, "Alte Version ist nicht mehr gültig"

            # Backup erstellen
            self._git_commit(
                f"[Backup] Vor Rollback von '{name}'",
                [playbook_path]
            )

            # Wiederherstellen
            with open(playbook_path, "w") as f:
                f.write(old_content)

            # Git-Commit
            self._git_commit(
                f"[Ansible Commander] Playbook '{name}' auf Version {commit_hash[:8]} zurückgesetzt (User: {username})",
                [playbook_path]
            )

            return True, f"Playbook '{name}' auf Version {commit_hash[:8]} zurückgesetzt"

        except Exception as e:
            return False, f"Wiederherstellung fehlgeschlagen: {str(e)}"

    def _git_commit(
        self,
        message: str,
        files: List[Path],
        deleted: bool = False
    ) -> bool:
        """Erstellt einen Git-Commit für die angegebenen Dateien"""
        try:
            # Dateien stagen
            for file_path in files:
                if deleted:
                    subprocess.run(
                        ["git", "rm", "--cached", str(file_path)],
                        capture_output=True,
                        cwd=str(self.playbook_dir)
                    )
                else:
                    subprocess.run(
                        ["git", "add", str(file_path)],
                        capture_output=True,
                        cwd=str(self.playbook_dir)
                    )

            # Commit erstellen
            result = subprocess.run(
                ["git", "commit", "-m", message],
                capture_output=True,
                cwd=str(self.playbook_dir)
            )

            return result.returncode == 0
        except Exception:
            return False

    def get_templates(self) -> List[Dict[str, str]]:
        """Gibt verfügbare Playbook-Templates zurück"""
        return [
            {
                "id": "basic",
                "name": "Basis-Template",
                "description": "Einfaches Playbook mit Tasks",
                "content": '''---
- name: Beschreibung des Playbooks
  hosts: all
  become: true
  gather_facts: true

  vars:
    # Variablen hier definieren
    example_var: "value"

  tasks:
    - name: Erste Aufgabe
      ansible.builtin.debug:
        msg: "Hello from {{ inventory_hostname }}"
'''
            },
            {
                "id": "ping",
                "name": "Ping-Test",
                "description": "Konnektivität testen",
                "content": '''---
- name: Konnektivität testen
  hosts: all
  gather_facts: false

  tasks:
    - name: Ping
      ansible.builtin.ping:

    - name: Hostname anzeigen
      ansible.builtin.command: hostname -f
      register: result
      changed_when: false

    - name: Ergebnis
      ansible.builtin.debug:
        var: result.stdout
'''
            },
            {
                "id": "apt-update",
                "name": "APT Update",
                "description": "Paketliste aktualisieren und upgraden",
                "content": '''---
- name: System-Updates
  hosts: all
  become: true
  gather_facts: true

  tasks:
    - name: Paketliste aktualisieren
      ansible.builtin.apt:
        update_cache: true
        cache_valid_time: 3600
      when: ansible_os_family == "Debian"

    - name: Pakete upgraden
      ansible.builtin.apt:
        upgrade: safe
      when: ansible_os_family == "Debian"
'''
            },
            {
                "id": "shell-command",
                "name": "Shell-Befehl",
                "description": "Beliebigen Shell-Befehl ausführen",
                "content": '''---
- name: Shell-Befehl ausführen
  hosts: all
  become: true
  gather_facts: false

  vars:
    command: "hostname -f"

  tasks:
    - name: Befehl ausführen
      ansible.builtin.shell: "{{ command }}"
      register: result
      changed_when: false

    - name: Ergebnis anzeigen
      ansible.builtin.debug:
        var: result.stdout_lines
'''
            },
            {
                "id": "file-copy",
                "name": "Datei kopieren",
                "description": "Datei auf Remote-Hosts kopieren",
                "content": '''---
- name: Datei kopieren
  hosts: all
  become: true
  gather_facts: false

  vars:
    src_file: "/path/to/local/file"
    dest_file: "/path/to/remote/file"
    file_mode: "0644"
    file_owner: "root"
    file_group: "root"

  tasks:
    - name: Datei kopieren
      ansible.builtin.copy:
        src: "{{ src_file }}"
        dest: "{{ dest_file }}"
        mode: "{{ file_mode }}"
        owner: "{{ file_owner }}"
        group: "{{ file_group }}"
'''
            },
            {
                "id": "service-restart",
                "name": "Service neustarten",
                "description": "Systemd-Service neustarten",
                "content": '''---
- name: Service neustarten
  hosts: all
  become: true
  gather_facts: false

  vars:
    service_name: "nginx"

  tasks:
    - name: Service neustarten
      ansible.builtin.systemd:
        name: "{{ service_name }}"
        state: restarted
        daemon_reload: true

    - name: Service-Status prüfen
      ansible.builtin.systemd:
        name: "{{ service_name }}"
      register: service_status

    - name: Status anzeigen
      ansible.builtin.debug:
        msg: "{{ service_name }} ist {{ service_status.status.ActiveState }}"
'''
            }
        ]


# Singleton-Instanz
_editor: Optional[PlaybookEditor] = None


def get_playbook_editor(playbook_dir: str = None) -> PlaybookEditor:
    """Gibt den PlaybookEditor zurück (Singleton)"""
    global _editor
    if _editor is None:
        _editor = PlaybookEditor(playbook_dir or settings.ansible_playbook_dir)
    return _editor
