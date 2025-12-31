"""
PVE Commander - FastAPI Backend

Standalone VM-Management fuer Proxmox mit integriertem NetBox
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings, log_security_warnings_on_startup
from app.logging_config import setup_logging, get_logger

# Logging Setup - muss vor anderen Imports passieren
setup_logging()
logger = get_logger(__name__)
from app.database import init_db
from app.exceptions import register_exception_handlers
from app.routers import auth_router, inventory_router, playbooks_router, executions_router, users_router, settings_router, terraform_router, vm_templates_router, cloud_init_router, setup_router, netbox_router
from app.routers.websocket import router as websocket_router
from app.routers.notifications import router as notifications_router
from app.routers.password_reset import router as password_reset_router
from app.routers.cloud_init_settings import router as cloud_init_settings_router
from app.routers.backup import router as backup_router
from app.routers.roles import router as roles_router
from app.routers.audit import router as audit_router
from app.routers.rollback import router as rollback_router
from app.services.inventory_sync_service import get_sync_service
from app.services.backup_scheduler import start_backup_scheduler, stop_backup_scheduler
from app.services.terraform_health_service import get_terraform_health_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup und Shutdown Events"""
    # Startup
    await init_db()

    # Sicherheitswarnungen ausgeben (CRIT-02, CRIT-06)
    log_security_warnings_on_startup()

    # Background Inventory-Sync starten
    sync_service = get_sync_service()
    await sync_service.start_background_sync()
    logger.info("Background Inventory-Sync gestartet")

    # Backup-Scheduler starten
    await start_backup_scheduler()
    logger.info("Backup-Scheduler gestartet")

    # Terraform Health-Check starten
    health_service = get_terraform_health_service()
    await health_service.start_background_check()
    logger.info("Terraform Health-Check gestartet")

    yield

    # Shutdown
    await health_service.stop_background_check()
    logger.info("Terraform Health-Check gestoppt")

    await stop_backup_scheduler()
    logger.info("Backup-Scheduler gestoppt")

    await sync_service.stop_background_sync()
    logger.info("Background Inventory-Sync gestoppt")


app = FastAPI(
    title=settings.app_name,
    description="Standalone VM-Management fuer Proxmox mit integriertem NetBox, Ansible und Terraform",
    version="1.0.10",
    lifespan=lifespan,
)

# CORS (HIGH-01: Warnung bei Wildcard erfolgt beim Startup in log_security_warnings_on_startup)
# CORS wird nur hinzugefuegt wenn Origins konfiguriert sind
if settings.cors_origins:
    # Bei Wildcard: Credentials werden ignoriert (Browser-Sicherheit)
    allow_creds = "*" not in settings.cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=allow_creds,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    )

# Exception-Handler registrieren
register_exception_handlers(app)

# API Versionierung
from app.api_versioning import create_versioned_app
create_versioned_app(app)

# Router einbinden
app.include_router(auth_router)
app.include_router(inventory_router)
app.include_router(playbooks_router)
app.include_router(executions_router)
app.include_router(users_router)
app.include_router(settings_router)
app.include_router(terraform_router)
app.include_router(vm_templates_router)
app.include_router(cloud_init_router)
app.include_router(setup_router)
app.include_router(netbox_router)
app.include_router(websocket_router)
app.include_router(notifications_router)
app.include_router(password_reset_router)
app.include_router(cloud_init_settings_router)
app.include_router(backup_router)
app.include_router(roles_router)
app.include_router(audit_router)
app.include_router(rollback_router)


@app.get("/")
async def root():
    """Health Check"""
    return {
        "app": settings.app_name,
        "version": "1.0.10",
        "status": "running",
    }


@app.get("/api/health")
async def health():
    """
    Einfacher Health Check fuer Monitoring und Load Balancer.

    HIGH-02: Gibt nur Basis-Status zurueck, keine Infrastruktur-Details.
    Fuer detaillierte Infos: /api/health/detailed (erfordert Auth)
    """
    return {"status": "healthy"}


@app.get("/api/health/detailed")
async def health_detailed():
    """
    Detaillierter Health Check mit Service-Status.

    HIGH-02: Detaillierte Infrastruktur-Infos sind oeffentlich, aber
    ohne sensible Details wie Node-Anzahl oder Cluster-Namen.
    """
    import httpx
    from app.services.proxmox_service import proxmox_service

    services = {
        "api": {"status": "healthy"},
        "netbox": {"status": "unknown"},
        "proxmox": {"status": "unknown"},
    }

    # NetBox Status pruefen
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.netbox_url}/api/status/")
            if response.status_code == 200:
                services["netbox"] = {"status": "healthy"}
            else:
                services["netbox"] = {"status": "degraded"}
    except httpx.ConnectError:
        services["netbox"] = {"status": "starting"}
    except httpx.TimeoutException:
        services["netbox"] = {"status": "starting"}
    except Exception:
        services["netbox"] = {"status": "error"}

    # Proxmox Status pruefen (HIGH-02: keine Node-Anzahl preisgeben)
    if not proxmox_service.is_configured():
        services["proxmox"] = {"status": "not_configured"}
    else:
        try:
            nodes = await proxmox_service.get_node_stats()
            if nodes:
                online_count = len([n for n in nodes if n.get("status") == "online"])
                if online_count == len(nodes):
                    services["proxmox"] = {"status": "healthy"}
                elif online_count > 0:
                    services["proxmox"] = {"status": "degraded"}
                else:
                    services["proxmox"] = {"status": "error"}
            else:
                services["proxmox"] = {"status": "error"}
        except Exception:
            services["proxmox"] = {"status": "error"}

    # Gesamtstatus ermitteln
    overall = "healthy"
    if any(s["status"] == "error" for s in services.values()):
        overall = "degraded"
    elif any(s["status"] in ("starting", "not_configured") for s in services.values()):
        overall = "starting"

    return {
        "status": overall,
        "services": services,
    }
