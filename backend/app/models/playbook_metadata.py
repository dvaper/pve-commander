"""
PlaybookMetadata - Erweiterte Metadaten fuer Playbook-Kategorisierung
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.sql import func

from app.database import Base


class PlaybookMetadata(Base):
    """
    Erweiterte Metadaten fuer Playbooks.

    Ermoeglicht:
    - Rollen-basierte Zugriffskontrolle nach OS-Type/Kategorie
    - Durchsuchbare/filterbare Playbook-Listen
    - Benutzerdefinierte Tags
    - Risiko-Level und Bestaetigungspflicht
    """
    __tablename__ = "playbook_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Playbook Identifier (entspricht Dateiname ohne .yml)
    playbook_name = Column(String(255), unique=True, nullable=False, index=True)

    # Anzeigename
    display_name = Column(String(255), nullable=True)

    # Beschreibung (kann aus YAML extrahiert werden)
    description = Column(Text, nullable=True)

    # OS-Type Einschraenkung
    os_type = Column(String(20), default="all", nullable=False)  # linux, windows, all

    # Kategorie
    category = Column(String(50), default="custom", nullable=False)
    # Kategorien: system, maintenance, deployment, security, monitoring, custom

    # Freie Tags (JSON Array)
    tags = Column(Text, nullable=True)  # ["docker", "nginx", "production"]

    # Bestaetigung vor Ausfuehrung erforderlich
    requires_confirmation = Column(Boolean, default=False)

    # Risiko-Level (info, warning, danger)
    risk_level = Column(String(20), default="info")

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    updated_by = Column(String(100), nullable=True)
