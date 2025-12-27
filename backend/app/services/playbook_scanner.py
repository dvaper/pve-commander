"""
Playbook Scanner - Scannt Playbook-Verzeichnis
"""
import time
import yaml
from pathlib import Path
from typing import List, Optional
from app.schemas.playbook import PlaybookInfo, PlaybookDetail


class PlaybookScanner:
    """Scanner für Ansible Playbooks"""

    # Cache-Invalidierung nach 5 Sekunden
    CACHE_TTL_SECONDS = 5

    def __init__(self, playbook_dir: str):
        self.playbook_dir = Path(playbook_dir)
        self._playbooks: List[PlaybookInfo] = []
        self._last_scan: float = 0
        self._scan()

    def _check_and_rescan(self):
        """Prüft ob der Cache abgelaufen ist und scannt ggf. neu"""
        current_time = time.time()
        if current_time - self._last_scan > self.CACHE_TTL_SECONDS:
            self._scan()

    def _scan(self):
        """Scannt das Playbook-Verzeichnis"""
        self._playbooks = []
        self._last_scan = time.time()

        if not self.playbook_dir.exists():
            return

        # Alle YAML-Dateien im Verzeichnis
        for yml_file in sorted(self.playbook_dir.glob("*.yml")):
            try:
                playbook_info = self._parse_playbook_info(yml_file)
                if playbook_info:
                    self._playbooks.append(playbook_info)
            except Exception:
                # Ungültige YAML-Dateien überspringen
                pass

        # Auch .yaml Endung
        for yml_file in sorted(self.playbook_dir.glob("*.yaml")):
            try:
                playbook_info = self._parse_playbook_info(yml_file)
                if playbook_info:
                    self._playbooks.append(playbook_info)
            except Exception:
                pass

    def _parse_playbook_info(self, yml_file: Path) -> Optional[PlaybookInfo]:
        """Parst grundlegende Playbook-Informationen"""
        with open(yml_file, "r") as f:
            content = yaml.safe_load(f)

        if not content or not isinstance(content, list):
            return None

        # Erstes Play
        first_play = content[0] if content else {}
        hosts_target = first_play.get("hosts", "all")
        description = first_play.get("name", None)

        return PlaybookInfo(
            name=yml_file.stem,
            path=str(yml_file.relative_to(self.playbook_dir.parent)),
            hosts_target=hosts_target,
            description=description,
        )

    def reload(self):
        """Scannt erneut"""
        self._scan()

    def get_playbooks(self) -> List[PlaybookInfo]:
        """Gibt alle Playbooks zurück"""
        self._check_and_rescan()
        return self._playbooks

    def get_playbook_detail(self, name: str) -> Optional[PlaybookDetail]:
        """Gibt detaillierte Playbook-Informationen zurück"""
        self._check_and_rescan()
        yml_file = self.playbook_dir / f"{name}.yml"
        if not yml_file.exists():
            yml_file = self.playbook_dir / f"{name}.yaml"
        if not yml_file.exists():
            return None

        with open(yml_file, "r") as f:
            raw_content = f.read()

        content = yaml.safe_load(raw_content)
        if not content or not isinstance(content, list):
            return None

        first_play = content[0] if content else {}

        # Tasks extrahieren
        tasks = []
        for play in content:
            if "tasks" in play:
                for task in play["tasks"]:
                    task_name = task.get("name", "Unnamed task")
                    tasks.append(task_name)

        # Roles extrahieren
        roles = []
        for play in content:
            if "roles" in play:
                for role in play["roles"]:
                    if isinstance(role, str):
                        roles.append(role)
                    elif isinstance(role, dict):
                        roles.append(role.get("role", role.get("name", "unknown")))

        # Variablen extrahieren
        vars_list = []
        for play in content:
            if "vars" in play:
                vars_list.extend(play["vars"].keys())

        return PlaybookDetail(
            name=name,
            path=str(yml_file.relative_to(self.playbook_dir.parent)),
            hosts_target=first_play.get("hosts", "all"),
            description=first_play.get("name", None),
            content=raw_content,
            tasks=tasks,
            roles=roles,
            vars=vars_list,
        )
