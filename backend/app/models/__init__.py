"""
SQLAlchemy Models
"""
from app.models.user import User
from app.models.user_group_access import UserGroupAccess
from app.models.user_playbook_access import UserPlaybookAccess
from app.models.user_host_access import UserHostAccess
from app.models.app_settings import AppSettings
from app.models.execution import Execution
from app.models.execution_log import ExecutionLog
from app.models.vm_template import VMTemplate
from app.models.vm_history import VMHistory

# Benachrichtigungs-Models
from app.models.notification_settings import NotificationSettings
from app.models.user_notification_preferences import UserNotificationPreferences
from app.models.password_reset_token import PasswordResetToken
from app.models.webhook import Webhook
from app.models.notification_log import NotificationLog

# Cloud-Init Settings
from app.models.cloud_init_settings import CloudInitSettings

# Backup Models
from app.models.backup import BackupHistory, BackupSchedule

# RBAC Models
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user_role import UserRole
from app.models.playbook_metadata import PlaybookMetadata

# Audit Models
from app.models.audit_log import AuditLog
from app.models.audit_rollback import AuditRollback

# Terraform Health Model
from app.models.terraform_health import TerraformHealthStatus

# NetBox Cache Model
from app.models.netbox_cache import NetBoxScanCache

__all__ = [
    "User",
    "UserGroupAccess",
    "UserPlaybookAccess",
    "UserHostAccess",
    "AppSettings",
    "Execution",
    "ExecutionLog",
    "VMTemplate",
    "VMHistory",
    # Benachrichtigungs-Models
    "NotificationSettings",
    "UserNotificationPreferences",
    "PasswordResetToken",
    "Webhook",
    "NotificationLog",
    # Cloud-Init Settings
    "CloudInitSettings",
    # Backup Models
    "BackupHistory",
    "BackupSchedule",
    # RBAC Models
    "Permission",
    "Role",
    "RolePermission",
    "UserRole",
    "PlaybookMetadata",
    # Audit Models
    "AuditLog",
    "AuditRollback",
    # Terraform Health Model
    "TerraformHealthStatus",
    # NetBox Cache Model
    "NetBoxScanCache",
]
