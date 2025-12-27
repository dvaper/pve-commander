"""
VM History Service - Verwaltet den Änderungsverlauf für VMs
"""
from typing import Optional, List
from datetime import datetime

from sqlalchemy import select, desc

from app.database import async_session
from app.models.vm_history import VMHistory


class VMHistoryService:
    """Service für VM-Änderungsverlauf"""

    async def log_change(
        self,
        vm_name: str,
        action: str,
        user_id: int,
        tf_config_before: Optional[str] = None,
        tf_config_after: Optional[str] = None,
        execution_id: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> int:
        """
        Protokolliert eine Änderung an einer VM.

        Args:
            vm_name: Name der VM
            action: Art der Änderung (created, updated, deployed, destroyed, imported, config_changed)
            user_id: User-ID des Ausführenden
            tf_config_before: TF-Konfiguration vor der Änderung
            tf_config_after: TF-Konfiguration nach der Änderung
            execution_id: Optionale Verknüpfung zur Execution
            metadata: Zusätzliche Metadaten (dict)

        Returns:
            ID des History-Eintrags
        """
        async with async_session() as db:
            history_entry = VMHistory(
                vm_name=vm_name,
                action=action,
                user_id=user_id,
                tf_config_before=tf_config_before,
                tf_config_after=tf_config_after,
                execution_id=execution_id,
                extra_data=metadata or {},
            )
            db.add(history_entry)
            await db.commit()
            await db.refresh(history_entry)
            return history_entry.id

    async def get_vm_history(
        self,
        vm_name: str,
        limit: int = 50,
    ) -> List[dict]:
        """
        Holt den Änderungsverlauf einer bestimmten VM.

        Args:
            vm_name: Name der VM
            limit: Maximale Anzahl Einträge

        Returns:
            Liste von History-Einträgen
        """
        async with async_session() as db:
            result = await db.execute(
                select(VMHistory)
                .where(VMHistory.vm_name == vm_name)
                .order_by(desc(VMHistory.created_at))
                .limit(limit)
            )
            entries = result.scalars().all()

            return [
                {
                    "id": e.id,
                    "vm_name": e.vm_name,
                    "action": e.action,
                    "user_id": e.user_id,
                    "execution_id": e.execution_id,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                    "metadata": e.extra_data or {},
                    "has_config_diff": bool(e.tf_config_before or e.tf_config_after),
                }
                for e in entries
            ]

    async def get_global_history(
        self,
        limit: int = 100,
        action_filter: Optional[str] = None,
    ) -> List[dict]:
        """
        Holt den globalen Änderungsverlauf aller VMs.

        Args:
            limit: Maximale Anzahl Einträge
            action_filter: Optional: Nur bestimmte Aktionen anzeigen

        Returns:
            Liste von History-Einträgen
        """
        async with async_session() as db:
            query = select(VMHistory).order_by(desc(VMHistory.created_at)).limit(limit)

            if action_filter:
                query = query.where(VMHistory.action == action_filter)

            result = await db.execute(query)
            entries = result.scalars().all()

            return [
                {
                    "id": e.id,
                    "vm_name": e.vm_name,
                    "action": e.action,
                    "user_id": e.user_id,
                    "execution_id": e.execution_id,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                    "metadata": e.extra_data or {},
                    "has_config_diff": bool(e.tf_config_before or e.tf_config_after),
                }
                for e in entries
            ]

    async def get_history_entry(self, history_id: int) -> Optional[dict]:
        """
        Holt einen einzelnen History-Eintrag mit vollständigen Daten.

        Args:
            history_id: ID des History-Eintrags

        Returns:
            History-Eintrag mit TF-Configs oder None
        """
        async with async_session() as db:
            result = await db.execute(
                select(VMHistory).where(VMHistory.id == history_id)
            )
            entry = result.scalar_one_or_none()

            if not entry:
                return None

            return {
                "id": entry.id,
                "vm_name": entry.vm_name,
                "action": entry.action,
                "user_id": entry.user_id,
                "execution_id": entry.execution_id,
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
                "metadata": entry.extra_data or {},
                "tf_config_before": entry.tf_config_before,
                "tf_config_after": entry.tf_config_after,
            }

    async def rollback_to_entry(
        self,
        history_id: int,
        user_id: int,
    ) -> dict:
        """
        Setzt eine VM auf einen früheren Stand zurück.

        Args:
            history_id: ID des History-Eintrags auf den zurückgesetzt werden soll
            user_id: User-ID des Ausführenden

        Returns:
            dict mit success, message oder error
        """
        from app.services.vm_deployment_service import vm_deployment_service

        async with async_session() as db:
            result = await db.execute(
                select(VMHistory).where(VMHistory.id == history_id)
            )
            entry = result.scalar_one_or_none()

            if not entry:
                return {"success": False, "error": "History-Eintrag nicht gefunden"}

            # Prüfen ob wir eine TF-Konfiguration haben zum Zurücksetzen
            target_config = entry.tf_config_before
            if not target_config:
                return {
                    "success": False,
                    "error": "Kein vorheriger Konfigurationsstand verfügbar",
                }

            vm_name = entry.vm_name

            # Aktuelle Konfiguration lesen (für History)
            current_config = None
            tf_file = vm_deployment_service.get_tf_filepath(vm_name)
            if tf_file.exists():
                current_config = tf_file.read_text()

            # TF-Datei mit alter Konfiguration überschreiben
            tf_file.write_text(target_config)

            # History-Eintrag für Rollback erstellen
            await self.log_change(
                vm_name=vm_name,
                action="rollback",
                user_id=user_id,
                tf_config_before=current_config,
                tf_config_after=target_config,
                metadata={
                    "rollback_to_history_id": history_id,
                    "original_action": entry.action,
                },
            )

            return {
                "success": True,
                "message": f"VM '{vm_name}' auf Stand von {entry.created_at.strftime('%d.%m.%Y %H:%M')} zurückgesetzt",
                "vm_name": vm_name,
                "rollback_history_id": history_id,
            }

    async def get_stats(self) -> dict:
        """
        Holt Statistiken über den Änderungsverlauf.

        Returns:
            dict mit Statistiken
        """
        async with async_session() as db:
            # Gesamtanzahl
            total_result = await db.execute(select(VMHistory))
            total = len(total_result.scalars().all())

            # Anzahl pro Aktion
            actions = {}
            for action in ["created", "deployed", "destroyed", "imported", "config_changed", "rollback"]:
                result = await db.execute(
                    select(VMHistory).where(VMHistory.action == action)
                )
                actions[action] = len(result.scalars().all())

            return {
                "total": total,
                "by_action": actions,
            }


# Singleton-Instanz
vm_history_service = VMHistoryService()
