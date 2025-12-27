"""
RBAC Seed Data - Default Permissions und Rollen
"""
import json
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user_role import UserRole
from app.models.user import User

logger = logging.getLogger(__name__)


# =============================================================================
# Permission Definitionen
# =============================================================================

PERMISSIONS = {
    # User Management
    "users.read": ("users", "read", "Benutzerliste und -details anzeigen"),
    "users.write": ("users", "write", "Benutzer erstellen und bearbeiten"),
    "users.delete": ("users", "delete", "Benutzer loeschen"),
    "users.admin": ("users", "admin", "Vollstaendige Benutzerverwaltung inkl. Passwort-Reset"),

    # Role Management
    "roles.read": ("roles", "read", "Rollen und Berechtigungen anzeigen"),
    "roles.write": ("roles", "write", "Rollen erstellen und bearbeiten"),
    "roles.delete": ("roles", "delete", "Rollen loeschen"),
    "roles.assign": ("roles", "assign", "Rollen an Benutzer zuweisen"),

    # Playbook Operations
    "playbooks.read": ("playbooks", "read", "Playbooks anzeigen"),
    "playbooks.write": ("playbooks", "write", "Custom Playbooks erstellen und bearbeiten"),
    "playbooks.delete": ("playbooks", "delete", "Custom Playbooks loeschen"),
    "playbooks.execute": ("playbooks", "execute", "Playbooks ausfuehren"),

    # Inventory Management
    "inventory.read": ("inventory", "read", "Inventory-Gruppen und Hosts anzeigen"),
    "inventory.write": ("inventory", "write", "Inventory bearbeiten"),
    "inventory.sync": ("inventory", "sync", "Inventory-Synchronisation ausloesen"),

    # Execution History
    "executions.read": ("executions", "read", "Eigene Execution-Historie anzeigen"),
    "executions.read_all": ("executions", "read_all", "Alle Executions aller Benutzer anzeigen"),
    "executions.cancel": ("executions", "cancel", "Laufende Executions abbrechen"),
    "executions.delete": ("executions", "delete", "Execution-Historie loeschen"),

    # Settings
    "settings.read": ("settings", "read", "Anwendungseinstellungen anzeigen"),
    "settings.write": ("settings", "write", "Anwendungseinstellungen aendern"),

    # Terraform/VMs
    "terraform.read": ("terraform", "read", "VM-Konfigurationen anzeigen"),
    "terraform.execute": ("terraform", "execute", "Terraform-Operationen ausfuehren"),
    "terraform.write": ("terraform", "write", "VM-Konfigurationen bearbeiten"),

    # VM Power Operations
    "vms.read": ("vms", "read", "VM-Liste und Status anzeigen"),
    "vms.power": ("vms", "power", "VMs starten/stoppen/neustarten"),
    "vms.create": ("vms", "create", "Neue VMs erstellen"),
    "vms.delete": ("vms", "delete", "VMs loeschen"),

    # Audit
    "audit.read": ("audit", "read", "Audit-Logs anzeigen"),
    "audit.verify": ("audit", "verify", "Audit-Chain verifizieren"),
    "audit.export": ("audit", "export", "Audit-Logs exportieren"),
    "audit.rollback": ("audit", "rollback", "Rollback-Operationen ausfuehren"),

    # Backup
    "backup.read": ("backup", "read", "Backup-Historie anzeigen"),
    "backup.create": ("backup", "create", "Backups erstellen"),
    "backup.restore": ("backup", "restore", "Aus Backups wiederherstellen"),
    "backup.delete": ("backup", "delete", "Backups loeschen"),

    # NetBox Integration
    "netbox.read": ("netbox", "read", "NetBox-Daten anzeigen"),
    "netbox.sync": ("netbox", "sync", "NetBox-Synchronisation ausloesen"),
    "netbox.write": ("netbox", "write", "NetBox-Daten bearbeiten"),

    # Notifications
    "notifications.read": ("notifications", "read", "Benachrichtigungs-Einstellungen anzeigen"),
    "notifications.write": ("notifications", "write", "Benachrichtigungs-Einstellungen bearbeiten"),
}


