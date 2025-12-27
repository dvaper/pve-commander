"""
Unit Tests fuer app.services.permission_service

Tests fuer PermissionService Zugriffslogik.
"""
import pytest
from unittest.mock import Mock, MagicMock

from app.services.permission_service import PermissionService, get_permission_service


class TestPermissionServiceSuperAdmin:
    """Tests fuer Super-Admin Berechtigungen"""

    def test_is_super_admin_true(self):
        """Super-Admin wird korrekt erkannt"""
        user = Mock()
        user.is_super_admin = True
        user.is_active = True

        service = PermissionService(user)

        assert service.is_super_admin is True

    def test_is_super_admin_false(self):
        """Normaler User ist kein Super-Admin"""
        user = Mock()
        user.is_super_admin = False
        user.is_active = True

        service = PermissionService(user)

        assert service.is_super_admin is False

    def test_is_super_admin_with_none_user(self):
        """None-User ist kein Super-Admin"""
        service = PermissionService(None)

        assert service.is_super_admin is False

    def test_super_admin_can_manage_users(self):
        """Super-Admin kann Benutzer verwalten"""
        user = Mock()
        user.is_super_admin = True
        user.is_active = True

        service = PermissionService(user)

        assert service.can_manage_users is True

    def test_regular_user_cannot_manage_users(self):
        """Normaler User kann keine Benutzer verwalten"""
        user = Mock()
        user.is_super_admin = False
        user.is_active = True

        service = PermissionService(user)

        assert service.can_manage_users is False

    def test_super_admin_can_manage_settings(self):
        """Super-Admin kann Settings verwalten"""
        user = Mock()
        user.is_super_admin = True
        user.is_active = True

        service = PermissionService(user)

        assert service.can_manage_settings is True


class TestPermissionServiceGroups:
    """Tests fuer Gruppen-Berechtigungen"""

    def test_super_admin_accessible_groups_empty(self):
        """Super-Admin hat leeres Set (= alle Gruppen)"""
        user = Mock()
        user.is_super_admin = True
        user.is_active = True

        service = PermissionService(user)

        assert service.get_accessible_groups() == set()

    def test_regular_user_accessible_groups(self):
        """Normaler User hat zugewiesene Gruppen"""
        user = Mock()
        user.is_super_admin = False
        user.is_active = True

        # Mock group_access Relationship
        access1 = Mock()
        access1.group_name = "webservers"
        access2 = Mock()
        access2.group_name = "databases"
        user.group_access = [access1, access2]

        service = PermissionService(user)
        groups = service.get_accessible_groups()

        assert groups == {"webservers", "databases"}

    def test_super_admin_can_access_any_group(self):
        """Super-Admin kann auf jede Gruppe zugreifen"""
        user = Mock()
        user.is_super_admin = True
        user.is_active = True

        service = PermissionService(user)

        assert service.can_access_group("any_group") is True
        assert service.can_access_group("another_group") is True

    def test_regular_user_can_access_assigned_group(self):
        """Normaler User kann auf zugewiesene Gruppe zugreifen"""
        user = Mock()
        user.is_super_admin = False
        user.is_active = True

        access = Mock()
        access.group_name = "webservers"
        user.group_access = [access]

        service = PermissionService(user)

        assert service.can_access_group("webservers") is True

    def test_regular_user_cannot_access_unassigned_group(self):
        """Normaler User kann nicht auf nicht zugewiesene Gruppe zugreifen"""
        user = Mock()
        user.is_super_admin = False
        user.is_active = True
        user.group_access = []

        service = PermissionService(user)

        assert service.can_access_group("webservers") is False

    def test_filter_groups_super_admin(self):
        """Super-Admin erhaelt alle Gruppen"""
        user = Mock()
        user.is_super_admin = True
        user.is_active = True

        service = PermissionService(user)
        all_groups = ["webservers", "databases", "monitoring"]

        filtered = service.filter_groups(all_groups)

        assert filtered == all_groups

    def test_filter_groups_regular_user(self):
        """Normaler User erhaelt nur zugewiesene Gruppen"""
        user = Mock()
        user.is_super_admin = False
        user.is_active = True

        access = Mock()
        access.group_name = "webservers"
        user.group_access = [access]

        service = PermissionService(user)
        all_groups = ["webservers", "databases", "monitoring"]

        filtered = service.filter_groups(all_groups)

        assert filtered == ["webservers"]

    def test_can_access_any_group_super_admin(self):
        """Super-Admin kann auf beliebige Gruppe zugreifen"""
        user = Mock()
        user.is_super_admin = True
        user.is_active = True

        service = PermissionService(user)

        assert service.can_access_any_group(["unknown", "groups"]) is True

    def test_can_access_any_group_regular_user_has_one(self):
        """User hat Zugriff auf mindestens eine Gruppe"""
        user = Mock()
        user.is_super_admin = False
        user.is_active = True

        access = Mock()
        access.group_name = "webservers"
        user.group_access = [access]

        service = PermissionService(user)

        assert service.can_access_any_group(["webservers", "databases"]) is True

    def test_can_access_any_group_regular_user_has_none(self):
        """User hat keinen Zugriff auf Gruppen"""
        user = Mock()
        user.is_super_admin = False
        user.is_active = True
        user.group_access = []

        service = PermissionService(user)

        assert service.can_access_any_group(["webservers", "databases"]) is False


