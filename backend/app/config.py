"""
Konfiguration fuer PVE Commander

Alle Einstellungen werden aus Umgebungsvariablen und .env Datei geladen.
Siehe .env.example fuer verfuegbare Optionen.

Hot-Reload: Nach Aenderungen an der .env Datei kann reload_settings()
aufgerufen werden. Alle Module die 'settings' importiert haben sehen
automatisch die neuen Werte (via SettingsProxy).
"""
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional, Any
from dotenv import load_dotenv
import os
import threading
import logging
import warnings

logger = logging.getLogger(__name__)

# Security: Default-Wert fuer SECRET_KEY (nur fuer Entwicklung!)
INSECURE_SECRET_KEY = "change-me-in-production"


class Settings(BaseSettings):
    """Application Settings - geladen aus Umgebungsvariablen"""

    # ==========================================================================
    # App Einstellungen
    # ==========================================================================
    app_name: str = "PVE Commander"
    debug: bool = False
    secret_key: str = INSECURE_SECRET_KEY  # WARNUNG: In Produktion aendern!

    @property
    def is_secret_key_insecure(self) -> bool:
        """Prueft ob der unsichere Default-Secret-Key verwendet wird."""
        return self.secret_key == INSECURE_SECRET_KEY

    # JWT Auth
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 Stunden

    # App Admin (aus Setup-Wizard)
    app_admin_user: str = "admin"
    app_admin_password: Optional[str] = None  # Wenn None, wird generiert
    app_admin_email: str = "admin@local"

    # ==========================================================================
    # Datenbank
    # ==========================================================================
    # SQLite fuer App-Daten (Users, Executions, History)
    data_dir: str = "/data"

    @property
    def database_url(self) -> str:
        """SQLite Datenbank-Pfad"""
        return f"sqlite+aiosqlite:///{self.data_dir}/db/commander.db"

    # ==========================================================================
    # Pfade (aus DATA_DIR abgeleitet)
    # ==========================================================================
    inventory_dir: str = "/data/inventory"
    playbooks_dir: str = "/data/playbooks"
    roles_dir: str = "/data/roles"
    terraform_dir: str = "/data/terraform"
    ssh_key_path: str = "/data/ssh/id_ed25519"

    @property
    def ansible_inventory_path(self) -> str:
        """Hauptpfad zum Ansible Inventory"""
        return f"{self.inventory_dir}/hosts.yml"

    @property
    def ansible_playbook_dir(self) -> str:
        """Alias fuer playbooks_dir (Kompatibilitaet)"""
        return self.playbooks_dir

    # ==========================================================================
    # NetBox (interner Container)
    # ==========================================================================
    netbox_url: str = "http://netbox:8080"
    netbox_token: Optional[str] = None
    # Externe URL fuer Frontend (konfigurierbar im Setup-Wizard)
    netbox_external_url: Optional[str] = None

    # ==========================================================================
    # Proxmox API
    # ==========================================================================
    proxmox_host: str = ""
    proxmox_user: str = "terraform@pve"
    proxmox_token_id: Optional[str] = None
    proxmox_token_secret: Optional[str] = None
    proxmox_verify_ssl: bool = False

    # Alias-Properties fuer Kompatibilitaet mit bestehendem Code
    @property
    def proxmox_token_name(self) -> Optional[str]:
        """Extrahiert Token-Name aus Token-ID (user@realm!token-name -> token-name)"""
        if self.proxmox_token_id and "!" in self.proxmox_token_id:
            return self.proxmox_token_id.split("!")[-1]
        return self.proxmox_token_id

    @property
    def proxmox_token_value(self) -> Optional[str]:
        """Alias fuer proxmox_token_secret"""
        return self.proxmox_token_secret

    # ==========================================================================
    # Proxmox Inventory Sync
    # ==========================================================================
    proxmox_inventory_sync: bool = False
    proxmox_sync_interval: int = 60  # Minuten
    proxmox_sync_tag: str = ""  # Nur VMs mit diesem Tag importieren

    # ==========================================================================
    # Ansible Einstellungen
    # ==========================================================================
    ansible_remote_user: str = "ansible"
    ansible_ssh_key: str = "id_ed25519"
    ansible_host_key_checking: bool = False

    # ==========================================================================
    # VM Deployment Defaults
    # ==========================================================================
    default_ssh_user: str = "ansible"
    default_template_id: int = 940001
    default_storage: str = "local-ssd"
    default_vlan: int = 60

    # ==========================================================================
    # CORS
    # ==========================================================================
    cors_origins: list[str] = ["*"]  # Im Container: Frontend ist am gleichen Origin

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Case-insensitive environment variables
        case_sensitive = False
        # Extra Variablen ignorieren (z.B. fuer andere Container)
        extra = "ignore"


# =============================================================================
# Settings Proxy fuer Hot-Reload Support (Thread-Safe)
# =============================================================================

# Lock fuer Thread-sichere Settings-Zugriffe
_settings_lock = threading.RLock()


