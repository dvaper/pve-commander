"""
Unit Tests fuer app.auth.security

Tests fuer Password-Hashing und JWT-Token-Handling.
"""
import pytest
from datetime import timedelta

from app.auth.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_token,
)


class TestPasswordHashing:
    """Tests fuer Password-Hashing-Funktionen"""

    def test_hash_password_returns_hash(self):
        """Hash ist nicht gleich Original-Passwort"""
        password = "secure_password_123"
        hashed = get_password_hash(password)

        assert hashed != password
        assert len(hashed) > 50  # bcrypt hashes sind lang

    def test_hash_is_different_each_time(self):
        """Gleiche Passwoerter erzeugen unterschiedliche Hashes (Salt)"""
        password = "same_password"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        assert hash1 != hash2

    def test_verify_password_correct(self):
        """Korrektes Passwort wird verifiziert"""
        password = "my_secret_password"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Falsches Passwort wird abgelehnt"""
        password = "correct_password"
        hashed = get_password_hash(password)

        assert verify_password("wrong_password", hashed) is False

    def test_verify_empty_password(self):
        """Leeres Passwort gegen Hash"""
        hashed = get_password_hash("some_password")

        assert verify_password("", hashed) is False

    def test_hash_empty_password(self):
        """Leeres Passwort kann gehasht werden"""
        hashed = get_password_hash("")

        assert hashed is not None
        assert verify_password("", hashed) is True


class TestJWTToken:
    """Tests fuer JWT Token Handling"""

    def test_create_token_returns_string(self):
        """Token ist ein nicht-leerer String"""
        token = create_access_token(data={"sub": "testuser"})

        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_token_with_custom_expiry(self):
        """Token mit custom Expiry funktioniert"""
        token = create_access_token(
            data={"sub": "testuser"},
            expires_delta=timedelta(hours=2)
        )

        assert isinstance(token, str)
        decoded = decode_token(token)
        assert decoded is not None
        assert decoded.username == "testuser"

    def test_decode_valid_token(self):
        """Valider Token wird korrekt dekodiert"""
        username = "testuser"
        token = create_access_token(data={"sub": username})

        decoded = decode_token(token)

        assert decoded is not None
        assert decoded.username == username

    def test_decode_token_with_user_id(self):
        """Token mit user_id wird korrekt dekodiert"""
        token = create_access_token(data={"sub": "testuser", "user_id": 42})

        decoded = decode_token(token)

        assert decoded is not None
        assert decoded.username == "testuser"
        assert decoded.user_id == 42

    def test_decode_invalid_token(self):
        """Invalider Token gibt None zurueck"""
        decoded = decode_token("invalid.token.here")

        assert decoded is None

    def test_decode_expired_token(self):
        """Abgelaufener Token gibt None zurueck"""
        # Token der sofort ablaeuft
        token = create_access_token(
            data={"sub": "testuser"},
            expires_delta=timedelta(seconds=-1)
        )

        decoded = decode_token(token)

        assert decoded is None

    def test_decode_token_without_sub(self):
        """Token ohne 'sub' claim gibt None zurueck"""
        from jose import jwt
        from app.config import settings

        # Token ohne 'sub' erstellen
        token = jwt.encode(
            {"some": "data"},
            settings.secret_key,
            algorithm=settings.algorithm
        )

        decoded = decode_token(token)

        assert decoded is None

    def test_decode_empty_token(self):
        """Leerer Token gibt None zurueck"""
        decoded = decode_token("")

        assert decoded is None

    def test_token_structure(self):
        """Token hat JWT-Struktur (3 Teile)"""
        token = create_access_token(data={"sub": "testuser"})
        parts = token.split(".")

        assert len(parts) == 3  # header.payload.signature
