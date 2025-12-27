"""
BackupScheduler - Automatische Backups nach Zeitplan

Verwendet APScheduler fuer geplante Backup-Jobs.
Wird beim App-Start initialisiert und laeuft im Hintergrund.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.database import async_session
from app.models.backup import BackupSchedule
from app.services.backup_service import backup_service, BackupOptions

logger = logging.getLogger(__name__)


class BackupScheduler:
    """Scheduler fuer automatische Backups"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._job_id = "scheduled_backup"
        self._running = False

    async def start(self):
        """Startet den Scheduler"""
        if self._running:
            logger.warning("BackupScheduler laeuft bereits")
            return

        try:
            # Scheduler starten
            self.scheduler.start()
            self._running = True
            logger.info("BackupScheduler gestartet")

            # Zeitplan aus Datenbank laden und Job einrichten
            await self._update_job_from_db()

        except Exception as e:
            logger.error(f"BackupScheduler Start fehlgeschlagen: {e}")

    async def stop(self):
        """Stoppt den Scheduler"""
        if not self._running:
            return

        try:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("BackupScheduler gestoppt")
        except Exception as e:
            logger.error(f"BackupScheduler Stop fehlgeschlagen: {e}")

    async def _update_job_from_db(self):
        """Aktualisiert den Job basierend auf der Datenbank-Konfiguration"""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(BackupSchedule).where(BackupSchedule.id == 1)
                )
                schedule = result.scalar_one_or_none()

                if not schedule or not schedule.enabled:
                    # Zeitplan deaktiviert - Job entfernen falls vorhanden
                    self._remove_job()
                    logger.info("Geplantes Backup deaktiviert")
                    return

                # Trigger erstellen basierend auf Frequenz
                trigger = self._create_trigger(schedule.frequency, schedule.time)

                if trigger:
                    await self._add_or_update_job(trigger, schedule)
                    logger.info(
                        f"Backup-Job konfiguriert: {schedule.frequency} um {schedule.time}"
                    )

        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren des Backup-Jobs: {e}")

    def _create_trigger(self, frequency: str, time_str: str) -> Optional[CronTrigger]:
        """Erstellt einen CronTrigger basierend auf Frequenz und Zeit"""
        try:
            hour, minute = time_str.split(":")
            hour = int(hour)
            minute = int(minute)

            if frequency == "daily":
                return CronTrigger(hour=hour, minute=minute)
            elif frequency == "weekly":
                # Sonntag um die angegebene Zeit
                return CronTrigger(day_of_week="sun", hour=hour, minute=minute)
            else:
                logger.warning(f"Unbekannte Frequenz: {frequency}")
                return None

        except Exception as e:
            logger.error(f"Fehler beim Erstellen des Triggers: {e}")
            return None

    async def _add_or_update_job(self, trigger: CronTrigger, schedule: BackupSchedule):
        """Fuegt einen Job hinzu oder aktualisiert ihn"""
        # Existierenden Job entfernen
        self._remove_job()

        # Neuen Job hinzufuegen
        self.scheduler.add_job(
            self._run_scheduled_backup,
            trigger=trigger,
            id=self._job_id,
            name="Scheduled Backup",
            replace_existing=True,
        )

        # Naechsten Lauf berechnen und speichern
        job = self.scheduler.get_job(self._job_id)
        if job:
            next_run = job.next_run_time
            await self._update_next_run(next_run)

    def _remove_job(self):
        """Entfernt den geplanten Job"""
        try:
            if self.scheduler.get_job(self._job_id):
                self.scheduler.remove_job(self._job_id)
        except Exception:
            pass

    async def _update_next_run(self, next_run: datetime):
        """Aktualisiert next_run in der Datenbank"""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(BackupSchedule).where(BackupSchedule.id == 1)
                )
                schedule = result.scalar_one_or_none()

                if schedule:
                    schedule.next_run = next_run
                    await session.commit()

        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren von next_run: {e}")

    async def _run_scheduled_backup(self):
        """Fuehrt das geplante Backup aus"""
        logger.info("Starte geplantes Backup...")

        try:
            # Optionen aus Datenbank laden
            async with async_session() as session:
                result = await session.execute(
                    select(BackupSchedule).where(BackupSchedule.id == 1)
                )
                schedule = result.scalar_one_or_none()

                if not schedule:
                    logger.error("Kein Backup-Zeitplan gefunden")
                    return

                # Optionen laden
                import json
                options_data = json.loads(schedule.options) if schedule.options else {}
                options = BackupOptions(**options_data)

                # Backup erstellen
                result = await backup_service.create_backup(options, is_scheduled=True)

                # last_run aktualisieren
                schedule.last_run = datetime.now()

                # next_run berechnen
                job = self.scheduler.get_job(self._job_id)
                if job:
                    schedule.next_run = job.next_run_time

                await session.commit()

                if result.success:
                    logger.info(f"Geplantes Backup erfolgreich: {result.filename}")

                    # Alte Backups aufraeumen
                    await backup_service.cleanup_old_backups(schedule.retention_days)
                else:
                    logger.error(f"Geplantes Backup fehlgeschlagen: {result.message}")

        except Exception as e:
            logger.error(f"Fehler beim geplanten Backup: {e}")

    async def reload_schedule(self):
        """Laedt den Zeitplan neu aus der Datenbank"""
        await self._update_job_from_db()


# Singleton-Instanz
backup_scheduler = BackupScheduler()


async def start_backup_scheduler():
    """Startet den Backup-Scheduler (fuer main.py)"""
    await backup_scheduler.start()


async def stop_backup_scheduler():
    """Stoppt den Backup-Scheduler (fuer main.py)"""
    await backup_scheduler.stop()
