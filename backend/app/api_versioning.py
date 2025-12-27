"""
API Versionierung fuer PVE Commander

Stellt versionierte API-Endpunkte bereit:
- /api/v1/... - Aktuelle stabile API
- /api/... - Alias fuer v1 (Rueckwaertskompatibilitaet)

Zukuenftige Versionen:
- /api/v2/... - Naechste API-Version (wenn noetig)

Verwendung in main.py:
    from app.api_versioning import create_versioned_app
    create_versioned_app(app)
"""

from fastapi import FastAPI, APIRouter, Request
from fastapi.responses import JSONResponse


# API Version Info
API_VERSION = "v1"
API_VERSION_FULL = "1.0.0"


def get_api_info() -> dict:
    """Gibt API-Versions-Informationen zurueck."""
    return {
        "version": API_VERSION_FULL,
        "api_version": API_VERSION,
        "supported_versions": ["v1"],
        "deprecated_versions": [],
        "latest": API_VERSION,
    }


def create_version_router() -> APIRouter:
    """
    Erstellt einen Router fuer API-Versions-Endpunkte.

    Endpunkte:
    - GET /api/version - API-Versions-Info
    - GET /api/v1/version - Gleiche Info (versioniert)
    """
    router = APIRouter(tags=["api-info"])

    @router.get("/api/version")
    @router.get("/api/v1/version")
    async def api_version():
        """Gibt die aktuelle API-Version zurueck."""
        return get_api_info()

    return router


def add_version_header_middleware(app: FastAPI) -> None:
    """
    Fuegt X-API-Version Header zu allen Responses hinzu.

    Hilft Clients die API-Version zu erkennen.
    """
    @app.middleware("http")
    async def add_version_header(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-API-Version"] = API_VERSION_FULL
        return response


def create_versioned_app(app: FastAPI) -> None:
    """
    Konfiguriert API-Versionierung fuer die FastAPI-App.

    Fuegt hinzu:
    - Version-Info Endpunkt
    - X-API-Version Header
    - Dokumentation der API-Versionen
    """
    # Version Header Middleware
    add_version_header_middleware(app)

    # Version Router
    version_router = create_version_router()
    app.include_router(version_router)

    # OpenAPI Schema anpassen
    if app.openapi_schema:
        app.openapi_schema["info"]["version"] = API_VERSION_FULL


# Router-Prefix Konstanten fuer konsistente Verwendung
class APIPrefix:
    """
    Konstanten fuer API-Prefixes.

    Verwendung in Routern:
        from app.api_versioning import APIPrefix
        router = APIRouter(prefix=APIPrefix.TERRAFORM, tags=["terraform"])
    """
    # Basis-Prefixes (ohne Version - fuer Rueckwaertskompatibilitaet)
    AUTH = "/api/auth"
    USERS = "/api/users"
    INVENTORY = "/api/inventory"
    PLAYBOOKS = "/api/playbooks"
    EXECUTIONS = "/api/executions"
    SETTINGS = "/api/settings"
    TERRAFORM = "/api/terraform"
    NETBOX = "/api/netbox"
    CLOUD_INIT = "/api/cloud-init"
    BACKUP = "/api/backup"
    ROLES = "/api/roles"
    AUDIT = "/api/audit"
    SETUP = "/api/setup"
    NOTIFICATIONS = "/api/notifications"
    ROLLBACK = "/api/rollback"

    # Versionierte Prefixes (fuer zukuenftige Verwendung)
    @classmethod
    def v1(cls, path: str) -> str:
        """Gibt versionierten Pfad zurueck: /api/v1/..."""
        return f"/api/v1{path.replace('/api', '')}"
