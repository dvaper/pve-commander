"""
Structured Logging Konfiguration fuer PVE Commander

Stellt JSON-formatierte Logs bereit fuer bessere Log-Aggregation
und -Analyse (z.B. mit Loki, ELK Stack, etc.)

Verwendung:
    from app.logging_config import setup_logging, get_logger

    # Beim App-Start:
    setup_logging()

    # In Modulen:
    logger = get_logger(__name__)
    logger.info("Message", extra={"user_id": 123, "action": "login"})
"""

import json
import logging
import sys
from datetime import datetime
from typing import Any

from app.config import settings


class StructuredFormatter(logging.Formatter):
    """
    JSON-Formatter fuer strukturierte Logs.

    Output-Format:
    {
        "timestamp": "2025-12-29T14:30:00.123456",
        "level": "INFO",
        "logger": "app.routers.auth",
        "message": "User logged in",
        "user_id": 123,
        "request_id": "abc-123"
    }
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Source location (nur in Debug-Mode fuer Performance)
        if settings.debug:
            log_data["source"] = {
                "file": record.filename,
                "line": record.lineno,
                "function": record.funcName,
            }

        # Exception-Info hinzufuegen falls vorhanden
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Extra-Felder aus record hinzufuegen
        # Ignoriere Standard-LogRecord-Attribute
        standard_attrs = {
            "name", "msg", "args", "created", "filename", "funcName",
            "levelname", "levelno", "lineno", "module", "msecs",
            "pathname", "process", "processName", "relativeCreated",
            "stack_info", "exc_info", "exc_text", "thread", "threadName",
            "taskName", "message",
        }

        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                log_data[key] = value

        return json.dumps(log_data, default=str, ensure_ascii=False)


class HumanReadableFormatter(logging.Formatter):
    """
    Menschenlesbarer Formatter fuer Entwicklung.

    Output-Format:
    2025-12-29 14:30:00 | INFO     | app.routers.auth | User logged in | user_id=123
    """

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname

        # Farbe hinzufuegen wenn TTY
        if sys.stderr.isatty():
            color = self.COLORS.get(level, "")
            level_str = f"{color}{level:8}{self.RESET}"
        else:
            level_str = f"{level:8}"

        # Basis-Nachricht
        message = f"{timestamp} | {level_str} | {record.name} | {record.getMessage()}"

        # Extra-Felder hinzufuegen
        standard_attrs = {
            "name", "msg", "args", "created", "filename", "funcName",
            "levelname", "levelno", "lineno", "module", "msecs",
            "pathname", "process", "processName", "relativeCreated",
            "stack_info", "exc_info", "exc_text", "thread", "threadName",
            "taskName", "message",
        }

        extras = []
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                extras.append(f"{key}={value}")

        if extras:
            message += f" | {', '.join(extras)}"

        # Exception hinzufuegen
        if record.exc_info:
            message += f"\n{self.formatException(record.exc_info)}"

        return message


def setup_logging(json_format: bool = None) -> None:
    """
    Konfiguriert das Logging-System.

    Args:
        json_format: Erzwinge JSON-Format (True) oder Human-Readable (False).
                     Wenn None, wird JSON in Production verwendet.
    """
    # Entscheide Format basierend auf Environment
    if json_format is None:
        # JSON in Production, Human-Readable in Development
        use_json = not settings.debug
    else:
        use_json = json_format

    # Formatter waehlen
    if use_json:
        formatter = StructuredFormatter()
    else:
        formatter = HumanReadableFormatter()

    # Root Logger konfigurieren
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    # Alle existierenden Handler entfernen
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console Handler hinzufuegen
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Spezifische Logger-Level setzen
    # Reduziere Noise von Third-Party Libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.debug else logging.WARNING
    )


def get_logger(name: str) -> logging.Logger:
    """
    Gibt einen Logger mit dem angegebenen Namen zurueck.

    Convenience-Funktion die sicherstellt, dass der Logger
    korrekt konfiguriert ist.

    Args:
        name: Logger-Name (normalerweise __name__)

    Returns:
        Konfigurierter Logger
    """
    return logging.getLogger(name)


class LogContext:
    """
    Context Manager fuer zusaetzliche Log-Felder.

    Verwendung:
        with LogContext(request_id="abc-123", user_id=42):
            logger.info("Processing request")
            # Log enthaelt automatisch request_id und user_id
    """

    _context: dict[str, Any] = {}

    def __init__(self, **kwargs: Any):
        self.context = kwargs
        self._old_context: dict[str, Any] = {}

    def __enter__(self) -> "LogContext":
        self._old_context = LogContext._context.copy()
        LogContext._context.update(self.context)
        return self

    def __exit__(self, *args: Any) -> None:
        LogContext._context = self._old_context

    @classmethod
    def get_context(cls) -> dict[str, Any]:
        """Gibt den aktuellen Log-Context zurueck."""
        return cls._context.copy()


class ContextualLogger(logging.LoggerAdapter):
    """
    Logger-Adapter der automatisch Context-Felder hinzufuegt.

    Verwendung:
        logger = ContextualLogger(logging.getLogger(__name__))
        logger.info("Message")  # Enthaelt automatisch LogContext-Felder
    """

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        extra = kwargs.get("extra", {})
        extra.update(LogContext.get_context())
        kwargs["extra"] = extra
        return msg, kwargs
