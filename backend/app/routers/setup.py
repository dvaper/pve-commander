"""
Setup Router - Web-basierter Setup-Wizard

Endpoints fuer die initiale Konfiguration beim ersten App-Start.
Diese Endpoints sind ohne Authentifizierung zugaenglich.

Security Features (CRIT-01):
- Rate-Limiting fuer alle Setup-Endpoints
- Logging bei Zugriff nach Setup-Abschluss
- force-Parameter nur fuer Rekonfiguration (mit Warnung)
"""
import os
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.utils.rate_limit import check_rate_limit, RateLimitConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/setup", tags=["setup"])


# =============================================================================
# Schemas
# =============================================================================

class SetupStatus(BaseModel):
    """Status der App-Konfiguration"""
    setup_complete: bool
    has_proxmox_config: bool
    has_secret_key: bool
    has_ssh_key: bool
    missing_items: list[str] = []


class ProxmoxConfig(BaseModel):
    """Proxmox-Verbindungskonfiguration"""
    host: str = Field(..., min_length=1, description="Proxmox Host (IP oder Hostname)")
    token_id: str = Field(..., min_length=1, description="API Token ID (user@realm!token-name)")
    token_secret: str = Field(..., min_length=1, description="API Token Secret")
    verify_ssl: bool = Field(default=False, description="SSL-Zertifikat verifizieren")


class ProxmoxValidationResult(BaseModel):
    """Ergebnis der Proxmox-Verbindungspruefung"""
    success: bool
    message: str
    version: Optional[str] = None
    cluster_name: Optional[str] = None
    node_count: Optional[int] = None
    error: Optional[str] = None


class SetupConfig(BaseModel):
    """Vollstaendige Setup-Konfiguration"""
    # Proxmox
    proxmox_host: str = Field(..., min_length=1)
    proxmox_token_id: str = Field(..., min_length=1)
    proxmox_token_secret: str = Field(..., min_length=1)
    proxmox_verify_ssl: bool = False

    # NetBox Admin Credentials (fuer integriertes NetBox)
    netbox_admin_user: str = Field(default="admin", description="NetBox Admin-Benutzername")
    netbox_admin_password: str = Field(default="admin", min_length=4, description="NetBox Admin-Passwort")
    netbox_admin_email: str = Field(default="admin@example.com", description="NetBox Admin E-Mail")

    # App Admin Credentials
    app_admin_user: str = Field(default="admin", description="App Admin-Benutzername")
    app_admin_password: str = Field(default="", min_length=0, description="App Admin-Passwort (min. 6 Zeichen)")
    app_admin_email: str = Field(default="admin@local", description="App Admin E-Mail")

    # Optionale Einstellungen
    secret_key: Optional[str] = None  # Wird generiert wenn nicht angegeben
    netbox_token: Optional[str] = None
    netbox_url: Optional[str] = None  # Fuer externes NetBox
    netbox_external_url: Optional[str] = None  # Externe URL fuer Browser-Links
    default_ssh_user: str = "ansible"
    ansible_remote_user: str = "ansible"

    # Cloud-Init Einstellungen (optional)
    cloud_init_admin_username: str = Field(
        default="ansible",
        description="Admin-Benutzername fuer Cloud-Init erstellte VMs"
    )
    cloud_init_admin_gecos: str = Field(
        default="Homelab Admin",
        description="Admin GECOS-String (Vollstaendiger Name)"
    )
    cloud_init_ssh_keys: Optional[list[str]] = Field(
        default=None,
        description="SSH Authorized Keys fuer Cloud-Init (ein Key pro Eintrag)"
    )
    cloud_init_phone_home_enabled: bool = Field(
        default=True,
        description="Phone-Home Callback aktivieren"
    )
    cloud_init_nas_snippets_path: Optional[str] = Field(
        default=None,
        description="Pfad zum NAS Snippets Verzeichnis (z.B. /mnt/pve/nas/snippets)"
    )
    cloud_init_nas_snippets_ref: Optional[str] = Field(
        default=None,
        description="Proxmox Storage-Referenz (z.B. nas:snippets)"
    )


class SetupSaveResult(BaseModel):
    """Ergebnis des Setup-Speicherns"""
    success: bool
    message: str
    restart_required: bool = True
    env_file_path: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# Security Helper Functions (CRIT-01)
# =============================================================================

def _get_client_ip(request: Request) -> str:
    """Ermittelt Client-IP aus Request (beruecksichtigt X-Forwarded-For)."""
    if request:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        elif request.client:
            return request.client.host
    return "unknown"


def _check_setup_rate_limit(request: Request, endpoint: str) -> None:
    """
    Prueft Rate-Limit fuer Setup-Endpoints.

    Raises HTTPException 429 wenn Limit erreicht.
    """
    client_ip = _get_client_ip(request)
    rate_key = f"setup:{endpoint}:{client_ip}"

    if not check_rate_limit(
        rate_key,
        limit=RateLimitConfig.SETUP_LIMIT,
        window_seconds=RateLimitConfig.SETUP_WINDOW
    ):
        logger.warning(f"Setup Rate-Limit erreicht: {endpoint} von {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Zu viele Anfragen. Bitte warten Sie eine Minute.",
            headers={"Retry-After": "60"},
        )


def _log_setup_access(request: Request, endpoint: str, setup_complete: bool) -> None:
    """Loggt Zugriff auf Setup-Endpoints (besonders nach Abschluss)."""
    client_ip = _get_client_ip(request)
    if setup_complete:
        logger.warning(
            f"SICHERHEIT: Setup-Endpoint '{endpoint}' nach Abschluss aufgerufen "
            f"von IP {client_ip}"
        )
    else:
        logger.info(f"Setup-Endpoint '{endpoint}' aufgerufen von IP {client_ip}")


# =============================================================================
# Helper Functions
# =============================================================================