class TestPermissionServicePlaybooks:
    """Tests fuer Playbook-Berechtigungen"""

    def test_super_admin_can_access_any_playbook(self):
        """Super-Admin kann auf jedes Playbook zugreifen"""
        user = Mock()
        user.is_super_admin = True
        user.is_active = True

        service = PermissionService(user)

        assert service.can_access_playbook("any_playbook.yml") is True

    def test_regular_user_can_access_assigned_playbook(self):
        """Normaler User kann auf zugewiesenes Playbook zugreifen"""
        user = Mock()
        user.is_super_admin = False
        user.is_active = True

        access = Mock()
        access.playbook_name = "deploy.yml"
        user.playbook_access = [access]

        service = PermissionService(user)

        assert service.can_access_playbook("deploy.yml") is True

    def test_regular_user_cannot_access_unassigned_playbook(self):
        """Normaler User kann nicht auf nicht zugewiesenes Playbook zugreifen"""
        user = Mock()
        user.is_super_admin = False
        user.is_active = True
        user.playbook_access = []

        service = PermissionService(user)

        assert service.can_access_playbook("deploy.yml") is False

    def test_filter_playbooks_super_admin(self):
        """Super-Admin erhaelt alle Playbooks"""
        user = Mock()
        user.is_super_admin = True
        user.is_active = True

        service = PermissionService(user)
        playbooks = [
            {"name": "deploy.yml"},
            {"name": "backup.yml"},
        ]

        filtered = service.filter_playbooks(playbooks)

        assert filtered == playbooks

    def test_filter_playbooks_regular_user(self):
        """Normaler User erhaelt nur zugewiesene Playbooks"""
        user = Mock()
        user.is_super_admin = False
        user.is_active = True

        access = Mock()
        access.playbook_name = "deploy.yml"
        user.playbook_access = [access]

        service = PermissionService(user)
        playbooks = [
            {"name": "deploy.yml"},
            {"name": "backup.yml"},
        ]

        filtered = service.filter_playbooks(playbooks)

        assert len(filtered) == 1
        assert filtered[0]["name"] == "deploy.yml"


class TestPermissionServiceExecutions:
    """Tests fuer Execution-Berechtigungen"""

    def test_super_admin_can_view_any_execution(self):
        """Super-Admin kann jede Execution sehen"""
        user = Mock()
        user.is_super_admin = True
        user.is_active = True
        user.id = 1

        service = PermissionService(user)

        assert service.can_view_execution(999) is True

    def test_regular_user_can_view_own_execution(self):
        """Normaler User kann eigene Execution sehen"""
        user = Mock()
        user.is_super_admin = False
        user.is_active = True
        user.id = 42

        service = PermissionService(user)

        assert service.can_view_execution(42) is True

    def test_regular_user_cannot_view_other_execution(self):
        """Normaler User kann fremde Execution nicht sehen"""
        user = Mock()
        user.is_super_admin = False
        user.is_active = True
        user.id = 42

        service = PermissionService(user)

        assert service.can_view_execution(99) is False

    def test_super_admin_can_cancel_any_execution(self):
        """Super-Admin kann jede Execution abbrechen"""
        user = Mock()
        user.is_super_admin = True
        user.is_active = True
        user.id = 1

        service = PermissionService(user)

        assert service.can_cancel_execution(999) is True

    def test_regular_user_can_cancel_own_execution(self):
        """Normaler User kann eigene Execution abbrechen"""
        user = Mock()
        user.is_super_admin = False
        user.is_active = True
        user.id = 42

        service = PermissionService(user)

        assert service.can_cancel_execution(42) is True

    def test_execution_filter_super_admin(self):
        """Super-Admin hat keine Execution-Filterung"""
        user = Mock()
        user.is_super_admin = True
        user.is_active = True
        user.id = 1

        service = PermissionService(user)

        assert service.get_execution_filter_user_id() is None

    def test_execution_filter_regular_user(self):
        """Normaler User wird nach User-ID gefiltert"""
        user = Mock()
        user.is_super_admin = False
        user.is_active = True
        user.id = 42

        service = PermissionService(user)

        assert service.get_execution_filter_user_id() == 42


