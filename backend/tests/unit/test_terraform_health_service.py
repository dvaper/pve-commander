"""
Tests fuer den Terraform Health Service

Fokus: Verhalten der check_health() Methode bei verschiedenen
Proxmox-API-Zustaenden (erreichbar / unerreichbar / Empty).
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.services.terraform_health_service import TerraformHealthService


def _state_show_payload(vmid: int, name: str, node: str = "gandalf") -> dict:
    """Hilfsfunktion: Build state_show response wie terraform_service liefert"""
    return {
        "success": True,
        "data": {
            "values": {
                "vm_id": vmid,
                "name": name,
                "node_name": node,
            }
        },
    }


@pytest.fixture
def service():
    """TerraformHealthService mit gemockten externen Abhaengigkeiten"""
    svc = TerraformHealthService()
    svc._terraform_service = AsyncMock()
    svc._save_status = AsyncMock()
    svc.get_last_status = AsyncMock()
    return svc


class TestCheckHealthSanityGuard:
    """Sanity-Guard: Leeres Proxmox-Resultat = API down -> Skip"""

    @pytest.mark.asyncio
    async def test_skips_when_proxmox_returns_empty(self, service):
        """
        Regression: Bei unerreichbarer Proxmox-API darf der Health-Check
        die State-VMs NICHT als verwaist markieren. Stattdessen: skip,
        persistierter Status unveraendert, keine Notification.
        """
        service._terraform_service.state_list.return_value = [
            "module.vms.proxmox_virtual_environment_vm.adguard02",
            "module.vms.proxmox_virtual_environment_vm.code",
        ]
        service._terraform_service.state_show.side_effect = [
            _state_show_payload(60104, "adguard02"),
            _state_show_payload(60160, "code"),
        ]
        service.get_last_status.return_value = {
            "healthy": True,
            "total_vms": 2,
            "orphaned_count": 0,
            "orphaned_vms": [],
        }

        with patch(
            "app.services.terraform_health_service.proxmox_service.get_all_vms",
            new=AsyncMock(return_value=[]),
        ):
            result = await service.check_health()

        assert result["skipped"] is True
        assert result["healthy"] is True
        assert result["orphaned_count"] == 0
        # Persistenter Status darf NICHT geschrieben werden
        service._save_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_preserves_last_known_status(self, service):
        """Bei Skip wird der letzte bekannte Status durchgereicht"""
        service._terraform_service.state_list.return_value = []
        service.get_last_status.return_value = {
            "healthy": False,
            "total_vms": 23,
            "orphaned_count": 5,
            "orphaned_vms": [{"vmid": 999, "address": "x", "reason": "y"}],
        }

        with patch(
            "app.services.terraform_health_service.proxmox_service.get_all_vms",
            new=AsyncMock(return_value=[]),
        ):
            result = await service.check_health()

        assert result["skipped"] is True
        assert result["healthy"] is False
        assert result["total_vms"] == 23
        assert result["orphaned_count"] == 5


class TestCheckHealthRealOrphans:
    """Echte Orphan-Detection bei erreichbarer API"""

    @pytest.mark.asyncio
    async def test_detects_real_orphans(self, service):
        """VMID im State, aber nicht in Proxmox -> verwaist"""
        service._terraform_service.state_list.return_value = [
            "module.vms.proxmox_virtual_environment_vm.alive",
            "module.vms.proxmox_virtual_environment_vm.dead",
        ]
        service._terraform_service.state_show.side_effect = [
            _state_show_payload(100, "alive"),
            _state_show_payload(200, "dead"),
        ]

        with patch(
            "app.services.terraform_health_service.proxmox_service.get_all_vms",
            new=AsyncMock(return_value=[{"vmid": 100, "name": "alive"}]),
        ):
            result = await service.check_health()

        assert result.get("skipped") is not True
        assert result["healthy"] is False
        assert result["orphaned_count"] == 1
        assert result["total_vms"] == 2
        assert result["orphaned_vms"][0]["vmid"] == 200
        # Bei echtem Befund MUSS persistiert werden
        service._save_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_healthy_when_all_match(self, service):
        """Alle State-VMs in Proxmox vorhanden -> healthy"""
        service._terraform_service.state_list.return_value = [
            "module.vms.proxmox_virtual_environment_vm.a",
            "module.vms.proxmox_virtual_environment_vm.b",
        ]
        service._terraform_service.state_show.side_effect = [
            _state_show_payload(100, "a"),
            _state_show_payload(200, "b"),
        ]

        with patch(
            "app.services.terraform_health_service.proxmox_service.get_all_vms",
            new=AsyncMock(return_value=[
                {"vmid": 100, "name": "a"},
                {"vmid": 200, "name": "b"},
            ]),
        ):
            result = await service.check_health()

        assert result.get("skipped") is not True
        assert result["healthy"] is True
        assert result["orphaned_count"] == 0
        assert result["total_vms"] == 2
        service._save_status.assert_called_once()