def get_env_file_path() -> Path:
    """Gibt den Pfad zur .env Datei zurueck"""
    # ENV_FILE wird per docker-compose auf /app/.env gesetzt,
    # welches zur Root .env gemountet ist
    from app.config import settings
    env_file = os.getenv("ENV_FILE", f"{settings.data_dir}/config/.env")
    return Path(env_file)


def check_setup_status() -> SetupStatus:
    """Prueft ob die App bereits konfiguriert ist"""
    from app.config import settings

    missing = []

    # Proxmox-Konfiguration
    has_proxmox = bool(
        settings.proxmox_host and
        settings.proxmox_token_id and
        settings.proxmox_token_secret
    )
    if not has_proxmox:
        if not settings.proxmox_host:
            missing.append("Proxmox Host")
        if not settings.proxmox_token_id:
            missing.append("Proxmox Token ID")
        if not settings.proxmox_token_secret:
            missing.append("Proxmox Token Secret")

    # Secret Key (fuer JWT)
    has_secret = settings.secret_key != "change-me-in-production"
    if not has_secret:
        missing.append("Secret Key")

    # SSH Key
    ssh_key_path = Path(settings.ssh_key_path)
    has_ssh = ssh_key_path.exists()
    if not has_ssh:
        missing.append("SSH Key")

    # Setup ist komplett wenn Proxmox konfiguriert ist
    # (Secret Key wird generiert, SSH Key ist optional)
    setup_complete = has_proxmox

    return SetupStatus(
        setup_complete=setup_complete,
        has_proxmox_config=has_proxmox,
        has_secret_key=has_secret,
        has_ssh_key=has_ssh,
        missing_items=missing,
    )


def generate_secret_key() -> str:
    """Generiert einen sicheren Secret Key (64 hex chars)"""
    import secrets
    return secrets.token_hex(32)


def generate_netbox_secret_key() -> str:
    """Generiert einen sicheren NetBox Secret Key (mind. 50 Zeichen)"""
    import secrets
    # NetBox erfordert mind. 50 Zeichen - wir generieren 60 fuer Sicherheit
    charset = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    return ''.join(secrets.choice(charset) for _ in range(60))


def generate_netbox_api_token() -> str:
    """Generiert einen sicheren NetBox API Token (40 hex chars)"""
    import secrets
    return secrets.token_hex(20)


def create_env_symlink(env_path: Path) -> bool:
    """
    Erstellt einen Symlink von der Root .env zur config .env.

    Docker-Compose Variable-Interpolation (${VAR}) liest aus .env im
    gleichen Verzeichnis wie docker-compose.yml. Der Setup-Wizard
    speichert aber nach data/config/.env. Dieser Symlink verbindet beide.

    Returns:
        True wenn Symlink erstellt oder bereits vorhanden, False bei Fehler
    """
    # Finde das Root-Verzeichnis (wo docker-compose.yml liegt)
    # Im Container: /app -> /data ist das Datenverzeichnis
    # env_path ist z.B. /data/config/.env
    # Root waere /app oder das Parent von /data

    # Typische Pfade:
    # - Container: env_path = /data/config/.env, root = /app (aber /app/.env -> /data/config/.env)
    # - Host: env_path = /opt/pve-commander/data/config/.env, root = /opt/pve-commander

    try:
        # Suche nach docker-compose.yml um Root zu finden
        possible_roots = [
            env_path.parent.parent.parent,  # /opt/pve-commander/data/config/.env -> /opt/pve-commander
            Path("/opt/pve-commander"),
            Path("/app"),
        ]

        root_dir = None
        for root in possible_roots:
            if (root / "docker-compose.yml").exists():
                root_dir = root
                break

        if not root_dir:
            logger.warning("Konnte docker-compose.yml nicht finden, Symlink wird nicht erstellt")
            return False

        symlink_path = root_dir / ".env"

        # Pruefen ob bereits korrekt verlinkt
        if symlink_path.is_symlink():
            if symlink_path.resolve() == env_path.resolve():
                logger.info(f"Symlink bereits korrekt: {symlink_path} -> {env_path}")
                return True
            else:
                # Falscher Symlink - entfernen
                symlink_path.unlink()
                logger.info(f"Alter Symlink entfernt: {symlink_path}")
        elif symlink_path.exists():
            # Regulaere Datei - nicht ueberschreiben
            logger.warning(f".env existiert als regulaere Datei: {symlink_path}")
            return False

        # Symlink erstellen
        symlink_path.symlink_to(env_path)
        logger.info(f"Symlink erstellt: {symlink_path} -> {env_path}")
        return True

    except PermissionError:
        logger.warning(f"Keine Berechtigung zum Erstellen des Symlinks")
        return False
    except Exception as e:
        logger.warning(f"Fehler beim Erstellen des Symlinks: {e}")
        return False


