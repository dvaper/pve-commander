"""
Terraform Health Service - Periodischer Health-Check fuer Terraform State

Funktionen:
- Periodische Pruefung alle 5 Minuten
- Erkennung verwaister VMs (State vorhanden, Proxmox nicht)
- Notification bei Problemen (Gotify/Email/Webhook)
- Persistenter Health-Status in Datenbank
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select

from app.database import async_session
from app.models.terraform_health import TerraformHealthStatus
from app.services.proxmox_service import proxmox_service
from app.services.terraform_service import TerraformService
from app.services.notification_service import get_notification_service

logger = logging.getLogger(__name__)


class TerraformHealthService:
    """Service fuer periodische Terraform State Health-Checks"""

    def __init__(self):
        self.check_interval_seconds: int = 300  # 5 Minuten
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_orphaned_count: int = 0  # Fuer Deduplizierung von Notifications
        self._terraform_service = TerraformService()

    async def start_background_check(self):
        """Startet den periodischen Background Health-Check"""
        if self._running:
            logger.info("Terraform Health-Check laeuft bereits")
            return

        self._running = True
        self._task = asyncio.create_task(self._check_loop())
        logger.info(f"Terraform Health-Check gestartet (Intervall: {self.check_interval_seconds}s)")

    async def stop_background_check(self):
        """Stoppt den periodischen Background Health-Check"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Terraform Health-Check gestoppt")

    async def _check_loop(self):
        """Hauptschleife fuer periodischen Health-Check"""
        while self._running:
            try:
                # Warten vor erstem Check (gibt App Zeit zum Starten)
                await asyncio.sleep(60)  # 1 Minute nach Start

                while self._running:
                    logger.debug("Starte automatischen Terraform Health-Check...")

                    try:
                        result = await self.check_health()

                        if result.get("healthy"):
                            logger.debug(f"Health-Check OK: {result.get('total_vms', 0)} VMs")
                        else:
                            logger.warning(
                                f"Health-Check: {result.get('orphaned_count', 0)} verwaiste VM(s) gefunden"
                            )

                            # Notification senden wenn neue verwaiste VMs gefunden wurden
                            await self._send_notification_if_needed(result)

                    except Exception as e:
                        logger.error(f"Health-Check Fehler: {e}")

                    await asyncio.sleep(self.check_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Fehler im Health-Check-Loop: {e}")
                await asyncio.sleep(60)  # Bei Fehler 1 Minute warten

    async def check_health(self) -> dict:
        """
        Fuehrt Health-Check durch und speichert Status.

        Vergleicht VMs im Terraform State mit Proxmox.
        Erkennt verwaiste VMs (State vorhanden, Proxmox nicht).

        Returns:
            dict mit healthy, total_vms, orphaned_count, orphaned_vms
        """
        try:
            # Alle Ressourcen aus dem State holen
            state_resources = await self._terraform_service.state_list()

            # Alle VMs aus Proxmox holen
            proxmox_vms = await proxmox_service.get_all_vms()
            proxmox_vmids = {vm.get("vmid") for vm in proxmox_vms}

            orphaned_vms = []
            total_vms = 0

            for address in state_resources:
                # Nur VM-Ressourcen pruefen
                if "proxmox_virtual_environment_vm" not in address:
                    continue

                total_vms += 1

                # State-Details holen um VMID zu extrahieren
                state_detail = await self._terraform_service.state_show(address)
                if not state_detail.get("success") or not state_detail.get("data"):
                    continue

                data = state_detail["data"]
                values = data.get("values", {})

                vmid = values.get("vm_id") or values.get("vmid")
                vm_name = values.get("name")
                node = values.get("node_name") or values.get("target_node")

                # Modul-Name aus Adresse extrahieren
                parts = address.split(".")
                module = parts[1] if len(parts) > 2 and parts[0] == "module" else None

                # Pruefen ob VM in Proxmox existiert
                if vmid and vmid not in proxmox_vmids:
                    orphaned_vms.append({
                        "address": address,
                        "module": module,
                        "vm_name": vm_name,
                        "vmid": vmid,
                        "node": node,
                        "reason": f"VMID {vmid} existiert nicht mehr in Proxmox",
                    })

            healthy = len(orphaned_vms) == 0
            orphaned_count = len(orphaned_vms)

            # Status in Datenbank speichern
            await self._save_status(
                healthy=healthy,
                total_vms=total_vms,
                orphaned_count=orphaned_count,
                orphaned_vms=orphaned_vms,
            )

            return {
                "healthy": healthy,
                "total_vms": total_vms,
                "orphaned_count": orphaned_count,
                "orphaned_vms": orphaned_vms,
            }

        except Exception as e:
            logger.error(f"Health-Check fehlgeschlagen: {e}")
            return {
                "healthy": True,  # Im Fehlerfall nicht als unhealthy markieren
                "total_vms": 0,
                "orphaned_count": 0,
                "orphaned_vms": [],
                "error": str(e),
            }

    async def _save_status(
        self,
        healthy: bool,
        total_vms: int,
        orphaned_count: int,
        orphaned_vms: list,
    ):
        """Speichert den Health-Status in der Datenbank"""
        async with async_session() as session:
            try:
                # Bestehenden Status laden oder neuen erstellen
                result = await session.execute(
                    select(TerraformHealthStatus).where(TerraformHealthStatus.id == 1)
                )
                status = result.scalar_one_or_none()

                now = datetime.utcnow()
                next_check = now + timedelta(seconds=self.check_interval_seconds)

                if status is None:
                    status = TerraformHealthStatus(
                        id=1,
                        healthy=healthy,
                        total_vms=total_vms,
                        orphaned_count=orphaned_count,
                        orphaned_vms=orphaned_vms,  # JSONList serialisiert automatisch
                        last_check=now,
                        next_check=next_check,
                    )
                    session.add(status)
                else:
                    status.healthy = healthy
                    status.total_vms = total_vms
                    status.orphaned_count = orphaned_count
                    status.orphaned_vms = orphaned_vms  # JSONList serialisiert automatisch
                    status.last_check = now
                    status.next_check = next_check

                await session.commit()

            except Exception as e:
                logger.error(f"Fehler beim Speichern des Health-Status: {e}")
                await session.rollback()

    async def get_last_status(self) -> dict:
        """
        Gibt den letzten gespeicherten Health-Status zurueck.

        Returns:
            dict mit healthy, total_vms, orphaned_count, orphaned_vms, last_check, next_check
        """
        async with async_session() as session:
            try:
                result = await session.execute(
                    select(TerraformHealthStatus).where(TerraformHealthStatus.id == 1)
                )
                status = result.scalar_one_or_none()

                if status is None:
                    return {
                        "healthy": True,
                        "total_vms": 0,
                        "orphaned_count": 0,
                        "orphaned_vms": [],
                        "last_check": None,
                        "next_check": None,
                    }

                return {
                    "healthy": status.healthy,
                    "total_vms": status.total_vms,
                    "orphaned_count": status.orphaned_count,
                    "orphaned_vms": status.orphaned_vms or [],  # JSONList deserialisiert automatisch
                    "last_check": status.last_check.isoformat() if status.last_check else None,
                    "next_check": status.next_check.isoformat() if status.next_check else None,
                }

            except Exception as e:
                logger.error(f"Fehler beim Laden des Health-Status: {e}")
                return {
                    "healthy": True,
                    "total_vms": 0,
                    "orphaned_count": 0,
                    "orphaned_vms": [],
                    "last_check": None,
                    "next_check": None,
                    "error": str(e),
                }

    async def _send_notification_if_needed(self, result: dict):
        """
        Sendet Notification wenn neue verwaiste VMs gefunden wurden.

        Dedupliziert Notifications um Spam zu vermeiden:
        - Nur senden wenn orphaned_count sich geaendert hat
        - Oder bei erstem Fund nach healthy-Status
        """
        orphaned_count = result.get("orphaned_count", 0)
        orphaned_vms = result.get("orphaned_vms", [])

        # Nur benachrichtigen wenn sich die Anzahl geaendert hat
        if orphaned_count == self._last_orphaned_count:
            return

        # Merken fuer naechsten Check
        previous_count = self._last_orphaned_count
        self._last_orphaned_count = orphaned_count

        # Nicht benachrichtigen wenn jetzt 0 (Problem geloest)
        if orphaned_count == 0:
            logger.info("Alle verwaisten VMs wurden bereinigt")
            return

        # Notification senden
        try:
            async with async_session() as session:
                notification_service = get_notification_service(session)

                # VM-Liste formatieren
                vm_list = "\n".join([
                    f"- {vm.get('vm_name', 'Unbekannt')} (VMID: {vm.get('vmid', '?')})"
                    for vm in orphaned_vms[:10]  # Max 10 VMs in Notification
                ])

                if len(orphaned_vms) > 10:
                    vm_list += f"\n... und {len(orphaned_vms) - 10} weitere"

                subject = f"Terraform State: {orphaned_count} verwaiste VM(s) gefunden"
                message = (
                    f"Der automatische Health-Check hat {orphaned_count} verwaiste VM(s) "
                    f"im Terraform State erkannt.\n\n"
                    f"Diese VMs sind im State registriert, existieren aber nicht mehr in Proxmox:\n\n"
                    f"{vm_list}\n\n"
                    f"Bitte bereinigen Sie den State ueber die Terraform-Verwaltung."
                )

                if previous_count > 0:
                    message += f"\n\n(Aenderung: {previous_count} -> {orphaned_count})"

                await notification_service.notify(
                    event_type="system_alert",
                    subject=subject,
                    message=message,
                    payload={
                        "orphaned_count": orphaned_count,
                        "orphaned_vms": orphaned_vms,
                        "check_timestamp": datetime.utcnow().isoformat(),
                    }
                )

                logger.info(f"Notification gesendet: {orphaned_count} verwaiste VM(s)")

        except Exception as e:
            logger.error(f"Notification konnte nicht gesendet werden: {e}")

    def get_status(self) -> dict:
        """Gibt den aktuellen Service-Status zurueck (synchron)"""
        return {
            "running": self._running,
            "interval_seconds": self.check_interval_seconds,
            "last_orphaned_count": self._last_orphaned_count,
        }


# Singleton-Instanz
_health_service: Optional[TerraformHealthService] = None


def get_terraform_health_service() -> TerraformHealthService:
    """Gibt die Singleton-Instanz des Health-Service zurueck"""
    global _health_service
    if _health_service is None:
        _health_service = TerraformHealthService()
    return _health_service