class SettingsProxy:
    """
    Thread-sichere Proxy-Klasse die alle Attributzugriffe an die aktuelle
    Settings-Instanz weiterleitet.

    Ermoeglicht Hot-Reload: Nach reload_settings() sehen alle Module die bereits
    'settings' importiert haben automatisch die neuen Werte.

    Thread-Safety: Verwendet RLock fuer sichere Zugriffe bei parallelen Requests.
    """

    def __getattr__(self, name: str) -> Any:
        with _settings_lock:
            return getattr(_current_settings, name)

    def __setattr__(self, name: str, value: Any) -> None:
        with _settings_lock:
            setattr(_current_settings, name, value)

    def __repr__(self) -> str:
        with _settings_lock:
            return f"SettingsProxy({_current_settings!r})"


def _load_initial_settings() -> Settings:
    """Laedt die initialen Settings aus der .env Datei."""
    env_file = os.getenv("ENV_FILE", "/app/.env")
    if os.path.exists(env_file):
        load_dotenv(env_file, override=True)
    return Settings()


# Interne Settings-Instanz (wird bei reload ersetzt)
_current_settings: Settings = _load_initial_settings()

# Oeffentlicher Proxy (bleibt immer das gleiche Objekt)
settings: SettingsProxy = SettingsProxy()


def reload_settings(env_file: str = None) -> Settings:
    """
    Laedt die Settings neu aus der .env Datei (Thread-Safe).

    Wird vom Setup-Wizard aufgerufen nachdem die Konfiguration gespeichert wurde.
    Alle Module die 'settings' importiert haben sehen automatisch die neuen Werte.

    Thread-Safety: Verwendet Lock um Race Conditions zu vermeiden.
    """
    global _current_settings

    # Bestimme den Pfad zur .env Datei
    if env_file is None:
        env_file = os.getenv("ENV_FILE", "/app/.env")

    # Lade die .env Datei in die Umgebungsvariablen (override=True)
    if os.path.exists(env_file):
        load_dotenv(env_file, override=True)

    # Thread-sicheres Update der Settings-Instanz
    with _settings_lock:
        _current_settings = Settings()
        return _current_settings


def get_settings() -> Settings:
    """Gibt die aktuelle Settings-Instanz zurueck (Thread-Safe)."""
    with _settings_lock:
        return _current_settings


def check_security_warnings() -> list[str]:
    """
    Prueft auf unsichere Konfiguration und gibt Warnungen zurueck.

    Diese Funktion sollte beim App-Start aufgerufen werden.
    Gibt eine Liste von Warnmeldungen zurueck.
    """
    warnings_list = []

    with _settings_lock:
        # CRIT-06: Unsicherer SECRET_KEY
        if _current_settings.is_secret_key_insecure:
            msg = (
                "SICHERHEITSWARNUNG: Der Standard-SECRET_KEY wird verwendet! "
                "Bitte setzen Sie einen sicheren SECRET_KEY in der .env Datei. "
                "JWT-Tokens koennten gefaelscht werden."
            )
            warnings_list.append(msg)
            logger.warning(msg)

        # Debug-Modus in Produktion
        if _current_settings.debug and not _current_settings.is_secret_key_insecure:
            msg = "WARNUNG: Debug-Modus ist aktiviert. Nicht fuer Produktion empfohlen."
            warnings_list.append(msg)
            logger.warning(msg)

        # CORS Wildcard
        if "*" in _current_settings.cors_origins:
            msg = (
                "SICHERHEITSWARNUNG: CORS erlaubt alle Origins (*). "
                "Fuer Produktion sollten spezifische Origins konfiguriert werden."
            )
            warnings_list.append(msg)
            logger.warning(msg)

        # MED-02: SQLite Datenbank-Sicherheit
        db_path = Path(_current_settings.data_dir) / "db" / "commander.db"
        if db_path.exists():
            # Pruefen ob Datenbank-Verzeichnis ausserhalb von /data liegt
            if not str(db_path).startswith("/data"):
                msg = (
                    "SICHERHEITSHINWEIS: SQLite-Datenbank liegt ausserhalb von /data. "
                    "Stellen Sie sicher, dass der Pfad angemessen geschuetzt ist."
                )
                warnings_list.append(msg)
                logger.info(msg)

        # MED-03: Docker Socket Warnung
        docker_socket = Path("/var/run/docker.sock")
        if docker_socket.exists():
            msg = (
                "SICHERHEITSHINWEIS: Docker Socket ist gemountet. "
                "Der Container hat Zugriff auf den Docker-Daemon des Hosts. "
                "Dies ist fuer Terraform/Docker-Operationen erforderlich, "
                "aber ein Sicherheitsrisiko bei kompromittierter App."
            )
            warnings_list.append(msg)
            logger.info(msg)

    return warnings_list


def log_security_warnings_on_startup():
    """Gibt Sicherheitswarnungen beim App-Start aus."""
    warnings_list = check_security_warnings()
    if warnings_list:
        logger.warning("=" * 60)
        logger.warning("SICHERHEITSWARNUNGEN BEIM START:")
        for w in warnings_list:
            logger.warning(f"  - {w}")
        logger.warning("=" * 60)
