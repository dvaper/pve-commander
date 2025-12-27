"""
Custom SQLAlchemy Column Types fuer PVE Commander

Stellt wiederverwendbare Column-Typen bereit:
- JSONColumn: Automatische JSON Serialisierung/Deserialisierung
- EncryptedColumn: Verschluesselte Text-Spalten (TODO)

Verwendung:
    from app.models.types import JSONColumn

    class MyModel(Base):
        data = Column(JSONColumn, default={})
        items = Column(JSONColumn, default=[])
"""

import json
from typing import Any, Optional
from sqlalchemy import Text, TypeDecorator


class JSONColumn(TypeDecorator):
    """
    SQLAlchemy TypeDecorator fuer JSON-Daten.

    Speichert JSON als Text in SQLite, serialisiert/deserialisiert automatisch.

    Vorteile gegenueber manuellem json.loads/json.dumps:
    - Automatische Serialisierung beim Speichern
    - Automatische Deserialisierung beim Laden
    - Einheitliches Verhalten in allen Models
    - Einfacheres Testing

    Beispiel:
        class Execution(Base):
            target_hosts = Column(JSONColumn, default=[])
            extra_vars = Column(JSONColumn, default={})

        # Verwendung:
        execution.target_hosts = ["host1", "host2"]
        execution.extra_vars = {"key": "value"}

        # Beim Laden sind es automatisch Python-Objekte:
        print(execution.target_hosts)  # ['host1', 'host2']
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Optional[str]:
        """Konvertiert Python-Objekt zu JSON-String fuer DB."""
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False, default=str)

    def process_result_value(self, value: Optional[str], dialect: Any) -> Any:
        """Konvertiert JSON-String aus DB zu Python-Objekt."""
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            # Bei fehlerhaftem JSON: leeres Objekt zurueckgeben
            return None

    def copy(self, **kwargs: Any) -> "JSONColumn":
        """Erstellt eine Kopie dieses Types."""
        return JSONColumn()


class JSONList(JSONColumn):
    """
    JSONColumn der bei None/fehlerhaft eine leere Liste zurueckgibt.

    Verwendung:
        tags = Column(JSONList, default=[])
    """

    def process_result_value(self, value: Optional[str], dialect: Any) -> list:
        result = super().process_result_value(value, dialect)
        if result is None:
            return []
        if not isinstance(result, list):
            return []
        return result

    def copy(self, **kwargs: Any) -> "JSONList":
        """Erstellt eine Kopie dieses Types."""
        return JSONList()


class JSONDict(JSONColumn):
    """
    JSONColumn der bei None/fehlerhaft ein leeres Dict zurueckgibt.

    Verwendung:
        extra_vars = Column(JSONDict, default={})
    """

    def process_result_value(self, value: Optional[str], dialect: Any) -> dict:
        result = super().process_result_value(value, dialect)
        if result is None:
            return {}
        if not isinstance(result, dict):
            return {}
        return result

    def copy(self, **kwargs: Any) -> "JSONDict":
        """Erstellt eine Kopie dieses Types."""
        return JSONDict()
