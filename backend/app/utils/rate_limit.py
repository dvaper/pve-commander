"""
Rate Limiting Utilities

In-Memory Rate-Limiting fuer API-Endpoints.
Schuetzt gegen Brute-Force-Angriffe auf Login und andere sensible Endpoints.

HINWEIS: Bei Multi-Instance-Deployments sollte Redis verwendet werden.
Diese In-Memory-Implementierung funktioniert nur pro Instanz.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)

# Thread-safe Rate-Limit Cache
_rate_limit_lock = threading.RLock()
_rate_limit_cache: Dict[str, List[datetime]] = defaultdict(list)


def check_rate_limit(
    key: str,
    limit: int = 5,
    window_seconds: int = 60,
    log_exceeded: bool = True
) -> bool:
    """
    Prueft ob ein Rate-Limit ueberschritten wurde.

    Args:
        key: Eindeutiger Schluessel (z.B. "login:192.168.1.1" oder "login:username")
        limit: Maximale Anzahl Anfragen im Zeitfenster
        window_seconds: Zeitfenster in Sekunden
        log_exceeded: Ob bei Ueberschreitung geloggt werden soll

    Returns:
        True wenn Anfrage erlaubt, False wenn Rate-Limit erreicht
    """
    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=window_seconds)

    with _rate_limit_lock:
        # Alte Eintraege entfernen
        _rate_limit_cache[key] = [t for t in _rate_limit_cache[key] if t > cutoff]

        # Pruefen ob Limit erreicht
        if len(_rate_limit_cache[key]) >= limit:
            if log_exceeded:
                logger.warning(f"Rate-Limit erreicht fuer {key}: {limit}/{window_seconds}s")
            return False

        # Neuen Zeitstempel hinzufuegen
        _rate_limit_cache[key].append(now)
        return True


def get_rate_limit_remaining(key: str, limit: int = 5, window_seconds: int = 60) -> int:
    """
    Gibt die verbleibende Anzahl Anfragen zurueck.

    Args:
        key: Eindeutiger Schluessel
        limit: Maximale Anzahl Anfragen
        window_seconds: Zeitfenster in Sekunden

    Returns:
        Anzahl verbleibender Anfragen
    """
    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=window_seconds)

    with _rate_limit_lock:
        _rate_limit_cache[key] = [t for t in _rate_limit_cache[key] if t > cutoff]
        return max(0, limit - len(_rate_limit_cache[key]))


def clear_rate_limit(key: str) -> None:
    """
    Loescht Rate-Limit-Eintraege fuer einen Schluessel.

    Nuetzlich nach erfolgreichem Login um fehlgeschlagene Versuche zurueckzusetzen.
    """
    with _rate_limit_lock:
        if key in _rate_limit_cache:
            del _rate_limit_cache[key]


def cleanup_expired_entries(max_age_seconds: int = 3600) -> int:
    """
    Entfernt abgelaufene Eintraege aus dem Cache.

    Sollte periodisch aufgerufen werden um Memory-Leaks zu vermeiden.

    Args:
        max_age_seconds: Maximales Alter der Eintraege

    Returns:
        Anzahl entfernter Schluessel
    """
    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=max_age_seconds)
    removed = 0

    with _rate_limit_lock:
        keys_to_remove = []
        for key, timestamps in _rate_limit_cache.items():
            # Entferne alte Timestamps
            _rate_limit_cache[key] = [t for t in timestamps if t > cutoff]
            # Merke leere Keys zum Loeschen
            if not _rate_limit_cache[key]:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del _rate_limit_cache[key]
            removed += 1

    return removed


# Rate-Limit Konfiguration (kann ueberschrieben werden)
class RateLimitConfig:
    """Konfiguration fuer verschiedene Rate-Limits."""

    # Login: 5 Versuche pro Minute pro IP
    LOGIN_LIMIT = 5
    LOGIN_WINDOW = 60  # Sekunden

    # Login pro Username: 10 Versuche pro 5 Minuten
    LOGIN_USER_LIMIT = 10
    LOGIN_USER_WINDOW = 300  # Sekunden

    # Password Reset: 3 Versuche pro Minute
    PASSWORD_RESET_LIMIT = 3
    PASSWORD_RESET_WINDOW = 60

    # Setup Endpoints: 10 Versuche pro Minute
    SETUP_LIMIT = 10
    SETUP_WINDOW = 60
