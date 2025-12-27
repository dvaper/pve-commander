"""
NetBox Service - Integration mit NetBox IPAM für IP-Management

Alle VLANs und Prefixes werden dynamisch aus NetBox geladen.
Die Konfiguration erfolgt direkt in NetBox (nicht in der Applikation).
"""
import httpx
from typing import Optional
from app.config import settings


class NetBoxService:
    """Service für NetBox IPAM Integration"""

    def __init__(self):
        self.base_url = settings.netbox_url
        self.token = settings.netbox_token
        self.headers = {
            "Authorization": f"Token {self.token}",
            "Content-Type": "application/json",
        }

    def _check_token(self):
        """Prüft ob NetBox-Token konfiguriert ist"""
        if not self.token:
            raise ValueError("NetBox API Token nicht konfiguriert (NETBOX_TOKEN)")

    async def get_vlans(self) -> list[dict]:
        """
        Holt alle VLANs aus NetBox.

        Gibt VLANs zurück die einen zugehörigen Prefix haben.
        """
        self._check_token()

        async with httpx.AsyncClient() as client:
            # Alle Prefixes mit zugehörigen VLANs laden
            response = await client.get(
                f"{self.base_url}/api/ipam/prefixes/",
                params={"limit": 100},
                headers=self.headers,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            result = []
            for prefix_info in data["results"]:
                vlan_info = prefix_info.get("vlan")
                if vlan_info:
                    vlan_id = vlan_info.get("vid", 0)
                    prefix = prefix_info.get("prefix", "")

                    # Bridge und Gateway aus VLAN-ID ableiten
                    bridge = f"vmbr{vlan_id}"
                    gateway = self._gateway_from_prefix(prefix)

                    result.append({
                        "id": vlan_id,
                        "name": vlan_info.get("name", f"VLAN{vlan_id}"),
                        "prefix": prefix,
                        "bridge": bridge,
                        "gateway": gateway,
                    })

            return sorted(result, key=lambda x: x["id"])

    def _gateway_from_prefix(self, prefix: str) -> str:
        """Leitet Gateway aus Prefix ab (erstes IP im Subnet)"""
        if not prefix:
            return ""
        # prefix ist z.B. "10.0.0.0/24"
        network = prefix.split("/")[0]
        octets = network.split(".")
        if len(octets) == 4:
            octets[3] = "1"  # Gateway ist typischerweise .1
            return ".".join(octets)
        return ""

    async def get_prefix_for_vlan(self, vlan: int) -> Optional[str]:
        """Holt den Prefix aus NetBox für ein VLAN"""
        self._check_token()

        async with httpx.AsyncClient() as client:
            # Prefix mit VLAN-ID suchen
            response = await client.get(
                f"{self.base_url}/api/ipam/prefixes/",
                params={"vlan_vid": vlan},
                headers=self.headers,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            if data["count"] > 0:
                return data["results"][0]["prefix"]
            return None

    async def get_prefix_id(self, vlan: int) -> Optional[int]:
        """Holt die Prefix-ID aus NetBox für ein VLAN"""
        self._check_token()

        async with httpx.AsyncClient() as client:
            # Prefix mit VLAN-ID suchen
            response = await client.get(
                f"{self.base_url}/api/ipam/prefixes/",
                params={"vlan_vid": vlan},
                headers=self.headers,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            if data["count"] > 0:
                return data["results"][0]["id"]
            return None

    async def get_available_ips(self, vlan: int, limit: int = 10) -> list[dict]:
        """Holt freie IPs aus NetBox für ein VLAN"""
        self._check_token()

        prefix_id = await self.get_prefix_id(vlan)
        if not prefix_id:
            raise ValueError(f"Prefix für VLAN {vlan} nicht in NetBox gefunden")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/ipam/prefixes/{prefix_id}/available-ips/",
                params={"limit": limit},
                headers=self.headers,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            result = []
            for ip_info in data:
                address = ip_info["address"].split("/")[0]
                octets = address.split(".")
                vmid = int(octets[2]) * 1000 + int(octets[3])

                result.append({
                    "address": address,
                    "vmid": vmid,
                    "vlan": vlan,
                })

            return result

    async def get_used_ips(self, vlan: int, limit: int = 100) -> list[dict]:
        """Holt belegte IPs aus NetBox für ein VLAN"""
        self._check_token()

        prefix = await self.get_prefix_for_vlan(vlan)
        if not prefix:
            raise ValueError(f"VLAN {vlan} nicht in NetBox konfiguriert")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/ipam/ip-addresses/",
                params={"parent": prefix, "limit": limit},
                headers=self.headers,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            result = []
            for ip_info in data["results"]:
                address = ip_info["address"].split("/")[0]
                result.append({
                    "address": address,
                    "description": ip_info.get("description", ""),
                    "status": ip_info.get("status", {}).get("value", "active"),
                    "dns_name": ip_info.get("dns_name", ""),
                })

            return sorted(result, key=lambda x: int(x["address"].split(".")[-1]))

    async def reserve_ip(self, ip_address: str, description: str, dns_name: str = "") -> dict:
        """Reserviert eine IP-Adresse in NetBox"""
        self._check_token()

        async with httpx.AsyncClient() as client:
            # Prüfen ob IP bereits existiert
            check_response = await client.get(
                f"{self.base_url}/api/ipam/ip-addresses/",
                params={"address": ip_address},
                headers=self.headers,
                timeout=10.0,
            )
            check_response.raise_for_status()
            existing = check_response.json()

            if existing["count"] > 0:
                # IP existiert bereits - aktualisieren
                ip_id = existing["results"][0]["id"]
                response = await client.patch(
                    f"{self.base_url}/api/ipam/ip-addresses/{ip_id}/",
                    json={
                        "description": description,
                        "dns_name": dns_name,
                        "status": "reserved",
                    },
                    headers=self.headers,
                    timeout=10.0,
                )
            else:
                # Neue IP erstellen
                response = await client.post(
                    f"{self.base_url}/api/ipam/ip-addresses/",
                    json={
                        "address": f"{ip_address}/24",
                        "description": description,
                        "dns_name": dns_name,
                        "status": "reserved",
                    },
                    headers=self.headers,
                    timeout=10.0,
                )

            response.raise_for_status()
            return response.json()

    async def activate_ip(self, ip_address: str) -> dict:
        """Setzt IP-Status auf 'active' (nach erfolgreichem Deploy)"""
        self._check_token()

        async with httpx.AsyncClient() as client:
            # IP finden
            check_response = await client.get(
                f"{self.base_url}/api/ipam/ip-addresses/",
                params={"address": ip_address},
                headers=self.headers,
                timeout=10.0,
            )
            check_response.raise_for_status()
            existing = check_response.json()

            if existing["count"] == 0:
                raise ValueError(f"IP {ip_address} nicht in NetBox gefunden")

            ip_id = existing["results"][0]["id"]

            # Status auf active setzen
            response = await client.patch(
                f"{self.base_url}/api/ipam/ip-addresses/{ip_id}/",
                json={"status": "active"},
                headers=self.headers,
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()

    async def release_ip(self, ip_address: str) -> bool:
        """Gibt eine IP-Adresse frei (löscht sie aus NetBox)"""
        self._check_token()

        async with httpx.AsyncClient() as client:
            # IP finden
            check_response = await client.get(
                f"{self.base_url}/api/ipam/ip-addresses/",
                params={"address": ip_address},
                headers=self.headers,
                timeout=10.0,
            )
            check_response.raise_for_status()
            existing = check_response.json()

            if existing["count"] == 0:
                return False

            ip_id = existing["results"][0]["id"]

            # IP löschen
            response = await client.delete(
                f"{self.base_url}/api/ipam/ip-addresses/{ip_id}/",
                headers=self.headers,
                timeout=10.0,
            )
            return response.status_code == 204

    async def check_ip_available(self, ip_address: str) -> bool:
        """Prüft ob eine IP-Adresse verfügbar ist"""
        self._check_token()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/ipam/ip-addresses/",
                params={"address": ip_address},
                headers=self.headers,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            return data["count"] == 0

    async def get_active_ips(self, prefix: str = None) -> list[dict]:
        """
        Holt alle aktiven IP-Adressen aus NetBox.

        Args:
            prefix: Optional - nur IPs aus diesem Prefix

        Returns:
            Liste von IP-Adressen mit Metadaten
        """
        self._check_token()

        async with httpx.AsyncClient() as client:
            params = {"status": "active", "limit": 1000}
            if prefix:
                params["parent"] = prefix

            response = await client.get(
                f"{self.base_url}/api/ipam/ip-addresses/",
                params=params,
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            return [
                {
                    "id": ip["id"],
                    "address": ip["address"].split("/")[0],  # Ohne CIDR
                    "description": ip.get("description", ""),
                    "dns_name": ip.get("dns_name", ""),
                    "status": ip["status"]["value"],
                }
                for ip in data.get("results", [])
            ]

    # =========================================================================
    # Virtualization - VM Management
    # =========================================================================

    async def get_or_create_cluster(self, cluster_name: str = "Proxmox") -> int:
        """
        Holt oder erstellt einen Virtualization-Cluster in NetBox.

        Args:
            cluster_name: Name des Clusters

        Returns:
            NetBox-ID des Clusters
        """
        self._check_token()

        async with httpx.AsyncClient() as client:
            # Cluster suchen
            response = await client.get(
                f"{self.base_url}/api/virtualization/clusters/",
                params={"name": cluster_name},
                headers=self.headers,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            if data["count"] > 0:
                return data["results"][0]["id"]

            # Cluster-Type holen oder erstellen
            type_response = await client.get(
                f"{self.base_url}/api/virtualization/cluster-types/",
                params={"name": "Proxmox VE"},
                headers=self.headers,
                timeout=10.0,
            )
            type_response.raise_for_status()
            type_data = type_response.json()

            if type_data["count"] > 0:
                cluster_type_id = type_data["results"][0]["id"]
            else:
                # Cluster-Type erstellen
                create_type_response = await client.post(
                    f"{self.base_url}/api/virtualization/cluster-types/",
                    json={
                        "name": "Proxmox VE",
                        "slug": "proxmox-ve",
                        "description": "Proxmox Virtual Environment",
                    },
                    headers=self.headers,
                    timeout=10.0,
                )
                create_type_response.raise_for_status()
                cluster_type_id = create_type_response.json()["id"]

            # Cluster erstellen
            create_response = await client.post(
                f"{self.base_url}/api/virtualization/clusters/",
                json={
                    "name": cluster_name,
                    "type": cluster_type_id,
                    "description": "Automatisch erstellt durch PVE Commander",
                },
                headers=self.headers,
                timeout=10.0,
            )
            create_response.raise_for_status()
            return create_response.json()["id"]

    async def create_vm(
        self,
        name: str,
        vcpus: int = 2,
        memory_mb: int = 4096,
        disk_gb: int = 32,
        cluster_name: str = "Proxmox",
        description: str = "",
    ) -> dict:
        """
        Erstellt ein VM-Objekt in NetBox (virtualization/virtual-machines).

        Args:
            name: Name der VM
            vcpus: Anzahl vCPUs
            memory_mb: RAM in MB
            disk_gb: Disk-Groesse in GB
            cluster_name: Name des Clusters
            description: Beschreibung

        Returns:
            VM-Objekt bei Erfolg
        """
        self._check_token()

        cluster_id = await self.get_or_create_cluster(cluster_name)

        async with httpx.AsyncClient() as client:
            # Pruefen ob VM bereits existiert
            check_response = await client.get(
                f"{self.base_url}/api/virtualization/virtual-machines/",
                params={"name": name},
                headers=self.headers,
                timeout=10.0,
            )
            check_response.raise_for_status()
            existing = check_response.json()

            if existing["count"] > 0:
                # VM existiert - aktualisieren
                vm_id = existing["results"][0]["id"]
                response = await client.patch(
                    f"{self.base_url}/api/virtualization/virtual-machines/{vm_id}/",
                    json={
                        "vcpus": vcpus,
                        "memory": memory_mb,
                        "disk": disk_gb,
                        "description": description,
                        "status": "active",
                    },
                    headers=self.headers,
                    timeout=10.0,
                )
            else:
                # Neue VM erstellen
                response = await client.post(
                    f"{self.base_url}/api/virtualization/virtual-machines/",
                    json={
                        "name": name,
                        "cluster": cluster_id,
                        "vcpus": vcpus,
                        "memory": memory_mb,
                        "disk": disk_gb,
                        "description": description,
                        "status": "active",
                    },
                    headers=self.headers,
                    timeout=10.0,
                )

            response.raise_for_status()
            return response.json()

    async def assign_ip_to_vm(self, vm_name: str, ip_address: str) -> bool:
        """
        Verknuepft eine IP-Adresse mit einer VM als primary_ip4.

        Args:
            vm_name: Name der VM
            ip_address: IP-Adresse (ohne CIDR)

        Returns:
            True bei Erfolg
        """
        self._check_token()

        async with httpx.AsyncClient() as client:
            # VM finden
            vm_response = await client.get(
                f"{self.base_url}/api/virtualization/virtual-machines/",
                params={"name": vm_name},
                headers=self.headers,
                timeout=10.0,
            )
            vm_response.raise_for_status()
            vm_data = vm_response.json()

            if vm_data["count"] == 0:
                return False

            vm_id = vm_data["results"][0]["id"]

            # IP finden
            ip_response = await client.get(
                f"{self.base_url}/api/ipam/ip-addresses/",
                params={"address": ip_address},
                headers=self.headers,
                timeout=10.0,
            )
            ip_response.raise_for_status()
            ip_data = ip_response.json()

            if ip_data["count"] == 0:
                return False

            ip_id = ip_data["results"][0]["id"]

            # IP mit VM verknuepfen (assigned_object)
            await client.patch(
                f"{self.base_url}/api/ipam/ip-addresses/{ip_id}/",
                json={
                    "assigned_object_type": "virtualization.virtualmachine",
                    "assigned_object_id": vm_id,
                },
                headers=self.headers,
                timeout=10.0,
            )

            # VM aktualisieren mit primary_ip4
            update_response = await client.patch(
                f"{self.base_url}/api/virtualization/virtual-machines/{vm_id}/",
                json={"primary_ip4": ip_id},
                headers=self.headers,
                timeout=10.0,
            )
            update_response.raise_for_status()

            return True

    async def create_vm_with_ip(
        self,
        name: str,
        ip_address: str,
        vcpus: int = 2,
        memory_mb: int = 4096,
        disk_gb: int = 32,
        cluster_name: str = "Proxmox",
        description: str = "",
    ) -> dict:
        """
        Erstellt ein VM-Objekt und verknuepft die IP als primary_ip4.

        Args:
            name: Name der VM
            ip_address: IP-Adresse
            vcpus: Anzahl vCPUs
            memory_mb: RAM in MB
            disk_gb: Disk-Groesse in GB
            cluster_name: Name des Clusters
            description: Beschreibung

        Returns:
            dict mit vm und ip_assigned Status
        """
        result = {
            "success": False,
            "vm": None,
            "ip_assigned": False,
            "error": None,
        }

        try:
            # VM erstellen
            vm = await self.create_vm(
                name=name,
                vcpus=vcpus,
                memory_mb=memory_mb,
                disk_gb=disk_gb,
                cluster_name=cluster_name,
                description=description,
            )
            result["vm"] = vm
            result["success"] = True

            # IP zuweisen
            ip_assigned = await self.assign_ip_to_vm(name, ip_address)
            result["ip_assigned"] = ip_assigned

        except Exception as e:
            result["error"] = str(e)

        return result

    async def delete_vm(self, name: str) -> bool:
        """
        Löscht eine VM aus NetBox (virtualization/virtual-machines).

        Args:
            name: Name der VM

        Returns:
            True bei Erfolg, False wenn VM nicht gefunden
        """
        self._check_token()

        async with httpx.AsyncClient() as client:
            # VM finden
            response = await client.get(
                f"{self.base_url}/api/virtualization/virtual-machines/",
                params={"name": name},
                headers=self.headers,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            if data["count"] == 0:
                return False

            vm_id = data["results"][0]["id"]

            # VM löschen
            delete_response = await client.delete(
                f"{self.base_url}/api/virtualization/virtual-machines/{vm_id}/",
                headers=self.headers,
                timeout=10.0,
            )
            return delete_response.status_code == 204

    async def delete_vm_and_ip(self, name: str, ip_address: str) -> dict:
        """
        Löscht eine VM und deren IP aus NetBox.

        Args:
            name: Name der VM
            ip_address: IP-Adresse der VM

        Returns:
            dict mit vm_deleted und ip_deleted Status
        """
        vm_deleted = False
        ip_deleted = False

        try:
            vm_deleted = await self.delete_vm(name)
        except Exception:
            pass

        try:
            ip_deleted = await self.release_ip(ip_address)
        except Exception:
            pass

        return {
            "vm_deleted": vm_deleted,
            "ip_deleted": ip_deleted,
        }

    async def get_all_vms(self) -> list[dict]:
        """
        Holt alle VMs aus NetBox.

        Returns:
            Liste aller VM-Objekte mit ID, Name, IP, etc.
        """
        self._check_token()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/virtualization/virtual-machines/",
                params={"limit": 1000},
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            result = []
            for vm in data.get("results", []):
                primary_ip = vm.get("primary_ip4")
                ip_address = None
                if primary_ip:
                    ip_address = primary_ip.get("address", "").split("/")[0]

                result.append({
                    "id": vm["id"],
                    "name": vm["name"],
                    "ip_address": ip_address,
                    "vcpus": vm.get("vcpus"),
                    "memory_mb": vm.get("memory"),
                    "disk_gb": vm.get("disk"),
                    "description": vm.get("description", ""),
                    "status": vm.get("status", {}).get("value", "active"),
                })

            return result

    async def delete_vm_by_id(self, vm_id: int) -> dict:
        """
        Löscht eine VM aus NetBox anhand der NetBox-ID.
        Gibt auch die verknüpfte IP-Adresse frei.

        Args:
            vm_id: NetBox-interne VM-ID

        Returns:
            dict mit deleted_vm, released_ip und success Status
        """
        self._check_token()

        result = {
            "success": False,
            "deleted_vm": None,
            "released_ip": None,
            "error": None,
        }

        async with httpx.AsyncClient() as client:
            # VM-Details holen (für Name und IP)
            vm_response = await client.get(
                f"{self.base_url}/api/virtualization/virtual-machines/{vm_id}/",
                headers=self.headers,
                timeout=10.0,
            )

            if vm_response.status_code == 404:
                result["error"] = f"VM mit ID {vm_id} nicht gefunden"
                return result

            vm_response.raise_for_status()
            vm_data = vm_response.json()
            result["deleted_vm"] = vm_data["name"]

            # Primary IP ermitteln
            primary_ip = vm_data.get("primary_ip4")
            ip_address = None
            if primary_ip:
                ip_address = primary_ip.get("address", "").split("/")[0]

            # VM löschen
            delete_response = await client.delete(
                f"{self.base_url}/api/virtualization/virtual-machines/{vm_id}/",
                headers=self.headers,
                timeout=10.0,
            )

            if delete_response.status_code != 204:
                result["error"] = f"Fehler beim Löschen: {delete_response.status_code}"
                return result

            result["success"] = True

            # IP freigeben wenn vorhanden
            if ip_address:
                try:
                    ip_released = await self.release_ip(ip_address)
                    if ip_released:
                        result["released_ip"] = ip_address
                except Exception:
                    pass  # IP-Freigabe optional

            return result

    async def sync_vm_from_proxmox(
        self,
        name: str,
        vmid: int,
        ip_address: str,
        node: str,
        vcpus: int = 2,
        memory_mb: int = 4096,
        disk_gb: int = 32,
    ) -> dict:
        """
        Synchronisiert eine VM aus Proxmox nach NetBox.
        Wrapper für create_vm_with_ip() mit spezifischer Description.

        Args:
            name: Name der VM
            vmid: Proxmox VMID
            ip_address: IP-Adresse
            node: Proxmox-Node
            vcpus: Anzahl vCPUs
            memory_mb: RAM in MB
            disk_gb: Disk-Größe in GB

        Returns:
            dict mit success, vm, ip_assigned, error
        """
        description = f"Synchronisiert aus Proxmox (VMID: {vmid}, Node: {node})"

        return await self.create_vm_with_ip(
            name=name,
            ip_address=ip_address,
            vcpus=vcpus,
            memory_mb=memory_mb,
            disk_gb=disk_gb,
            cluster_name="Proxmox",
            description=description,
        )

    async def update_vm(
        self,
        vm_id: int,
        vcpus: int,
        memory_mb: int,
        disk_gb: int,
    ) -> dict:
        """
        Aktualisiert eine existierende VM in NetBox.

        Args:
            vm_id: NetBox-interne VM-ID
            vcpus: Anzahl vCPUs
            memory_mb: RAM in MB
            disk_gb: Disk-Größe in GB

        Returns:
            dict mit success, vm_name und error
        """
        self._check_token()

        result = {
            "success": False,
            "vm_name": None,
            "error": None,
        }

        async with httpx.AsyncClient() as client:
            # VM aktualisieren
            update_data = {
                "vcpus": vcpus,
                "memory": memory_mb,
                "disk": disk_gb,
            }

            response = await client.patch(
                f"{self.base_url}/api/virtualization/virtual-machines/{vm_id}/",
                headers=self.headers,
                json=update_data,
                timeout=10.0,
            )

            if response.status_code == 404:
                result["error"] = f"VM mit ID {vm_id} nicht gefunden"
                return result

            if response.status_code not in [200, 201]:
                result["error"] = f"Fehler beim Aktualisieren: {response.status_code}"
                return result

            vm_data = response.json()
            result["success"] = True
            result["vm_name"] = vm_data.get("name")

            return result

    async def check_ipam_status(self) -> dict:
        """
        Prüft den IPAM-Status in NetBox.

        Gibt zurück ob Prefixes konfiguriert sind.
        Ohne Prefixes können keine freien IPs abgefragt werden.

        Returns:
            dict mit Status-Informationen
        """
        self._check_token()

        result = {
            "configured": False,
            "prefixes_count": 0,
            "vlans_count": 0,
            "netbox_url": self.base_url,
        }

        try:
            async with httpx.AsyncClient() as client:
                # Prefixes zählen
                response = await client.get(
                    f"{self.base_url}/api/ipam/prefixes/",
                    headers=self.headers,
                    timeout=10.0,
                )
                response.raise_for_status()
                result["prefixes_count"] = response.json()["count"]

                # VLANs zählen
                response = await client.get(
                    f"{self.base_url}/api/ipam/vlans/",
                    headers=self.headers,
                    timeout=10.0,
                )
                response.raise_for_status()
                result["vlans_count"] = response.json()["count"]

                # Konfiguriert wenn mindestens ein Prefix existiert
                result["configured"] = result["prefixes_count"] > 0

        except Exception as e:
            result["error"] = str(e)

        return result

    async def vlan_exists(self, vlan_id: int) -> bool:
        """
        Prüft ob ein VLAN mit der angegebenen ID in NetBox existiert.

        Args:
            vlan_id: VLAN-ID (vid)

        Returns:
            True wenn VLAN existiert, sonst False
        """
        self._check_token()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/ipam/vlans/",
                params={"vid": vlan_id},
                headers=self.headers,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            return data["count"] > 0

    async def create_vlan(self, vlan_id: int, name: str = None) -> Optional[dict]:
        """
        Erstellt ein VLAN in NetBox.

        Args:
            vlan_id: VLAN-ID (vid)
            name: Name des VLANs (default: VLAN{vlan_id})

        Returns:
            VLAN-Objekt bei Erfolg, None bei Fehler
        """
        self._check_token()

        if name is None:
            name = f"VLAN{vlan_id}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/ipam/vlans/",
                json={
                    "vid": vlan_id,
                    "name": name,
                    "status": "active",
                    "description": "Importiert aus Proxmox",
                },
                headers=self.headers,
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_vlan_netbox_id(self, vlan_id: int) -> Optional[int]:
        """
        Holt die NetBox-interne ID eines VLANs.

        Args:
            vlan_id: VLAN-ID (vid)

        Returns:
            NetBox ID des VLANs oder None
        """
        self._check_token()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/ipam/vlans/",
                params={"vid": vlan_id},
                headers=self.headers,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            if data["count"] > 0:
                return data["results"][0]["id"]
            return None

    async def create_prefix_for_vlan(
        self, vlan_id: int, prefix: str = None
    ) -> Optional[dict]:
        """
        Erstellt einen Prefix für ein VLAN in NetBox.

        Args:
            vlan_id: VLAN-ID (vid)
            prefix: IP-Prefix (default: 192.168.{vlan_id}.0/24)

        Returns:
            Prefix-Objekt bei Erfolg, None bei Fehler
        """
        self._check_token()

        if prefix is None:
            prefix = f"192.168.{vlan_id}.0/24"

        # NetBox-interne VLAN-ID ermitteln
        vlan_netbox_id = await self.get_vlan_netbox_id(vlan_id)
        if not vlan_netbox_id:
            raise ValueError(f"VLAN {vlan_id} nicht in NetBox gefunden")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/ipam/prefixes/",
                json={
                    "prefix": prefix,
                    "vlan": vlan_netbox_id,
                    "status": "active",
                    "is_pool": True,
                    "description": "Automatisch erstellt",
                },
                headers=self.headers,
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_prefixes_with_utilization(self) -> list[dict]:
        """
        Holt alle Prefixes aus NetBox mit Auslastungsdaten.

        Returns:
            Liste von Prefix-Objekten mit utilization
        """
        self._check_token()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/ipam/prefixes/",
                params={"limit": 100},
                headers=self.headers,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            result = []
            for prefix_info in data["results"]:
                vlan_info = prefix_info.get("vlan")
                vlan_id = vlan_info.get("vid") if vlan_info else None

                # Utilization berechnen (falls children existiert)
                utilization = 0
                children = prefix_info.get("children", 0)
                family = prefix_info.get("family", {}).get("value", 4)

                # Vereinfachte Berechnung basierend auf Prefix-Größe
                prefix_str = prefix_info.get("prefix", "")
                if "/" in prefix_str:
                    cidr = int(prefix_str.split("/")[1])
                    if family == 4:
                        total_ips = 2 ** (32 - cidr) - 2  # Netz + Broadcast abziehen
                        if total_ips > 0:
                            # Holen wir die Anzahl der verwendeten IPs
                            try:
                                ip_response = await client.get(
                                    f"{self.base_url}/api/ipam/ip-addresses/",
                                    params={"parent": prefix_str},
                                    headers=self.headers,
                                    timeout=10.0,
                                )
                                ip_response.raise_for_status()
                                used_ips = ip_response.json()["count"]
                                utilization = int((used_ips / total_ips) * 100)
                            except Exception:
                                utilization = 0

                result.append({
                    "prefix": prefix_str,
                    "vlan": vlan_id,
                    "description": prefix_info.get("description", ""),
                    "utilization": utilization,
                })

            return sorted(result, key=lambda x: x["prefix"])


# Singleton-Instanz
netbox_service = NetBoxService()