# =============================================================================
# Default Rollen
# =============================================================================

DEFAULT_ROLES = [
    {
        "name": "super-admin",
        "display_name": "Super-Administrator",
        "description": "Vollzugriff auf alle Funktionen. Kann System-Einstellungen aendern und Benutzer verwalten.",
        "is_system_role": True,
        "is_super_admin": True,
        "priority": 1000,
        "permissions": [],  # Super-Admin braucht keine expliziten Permissions
    },
    {
        "name": "admin",
        "display_name": "Administrator",
        "description": "Kann Benutzer und Rollen verwalten, Audit-Logs einsehen, aber keine System-Einstellungen aendern.",
        "is_system_role": True,
        "is_super_admin": False,
        "priority": 900,
        "permissions": [
            "users.read", "users.write", "users.delete",
            "roles.read", "roles.write", "roles.assign",
            "audit.read", "audit.verify", "audit.export",
            "settings.read",
            "playbooks.read", "playbooks.execute",
            "inventory.read",
            "executions.read_all",
            "vms.read",
            "backup.read",
            "netbox.read",
            "notifications.read",
        ],
    },
    {
        "name": "linux-admin",
        "display_name": "Linux-Administrator",
        "description": "Kann Linux-Systeme verwalten. Zugriff auf Linux-Playbooks und -Gruppen.",
        "is_system_role": True,
        "is_super_admin": False,
        "priority": 500,
        "allowed_os_types": ["linux", "all"],
        "permissions": [
            "playbooks.read", "playbooks.write", "playbooks.execute",
            "inventory.read", "inventory.write", "inventory.sync",
            "executions.read", "executions.cancel",
            "terraform.read", "terraform.execute", "terraform.write",
            "vms.read", "vms.power", "vms.create",
            "backup.read", "backup.create",
            "netbox.read", "netbox.sync",
        ],
    },
    {
        "name": "windows-admin",
        "display_name": "Windows-Administrator",
        "description": "Kann Windows-Systeme verwalten. Zugriff auf Windows-Playbooks und -Gruppen.",
        "is_system_role": True,
        "is_super_admin": False,
        "priority": 500,
        "allowed_os_types": ["windows", "all"],
        "permissions": [
            "playbooks.read", "playbooks.write", "playbooks.execute",
            "inventory.read", "inventory.write",
            "executions.read", "executions.cancel",
            "vms.read", "vms.power",
            "backup.read", "backup.create",
        ],
    },
    {
        "name": "operator",
        "display_name": "Operator",
        "description": "Kann Playbooks ausfuehren und VMs steuern. Keine Aenderungen an Konfigurationen.",
        "is_system_role": True,
        "is_super_admin": False,
        "priority": 300,
        "permissions": [
            "playbooks.read", "playbooks.execute",
            "inventory.read",
            "executions.read",
            "vms.read", "vms.power",
            "backup.read",
            "netbox.read",
        ],
    },
    {
        "name": "read-only",
        "display_name": "Nur Lesen",
        "description": "Kann alle Daten einsehen, aber keine Aenderungen vornehmen.",
        "is_system_role": True,
        "is_super_admin": False,
        "priority": 100,
        "permissions": [
            "playbooks.read",
            "inventory.read",
            "executions.read",
            "vms.read",
            "backup.read",
            "netbox.read",
            "settings.read",
        ],
    },
]


# =============================================================================
# Seeding Functions
# =============================================================================

