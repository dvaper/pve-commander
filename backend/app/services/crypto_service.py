"""
Crypto Service - Verschluesselung von sensiblen Daten
"""
import base64
import hashlib
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

logger = logging.getLogger(__name__)


def _get_encryption_key() -> bytes:
    """
    Leitet einen Verschluesselungskey aus dem SECRET_KEY ab.
    Der Key muss 32 Bytes lang und base64-encoded sein.
    """
    secret = settings.secret_key
    if not secret:
        raise ValueError("SECRET_KEY ist nicht gesetzt - Verschluesselung nicht moeglich")

    # SHA256 Hash des Secrets (32 Bytes)
    key_bytes = hashlib.sha256(secret.encode()).digest()
    # Base64-encode fuer Fernet
    return base64.urlsafe_b64encode(key_bytes)


def encrypt_value(value: str) -> str:
    """
    Verschluesselt einen String-Wert.

    Args:
        value: Klartext-Wert

    Returns:
        Verschluesselter Wert (base64-encoded)
    """
    if not value:
        return ""

    try:
        fernet = Fernet(_get_encryption_key())
        encrypted = fernet.encrypt(value.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Verschluesselung fehlgeschlagen: {e}")
        raise ValueError("Verschluesselung fehlgeschlagen")


def decrypt_value(encrypted_value: str) -> Optional[str]:
    """
    Entschluesselt einen verschluesselten Wert.

    Args:
        encrypted_value: Verschluesselter Wert

    Returns:
        Klartext-Wert oder None bei Fehler
    """
    if not encrypted_value:
        return None

    try:
        fernet = Fernet(_get_encryption_key())
        decrypted = fernet.decrypt(encrypted_value.encode())
        return decrypted.decode()
    except InvalidToken:
        logger.error("Entschluesselung fehlgeschlagen: Ungueltiger Token (Key geaendert?)")
        return None
    except Exception as e:
        logger.error(f"Entschluesselung fehlgeschlagen: {e}")
        return None


def is_encrypted(value: str) -> bool:
    """
    Prueft ob ein Wert verschluesselt ist (versucht zu entschluesseln).

    Args:
        value: Zu pruefender Wert

    Returns:
        True wenn Wert erfolgreich entschluesselt werden kann
    """
    if not value:
        return False

    try:
        fernet = Fernet(_get_encryption_key())
        fernet.decrypt(value.encode())
        return True
    except Exception:
        # Entschluesselung fehlgeschlagen (InvalidToken, ValueError, etc.)
        return False
