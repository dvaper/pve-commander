"""
Ansible Service - Führt Playbooks aus
"""
import asyncio
import json
import logging
import os
from typing import List, Optional
from pathlib import Path

from sqlalchemy import select

from app.database import async_session
from app.models.execution import Execution
from app.config import settings
from app.services.execution_runner import ExecutionRunner

logger = logging.getLogger(__name__)


class AnsibleService:
    """Service für Ansible-Ausführungen"""

    def __init__(self):
        self.playbook_dir = Path(settings.ansible_playbook_dir)
        self.inventory_path = Path(settings.ansible_inventory_path)

    async def run_playbook(
        self,
        execution_id: int,
        playbook_name: str,
        target_hosts: Optional[List[str]] = None,
        target_groups: Optional[List[str]] = None,
        extra_vars: Optional[dict] = None,
    ):
        """Führt ein Playbook aus"""
        # Kommando bauen
        cmd = self._build_command(
            playbook_name,
            target_hosts,
            target_groups,
            extra_vars,
        )

        # Umgebungsvariablen für Ansible
        env = os.environ.copy()
        env["ANSIBLE_FORCE_COLOR"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        env["ANSIBLE_HOST_KEY_CHECKING"] = "False"
        # Optimierte Ansible-Konfiguration verwenden
        ansible_cfg = Path(settings.data_dir) / "config" / "ansible.cfg"
        if ansible_cfg.exists():
            env["ANSIBLE_CONFIG"] = str(ansible_cfg)

        # ExecutionRunner übernimmt Status-Tracking, Log-Streaming und DB-Speicherung
        runner = ExecutionRunner(
            execution_id=execution_id,
            cmd=cmd,
            cwd=str(self.playbook_dir.parent),
            env=env,
        )
        await runner.run()

    def _build_command(
        self,
        playbook_name: str,
        target_hosts: Optional[List[str]] = None,
        target_groups: Optional[List[str]] = None,
        extra_vars: Optional[dict] = None,
    ) -> List[str]:
        """Baut das ansible-playbook Kommando"""
        playbook_path = self.playbook_dir / f"{playbook_name}.yml"
        if not playbook_path.exists():
            playbook_path = self.playbook_dir / f"{playbook_name}.yaml"

        cmd = [
            "ansible-playbook",
            str(playbook_path),
            "-i", str(self.inventory_path),
            "--private-key", settings.ssh_key_path,
            "-u", settings.ansible_remote_user,
        ]

        # Limit (Hosts und Gruppen kombinieren)
        limits = []
        if target_hosts:
            limits.extend(target_hosts)
        if target_groups:
            limits.extend(target_groups)

        if limits:
            cmd.extend(["-l", ",".join(limits)])

        # Auto-Inject: SSH Public Key fuer add-ssh-key Playbook
        effective_vars = dict(extra_vars) if extra_vars else {}
        if playbook_name == "add-ssh-key" and "ssh_public_key" not in effective_vars:
            ssh_pub_path = Path(settings.ssh_key_path).with_suffix(".pub")
            if ssh_pub_path.exists():
                try:
                    ssh_public_key = ssh_pub_path.read_text().strip()
                    effective_vars["ssh_public_key"] = ssh_public_key
                    logger.info("SSH Public Key automatisch fuer add-ssh-key injiziert")
                except Exception as e:
                    logger.warning(f"Konnte SSH Public Key nicht lesen: {e}")

        # Extra Vars
        if effective_vars:
            cmd.extend(["-e", json.dumps(effective_vars)])

        return cmd

    async def wait_for_ssh(
        self,
        host: str,
        port: int = 22,
        timeout: int = 300,
        interval: int = 10,
    ) -> bool:
        """Wartet bis SSH auf dem Host erreichbar ist"""
        import socket
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((host, port))
                sock.close()

                if result == 0:
                    # SSH Port ist offen, kurz warten für SSH-Daemon
                    await asyncio.sleep(5)
                    return True
            except Exception:
                pass

            await asyncio.sleep(interval)

        return False

    async def create_and_run_playbook(
        self,
        playbook_name: str,
        target_host: str,
        user_id: int,
        extra_vars: Optional[dict] = None,
        parent_execution_id: Optional[int] = None,
    ) -> int:
        """Erstellt Execution und führt Playbook aus - Utility für Post-Deploy"""
        async with async_session() as db:
            execution = Execution(
                execution_type="ansible",
                playbook_name=playbook_name,
                target_hosts=target_host,
                extra_vars=json.dumps(extra_vars) if extra_vars else None,
                status="pending",
                user_id=user_id,
            )
            db.add(execution)
            await db.commit()
            await db.refresh(execution)
            execution_id = execution.id

        # Playbook im Hintergrund starten
        asyncio.create_task(
            self.run_playbook(
                execution_id=execution_id,
                playbook_name=playbook_name,
                target_hosts=[target_host],
                extra_vars=extra_vars,
            )
        )

        return execution_id

    async def run_playbook_batch(
        self,
        execution_ids: List[int],
        playbooks: List[str],
        target_hosts: Optional[List[str]] = None,
        target_groups: Optional[List[str]] = None,
        extra_vars: Optional[dict] = None,
    ):
        """
        Fuehrt mehrere Playbooks sequentiell aus.

        Jedes Playbook wartet auf den Abschluss des vorherigen.
        Bei einem Fehler werden nachfolgende Playbooks als 'cancelled' markiert.
        """
        if len(execution_ids) != len(playbooks):
            logger.error("execution_ids und playbooks muessen gleich lang sein")
            return

        failed = False
        for idx, (execution_id, playbook_name) in enumerate(zip(execution_ids, playbooks)):
            if failed:
                # Nachfolgende Executions abbrechen
                async with async_session() as db:
                    result = await db.execute(
                        select(Execution).where(Execution.id == execution_id)
                    )
                    execution = result.scalar_one_or_none()
                    if execution:
                        execution.status = "cancelled"
                        await db.commit()
                continue

            logger.info(f"Batch: Starte Playbook {idx + 1}/{len(playbooks)}: {playbook_name}")

            try:
                # Playbook ausfuehren (blockiert bis fertig)
                await self.run_playbook(
                    execution_id=execution_id,
                    playbook_name=playbook_name,
                    target_hosts=target_hosts,
                    target_groups=target_groups,
                    extra_vars={
                        **(extra_vars or {}),
                        "_batch_index": idx,
                        "_batch_total": len(playbooks),
                    },
                )

                # Status pruefen
                async with async_session() as db:
                    result = await db.execute(
                        select(Execution).where(Execution.id == execution_id)
                    )
                    execution = result.scalar_one_or_none()
                    if execution and execution.status == "failed":
                        logger.warning(f"Batch: Playbook {playbook_name} fehlgeschlagen, breche ab")
                        failed = True

            except Exception as e:
                logger.exception(f"Batch: Fehler bei Playbook {playbook_name}: {e}")
                failed = True

        logger.info(f"Batch: Abgeschlossen. Erfolg: {not failed}")