class TestPermissionServicePlaybookExecution:
    """Tests fuer Playbook-Ausfuehrung"""

    def test_super_admin_can_execute_any_playbook(self):
        """Super-Admin kann jedes Playbook ausfuehren"""
        user = Mock()
        user.is_super_admin = True
        user.is_active = True

        service = PermissionService(user)

        assert service.can_execute_playbook("any.yml", ["any_group"]) is True

    def test_regular_user_can_execute_assigned_playbook_on_assigned_groups(self):
        """Normaler User kann zugewiesenes Playbook auf zugewiesenen Gruppen ausfuehren"""
        user = Mock()
        user.is_super_admin = False
        user.is_active = True

        playbook_access = Mock()
        playbook_access.playbook_name = "deploy.yml"
        user.playbook_access = [playbook_access]

        group_access = Mock()
        group_access.group_name = "webservers"
        user.group_access = [group_access]

        service = PermissionService(user)

        assert service.can_execute_playbook("deploy.yml", ["webservers"]) is True

    def test_regular_user_cannot_execute_unassigned_playbook(self):
        """Normaler User kann nicht zugewiesenes Playbook nicht ausfuehren"""
        user = Mock()
        user.is_super_admin = False
        user.is_active = True
        user.playbook_access = []

        group_access = Mock()
        group_access.group_name = "webservers"
        user.group_access = [group_access]

        service = PermissionService(user)

        assert service.can_execute_playbook("deploy.yml", ["webservers"]) is False

    def test_regular_user_cannot_execute_on_unassigned_groups(self):
        """Normaler User kann nicht auf nicht zugewiesenen Gruppen ausfuehren"""
        user = Mock()
        user.is_super_admin = False
        user.is_active = True

        playbook_access = Mock()
        playbook_access.playbook_name = "deploy.yml"
        user.playbook_access = [playbook_access]

        user.group_access = []  # Keine Gruppen

        service = PermissionService(user)

        assert service.can_execute_playbook("deploy.yml", ["webservers"]) is False

    def test_regular_user_needs_all_groups(self):
        """User braucht Zugriff auf ALLE Ziel-Gruppen"""
        user = Mock()
        user.is_super_admin = False
        user.is_active = True

        playbook_access = Mock()
        playbook_access.playbook_name = "deploy.yml"
        user.playbook_access = [playbook_access]

        group_access = Mock()
        group_access.group_name = "webservers"
        user.group_access = [group_access]

        service = PermissionService(user)

        # Hat nur webservers, braucht aber webservers UND databases
        assert service.can_execute_playbook("deploy.yml", ["webservers", "databases"]) is False


class TestPermissionServiceAccessSummary:
    """Tests fuer Access-Summary"""

    def test_access_summary_super_admin(self):
        """Access Summary fuer Super-Admin"""
        user = Mock()
        user.is_super_admin = True
        user.is_active = True
        user.group_access = []
        user.playbook_access = []

        service = PermissionService(user)
        summary = service.get_access_summary()

        assert summary["is_super_admin"] is True
        assert summary["can_manage_users"] is True
        assert summary["can_manage_settings"] is True
        assert summary["accessible_groups"] == []
        assert summary["accessible_playbooks"] == []

    def test_access_summary_regular_user(self):
        """Access Summary fuer normalen User"""
        user = Mock()
        user.is_super_admin = False
        user.is_active = True

        group_access = Mock()
        group_access.group_name = "webservers"
        user.group_access = [group_access]

        playbook_access = Mock()
        playbook_access.playbook_name = "deploy.yml"
        user.playbook_access = [playbook_access]

        service = PermissionService(user)
        summary = service.get_access_summary()

        assert summary["is_super_admin"] is False
        assert summary["can_manage_users"] is False
        assert summary["accessible_groups"] == ["webservers"]
        assert summary["accessible_playbooks"] == ["deploy.yml"]


class TestPermissionServiceCaching:
    """Tests fuer Caching-Verhalten"""

    def test_accessible_groups_cached(self):
        """Gruppen werden gecacht"""
        user = Mock()
        user.is_super_admin = False
        user.is_active = True

        access = Mock()
        access.group_name = "webservers"
        user.group_access = [access]

        service = PermissionService(user)

        # Erstes Mal
        groups1 = service.get_accessible_groups()
        # Zweites Mal (sollte gecacht sein)
        groups2 = service.get_accessible_groups()

        assert groups1 is groups2  # Gleiches Objekt

    def test_accessible_playbooks_cached(self):
        """Playbooks werden gecacht"""
        user = Mock()
        user.is_super_admin = False
        user.is_active = True

        access = Mock()
        access.playbook_name = "deploy.yml"
        user.playbook_access = [access]

        service = PermissionService(user)

        playbooks1 = service.get_accessible_playbooks()
        playbooks2 = service.get_accessible_playbooks()

        assert playbooks1 is playbooks2


class TestFactoryFunction:
    """Tests fuer Factory-Funktion"""

    def test_get_permission_service_returns_service(self):
        """Factory gibt PermissionService zurueck"""
        user = Mock()

        service = get_permission_service(user)

        assert isinstance(service, PermissionService)
        assert service.user is user
