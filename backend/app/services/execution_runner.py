"""
Execution Runner - Gemeinsame Logik für Prozess-Ausführung mit Log-Streaming

Wird von AnsibleService und TerraformService verwendet.
"""
import asyncio
import os
from datetime import datetime
from typing import List, Optional, Callable, Dict, Any

from sqlalchemy import select

from app.database import async_session
from app.models.execution import Execution
from app.models.execution_log import ExecutionLog
from app.services.output_streamer import OutputStreamer
from app.services.notification_service import NotificationService


class ExecutionRunner:
    """
    Führt externe Prozesse aus und streamt Logs in Echtzeit.

    Features:
    - Stdout/Stderr parallel lesen
    - WebSocket-Broadcast für Live-Updates
    - Batch-Speicherung der Logs in die DB
    - Execution-Status-Tracking
    - Callbacks für Erfolg/Fehler
    """

    def __init__(
        self,
        execution_id: int,
        cmd: List[str],
        cwd: str,
        env: Optional[Dict[str, str]] = None,
        on_success: Optional[Callable] = None,
        on_failure: Optional[Callable] = None,
    ):
        self.execution_id = execution_id
        self.cmd = cmd
        self.cwd = cwd
        self.env = env or os.environ.copy()
        self.on_success = on_success
        self.on_failure = on_failure

        self.sequence_num = 0
        self.logs_buffer: List[Dict[str, Any]] = []

    async def run(self) -> int:
        """
        Führt den Prozess aus und streamt Logs.

        Returns:
            Exit-Code des Prozesses
        """
        # Status auf running setzen
        await self._set_status("running")

        try:
            # Prozess starten
            process = await asyncio.create_subprocess_exec(
                *self.cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.cwd,
                env=self.env,
            )

            # Log-Queue für Thread-sichere Kommunikation
            log_queue: asyncio.Queue = asyncio.Queue()
            streams_done = [False, False]

            async def read_stream(stream, log_type: str, stream_idx: int):
                """Liest einen Stream und schreibt in die Queue"""
                try:
                    while True:
                        line = await stream.readline()
                        if not line:
                            break
                        content = line.decode("utf-8", errors="replace")
                        await log_queue.put((log_type, content))
                finally:
                    streams_done[stream_idx] = True

            async def process_logs():
                """Verarbeitet Logs aus der Queue"""
                while True:
                    try:
                        log_type, content = await asyncio.wait_for(
                            log_queue.get(), timeout=0.5
                        )
                        self.sequence_num += 1

                        # Log für späteres Speichern vormerken
                        self.logs_buffer.append({
                            "execution_id": self.execution_id,
                            "log_type": log_type,
                            "content": content,
                            "sequence_num": self.sequence_num,
                        })

                        # WebSocket broadcast (sofort)
                        await OutputStreamer.broadcast(
                            self.execution_id,
                            {
                                "type": log_type,
                                "content": content,
                                "sequence_num": self.sequence_num,
                            }
                        )

                        log_queue.task_done()
                    except asyncio.TimeoutError:
                        # Prüfen ob beide Streams fertig sind
                        if all(streams_done):
                            # Queue leeren
                            await self._drain_queue(log_queue)
                            break

            # Streams parallel lesen, Logs verarbeiten
            await asyncio.gather(
                read_stream(process.stdout, "stdout", 0),
                read_stream(process.stderr, "stderr", 1),
                process_logs(),
            )

            # Auf Prozess-Ende warten
            return_code = await process.wait()

            # Logs in DB speichern
            await self._save_logs()

            # Execution finalisieren
            await self._finalize(return_code)

            return return_code

        except Exception as e:
            await self._handle_error(e)
            return -1

    async def _drain_queue(self, queue: asyncio.Queue):
        """Leert die Queue und verarbeitet verbleibende Logs"""
        while not queue.empty():
            try:
                log_type, content = queue.get_nowait()
                self.sequence_num += 1
                self.logs_buffer.append({
                    "execution_id": self.execution_id,
                    "log_type": log_type,
                    "content": content,
                    "sequence_num": self.sequence_num,
                })
                await OutputStreamer.broadcast(
                    self.execution_id,
                    {
                        "type": log_type,
                        "content": content,
                        "sequence_num": self.sequence_num,
                    }
                )
            except asyncio.QueueEmpty:
                break

    async def _set_status(self, status: str):
        """Setzt den Execution-Status"""
        async with async_session() as db:
            result = await db.execute(
                select(Execution).where(Execution.id == self.execution_id)
            )
            execution = result.scalar_one_or_none()
            if execution:
                execution.status = status
                if status == "running":
                    execution.started_at = datetime.now()
                await db.commit()

    async def _save_logs(self):
        """Speichert alle Logs in die Datenbank (Batch)"""
        if not self.logs_buffer:
            return

        async with async_session() as db:
            for log_data in self.logs_buffer:
                log_entry = ExecutionLog(**log_data)
                db.add(log_entry)
            await db.commit()

    async def _finalize(self, return_code: int):
        """Finalisiert die Execution nach Prozess-Ende"""
        async with async_session() as db:
            result = await db.execute(
                select(Execution).where(Execution.id == self.execution_id)
            )
            execution = result.scalar_one_or_none()
            if not execution:
                return

            execution.status = "success" if return_code == 0 else "failed"
            execution.exit_code = return_code
            execution.finished_at = datetime.now()

            if execution.started_at:
                execution.duration_seconds = (
                    execution.finished_at - execution.started_at
                ).total_seconds()

            await db.commit()

            # Ansible-Benachrichtigungen senden
            if execution.execution_type == "ansible":
                try:
                    notification_service = NotificationService(db)
                    if return_code == 0:
                        await notification_service.notify(
                            event_type="ansible_completed",
                            subject=f"Playbook '{execution.playbook_name}' erfolgreich",
                            message=(
                                f"Das Playbook '{execution.playbook_name}' wurde erfolgreich ausgefuehrt.\n\n"
                                f"Details:\n"
                                f"- Ziel: {execution.target_hosts or 'alle'}\n"
                                f"- Dauer: {execution.duration_seconds:.1f} Sekunden"
                            ),
                            payload={
                                "playbook_name": execution.playbook_name,
                                "target_hosts": execution.target_hosts,
                                "duration_seconds": execution.duration_seconds,
                                "execution_id": execution.id,
                            }
                        )
                    else:
                        await notification_service.notify(
                            event_type="ansible_failed",
                            subject=f"Playbook '{execution.playbook_name}' fehlgeschlagen",
                            message=(
                                f"Das Playbook '{execution.playbook_name}' ist fehlgeschlagen.\n\n"
                                f"Details:\n"
                                f"- Ziel: {execution.target_hosts or 'alle'}\n"
                                f"- Exit-Code: {return_code}\n"
                                f"- Dauer: {execution.duration_seconds:.1f} Sekunden"
                            ),
                            payload={
                                "playbook_name": execution.playbook_name,
                                "target_hosts": execution.target_hosts,
                                "exit_code": return_code,
                                "duration_seconds": execution.duration_seconds,
                                "execution_id": execution.id,
                            }
                        )
                except Exception as notify_error:
                    print(f"Warnung: Benachrichtigung konnte nicht gesendet werden: {notify_error}")

            # Callbacks ausführen
            if return_code == 0 and self.on_success:
                try:
                    await self.on_success()
                except Exception as callback_error:
                    await OutputStreamer.broadcast(
                        self.execution_id,
                        {
                            "type": "stderr",
                            "content": f"Callback-Warnung: {str(callback_error)}\n",
                            "sequence_num": self.sequence_num + 1,
                        }
                    )

            if return_code != 0 and self.on_failure:
                try:
                    await self.on_failure()
                except Exception as callback_error:
                    await OutputStreamer.broadcast(
                        self.execution_id,
                        {
                            "type": "stderr",
                            "content": f"Cleanup-Warnung: {str(callback_error)}\n",
                            "sequence_num": self.sequence_num + 1,
                        }
                    )

            # Abschluss-Nachricht senden
            await OutputStreamer.broadcast(
                self.execution_id,
                {
                    "type": "finished",
                    "status": execution.status,
                    "exit_code": return_code,
                    "duration": execution.duration_seconds,
                }
            )

    async def _handle_error(self, error: Exception):
        """Behandelt Fehler während der Ausführung"""
        import traceback
        print(f"[ERROR] Execution {self.execution_id} failed: {error}", flush=True)
        traceback.print_exc()

        # Logs speichern
        async with async_session() as db:
            for log_data in self.logs_buffer:
                log_entry = ExecutionLog(**log_data)
                db.add(log_entry)

            # Fehler-Log hinzufügen
            error_log = ExecutionLog(
                execution_id=self.execution_id,
                log_type="stderr",
                content=f"Fehler: {str(error)}\n",
                sequence_num=self.sequence_num + 1,
            )
            db.add(error_log)
            await db.commit()

        # Execution als failed markieren
        async with async_session() as db:
            result = await db.execute(
                select(Execution).where(Execution.id == self.execution_id)
            )
            execution = result.scalar_one_or_none()
            if execution:
                execution.status = "failed"
                execution.finished_at = datetime.now()
                if execution.started_at:
                    execution.duration_seconds = (
                        execution.finished_at - execution.started_at
                    ).total_seconds()
                await db.commit()

                # Failure-Callback
                if self.on_failure:
                    try:
                        await self.on_failure()
                    except Exception:
                        pass

                await OutputStreamer.broadcast(
                    self.execution_id,
                    {
                        "type": "finished",
                        "status": "failed",
                        "error": str(error),
                    }
                )
