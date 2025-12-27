"""
NetBox User Service - User-Synchronisation zwischen PVE Commander und NetBox
"""
import logging
from typing import Optional
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class NetBoxUserService:
    """Service für NetBox User-Management"""

    def __init__(self):
        self.base_url = settings.netbox_url
        self.token = settings.netbox_token

    @property
    def headers(self) -> dict:
        """HTTP Headers für NetBox API"""
        return {
            "Authorization": f"Token {self.token}",
            "Content-Type": "application/json",
        }

    def _check_config(self) -> bool:
        """Prüft ob NetBox konfiguriert ist"""
        if not self.base_url or not self.token:
            logger.warning("NetBox nicht konfiguriert (URL oder Token fehlt)")
            return False
        return True

    async def get_user_by_username(self, username: str) -> Optional[dict]:
        """
        Sucht einen NetBox-User nach Benutzername.

        Args:
            username: Benutzername

        Returns:
            User-Daten oder None wenn nicht gefunden
        """
        if not self._check_config():
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/users/users/",
                    params={"username": username},
                    headers=self.headers,
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

                if data.get("count", 0) > 0:
                    return data["results"][0]
                return None

        except Exception as e:
            logger.error(f"NetBox User-Suche fehlgeschlagen: {e}")
            return None

    async def get_user_by_id(self, user_id: int) -> Optional[dict]:
        """
        Holt einen NetBox-User nach ID.

        Args:
            user_id: NetBox User ID

        Returns:
            User-Daten oder None wenn nicht gefunden
        """
        if not self._check_config():
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/users/users/{user_id}/",
                    headers=self.headers,
                    timeout=10.0,
                )
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return response.json()

        except Exception as e:
            logger.error(f"NetBox User abrufen fehlgeschlagen: {e}")
            return None

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        is_staff: bool = False,
        first_name: str = "",
        last_name: str = "",
    ) -> Optional[dict]:
        """
        Erstellt einen neuen User in NetBox.

        Args:
            username: Benutzername
            email: E-Mail-Adresse
            password: Passwort (wird als Klartext gesendet, NetBox hasht es)
            is_staff: Staff-Status (für Admin-Zugang)
            first_name: Vorname (optional)
            last_name: Nachname (optional)

        Returns:
            Erstellter User oder None bei Fehler
        """
        if not self._check_config():
            return None

        # Prüfen ob User bereits existiert
        existing = await self.get_user_by_username(username)
        if existing:
            logger.info(f"NetBox User '{username}' existiert bereits (ID: {existing['id']})")
            return existing

        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "username": username,
                    "email": email or f"{username}@local",
                    "password": password,
                    "is_staff": is_staff,
                    "is_active": True,
                }

                if first_name:
                    payload["first_name"] = first_name
                if last_name:
                    payload["last_name"] = last_name

                response = await client.post(
                    f"{self.base_url}/api/users/users/",
                    json=payload,
                    headers=self.headers,
                    timeout=10.0,
                )
                response.raise_for_status()
                user = response.json()
                logger.info(f"NetBox User '{username}' erstellt (ID: {user['id']})")
                return user

        except httpx.HTTPStatusError as e:
            logger.error(f"NetBox User-Erstellung fehlgeschlagen: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"NetBox User-Erstellung fehlgeschlagen: {e}")
            return None

    async def update_user(
        self,
        user_id: int,
        email: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_staff: Optional[bool] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Aktualisiert einen NetBox-User.

        Args:
            user_id: NetBox User ID
            email: Neue E-Mail (optional)
            is_active: Aktiv-Status (optional)
            is_staff: Staff-Status (optional)
            first_name: Vorname (optional)
            last_name: Nachname (optional)

        Returns:
            Aktualisierter User oder None bei Fehler
        """
        if not self._check_config():
            return None

        try:
            payload = {}
            if email is not None:
                payload["email"] = email
            if is_active is not None:
                payload["is_active"] = is_active
            if is_staff is not None:
                payload["is_staff"] = is_staff
            if first_name is not None:
                payload["first_name"] = first_name
            if last_name is not None:
                payload["last_name"] = last_name

            if not payload:
                logger.warning("Keine Felder zum Aktualisieren angegeben")
                return await self.get_user_by_id(user_id)

            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.base_url}/api/users/users/{user_id}/",
                    json=payload,
                    headers=self.headers,
                    timeout=10.0,
                )
                response.raise_for_status()
                user = response.json()
                logger.info(f"NetBox User ID {user_id} aktualisiert")
                return user

        except Exception as e:
            logger.error(f"NetBox User-Update fehlgeschlagen: {e}")
            return None

    async def change_password(self, user_id: int, password: str) -> bool:
        """
        Ändert das Passwort eines NetBox-Users.

        Args:
            user_id: NetBox User ID
            password: Neues Passwort

        Returns:
            True bei Erfolg, False bei Fehler
        """
        if not self._check_config():
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.base_url}/api/users/users/{user_id}/",
                    json={"password": password},
                    headers=self.headers,
                    timeout=10.0,
                )
                response.raise_for_status()
                logger.info(f"NetBox Passwort für User ID {user_id} geändert")
                return True

        except Exception as e:
            logger.error(f"NetBox Passwort-Änderung fehlgeschlagen: {e}")
            return False

    async def deactivate_user(self, user_id: int) -> bool:
        """
        Deaktiviert einen NetBox-User (statt zu löschen).

        Args:
            user_id: NetBox User ID

        Returns:
            True bei Erfolg, False bei Fehler
        """
        if not self._check_config():
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.base_url}/api/users/users/{user_id}/",
                    json={"is_active": False},
                    headers=self.headers,
                    timeout=10.0,
                )
                response.raise_for_status()
                logger.info(f"NetBox User ID {user_id} deaktiviert")
                return True

        except Exception as e:
            logger.error(f"NetBox User-Deaktivierung fehlgeschlagen: {e}")
            return False

    async def delete_user(self, user_id: int) -> bool:
        """
        Löscht einen NetBox-User vollständig.

        HINWEIS: Normalerweise sollte deactivate_user verwendet werden.

        Args:
            user_id: NetBox User ID

        Returns:
            True bei Erfolg, False bei Fehler
        """
        if not self._check_config():
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.base_url}/api/users/users/{user_id}/",
                    headers=self.headers,
                    timeout=10.0,
                )
                if response.status_code == 204:
                    logger.info(f"NetBox User ID {user_id} gelöscht")
                    return True
                return False

        except Exception as e:
            logger.error(f"NetBox User-Löschung fehlgeschlagen: {e}")
            return False

    async def validate_credentials(self, username: str, password: str) -> bool:
        """
        Validiert Credentials gegen NetBox.

        HINWEIS: NetBox bietet keinen direkten Credential-Check via API.
        Diese Methode ist nur ein Platzhalter für zukünftige Implementierung.

        Args:
            username: Benutzername
            password: Passwort

        Returns:
            True wenn gültig, False wenn ungültig
        """
        logger.warning("NetBox Credential-Validierung nicht implementiert")
        return False

    async def sync_user_from_commander(
        self,
        username: str,
        email: str,
        password: str,
        is_super_admin: bool = False,
    ) -> Optional[int]:
        """
        Synchronisiert einen Commander-User nach NetBox.

        Erstellt den User wenn nicht vorhanden, aktualisiert sonst.

        Args:
            username: Benutzername
            email: E-Mail-Adresse
            password: Klartext-Passwort
            is_super_admin: Ob User Super-Admin ist (wird zu is_staff)

        Returns:
            NetBox User ID oder None bei Fehler
        """
        if not self._check_config():
            return None

        # Prüfen ob User bereits existiert
        existing = await self.get_user_by_username(username)

        if existing:
            # User existiert - Passwort aktualisieren
            user_id = existing["id"]
            await self.change_password(user_id, password)
            await self.update_user(user_id, email=email, is_staff=is_super_admin)
            return user_id
        else:
            # Neuen User erstellen
            user = await self.create_user(
                username=username,
                email=email,
                password=password,
                is_staff=is_super_admin,
            )
            return user["id"] if user else None


# Singleton-Instanz
netbox_user_service = NetBoxUserService()
