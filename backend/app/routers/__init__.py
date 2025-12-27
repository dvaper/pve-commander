"""
API Routers
"""
from app.routers.auth import router as auth_router
from app.routers.inventory import router as inventory_router
from app.routers.playbooks import router as playbooks_router
from app.routers.executions import router as executions_router
from app.routers.users import router as users_router
from app.routers.settings import router as settings_router
from app.routers.terraform import router as terraform_router
from app.routers.vm_templates import router as vm_templates_router
from app.routers.cloud_init import router as cloud_init_router
from app.routers.setup import router as setup_router
from app.routers.netbox import router as netbox_router

__all__ = [
    "auth_router",
    "inventory_router",
    "playbooks_router",
    "executions_router",
    "users_router",
    "settings_router",
    "terraform_router",
    "vm_templates_router",
    "cloud_init_router",
    "setup_router",
    "netbox_router",
]