async def sync_netbox_superuser(username: str, password: str, email: str, wait_for_ready: bool = False) -> dict:
    """
    Synchronisiert den NetBox-Superuser mit den Setup-Wizard Credentials.

    Da NetBox beim ersten Start mit Default-Credentials (admin/admin)
    initialisiert wird, muessen wir den User nachtraeglich aktualisieren.

    Args:
        username: NetBox Admin-Benutzername
        password: NetBox Admin-Passwort
        email: NetBox Admin E-Mail
        wait_for_ready: Wenn True, warte bis NetBox API erreichbar ist (max 5 Minuten)

    Returns:
        dict mit success, action, message
    """
    import subprocess
    import httpx

    try:
        # Zuerst pruefen ob der Container laeuft
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=pve-commander-netbox", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if "pve-commander-netbox" not in result.stdout:
            logger.info("NetBox-Container laeuft nicht, Superuser-Sync wird uebersprungen")
            return {"success": True, "action": "skipped", "message": "NetBox-Container nicht aktiv"}

        # Optional: Warte bis NetBox API erreichbar ist (fuer Erstinstallation)
        if wait_for_ready:
            logger.info("Warte auf NetBox-Initialisierung (max 5 Minuten)...")
            max_wait = 300  # 5 Minuten
            interval = 10  # Alle 10 Sekunden pruefen
            waited = 0

            while waited < max_wait:
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.get("http://netbox:8080/api/status/")
                        if resp.status_code == 200:
                            logger.info(f"NetBox ist bereit nach {waited} Sekunden")
                            break
                except Exception:
                    pass
                await asyncio.sleep(interval)
                waited += interval

            if waited >= max_wait:
                logger.warning("NetBox wurde nicht rechtzeitig bereit")
                return {"success": False, "action": "timeout", "message": "NetBox nicht rechtzeitig bereit"}

        # Python-Script zum Aktualisieren des Superusers
        python_script = f'''
from django.contrib.auth import get_user_model
User = get_user_model()

# Versuche existierenden admin zu finden und zu aktualisieren
try:
    user = User.objects.get(username="admin")
    user.username = "{username}"
    user.email = "{email}"
    user.set_password("{password}")
    user.is_superuser = True
    user.is_staff = True
    user.is_active = True
    user.save()
    print("UPDATED:admin->{username}")
except User.DoesNotExist:
    # Kein admin User, versuche Ziel-User zu finden
    try:
        user = User.objects.get(username="{username}")
        user.email = "{email}"
        user.set_password("{password}")
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.save()
        print("UPDATED:{username}")
    except User.DoesNotExist:
        # Kein User vorhanden, erstelle neuen
        user = User.objects.create_superuser("{username}", "{email}", "{password}")
        print("CREATED:{username}")
'''

        # Escape fuer Shell
        escaped_script = python_script.replace('"', '\\"').replace("'", "'\\''")

        # Ausfuehren im Container
        result = subprocess.run(
            [
                "docker", "exec", "pve-commander-netbox",
                "python", "/opt/netbox/netbox/manage.py", "shell", "-c", python_script
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        output = result.stdout.strip()

        if "UPDATED:" in output or "CREATED:" in output:
            action = "updated" if "UPDATED:" in output else "created"
            logger.info(f"NetBox-Superuser {action}: {username}")
            return {"success": True, "action": action, "message": f"NetBox-Superuser {action}"}
        else:
            # Fehler in der Ausgabe
            logger.warning(f"NetBox-Superuser Sync unbekanntes Ergebnis: {output}, stderr: {result.stderr}")
            return {"success": False, "action": "error", "message": result.stderr or output}

    except subprocess.TimeoutExpired:
        logger.warning("NetBox-Superuser Sync Timeout")
        return {"success": False, "action": "timeout", "message": "Timeout beim Sync"}
    except FileNotFoundError:
        # Docker nicht verfuegbar (z.B. im Container selbst)
        logger.info("Docker CLI nicht verfuegbar, NetBox-Sync wird uebersprungen")
        return {"success": True, "action": "skipped", "message": "Docker CLI nicht verfuegbar"}
    except Exception as e:
        logger.warning(f"NetBox-Superuser Sync Fehler: {e}")
        return {"success": False, "action": "error", "message": str(e)}


def quote_env_value(value: str) -> str:
    """
    Quoted einen Wert fuer .env Dateien korrekt.

    Regeln:
    - Werte mit Sonderzeichen (#, $, ", ', Leerzeichen, Backslash) werden in
      einfache Anführungszeichen gesetzt
    - Einfache Anführungszeichen im Wert werden escaped ('"'"')
    - Leere Werte bleiben leer
    - Einfache alphanumerische Werte bleiben unquoted
    """
    if not value:
        return ""

    # Zeichen die Quoting erfordern
    needs_quoting = any(c in value for c in '#$"\' \\')

    if not needs_quoting:
        return value

    # Mit einfachen Quotes: Einfache Quotes im Wert escapen
    # 'foo'bar' wird zu 'foo'"'"'bar'
    escaped = value.replace("'", "'\"'\"'")
    return f"'{escaped}'"


async def validate_proxmox_connection(config: ProxmoxConfig) -> ProxmoxValidationResult:
    """Testet die Proxmox-Verbindung mit den angegebenen Credentials"""
    import httpx
    import ssl
    from urllib.parse import urlparse

    # API URL bauen - unterstuetzt:
    # - 192.168.1.100 (IP ohne Port -> https + :8006)
    # - 192.168.1.100:8006 (IP mit Port -> https)
    # - proxmox.example.com (Hostname ohne Port -> https + :8006)
    # - proxmox.example.com:8006 (Hostname mit Port -> https)
    # - https://proxmox.example.com (HTTPS ohne Port -> bleibt, kein :8006)
    # - https://proxmox.example.com:443 (Reverse Proxy -> bleibt)
    host = config.host.strip().rstrip("/")

    # Pruefen ob bereits ein Schema vorhanden ist
    if not host.startswith("http://") and not host.startswith("https://"):
        # Kein Schema - pruefen ob Port vorhanden
        if ":" in host.split("/")[0]:
            # Port vorhanden (z.B. 192.168.1.100:8006)
            host = f"https://{host}"
        else:
            # Kein Port - Standard Proxmox Port hinzufuegen
            host = f"https://{host}:8006"
    else:
        # Schema vorhanden - pruefen ob Port noetig
        parsed = urlparse(host)
        if not parsed.port:
            # Kein expliziter Port - bei HTTPS Standard-Port verwenden (kein :8006!)
            # Benutzer hat bewusst Schema angegeben, vermutlich Reverse Proxy
            pass
        # Sonst: Port ist explizit angegeben, nichts aendern

    # Token Header
    auth_header = f"PVEAPIToken={config.token_id}={config.token_secret}"

    try:
        # SSL-Kontext konfigurieren
        ssl_context = None
        if config.verify_ssl:
            ssl_context = ssl.create_default_context()
        else:
            ssl_context = False

        async with httpx.AsyncClient(verify=ssl_context, timeout=15.0) as client:
            # Version abfragen
            version_response = await client.get(
                f"{host}/api2/json/version",
                headers={"Authorization": auth_header}
            )

            if version_response.status_code == 401:
                return ProxmoxValidationResult(
                    success=False,
                    message="Authentifizierung fehlgeschlagen",
                    error="Ungueltige Token-Credentials. Bitte Token ID und Secret pruefen."
                )

            if version_response.status_code != 200:
                return ProxmoxValidationResult(
                    success=False,
                    message=f"Proxmox API Fehler: {version_response.status_code}",
                    error=version_response.text
                )

            version_data = version_response.json().get("data", {})
            version = version_data.get("version", "unbekannt")

            # Cluster-Info abfragen
            cluster_response = await client.get(
                f"{host}/api2/json/cluster/status",
                headers={"Authorization": auth_header}
            )

            cluster_name = None
            node_count = 0

            if cluster_response.status_code == 200:
                cluster_data = cluster_response.json().get("data", [])
                for item in cluster_data:
                    if item.get("type") == "cluster":
                        cluster_name = item.get("name")
                    if item.get("type") == "node":
                        node_count += 1

            return ProxmoxValidationResult(
                success=True,
                message=f"Verbindung erfolgreich! Proxmox VE {version}",
                version=version,
                cluster_name=cluster_name,
                node_count=node_count,
            )

    except ssl.SSLCertVerificationError as e:
        return ProxmoxValidationResult(
            success=False,
            message="SSL-Zertifikatsfehler",
            error=f"Zertifikat konnte nicht verifiziert werden: {str(e)}. "
                  "Versuchen Sie 'SSL-Zertifikat verifizieren' zu deaktivieren, "
                  "oder stellen Sie sicher, dass das Zertifikat gueltig ist."
        )
    except ssl.SSLError as e:
        return ProxmoxValidationResult(
            success=False,
            message="SSL-Fehler",
            error=f"SSL-Verbindungsfehler: {str(e)}"
        )
    except httpx.ConnectError as e:
        error_str = str(e).upper()
        original_error = str(e)

        # Erweiterte SSL-Fehlererkennung - httpx wrapped SSL-Fehler oft in ConnectError
        ssl_keywords = ["SSL", "TLS", "CERTIFICATE", "CERT", "VERIFY", "HANDSHAKE", "SECURE"]
        if any(keyword in error_str for keyword in ssl_keywords):
            return ProxmoxValidationResult(
                success=False,
                message="SSL-Verbindungsfehler",
                error=f"SSL/TLS-Fehler beim Verbinden: {original_error}. "
                      "Versuchen Sie 'SSL-Zertifikat verifizieren' zu deaktivieren."
            )

        # Connection refused = Host erreichbar aber Port geschlossen
        if "CONNECTION REFUSED" in error_str or "ERRNO 111" in error_str:
            return ProxmoxValidationResult(
                success=False,
                message="Port nicht erreichbar",
                error=f"Verbindung zu {host} abgelehnt. "
                      "Der Host ist erreichbar, aber Port 8006 ist nicht offen. "
                      "Bei Reverse Proxy: Verwende 'https://hostname' (ohne :8006)."
            )

        return ProxmoxValidationResult(
            success=False,
            message="Verbindung fehlgeschlagen",
            error=f"Host nicht erreichbar: {config.host}. Pruefen Sie die IP/Hostname und Firewall."
        )
    except httpx.TimeoutException:
        return ProxmoxValidationResult(
            success=False,
            message="Timeout",
            error="Verbindung zum Proxmox-Server hat zu lange gedauert (15 Sekunden)."
        )
    except Exception as e:
        error_str = str(e).upper()
        # Erweiterte SSL-Fehlererkennung
        ssl_keywords = ["SSL", "TLS", "CERTIFICATE", "CERT", "VERIFY", "HANDSHAKE", "SECURE"]
        if any(keyword in error_str for keyword in ssl_keywords):
            return ProxmoxValidationResult(
                success=False,
                message="SSL-Fehler",
                error=f"SSL-Problem: {str(e)}. "
                      "Versuchen Sie 'SSL-Zertifikat verifizieren' zu deaktivieren."
            )
        return ProxmoxValidationResult(
            success=False,
            message="Unbekannter Fehler",
            error=str(e)
        )


async def generate_terraform_tfvars(config: SetupConfig) -> None:
    """
    Generiert die terraform.tfvars Datei aus der Setup-Konfiguration.

    Die tfvars enthaelt die Proxmox-Credentials und Default-Werte.
    """
    from pathlib import Path
    from app.config import settings

    terraform_dir = Path(settings.terraform_dir)
    tfvars_path = terraform_dir / "terraform.tfvars"

    # SSH Public Key lesen (falls vorhanden)
    ssh_public_key = ""
    ssh_key_path = Path(settings.ssh_key_path)
    ssh_pub_path = ssh_key_path.with_suffix(".pub")
    if ssh_pub_path.exists():
        try:
            ssh_public_key = ssh_pub_path.read_text().strip()
        except Exception:
            pass

    # Proxmox API URL zusammenbauen
    host = config.proxmox_host
    if not host.startswith("http"):
        api_url = f"https://{host}:8006/api2/json"
    elif ":8006" not in host and not host.endswith("/api2/json"):
        api_url = f"{host.rstrip('/')}/api2/json"
    else:
        api_url = f"{host.rstrip('/')}/api2/json" if not host.endswith("/api2/json") else host

    # tfvars Inhalt
    tfvars_content = f'''# PVE Commander - Terraform Variablen
# Automatisch generiert durch Setup-Wizard
# Erstellt: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

# Proxmox API
proxmox_api_url      = "{api_url}"
proxmox_token_id     = "{config.proxmox_token_id}"
proxmox_token_secret = "{config.proxmox_token_secret}"
proxmox_tls_insecure = {str(not config.proxmox_verify_ssl).lower()}

# VM-Defaults
default_template      = 940001
default_template_node = "pve-node-01"
ssh_user              = "{config.default_ssh_user}"
ssh_public_key        = "{ssh_public_key}"
default_dns           = ["10.0.0.1", "1.1.1.1"]
'''

    # Schreiben
    terraform_dir.mkdir(parents=True, exist_ok=True)
    tfvars_path.write_text(tfvars_content)
    logger.info(f"Terraform tfvars generiert: {tfvars_path}")


async def save_env_config(config: SetupConfig) -> SetupSaveResult:
    """Speichert die Konfiguration in die .env Datei"""
    env_path = get_env_file_path()

    # Verzeichnis erstellen falls nicht vorhanden
    env_path.parent.mkdir(parents=True, exist_ok=True)

    # Secret Key generieren falls nicht angegeben
    secret_key = config.secret_key or generate_secret_key()

    # Bestehende .env lesen falls vorhanden
    existing_lines = []
    existing_keys = set()
    existing_values = {}

    if env_path.exists():
        try:
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key = line.split("=", 1)[0]
                        value = line.split("=", 1)[1] if "=" in line else ""
                        existing_keys.add(key)
                        existing_values[key] = value
                    existing_lines.append(line)
        except Exception as e:
            logger.warning(f"Konnte bestehende .env nicht lesen: {e}")

    # NetBox Secret Key pruefen/generieren (mind. 50 Zeichen erforderlich)
    netbox_secret_key = existing_values.get("NETBOX_SECRET_KEY", "")
    if len(netbox_secret_key) < 50:
        netbox_secret_key = generate_netbox_secret_key()
        logger.info("Neuer NETBOX_SECRET_KEY generiert (mind. 50 Zeichen)")

    # NetBox API Token pruefen/generieren (40 hex chars)
    # Verwende config.netbox_token falls angegeben, sonst bestehenden oder neuen
    if config.netbox_token:
        netbox_api_token = config.netbox_token
    else:
        netbox_api_token = existing_values.get("NETBOX_TOKEN", "")
        # Generischer Default-Token oder leer -> neuen generieren
        if not netbox_api_token or netbox_api_token == "0123456789abcdef0123456789abcdef01234567":
            netbox_api_token = generate_netbox_api_token()
            logger.info("Neuer NETBOX_TOKEN generiert (40 hex chars)")

    # Neue Werte
    new_values = {
        "PROXMOX_HOST": config.proxmox_host,
        "PROXMOX_TOKEN_ID": config.proxmox_token_id,
        "PROXMOX_TOKEN_SECRET": config.proxmox_token_secret,
        "PROXMOX_VERIFY_SSL": str(config.proxmox_verify_ssl).lower(),
        "SECRET_KEY": secret_key,
        "DEFAULT_SSH_USER": config.default_ssh_user,
        "ANSIBLE_REMOTE_USER": config.ansible_remote_user,
        # NetBox Admin Credentials
        "NETBOX_ADMIN_USER": config.netbox_admin_user,
        "NETBOX_ADMIN_PASSWORD": config.netbox_admin_password,
        "NETBOX_ADMIN_EMAIL": config.netbox_admin_email,
        # App Admin Credentials
        "APP_ADMIN_USER": config.app_admin_user,
        "APP_ADMIN_PASSWORD": config.app_admin_password,
        "APP_ADMIN_EMAIL": config.app_admin_email,
        # NetBox Secret Key (mind. 50 Zeichen)
        "NETBOX_SECRET_KEY": netbox_secret_key,
        # NetBox API Token (40 hex chars)
        "NETBOX_TOKEN": netbox_api_token,
    }

    if config.netbox_url:
        new_values["NETBOX_URL"] = config.netbox_url

    try:
        # Header mit Erstellungsdatum
        from datetime import datetime
        header = f"# PVE Commander - Setup-Konfiguration\n# Erstellt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        # .env Datei schreiben
        with open(env_path, "w") as f:
            # Header nur bei neuer Datei
            if not existing_lines:
                f.write(header)

            # Bestehende Zeilen aktualisieren
            written_keys = set()
            for line in existing_lines:
                if line and not line.startswith("#") and "=" in line:
                    key = line.split("=")[0]
                    if key in new_values:
                        quoted_value = quote_env_value(str(new_values[key]))
                        f.write(f"{key}={quoted_value}\n")
                        written_keys.add(key)
                    else:
                        f.write(f"{line}\n")
                elif line.startswith("#") or not line:
                    # Kommentare und leere Zeilen behalten
                    f.write(f"{line}\n")
                # Zeilen ohne "=" werden ignoriert (ungueltige Eintraege)

            # Neue Werte hinzufuegen
            for key, value in new_values.items():
                if key not in written_keys:
                    quoted_value = quote_env_value(str(value))
                    f.write(f"{key}={quoted_value}\n")

        logger.info(f"Setup-Konfiguration gespeichert in {env_path}")

        # Symlink erstellen fuer docker-compose Variable-Interpolation
        symlink_created = create_env_symlink(env_path)
        if symlink_created:
            logger.info("Symlink fuer docker-compose erstellt")
        else:
            logger.warning("Symlink konnte nicht erstellt werden - Container-Neustart erforderlich")

        # Terraform tfvars generieren
        try:
            await generate_terraform_tfvars(config)
        except Exception as e:
            logger.warning(f"Terraform tfvars konnte nicht erstellt werden: {e}")

        return SetupSaveResult(
            success=True,
            message="Konfiguration erfolgreich gespeichert. Bitte Container neu starten.",
            restart_required=True,
            env_file_path=str(env_path),
        )

    except PermissionError:
        return SetupSaveResult(
            success=False,
            message="Keine Schreibberechtigung",
            error=f"Kann nicht in {env_path} schreiben. Pruefen Sie die Berechtigungen.",
            restart_required=False,
        )
    except Exception as e:
        return SetupSaveResult(
            success=False,
            message="Speichern fehlgeschlagen",
            error=str(e),
            restart_required=False,
        )


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/status", response_model=SetupStatus)
async def get_setup_status(request: Request):
    """
    Prueft ob die App bereits konfiguriert ist.

    Gibt zurueck welche Konfigurationselemente fehlen.
    Dieser Endpoint ist ohne Authentifizierung zugaenglich.

    Security: Rate-Limited (CRIT-01)
    """
    _check_setup_rate_limit(request, "status")
    status = check_setup_status()
    _log_setup_access(request, "status", status.setup_complete)
    return status


@router.post("/validate/proxmox", response_model=ProxmoxValidationResult)
async def validate_proxmox(config: ProxmoxConfig, request: Request):
    """
    Testet die Proxmox-Verbindung mit den angegebenen Credentials.

    Prueft:
    - Erreichbarkeit des Hosts
    - Gueltigkeit der API-Credentials
    - Liest Cluster-Informationen

    Dieser Endpoint ist ohne Authentifizierung zugaenglich.

    Security: Rate-Limited (CRIT-01)
    """
    _check_setup_rate_limit(request, "validate_proxmox")
    status = check_setup_status()
    _log_setup_access(request, "validate_proxmox", status.setup_complete)
    return await validate_proxmox_connection(config)


@router.post("/save", response_model=SetupSaveResult)
async def save_setup(config: SetupConfig, request: Request, force: bool = False):
    """
    Speichert die Setup-Konfiguration.

    Schreibt die Werte in die .env Datei.
    Nach dem Speichern muss der Container neu gestartet werden.

    Dieser Endpoint ist ohne Authentifizierung zugaenglich.

    Query-Parameter:
    - force: Wenn true, wird das Setup auch bei bereits abgeschlossener
             Konfiguration erneut durchgefuehrt (nur fuer Rekonfiguration)

    Security: Rate-Limited, Logging bei force-Verwendung (CRIT-01)
    """
    # CRIT-01: Rate-Limiting
    _check_setup_rate_limit(request, "save")

    # Pruefen ob Setup bereits abgeschlossen
    status = check_setup_status()
    _log_setup_access(request, "save", status.setup_complete)

    if status.setup_complete and not force:
        raise HTTPException(
            status_code=403,
            detail="Setup bereits abgeschlossen. Mit ?force=true kann das Setup erneut durchgefuehrt werden."
        )

    # CRIT-01: Warnung bei force-Verwendung nach Setup
    if status.setup_complete and force:
        client_ip = _get_client_ip(request)
        logger.warning(
            f"SICHERHEIT: Setup-Rekonfiguration mit force=true von IP {client_ip}. "
            "Alle Credentials werden ueberschrieben!"
        )

    # Proxmox-Verbindung validieren
    proxmox_config = ProxmoxConfig(
        host=config.proxmox_host,
        token_id=config.proxmox_token_id,
        token_secret=config.proxmox_token_secret,
        verify_ssl=config.proxmox_verify_ssl,
    )

    validation = await validate_proxmox_connection(proxmox_config)
    if not validation.success:
        raise HTTPException(
            status_code=400,
            detail=f"Proxmox-Verbindung fehlgeschlagen: {validation.error}"
        )

    # Konfiguration speichern
    result = await save_env_config(config)

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    # Settings neu laden (Hot-Reload via SettingsProxy)
    from app.config import reload_settings
    from app.database import ensure_admin_exists, async_session
    from app.services.cloud_init_settings_service import get_cloud_init_settings_service
    try:
        reload_settings(str(get_env_file_path()))
        logger.info("Settings wurden nach Setup neu geladen (Hot-Reload)")

        # Admin-User erstellen/aktualisieren mit EXPLIZITEN Credentials aus dem Wizard
        # (nicht aus Settings, um Race-Conditions zu vermeiden)
        admin_result = await ensure_admin_exists(
            username=config.app_admin_user,
            password=config.app_admin_password,
            email=config.app_admin_email,
        )

        if admin_result["success"]:
            logger.info(f"Admin-User: {admin_result['action']} - {admin_result['message']}")
            result.restart_required = False
            result.message = "Konfiguration erfolgreich gespeichert und aktiviert."
        else:
            logger.error(f"Admin-User Fehler: {admin_result.get('message')}")
            result.restart_required = True
            result.message = "Konfiguration gespeichert, aber Admin-Erstellung fehlgeschlagen. Bitte Container neu starten."

        # NetBox-Superuser synchronisieren (als Background-Task)
        # Bei Erstinstallation kann NetBox noch mit Migrationen beschaeftigt sein
        async def netbox_sync_background():
            try:
                netbox_result = await sync_netbox_superuser(
                    username=config.netbox_admin_user,
                    password=config.netbox_admin_password,
                    email=config.netbox_admin_email,
                    wait_for_ready=True,  # Warte bis NetBox bereit ist
                )
                if netbox_result["success"]:
                    logger.info(f"NetBox-Superuser: {netbox_result['action']} - {netbox_result['message']}")
                else:
                    logger.warning(f"NetBox-Superuser Sync fehlgeschlagen: {netbox_result['message']}")
            except Exception as e:
                logger.warning(f"NetBox-Superuser Sync Fehler: {e}")

        # Background-Task starten (blockiert nicht den Setup-Wizard)
        asyncio.create_task(netbox_sync_background())

        # Cloud-Init Settings in DB speichern
        try:
            async with async_session() as db:
                cloud_init_service = get_cloud_init_settings_service(db)
                await cloud_init_service.update_settings(
                    ssh_keys=config.cloud_init_ssh_keys or [],
                    phone_home_enabled=config.cloud_init_phone_home_enabled,
                    admin_username=config.cloud_init_admin_username,
                    admin_gecos=config.cloud_init_admin_gecos,
                    nas_snippets_path=config.cloud_init_nas_snippets_path,
                    nas_snippets_ref=config.cloud_init_nas_snippets_ref,
                )
                logger.info("Cloud-Init Settings in DB gespeichert")
        except Exception as e:
            logger.warning(f"Cloud-Init Settings konnten nicht gespeichert werden: {e}")
            # Kein Fehler - Setup kann trotzdem erfolgreich sein

        # NetBox External URL in DB speichern
        try:
            async with async_session() as db:
                from app.services.settings_service import get_settings_service
                settings_service = get_settings_service(db)
                await settings_service.set_netbox_external_url(config.netbox_external_url)
                logger.info(f"NetBox External URL gespeichert: {config.netbox_external_url}")
        except Exception as e:
            logger.warning(f"NetBox External URL konnte nicht gespeichert werden: {e}")
            # Kein Fehler - Setup kann trotzdem erfolgreich sein

    except Exception as e:
        logger.warning(f"Hot-Reload fehlgeschlagen: {e} - Container-Restart erforderlich")
        # Fallback: restart_required bleibt True

    return result


@router.get("/generate-secret")
async def generate_secret(request: Request):
    """
    Generiert einen neuen Secret Key.

    Kann im Frontend verwendet werden um einen sicheren Key zu generieren.

    Security: Rate-Limited (CRIT-01)
    """
    _check_setup_rate_limit(request, "generate_secret")
    return {"secret_key": generate_secret_key()}


# =============================================================================
# SSH Endpoints (fuer Setup-Wizard)
# =============================================================================

from app.services.ssh_service import (
    get_ssh_service,
    SSHKeyListResponse,
    SSHKeyImportRequest,
    SSHKeyImportResponse,
    SSHKeyUploadRequest,
    SSHKeyUploadResponse,
    SSHKeyGenerateRequest,
    SSHKeyGenerateResponse,
    SSHKeyActivateRequest,
    SSHKeyActivateResponse,
    SSHKeyDeleteRequest,
    SSHKeyDeleteResponse,
    SSHTestRequest,
    SSHTestResponse,
)


@router.get("/ssh-keys", response_model=SSHKeyListResponse)
async def list_ssh_keys():
    """
    Listet verfuegbare SSH-Keys auf.

    Zeigt Keys aus dem gemounteten Host-SSH-Verzeichnis (/host-ssh)
    sowie den aktuell konfigurierten Key.

    Dieser Endpoint ist ohne Authentifizierung zugaenglich.
    """
    ssh_service = get_ssh_service()
    return await ssh_service.list_available_keys()


@router.post("/ssh-import", response_model=SSHKeyImportResponse)
async def import_ssh_key(request: SSHKeyImportRequest):
    """
    Importiert einen SSH-Key aus dem gemounteten Host-SSH-Verzeichnis.

    Der Key wird nach data/ssh/ kopiert und kann dann fuer Ansible verwendet werden.

    Dieser Endpoint ist ohne Authentifizierung zugaenglich.
    """
    ssh_service = get_ssh_service()
    return await ssh_service.import_key(request)


@router.post("/ssh-upload", response_model=SSHKeyUploadResponse)
async def upload_ssh_key(key_request: SSHKeyUploadRequest, request: Request):
    """
    Speichert einen per Copy/Paste uebermittelten SSH-Key.

    Der Private Key wird validiert und nach data/ssh/ gespeichert.
    Falls kein Public Key mitgeliefert wird, wird dieser automatisch generiert.

    Dieser Endpoint ist ohne Authentifizierung zugaenglich.

    Security: Rate-Limited, Groessenbegrenzung in ssh_service (CRIT-01, CRIT-03)
    """
    _check_setup_rate_limit(request, "ssh_upload")
    status = check_setup_status()
    _log_setup_access(request, "ssh_upload", status.setup_complete)

    ssh_service = get_ssh_service()
    return await ssh_service.upload_key(key_request)


@router.post("/ssh-generate", response_model=SSHKeyGenerateResponse)
async def generate_ssh_key(request: SSHKeyGenerateRequest):
    """
    Generiert ein neues SSH-Schluesselpaar.

    Unterstuetzte Key-Typen: ed25519 (empfohlen), rsa (4096 bit).
    Der generierte Public Key wird zurueckgegeben und muss auf den
    Ziel-VMs in authorized_keys hinterlegt werden.

    Dieser Endpoint ist ohne Authentifizierung zugaenglich.
    """
    ssh_service = get_ssh_service()
    return await ssh_service.generate_key(request)


@router.post("/ssh-test", response_model=SSHTestResponse)
async def test_ssh_connection(request: SSHTestRequest):
    """
    Testet die SSH-Verbindung zu einem Host.

    Prueft:
    1. Ob der Host auf Port 22 (oder angegebenem Port) erreichbar ist
    2. Ob die SSH-Authentifizierung mit dem konfigurierten Key funktioniert

    Dieser Endpoint ist ohne Authentifizierung zugaenglich.
    """
    ssh_service = get_ssh_service()
    return await ssh_service.test_connection(request)


@router.post("/ssh-activate", response_model=SSHKeyActivateResponse)
async def activate_ssh_key(request: SSHKeyActivateRequest):
    """
    Aktiviert einen gespeicherten SSH-Key.

    Setzt den angegebenen Key als aktiven Key fuer SSH-Verbindungen.

    Dieser Endpoint ist ohne Authentifizierung zugaenglich.
    """
    ssh_service = get_ssh_service()
    return await ssh_service.activate_key(request)


@router.post("/ssh-delete", response_model=SSHKeyDeleteResponse)
async def delete_ssh_key(request: SSHKeyDeleteRequest):
    """
    Loescht einen gespeicherten SSH-Key.

    Der aktive Key kann nicht geloescht werden.

    Dieser Endpoint ist ohne Authentifizierung zugaenglich.
    """
    ssh_service = get_ssh_service()
    return await ssh_service.delete_key(request)


# =============================================================================
# NetBox Profile Control (fuer Setup-Wizard)
# =============================================================================

class NetBoxStartRequest(BaseModel):
    """Request zum Starten des NetBox-Profils"""
    wait_for_ready: bool = Field(
        default=True,
        description="Warte bis NetBox bereit ist (max 10 Minuten)"
    )


class NetBoxStartResponse(BaseModel):
    """Response vom NetBox-Start"""
    success: bool
    message: str
    status: str  # starting, ready, error, timeout
    elapsed_seconds: Optional[int] = None
    error: Optional[str] = None


class NetBoxStatusResponse(BaseModel):
    """NetBox-Container Status"""
    running: bool
    ready: bool
    status: str  # not_running, starting, ready, error


@router.get("/netbox/status", response_model=NetBoxStatusResponse)
async def get_netbox_status(request: Request):
    """
    Prueft den Status des NetBox-Containers.

    Returns:
        - running: Container laeuft (aber evtl. noch in Migration)
        - ready: NetBox API ist erreichbar
        - status: not_running, starting, ready, error
    """
    import subprocess
    import httpx

    _check_setup_rate_limit(request, "netbox_status")

    # Pruefen ob Container laeuft
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=pve-commander-netbox", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10
        )

        container_running = "pve-commander-netbox" in result.stdout

        if not container_running:
            return NetBoxStatusResponse(
                running=False,
                ready=False,
                status="not_running"
            )

        # Container laeuft - pruefen ob API bereit ist
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get("http://netbox:8080/api/status/")
                if resp.status_code == 200:
                    return NetBoxStatusResponse(
                        running=True,
                        ready=True,
                        status="ready"
                    )
                else:
                    return NetBoxStatusResponse(
                        running=True,
                        ready=False,
                        status="starting"
                    )
        except Exception:
            return NetBoxStatusResponse(
                running=True,
                ready=False,
                status="starting"
            )

    except FileNotFoundError:
        return NetBoxStatusResponse(
            running=False,
            ready=False,
            status="error"
        )
    except Exception as e:
        logger.warning(f"NetBox-Status Fehler: {e}")
        return NetBoxStatusResponse(
            running=False,
            ready=False,
            status="error"
        )


@router.post("/netbox/start", response_model=NetBoxStartResponse)
async def start_netbox_profile(req: NetBoxStartRequest, request: Request):
    """
    Startet das NetBox-Profil via Docker Compose.

    Fuehrt `docker compose --profile netbox up -d` aus.
    Bei Erstinstallation dauert die Initialisierung 5-10 Minuten
    (NetBox fuehrt ~200 Datenbank-Migrationen durch).

    Args:
        wait_for_ready: Wenn True, wartet der Endpoint bis NetBox bereit ist (max 10 Min)

    Security: Rate-Limited (CRIT-01)
    """
    import subprocess
    import httpx
    import time

    _check_setup_rate_limit(request, "netbox_start")
    status = check_setup_status()
    _log_setup_access(request, "netbox_start", status.setup_complete)

    start_time = time.time()

    try:
        # docker compose --profile netbox up -d ausfuehren
        # Suche docker-compose.yml im Datenverzeichnis oder typischen Pfaden
        compose_paths = [
            "/opt/pve-commander",
            "/app",
            "/data/..",  # Falls im Container
        ]

        compose_dir = None
        for path in compose_paths:
            if os.path.exists(os.path.join(path, "docker-compose.yml")):
                compose_dir = path
                break

        if not compose_dir:
            return NetBoxStartResponse(
                success=False,
                message="docker-compose.yml nicht gefunden",
                status="error",
                error="Konnte docker-compose.yml nicht finden"
            )

        logger.info(f"Starte NetBox-Profil in {compose_dir}")

        result = subprocess.run(
            ["docker", "compose", "--profile", "netbox", "up", "-d"],
            cwd=compose_dir,
            capture_output=True,
            text=True,
            timeout=120  # 2 Minuten fuer Pull/Start
        )

        if result.returncode != 0:
            logger.error(f"docker compose up Fehler: {result.stderr}")
            return NetBoxStartResponse(
                success=False,
                message="Docker Compose Fehler",
                status="error",
                error=result.stderr
            )

        logger.info("NetBox-Container gestartet, warte auf Initialisierung...")

        if not req.wait_for_ready:
            return NetBoxStartResponse(
                success=True,
                message="NetBox-Container gestartet. Initialisierung laeuft im Hintergrund.",
                status="starting",
                elapsed_seconds=int(time.time() - start_time)
            )

        # Warte bis NetBox bereit ist
        max_wait = 600  # 10 Minuten
        interval = 5  # Alle 5 Sekunden pruefen
        waited = 0

        while waited < max_wait:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get("http://netbox:8080/api/status/")
                    if resp.status_code == 200:
                        elapsed = int(time.time() - start_time)
                        logger.info(f"NetBox ist bereit nach {elapsed} Sekunden")
                        return NetBoxStartResponse(
                            success=True,
                            message=f"NetBox erfolgreich gestartet und bereit ({elapsed}s)",
                            status="ready",
                            elapsed_seconds=elapsed
                        )
            except Exception:
                pass

            await asyncio.sleep(interval)
            waited += interval

        # Timeout
        elapsed = int(time.time() - start_time)
        return NetBoxStartResponse(
            success=False,
            message=f"NetBox-Initialisierung Timeout nach {elapsed}s",
            status="timeout",
            elapsed_seconds=elapsed,
            error="NetBox wurde nach 10 Minuten nicht bereit. Pruefen Sie die Container-Logs."
        )

    except subprocess.TimeoutExpired:
        return NetBoxStartResponse(
            success=False,
            message="Docker Compose Timeout",
            status="error",
            error="docker compose up Timeout nach 2 Minuten"
        )
    except FileNotFoundError:
        return NetBoxStartResponse(
            success=False,
            message="Docker nicht gefunden",
            status="error",
            error="Docker CLI nicht verfuegbar"
        )
    except Exception as e:
        logger.error(f"NetBox-Start Fehler: {e}")
        return NetBoxStartResponse(
            success=False,
            message="Unbekannter Fehler",
            status="error",
            error=str(e)
        )
