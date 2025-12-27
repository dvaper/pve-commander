"""
AuditLog - Manipulationssicheres Audit-Logging mit Merkle-Tree Verifikation
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Index
from sqlalchemy.sql import func

from app.database import Base


class AuditLog(Base):
    """
    Immutables Audit-Log mit Hash-Chain fuer Integritaetsverifikation.

    Hash-Chain (Merkle-Tree Style):
    - Jeder Eintrag enthaelt Hash des vorherigen Eintrags
    - Chain kann auf Manipulation geprueft werden
    - Separate Tabelle verhindert versehentliches Loeschen

    Design-Prinzipien:
    1. KEIN DELETE: Kein Cascade Delete, kein Delete-Endpoint
    2. KEIN UPDATE: Eintraege sind immutabel
    3. HASH CHAIN: Jeder Eintrag referenziert vorherigen Hash
    4. ROLLBACK INFO: Speichert Daten fuer Undo-Operationen
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Eindeutige Sequenznummer fuer Sortierung
    sequence = Column(Integer, unique=True, nullable=False, index=True)

    # Timestamp (immutabel)
    timestamp = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )

    # Wer hat die Aktion ausgefuehrt
    user_id = Column(Integer, nullable=True)  # NULL fuer System-Aktionen
    username = Column(String(100), nullable=True)

    # Aktions-Klassifizierung
    action_type = Column(String(50), nullable=False, index=True)
    # Werte: CREATE, READ, UPDATE, DELETE, EXECUTE, LOGIN, LOGOUT,
    #        PERMISSION_CHANGE, ROLE_CHANGE, ROLLBACK

    # Resource-Informationen
    resource_type = Column(String(50), nullable=False, index=True)
    # Werte: user, role, playbook, execution, inventory, settings,
    #        terraform, vm, backup, notification

    resource_id = Column(String(255), nullable=True)  # ID der betroffenen Resource
    resource_name = Column(String(255), nullable=True)  # Lesbarer Name

    # Aktions-Details (JSON)
    # Enthaelt: old_value, new_value, parameters, changed_fields, etc.
    details = Column(Text, nullable=True)

    # IP-Adresse und User Agent
    ip_address = Column(String(45), nullable=True)  # IPv6-kompatibel
    user_agent = Column(String(500), nullable=True)

    # Request Correlation ID
    correlation_id = Column(String(100), nullable=True, index=True)

    # Rollback-Informationen
    is_rollbackable = Column(Boolean, default=False)
    rollback_data = Column(Text, nullable=True)  # JSON: Daten fuer Undo
    rollback_executed = Column(Boolean, default=False)
    rollback_by_entry_id = Column(Integer, nullable=True)  # Zeigt auf Rollback-Eintrag

    # Hash-Chain fuer Integritaetsverifikation
    entry_hash = Column(String(64), nullable=False, unique=True)  # SHA-256 dieses Eintrags
    previous_hash = Column(String(64), nullable=True)  # Hash des vorherigen Eintrags (NULL fuer ersten)

    # Zusaetzliche Indizes fuer effizientes Abfragen
    __table_args__ = (
        Index("ix_audit_user_action", "user_id", "action_type"),
        Index("ix_audit_resource", "resource_type", "resource_id"),
    )