async def seed_permissions(db: AsyncSession) -> int:
    """
    Seeded alle definierten Permissions in die Datenbank.

    Returns:
        Anzahl der neu erstellten Permissions
    """
    created = 0

    for perm_name, (resource, action, description) in PERMISSIONS.items():
        # Pruefen ob Permission bereits existiert
        result = await db.execute(
            select(Permission).where(Permission.name == perm_name)
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            permission = Permission(
                name=perm_name,
                resource=resource,
                action=action,
                description=description,
                is_system=True
            )
            db.add(permission)
            created += 1
            logger.debug(f"Permission erstellt: {perm_name}")

    if created > 0:
        await db.commit()
        logger.info(f"{created} Permissions erstellt")

    return created


async def seed_roles(db: AsyncSession) -> int:
    """
    Seeded Default-Rollen mit ihren Permissions.

    Returns:
        Anzahl der neu erstellten Rollen
    """
    created = 0

    for role_def in DEFAULT_ROLES:
        # Pruefen ob Rolle bereits existiert
        result = await db.execute(
            select(Role).where(Role.name == role_def["name"])
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            # Rolle erstellen
            role = Role(
                name=role_def["name"],
                display_name=role_def["display_name"],
                description=role_def["description"],
                is_system_role=role_def.get("is_system_role", False),
                is_super_admin=role_def.get("is_super_admin", False),
                priority=role_def.get("priority", 0),
                allowed_os_types=json.dumps(role_def.get("allowed_os_types")) if role_def.get("allowed_os_types") else None,
                allowed_categories=json.dumps(role_def.get("allowed_categories")) if role_def.get("allowed_categories") else None,
                created_by="system",
            )
            db.add(role)
            await db.flush()  # Um ID zu bekommen

            # Permissions zuweisen
            for perm_name in role_def.get("permissions", []):
                result = await db.execute(
                    select(Permission).where(Permission.name == perm_name)
                )
                permission = result.scalar_one_or_none()

                if permission:
                    role_perm = RolePermission(
                        role_id=role.id,
                        permission_id=permission.id,
                        is_deny=False
                    )
                    db.add(role_perm)
                else:
                    logger.warning(f"Permission nicht gefunden: {perm_name}")

            created += 1
            logger.debug(f"Rolle erstellt: {role_def['name']} mit {len(role_def.get('permissions', []))} Permissions")

    if created > 0:
        await db.commit()
        logger.info(f"{created} Rollen erstellt")

    return created


async def assign_super_admin_role(db: AsyncSession) -> int:
    """
    Weist allen existierenden Super-Admins die Super-Admin-Rolle zu.

    Returns:
        Anzahl der zugewiesenen Rollen
    """
    assigned = 0

    # Super-Admin Rolle finden
    result = await db.execute(
        select(Role).where(Role.name == "super-admin")
    )
    super_admin_role = result.scalar_one_or_none()

    if not super_admin_role:
        logger.warning("Super-Admin Rolle nicht gefunden")
        return 0

    # Alle Super-Admins finden
    result = await db.execute(
        select(User).where(User.is_super_admin == True)
    )
    super_admins = result.scalars().all()

    for user in super_admins:
        # Pruefen ob Rolle bereits zugewiesen
        result = await db.execute(
            select(UserRole).where(
                UserRole.user_id == user.id,
                UserRole.role_id == super_admin_role.id
            )
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            user_role = UserRole(
                user_id=user.id,
                role_id=super_admin_role.id,
            )
            db.add(user_role)
            assigned += 1
            logger.debug(f"Super-Admin Rolle zugewiesen an: {user.username}")

    if assigned > 0:
        await db.commit()
        logger.info(f"Super-Admin Rolle an {assigned} Benutzer zugewiesen")

    return assigned


async def seed_rbac_defaults(db: AsyncSession) -> dict:
    """
    Hauptfunktion zum Seeden aller RBAC-Defaults.

    Returns:
        Dictionary mit Statistiken
    """
    logger.info("Starte RBAC Seed...")

    permissions_created = await seed_permissions(db)
    roles_created = await seed_roles(db)
    roles_assigned = await assign_super_admin_role(db)

    stats = {
        "permissions_created": permissions_created,
        "roles_created": roles_created,
        "roles_assigned": roles_assigned,
    }

    logger.info(f"RBAC Seed abgeschlossen: {stats}")
    return stats
