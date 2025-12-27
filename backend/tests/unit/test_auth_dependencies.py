"""
Tests fuer Auth Dependencies
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_permission_service_dep,
    require_permission,
)
from app.services.permission_service import PermissionService
from app.exceptions import PermissionDeniedError


# =============================================================================
# Mock User Factory
# =============================================================================

def create_mock_user(
    is_super_admin: bool = False,
    is_admin: bool = False,
    is_active: bool = True,
    user_id: int = 1,
    username: str = "testuser",
):
    """Erstellt einen Mock-User mit konfigurierbaren Eigenschaften"""
    user = MagicMock()
    user.id = user_id
    user.username = username
    user.is_super_admin = is_super_admin
    user.is_admin = is_admin
    user.is_active = is_active
    user.group_access = []
    user.playbook_access = []
    return user


# =============================================================================
# Tests fuer get_permission_service_dep
# =============================================================================

class TestGetPermissionServiceDep:
    """Tests fuer die PermissionService Dependency"""

    @pytest.mark.asyncio
    async def test_returns_permission_service(self):
        """Test dass PermissionService zurueckgegeben wird"""
        mock_user = create_mock_user()

        result = await get_permission_service_dep(mock_user)

        assert isinstance(result, PermissionService)
        assert result.user == mock_user

    @pytest.mark.asyncio
    async def test_super_admin_check_in_service(self):
        """Test dass Super-Admin-Status korrekt ist"""
        super_admin = create_mock_user(is_super_admin=True)
        regular_user = create_mock_user(is_super_admin=False)

        admin_service = await get_permission_service_dep(super_admin)
        user_service = await get_permission_service_dep(regular_user)

        assert admin_service.is_super_admin is True
        assert user_service.is_super_admin is False


# =============================================================================
# Tests fuer require_permission
# =============================================================================

class TestRequirePermission:
    """Tests fuer die require_permission Funktion"""

    @pytest.mark.asyncio
    async def test_super_admin_has_all_permissions(self):
        """Test dass Super-Admin alle Permissions hat"""
        super_admin = create_mock_user(is_super_admin=True)

        # Sollte keine Exception werfen
        result = await require_permission("super_admin", super_admin)
        assert result == super_admin

        result = await require_permission("manage_users", super_admin)
        assert result == super_admin

        result = await require_permission("manage_settings", super_admin)
        assert result == super_admin

    @pytest.mark.asyncio
    async def test_regular_user_denied_super_admin(self):
        """Test dass regulaerer User keine Super-Admin Permission hat"""
        regular_user = create_mock_user(is_super_admin=False)

        with pytest.raises(PermissionDeniedError) as exc_info:
            await require_permission("super_admin", regular_user)

        assert "super_admin" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_regular_user_denied_manage_users(self):
        """Test dass regulaerer User keine User-Verwaltung hat"""
        regular_user = create_mock_user(is_super_admin=False)

        with pytest.raises(PermissionDeniedError) as exc_info:
            await require_permission("manage_users", regular_user)

        assert "manage_users" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_regular_user_denied_manage_settings(self):
        """Test dass regulaerer User keine Settings-Verwaltung hat"""
        regular_user = create_mock_user(is_super_admin=False)

        with pytest.raises(PermissionDeniedError) as exc_info:
            await require_permission("manage_settings", regular_user)

        assert "manage_settings" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_unknown_permission_raises_value_error(self):
        """Test dass unbekannte Permission ValueError wirft"""
        super_admin = create_mock_user(is_super_admin=True)

        with pytest.raises(ValueError) as exc_info:
            await require_permission("unknown_permission", super_admin)

        assert "Unbekannte Permission" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_permission_denied_error_has_correct_status(self):
        """Test dass PermissionDeniedError korrekten Status Code hat"""
        regular_user = create_mock_user(is_super_admin=False)

        with pytest.raises(PermissionDeniedError) as exc_info:
            await require_permission("super_admin", regular_user)

        assert exc_info.value.status_code == 403


# =============================================================================
# Tests fuer PermissionService Integration
# =============================================================================

class TestPermissionServiceIntegration:
    """Integrationstests fuer PermissionService ueber Dependencies"""

    @pytest.mark.asyncio
    async def test_group_access_for_regular_user(self):
        """Test Gruppen-Zugriff fuer regulaeren User"""
        # Mock User mit Gruppen-Zugriff
        mock_access = MagicMock()
        mock_access.group_name = "web_servers"

        user = create_mock_user(is_super_admin=False)
        user.group_access = [mock_access]

        service = await get_permission_service_dep(user)

        assert service.can_access_group("web_servers") is True
        assert service.can_access_group("database_servers") is False

    @pytest.mark.asyncio
    async def test_group_access_for_super_admin(self):
        """Test Gruppen-Zugriff fuer Super-Admin (alle erlaubt)"""
        user = create_mock_user(is_super_admin=True)

        service = await get_permission_service_dep(user)

        # Super-Admin hat Zugriff auf alle Gruppen
        assert service.can_access_group("web_servers") is True
        assert service.can_access_group("database_servers") is True
        assert service.can_access_group("any_group") is True

    @pytest.mark.asyncio
    async def test_playbook_access_for_regular_user(self):
        """Test Playbook-Zugriff fuer regulaeren User"""
        # Mock User mit Playbook-Zugriff
        mock_access = MagicMock()
        mock_access.playbook_name = "deploy.yml"

        user = create_mock_user(is_super_admin=False)
        user.playbook_access = [mock_access]

        service = await get_permission_service_dep(user)

        assert service.can_access_playbook("deploy.yml") is True
        assert service.can_access_playbook("secret.yml") is False

    @pytest.mark.asyncio
    async def test_execution_filter_for_regular_user(self):
        """Test Execution-Filter fuer regulaeren User"""
        user = create_mock_user(is_super_admin=False, user_id=42)

        service = await get_permission_service_dep(user)

        # Regulaerer User bekommt seine User-ID fuer Filterung
        assert service.get_execution_filter_user_id() == 42

    @pytest.mark.asyncio
    async def test_execution_filter_for_super_admin(self):
        """Test Execution-Filter fuer Super-Admin"""
        user = create_mock_user(is_super_admin=True, user_id=1)

        service = await get_permission_service_dep(user)

        # Super-Admin bekommt None (keine Filterung)
        assert service.get_execution_filter_user_id() is None

    @pytest.mark.asyncio
    async def test_can_execute_playbook_super_admin(self):
        """Test dass Super-Admin alle Playbooks ausfuehren kann"""
        user = create_mock_user(is_super_admin=True)

        service = await get_permission_service_dep(user)

        assert service.can_execute_playbook("any_playbook.yml", ["any_group"]) is True

    @pytest.mark.asyncio
    async def test_can_execute_playbook_regular_user_denied(self):
        """Test dass regulaerer User ohne Berechtigung nicht ausfuehren kann"""
        user = create_mock_user(is_super_admin=False)
        user.playbook_access = []  # Keine Playbook-Zugriffe
        user.group_access = []  # Keine Gruppen-Zugriffe

        service = await get_permission_service_dep(user)

        assert service.can_execute_playbook("deploy.yml", ["web_servers"]) is False

    @pytest.mark.asyncio
    async def test_can_execute_playbook_regular_user_allowed(self):
        """Test dass regulaerer User mit Berechtigung ausfuehren kann"""
        # Mock Playbook-Zugriff
        pb_access = MagicMock()
        pb_access.playbook_name = "deploy.yml"

        # Mock Gruppen-Zugriff
        grp_access = MagicMock()
        grp_access.group_name = "web_servers"

        user = create_mock_user(is_super_admin=False)
        user.playbook_access = [pb_access]
        user.group_access = [grp_access]

        service = await get_permission_service_dep(user)

        assert service.can_execute_playbook("deploy.yml", ["web_servers"]) is True
        # Andere Kombination nicht erlaubt
        assert service.can_execute_playbook("deploy.yml", ["db_servers"]) is False
        assert service.can_execute_playbook("other.yml", ["web_servers"]) is False
