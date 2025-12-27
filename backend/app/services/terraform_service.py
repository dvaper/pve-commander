"""
Terraform Service - Führt Terraform-Operationen aus
"""
import asyncio
import os
from datetime import datetime
from typing import List, Optional, Callable
from pathlib import Path

from sqlalchemy import select

from app.database import async_session
from app.models.execution import Execution
from app.models.execution_log import ExecutionLog
from app.config import settings
from app.services.execution_runner import ExecutionRunner
from app.services.output_streamer import OutputStreamer


class TerraformService:
    """Service für Terraform-Ausführungen"""

    def __init__(self):
        self.terraform_dir = Path(settings.terraform_dir)

    async def ensure_initialized(self) -> bool:
        """
        Stellt sicher, dass Terraform initialisiert ist.

        Führt terraform init aus, um neue Module zu registrieren.
        terraform init ist idempotent und schnell wenn nichts geändert wurde.
        Returns True wenn erfolgreich, False bei Fehler.
        """
        try:
            # Immer terraform init ausführen, um neue Module zu registrieren
            # -input=false verhindert interaktive Prompts
            # -upgrade=false verhindert Provider-Updates (schneller)
            process = await asyncio.create_subprocess_exec(
                "terraform", "init", "-input=false", "-upgrade=false",
                cwd=str(self.terraform_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")
                raise RuntimeError(f"terraform init fehlgeschlagen: {error_msg}")

            return True
        except FileNotFoundError:
            raise RuntimeError("Terraform Binary nicht gefunden")

    async def run_action(
        self,
        execution_id: int,
        action: str,  # 'plan', 'apply', 'destroy'
        module: Optional[str] = None,
        variables: Optional[dict] = None,
        on_success: Optional[Callable] = None,  # Callback bei Erfolg
        on_failure: Optional[Callable] = None,  # Callback bei Fehler (z.B. IP-Cleanup)
    ):
        """Führt eine Terraform-Operation aus"""
        # Terraform init sicherstellen
        try:
            await self.ensure_initialized()
        except RuntimeError as e:
            # Init-Fehler als Execution-Fehler speichern
            async with async_session() as db:
                result = await db.execute(
                    select(Execution).where(Execution.id == execution_id)
                )
                execution = result.scalar_one_or_none()
                if execution:
                    execution.status = "failed"
                    execution.finished_at = datetime.now()
                    await db.commit()

                    # Fehler-Log
                    error_log = ExecutionLog(
                        execution_id=execution_id,
                        log_type="stderr",
                        content=f"Terraform Init fehlgeschlagen: {str(e)}\n",
                        sequence_num=1,
                    )
                    db.add(error_log)
                    await db.commit()

                    await OutputStreamer.broadcast(
                        execution_id,
                        {
                            "type": "finished",
                            "status": "failed",
                            "error": str(e),
                        }
                    )

                    # Failure-Callback aufrufen
                    if on_failure:
                        try:
                            await on_failure()
                        except Exception:
                            pass
            return

        # Kommando bauen
        cmd = self._build_command(action, module, variables)

        # Environment vorbereiten
        env = os.environ.copy()
        env["TF_IN_AUTOMATION"] = "1"
        env["TF_CLI_ARGS"] = "-no-color"

        # ExecutionRunner übernimmt Status-Tracking, Log-Streaming und DB-Speicherung
        runner = ExecutionRunner(
            execution_id=execution_id,
            cmd=cmd,
            cwd=str(self.terraform_dir),
            env=env,
            on_success=on_success,
            on_failure=on_failure,
        )
        await runner.run()

    def _build_command(
        self,
        action: str,
        module: Optional[str] = None,
        variables: Optional[dict] = None,
    ) -> List[str]:
        """Baut das terraform Kommando"""
        cmd = ["terraform", action]

        # Auto-approve für apply/destroy
        if action in ["apply", "destroy"]:
            cmd.append("-auto-approve")

        # Target (Modul)
        if module:
            cmd.extend(["-target", f"module.{module}"])

        # Variablen
        if variables:
            for key, value in variables.items():
                cmd.extend(["-var", f"{key}={value}"])

        return cmd

    def get_modules(self) -> List[dict]:
        """Gibt verfügbare Terraform-Module zurück"""
        modules = []

        # .tf Dateien scannen
        for tf_file in self.terraform_dir.glob("*.tf"):
            if tf_file.name in ["variables.tf", "outputs.tf", "versions.tf", "providers.tf"]:
                continue

            # Module aus Datei extrahieren (vereinfacht)
            content = tf_file.read_text()
            if "module " in content:
                modules.append({
                    "file": tf_file.name,
                    "name": tf_file.stem,
                })

        return modules

    async def get_deployed_modules(self) -> List[str]:
        """Holt Liste deployed Module aus Terraform State.

        Führt `terraform state list` aus und extrahiert Module-Namen.
        Returned: ["vm_test", "vm_prod"] für deployed VMs.
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "terraform", "state", "list",
                cwd=str(self.terraform_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                # State nicht initialisiert oder leer
                return []

            # Module extrahieren: "module.vm_test" oder "module.vm_test.proxmox_vm_qemu.vm"
            # → "vm_test"
            modules = set()
            for line in stdout.decode().strip().split("\n"):
                if line.startswith("module."):
                    # module.vm_test.proxmox_vm_qemu.vm → vm_test
                    parts = line.split(".")
                    if len(parts) >= 2:
                        module_name = parts[1]
                        modules.add(module_name)

            return list(modules)
        except FileNotFoundError:
            # Terraform Binary nicht gefunden
            return []
        except Exception:
            return []

    async def remove_module_from_state(self, module_name: str) -> dict:
        """
        Entfernt ein Modul aus dem Terraform State.

        Args:
            module_name: Name des Moduls (ohne 'module.' Prefix)

        Returns:
            dict mit success und ggf. error
        """
        try:
            # Prüfen ob Modul im State existiert
            deployed_modules = await self.get_deployed_modules()
            if module_name not in deployed_modules:
                return {"success": True, "message": "Modul nicht im State"}

            # terraform state rm module.<name>
            process = await asyncio.create_subprocess_exec(
                "terraform", "state", "rm", f"module.{module_name}",
                cwd=str(self.terraform_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return {
                    "success": True,
                    "message": f"Modul {module_name} aus State entfernt",
                    "output": stdout.decode("utf-8", errors="replace"),
                }
            else:
                return {
                    "success": False,
                    "error": stderr.decode("utf-8", errors="replace"),
                }
        except FileNotFoundError:
            return {"success": False, "error": "Terraform Binary nicht gefunden"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def state_list(self) -> List[str]:
        """
        Listet alle Ressourcen im Terraform State.

        Returns:
            Liste von Ressourcen-Adressen (z.B. module.vm_test.proxmox_virtual_environment_vm.vm)
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "terraform", "state", "list",
                cwd=str(self.terraform_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return []

            resources = stdout.decode().strip().split("\n")
            return [r for r in resources if r]  # Leere Zeilen filtern
        except Exception:
            return []

    async def state_show(self, address: str) -> dict:
        """
        Zeigt Details einer Ressource im State.

        Args:
            address: Vollständige Ressourcen-Adresse (z.B. module.vm_test.proxmox_virtual_environment_vm.vm)

        Returns:
            dict mit Ressourcen-Details oder error
        """
        import json as json_lib
        try:
            # terraform show -json liefert den gesamten State als JSON
            process = await asyncio.create_subprocess_exec(
                "terraform", "show", "-json",
                cwd=str(self.terraform_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return {
                    "success": False,
                    "error": stderr.decode("utf-8", errors="replace"),
                }

            # JSON parsen und Ressource filtern
            try:
                state_data = json_lib.loads(stdout.decode())

                # Ressource im State suchen
                resource_data = None
                values = state_data.get("values", {})
                root_module = values.get("root_module", {})

                # Rekursiv in Modulen suchen
                def find_resource(module, target_address):
                    # Direkte Ressourcen im Modul
                    for res in module.get("resources", []):
                        if res.get("address") == target_address:
                            return res
                    # Child-Module durchsuchen
                    for child in module.get("child_modules", []):
                        result = find_resource(child, target_address)
                        if result:
                            return result
                    return None

                resource_data = find_resource(root_module, address)

                if resource_data:
                    return {
                        "success": True,
                        "address": address,
                        "data": resource_data,
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Ressource '{address}' nicht im State gefunden",
                    }
            except json_lib.JSONDecodeError:
                return {
                    "success": False,
                    "error": "State konnte nicht als JSON geparst werden",
                }
        except FileNotFoundError:
            return {"success": False, "error": "Terraform Binary nicht gefunden"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def state_remove(self, address: str) -> dict:
        """
        Entfernt eine Ressource aus dem State (ohne zu löschen).

        Args:
            address: Vollständige Ressourcen-Adresse

        Returns:
            dict mit success und message/error
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "terraform", "state", "rm", address,
                cwd=str(self.terraform_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return {
                    "success": True,
                    "message": f"Ressource {address} aus State entfernt",
                    "output": stdout.decode("utf-8", errors="replace"),
                }
            else:
                return {
                    "success": False,
                    "error": stderr.decode("utf-8", errors="replace"),
                }
        except FileNotFoundError:
            return {"success": False, "error": "Terraform Binary nicht gefunden"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def state_refresh(self) -> dict:
        """
        Aktualisiert den State mit dem aktuellen Infrastruktur-Zustand.

        Returns:
            dict mit success und message/error
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "terraform", "refresh",
                cwd=str(self.terraform_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return {
                    "success": True,
                    "message": "State aktualisiert",
                    "output": stdout.decode("utf-8", errors="replace"),
                }
            else:
                return {
                    "success": False,
                    "error": stderr.decode("utf-8", errors="replace"),
                }
        except FileNotFoundError:
            return {"success": False, "error": "Terraform Binary nicht gefunden"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def import_resource(self, address: str, resource_id: str) -> dict:
        """
        Importiert eine existierende Ressource in den Terraform State.

        Args:
            address: Terraform-Adresse (z.B. module.vm_test.proxmox_virtual_environment_vm.vm)
            resource_id: Ressourcen-ID (z.B. node/vmid für Proxmox VMs)

        Returns:
            dict mit success und message/error
        """
        try:
            # Terraform init sicherstellen
            await self.ensure_initialized()

            process = await asyncio.create_subprocess_exec(
                "terraform", "import", address, resource_id,
                cwd=str(self.terraform_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return {
                    "success": True,
                    "message": f"Ressource {address} importiert",
                    "output": stdout.decode("utf-8", errors="replace"),
                }
            else:
                error_text = stderr.decode("utf-8", errors="replace")
                # Spezifische Fehler abfangen
                if "Resource already managed" in error_text:
                    return {
                        "success": False,
                        "error": "Ressource wird bereits von Terraform verwaltet",
                    }
                return {
                    "success": False,
                    "error": error_text,
                }
        except FileNotFoundError:
            return {"success": False, "error": "Terraform Binary nicht gefunden"}
        except RuntimeError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}
