"""
Audit Service - Manipulationssicheres Logging mit Merkle-Tree Verifikation

Sicherheitsfeatures:
1. Hash Chain: Jeder Eintrag enthaelt Hash des vorherigen Eintrags
2. Entry Hash: SHA-256 des Eintrags-Inhalts (verhindert Modifikation)
3. Sequenznummern: Monoton steigend (verhindert Einfuegen/Loeschen)
4. Kein Delete API: Audit-Logs koennen nicht via API geloescht werden
5. Verifikation: Chain kann auf Integritaet geprueft werden
"""
import hashlib
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
import uuid

from app.models.audit_log import AuditLog
from app.models.audit_rollback import AuditRollback

logger = logging.getLogger(__name__)


# =============================================================================
# Action Types
# =============================================================================

class ActionType:
    """Definierte Aktionstypen fuer Audit-Logging."""
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    EXECUTE = "EXECUTE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    LOGIN_FAILED = "LOGIN_FAILED"
    PERMISSION_CHANGE = "PERMISSION_CHANGE"
    ROLE_CHANGE = "ROLE_CHANGE"
    ROLLBACK = "ROLLBACK"
    SETTINGS_CHANGE = "SETTINGS_CHANGE"
    BACKUP = "BACKUP"
    RESTORE = "RESTORE"


class ResourceType:
    """Definierte Ressourcentypen fuer Audit-Logging."""
    USER = "user"
    ROLE = "role"
    PERMISSION = "permission"
    PLAYBOOK = "playbook"
    EXECUTION = "execution"
    INVENTORY = "inventory"
    SETTINGS = "settings"
    TERRAFORM = "terraform"
    VM = "vm"
    BACKUP = "backup"
    NOTIFICATION = "notification"
    SESSION = "session"
    NETBOX = "netbox"


# =============================================================================
# Audit Service
# =============================================================================

class AuditService:
    """
    Manipulationssicherer Audit-Logging Service.

    Usage:
        audit = AuditService(db)
        await audit.log(
            user_id=1,
            username="admin",
            action_type=ActionType.UPDATE,
            resource_type=ResourceType.USER,
            resource_id="5",
            details={"old_value": {...}, "new_value": {...}},
            rollback_data={"restore": {...}},
            request_context={"ip": "192.168.1.1", "user_agent": "..."}
        )
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # Core Logging
    # =========================================================================

    async def log(
        self,
        action_type: str,
        resource_type: str,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        details: Optional[Dict] = None,
        rollback_data: Optional[Dict] = None,
        is_rollbackable: Optional[bool] = None,
        request_context: Optional[Dict] = None,
        correlation_id: Optional[str] = None,
    ) -> AuditLog:
        """
        Erstellt einen neuen Audit-Log-Eintrag mit Hash-Chain.

        Args:
            action_type: CREATE, READ, UPDATE, DELETE, EXECUTE, LOGIN, etc.
            resource_type: user, role, playbook, execution, etc.
            user_id: ID des ausfuehrenden Benutzers (None fuer System)
            username: Benutzername zum Zeitpunkt der Aktion
            resource_id: ID der betroffenen Ressource
            resource_name: Lesbarer Name der Ressource
            details: JSON-serialisierbare Aktions-Details
            rollback_data: Daten fuer Undo-Operation
            request_context: IP, User Agent, etc.
            correlation_id: Request-Tracking-ID

        Returns:
            Erstellter AuditLog-Eintrag
        """
        # Naechste Sequenznummer holen
        sequence = await self._get_next_sequence()

        # Vorherigen Hash holen
        previous_hash = await self._get_last_hash()

        # Correlation ID generieren falls nicht angegeben
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        # Timestamp festlegen
        timestamp = datetime.utcnow()

        # Eintrag erstellen
        entry = AuditLog(
            sequence=sequence,
            timestamp=timestamp,
            user_id=user_id,
            username=username,
            action_type=action_type,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            resource_name=resource_name,
            details=json.dumps(details, default=str, ensure_ascii=False) if details else None,
            ip_address=request_context.get("ip") if request_context else None,
            user_agent=request_context.get("user_agent") if request_context else None,
            correlation_id=correlation_id,
            is_rollbackable=is_rollbackable if is_rollbackable is not None else rollback_data is not None,
            rollback_data=json.dumps(rollback_data, default=str, ensure_ascii=False) if rollback_data else None,
            previous_hash=previous_hash,
            entry_hash="",  # Wird gleich berechnet
        )

        # Entry Hash berechnen
        entry.entry_hash = self._calculate_hash(entry, timestamp)

        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)

        logger.debug(
            f"Audit: {action_type} {resource_type} "
            f"by {username or 'system'} (seq={sequence})"
        )

        return entry

    def _calculate_hash(self, entry: AuditLog, timestamp: datetime) -> str:
        """
        Berechnet SHA-256 Hash des Audit-Eintrags.

        Hash beinhaltet:
        - sequence
        - timestamp (als normalisierter ISO String ohne Timezone)
        - user_id
        - username
        - action_type
        - resource_type
        - resource_id
        - details
        - previous_hash

        Dies stellt sicher, dass jede Modifikation erkennbar ist.
        """
        # Timestamp normalisieren: Timezone entfernen und auf Sekunden runden
        # Dies verhindert Hash-Mismatches durch DB-Roundtrip
        normalized_ts = timestamp.replace(tzinfo=None, microsecond=0)

        data = {
            "sequence": entry.sequence,
            "timestamp": normalized_ts.isoformat(),
            "user_id": entry.user_id,
            "username": entry.username,
            "action_type": entry.action_type,
            "resource_type": entry.resource_type,
            "resource_id": entry.resource_id,
            "details": entry.details,
            "previous_hash": entry.previous_hash,
        }

        # Deterministische JSON-Serialisierung
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()

    async def _get_next_sequence(self) -> int:
        """Holt naechste Sequenznummer (thread-safe)."""
        result = await self.db.execute(
            select(func.max(AuditLog.sequence))
        )
        max_seq = result.scalar() or 0
        return max_seq + 1

    async def _get_last_hash(self) -> Optional[str]:
        """Holt Hash des letzten Eintrags."""
        result = await self.db.execute(
            select(AuditLog.entry_hash)
            .order_by(desc(AuditLog.sequence))
            .limit(1)
        )
        row = result.first()
        return row[0] if row else None

    # =========================================================================
    # Query Methods
    # =========================================================================

    async def get_logs(
        self,
        page: int = 1,
        page_size: int = 50,
        user_id: Optional[int] = None,
        action_type: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        correlation_id: Optional[str] = None,
    ) -> Tuple[List[AuditLog], int]:
        """
        Holt Audit-Logs mit Filterung und Paginierung.

        Returns:
            Tuple aus (Liste der Logs, Gesamtanzahl)
        """
        query = select(AuditLog)
        count_query = select(func.count(AuditLog.id))

        # Filter anwenden
        if user_id is not None:
            query = query.where(AuditLog.user_id == user_id)
            count_query = count_query.where(AuditLog.user_id == user_id)

        if action_type:
            query = query.where(AuditLog.action_type == action_type)
            count_query = count_query.where(AuditLog.action_type == action_type)

        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
            count_query = count_query.where(AuditLog.resource_type == resource_type)

        if resource_id:
            query = query.where(AuditLog.resource_id == resource_id)
            count_query = count_query.where(AuditLog.resource_id == resource_id)

        if start_date:
            query = query.where(AuditLog.timestamp >= start_date)
            count_query = count_query.where(AuditLog.timestamp >= start_date)

        if end_date:
            query = query.where(AuditLog.timestamp <= end_date)
            count_query = count_query.where(AuditLog.timestamp <= end_date)

        if correlation_id:
            query = query.where(AuditLog.correlation_id == correlation_id)
            count_query = count_query.where(AuditLog.correlation_id == correlation_id)

        # Sortierung und Paginierung
        query = query.order_by(desc(AuditLog.timestamp))
        query = query.offset((page - 1) * page_size).limit(page_size)

        # Ausfuehren
        result = await self.db.execute(query)
        logs = result.scalars().all()

        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        return list(logs), total

    async def get_log_by_id(self, audit_id: int) -> Optional[AuditLog]:
        """Holt einen einzelnen Audit-Log-Eintrag."""
        result = await self.db.execute(
            select(AuditLog).where(AuditLog.id == audit_id)
        )
        return result.scalar_one_or_none()

    async def get_log_by_sequence(self, sequence: int) -> Optional[AuditLog]:
        """Holt Audit-Log nach Sequenznummer."""
        result = await self.db.execute(
            select(AuditLog).where(AuditLog.sequence == sequence)
        )
        return result.scalar_one_or_none()

    # =========================================================================
    # Verification
    # =========================================================================

    async def verify_chain(
        self,
        start_sequence: Optional[int] = None,
        end_sequence: Optional[int] = None
    ) -> Tuple[bool, List[Dict], int]:
        """
        Verifiziert Integritaet der Audit-Log-Chain.

        Args:
            start_sequence: Start des Bereichs (default: 1)
            end_sequence: Ende des Bereichs (default: letzter)

        Returns:
            Tuple aus (is_valid, Liste der Fehler, geprufte Eintraege)
        """
        query = select(AuditLog).order_by(AuditLog.sequence)

        if start_sequence:
            query = query.where(AuditLog.sequence >= start_sequence)
        if end_sequence:
            query = query.where(AuditLog.sequence <= end_sequence)

        result = await self.db.execute(query)
        entries = result.scalars().all()

        errors = []
        previous_hash = None
        entries_checked = 0

        # Wenn wir nicht bei 1 starten, vorherigen Hash holen
        if start_sequence and start_sequence > 1:
            prev_entry = await self.get_log_by_sequence(start_sequence - 1)
            if prev_entry:
                previous_hash = prev_entry.entry_hash

        for entry in entries:
            entries_checked += 1

            # Hash-Chain verifizieren
            if entry.previous_hash != previous_hash:
                errors.append({
                    "sequence": entry.sequence,
                    "error": "previous_hash_mismatch",
                    "expected": previous_hash,
                    "actual": entry.previous_hash,
                })

            # Entry-Hash verifizieren
            calculated_hash = self._calculate_hash(entry, entry.timestamp)
            if entry.entry_hash != calculated_hash:
                errors.append({
                    "sequence": entry.sequence,
                    "error": "entry_hash_mismatch",
                    "expected": calculated_hash,
                    "actual": entry.entry_hash,
                })

            previous_hash = entry.entry_hash

        return len(errors) == 0, errors, entries_checked

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_stats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Gibt Audit-Statistiken zurueck.
        """
        base_query = select(AuditLog)

        if start_date:
            base_query = base_query.where(AuditLog.timestamp >= start_date)
        if end_date:
            base_query = base_query.where(AuditLog.timestamp <= end_date)

        # Gesamtzahl
        total_result = await self.db.execute(
            select(func.count(AuditLog.id)).select_from(base_query.subquery())
        )
        total = total_result.scalar() or 0

        # Nach Action Type
        action_result = await self.db.execute(
            select(AuditLog.action_type, func.count(AuditLog.id))
            .where(AuditLog.timestamp >= start_date if start_date else True)
            .where(AuditLog.timestamp <= end_date if end_date else True)
            .group_by(AuditLog.action_type)
        )
        by_action = {row[0]: row[1] for row in action_result.fetchall()}

        # Nach Resource Type
        resource_result = await self.db.execute(
            select(AuditLog.resource_type, func.count(AuditLog.id))
            .where(AuditLog.timestamp >= start_date if start_date else True)
            .where(AuditLog.timestamp <= end_date if end_date else True)
            .group_by(AuditLog.resource_type)
        )
        by_resource = {row[0]: row[1] for row in resource_result.fetchall()}

        # Rollbackable
        rollback_result = await self.db.execute(
            select(func.count(AuditLog.id))
            .where(AuditLog.is_rollbackable == True)
            .where(AuditLog.rollback_executed == False)
            .where(AuditLog.timestamp >= start_date if start_date else True)
            .where(AuditLog.timestamp <= end_date if end_date else True)
        )
        rollbackable = rollback_result.scalar() or 0

        return {
            "total_entries": total,
            "by_action_type": by_action,
            "by_resource_type": by_resource,
            "rollbackable_count": rollbackable,
        }

    # =========================================================================
    # Rollback
    # =========================================================================

    async def request_rollback(
        self,
        audit_id: int,
        user_id: int,
        username: str,
        reason: Optional[str] = None
    ) -> AuditRollback:
        """
        Fordert Rollback eines Audit-Eintrags an.

        Args:
            audit_id: ID des Audit-Eintrags
            user_id: Benutzer der Rollback anfordert
            username: Benutzername
            reason: Grund fuer Rollback

        Returns:
            AuditRollback Record
        """
        # Original-Eintrag holen
        original = await self.get_log_by_id(audit_id)

        if not original:
            raise ValueError(f"Audit-Eintrag {audit_id} nicht gefunden")

        if not original.is_rollbackable:
            raise ValueError(f"Audit-Eintrag {audit_id} ist nicht rollback-faehig")

        if original.rollback_executed:
            raise ValueError(f"Audit-Eintrag {audit_id} wurde bereits zurueckgerollt")

        # Rollback-Request erstellen
        rollback = AuditRollback(
            original_audit_id=original.id,
            original_sequence=original.sequence,
            requested_by_user_id=user_id,
            requested_by_username=username,
            reason=reason,
            status="pending",
        )

        self.db.add(rollback)
        await self.db.commit()
        await self.db.refresh(rollback)

        logger.info(
            f"Rollback angefordert fuer Audit #{audit_id} von {username}"
        )

        return rollback

    async def get_rollback_requests(
        self,
        status: Optional[str] = None
    ) -> List[AuditRollback]:
        """Holt Rollback-Requests."""
        query = select(AuditRollback).order_by(desc(AuditRollback.requested_at))

        if status:
            query = query.where(AuditRollback.status == status)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_rollback_by_id(self, rollback_id: int) -> Optional[AuditRollback]:
        """Holt einen Rollback-Request."""
        result = await self.db.execute(
            select(AuditRollback).where(AuditRollback.id == rollback_id)
        )
        return result.scalar_one_or_none()


# =============================================================================
# Convenience Functions
# =============================================================================

async def audit_log(
    db: AsyncSession,
    action_type: str,
    resource_type: str,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    resource_id: Optional[str] = None,
    resource_name: Optional[str] = None,
    details: Optional[Dict] = None,
    rollback_data: Optional[Dict] = None,
    request_context: Optional[Dict] = None,
) -> AuditLog:
    """Convenience-Funktion fuer schnelles Audit-Logging."""
    service = AuditService(db)
    return await service.log(
        action_type=action_type,
        resource_type=resource_type,
        user_id=user_id,
        username=username,
        resource_id=resource_id,
        resource_name=resource_name,
        details=details,
        rollback_data=rollback_data,
        request_context=request_context,
    )
