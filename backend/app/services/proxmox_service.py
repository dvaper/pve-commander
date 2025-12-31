"""
Proxmox Service - Integration mit Proxmox VE API für VM-Status-Abfragen
"""
import asyncio
import logging
import httpx
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)


class ProxmoxService:
    """Service für Proxmox VE API Integration"""

    # Cache für Cluster-Nodes (wird dynamisch aus API geladen)
    _cluster_nodes_cache: list[str] = []
    _cluster_nodes_cache_time: float = 0
    _cache_ttl: float = 60.0  # 60 Sekunden Cache

    def __init__(self):
        # Settings werden dynamisch gelesen, nicht gecached
        # Damit funktioniert der Hot-Reload nach dem Setup-Wizard
        pass

    async def get_cluster_nodes(self, use_cache: bool = True) -> list[str]:
        """
        Holt die Liste aller Nodes im Cluster dynamisch aus der Proxmox API.

        Args:
            use_cache: Wenn True, wird gecachte Liste verwendet falls vorhanden

        Returns:
            Liste von Node-Namen (z.B. ["pve01", "pve02", "pve03"])
        """
        import time

        # Cache prüfen
        if use_cache and self._cluster_nodes_cache:
            if time.time() - self._cluster_nodes_cache_time < self._cache_ttl:
                return self._cluster_nodes_cache

        if not self.is_configured():
            logger.warning("Proxmox API nicht konfiguriert, kann Nodes nicht laden")
            return []

        try:
            resources = await self.get_cluster_resources("node")
            nodes = [
                r.get("node", "")
                for r in resources
                if r.get("type") == "node" and r.get("node")
            ]
            nodes = sorted(nodes)

            # Cache aktualisieren
            self._cluster_nodes_cache = nodes
            self._cluster_nodes_cache_time = time.time()

            logger.info(f"Cluster-Nodes geladen: {nodes}")
            return nodes

        except Exception as e:
            logger.error(f"Fehler beim Laden der Cluster-Nodes: {e}")
            # Falls Cache vorhanden, diesen als Fallback verwenden
            if self._cluster_nodes_cache:
                return self._cluster_nodes_cache
            return []

    async def validate_node_exists(self, node_name: str) -> bool:
        """Prüft ob ein Node im Cluster existiert"""
        nodes = await self.get_cluster_nodes()
        return node_name in nodes

    @property
    def host(self) -> str:
        return settings.proxmox_host

    @property
    def user(self) -> str:
        return settings.proxmox_user

    @property
    def token_id(self) -> str:
        """Vollstaendige Token-ID (user@realm!token-name)"""
        return settings.proxmox_token_id

    @property
    def token_name(self) -> str:
        return settings.proxmox_token_name

    @property
    def token_value(self) -> str:
        return settings.proxmox_token_secret

    @property
    def verify_ssl(self) -> bool:
        return settings.proxmox_verify_ssl

    @property
    def base_url(self) -> str:
        host = self.host
        # Falls host bereits eine URL ist (z.B. https://proxmox.example.com)
        if host.startswith("http://") or host.startswith("https://"):
            return f"{host.rstrip('/')}/api2/json"
        return f"https://{host}:8006/api2/json"

    def _get_headers(self) -> dict:
        """Erstellt Authorization-Header für Proxmox API"""
        if not self.token_id or not self.token_value:
            raise ValueError(
                "Proxmox API Token nicht konfiguriert "
                "(PROXMOX_TOKEN_ID und PROXMOX_TOKEN_SECRET)"
            )
        # Token-ID enthaelt bereits user@realm!token-name
        return {
            "Authorization": f"PVEAPIToken={self.token_id}={self.token_value}",
        }

    def is_configured(self) -> bool:
        """Prüft ob Proxmox API konfiguriert ist"""
        return bool(self.token_id and self.token_value)

    async def check_vm_exists(self, vmid: int, node: Optional[str] = None) -> dict:
        """
        Prüft ob eine VM mit der gegebenen VMID existiert.

        Returns:
            dict mit:
            - exists: bool - VM existiert
            - node: str - Auf welchem Node die VM läuft
            - status: str - VM-Status (running, stopped, etc.)
            - name: str - VM-Name
            - error: str - Fehlermeldung falls Prüfung fehlschlägt
        """
        if not self.is_configured():
            return {
                "exists": None,
                "error": "Proxmox API nicht konfiguriert",
                "configured": False,
            }

        try:
            headers = self._get_headers()

            # Wenn Node bekannt, direkt dort suchen - sonst alle Cluster-Nodes
            if node:
                nodes_to_check = [node]
            else:
                nodes_to_check = await self.get_cluster_nodes()

            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                for check_node in nodes_to_check:
                    try:
                        # VM-Status abfragen
                        response = await client.get(
                            f"{self.base_url}/nodes/{check_node}/qemu/{vmid}/status/current",
                            headers=headers,
                            timeout=5.0,
                        )

                        if response.status_code == 200:
                            data = response.json()["data"]
                            return {
                                "exists": True,
                                "configured": True,
                                "node": check_node,
                                "status": data.get("status", "unknown"),
                                "name": data.get("name", ""),
                                "vmid": vmid,
                            }
                        elif response.status_code == 500:
                            # VM nicht auf diesem Node, weiter suchen
                            continue
                    except httpx.TimeoutException:
                        continue
                    except Exception:
                        continue

                # VM auf keinem Node gefunden
                return {
                    "exists": False,
                    "configured": True,
                    "vmid": vmid,
                }

        except Exception as e:
            return {
                "exists": None,
                "configured": True,
                "error": str(e),
            }

    async def get_cluster_resources(self, resource_type: str = "vm") -> list[dict]:
        """
        Holt alle Ressourcen eines Typs aus dem Cluster.

        Args:
            resource_type: "vm", "storage", "node", etc.

        Retry-Logik: 3 Versuche mit exponential backoff (1s, 2s, 4s)
        um transiente Fehler nach Cluster-Neustart abzufangen.
        """
        import asyncio
        import logging

        logger = logging.getLogger(__name__)

        if not self.is_configured():
            return []

        max_retries = 3
        retry_delays = [1, 2, 4]  # Sekunden

        for attempt in range(max_retries):
            try:
                headers = self._get_headers()

                async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                    response = await client.get(
                        f"{self.base_url}/cluster/resources",
                        params={"type": resource_type},
                        headers=headers,
                        timeout=10.0,
                    )
                    response.raise_for_status()
                    return response.json().get("data", [])

            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    logger.warning(
                        f"Proxmox API returned {e.response.status_code}, "
                        f"retry {attempt + 1}/{max_retries} in {delay}s"
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.error(f"Proxmox API error: {e.response.status_code}")
                return []

            except Exception as e:
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    logger.warning(
                        f"Proxmox API request failed: {e}, "
                        f"retry {attempt + 1}/{max_retries} in {delay}s"
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.error(f"Proxmox API request failed after {max_retries} attempts: {e}")
                return []

        return []

    async def get_all_vms(self) -> list[dict]:
        """Holt alle VMs aus dem Cluster"""
        resources = await self.get_cluster_resources("vm")
        return [
            {
                "vmid": r.get("vmid"),
                "name": r.get("name"),
                "node": r.get("node"),
                "status": r.get("status"),
                "type": r.get("type"),  # qemu oder lxc
                "maxcpu": r.get("maxcpu", 1),
                "maxmem": r.get("maxmem", 0),
                "maxdisk": r.get("maxdisk", 0),
            }
            for r in resources
            if r.get("type") == "qemu"
        ]

    async def get_vm_config(self, vmid: int, node: str) -> dict:
        """
        Holt die vollständige Konfiguration einer VM.

        Returns:
            dict mit:
            - success: bool
            - config: dict mit VM-Konfiguration
            - error: str bei Fehlern
        """
        if not self.is_configured():
            return {"success": False, "error": "Proxmox API nicht konfiguriert"}

        try:
            headers = self._get_headers()

            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(
                    f"{self.base_url}/nodes/{node}/qemu/{vmid}/config",
                    headers=headers,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json().get("data", {})
                    return {
                        "success": True,
                        "config": data,
                        "vmid": vmid,
                        "node": node,
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}",
                    }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_vm_agent_network(self, vmid: int, node: str) -> dict:
        """
        Holt Netzwerk-Informationen via QEMU Guest Agent.

        Funktioniert nur bei laufenden VMs mit installiertem Guest Agent.

        Returns:
            dict mit:
            - success: bool
            - interfaces: Liste der Netzwerk-Interfaces mit IPs
            - primary_ip: Erste nicht-localhost IPv4-Adresse
            - error: str bei Fehlern
        """
        if not self.is_configured():
            return {"success": False, "error": "Proxmox API nicht konfiguriert"}

        try:
            headers = self._get_headers()

            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(
                    f"{self.base_url}/nodes/{node}/qemu/{vmid}/agent/network-get-interfaces",
                    headers=headers,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json().get("data", {})
                    result = data.get("result", [])

                    interfaces = []
                    primary_ip = None

                    for iface in result:
                        iface_name = iface.get("name", "")
                        # Loopback und Docker-Interfaces überspringen
                        if iface_name in ("lo", "docker0") or iface_name.startswith("veth"):
                            continue

                        ip_addresses = iface.get("ip-addresses", [])
                        ipv4_addrs = []
                        for ip in ip_addresses:
                            if ip.get("ip-address-type") == "ipv4":
                                addr = ip.get("ip-address")
                                if addr and not addr.startswith("127."):
                                    ipv4_addrs.append(addr)
                                    if primary_ip is None:
                                        primary_ip = addr

                        if ipv4_addrs:
                            interfaces.append({
                                "name": iface_name,
                                "ipv4": ipv4_addrs,
                                "mac": iface.get("hardware-address", ""),
                            })

                    return {
                        "success": True,
                        "interfaces": interfaces,
                        "primary_ip": primary_ip,
                        "vmid": vmid,
                        "node": node,
                    }
                elif response.status_code == 500:
                    # Guest Agent nicht verfügbar oder VM nicht laufend
                    return {
                        "success": False,
                        "error": "Guest Agent nicht verfügbar",
                        "agent_available": False,
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}",
                    }

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== VM Power Control ==========

    async def _vm_power_action(self, vmid: int, node: str, action: str) -> dict:
        """
        Führt eine Power-Aktion auf einer VM aus.

        Args:
            vmid: VM-ID
            node: Proxmox-Node
            action: start, stop, shutdown, reboot, reset

        Returns:
            dict mit upid (Task-ID) oder error
        """
        if not self.is_configured():
            return {"success": False, "error": "Proxmox API nicht konfiguriert"}

        try:
            headers = self._get_headers()

            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.post(
                    f"{self.base_url}/nodes/{node}/qemu/{vmid}/status/{action}",
                    headers=headers,
                    timeout=30.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "upid": data.get("data"),
                        "vmid": vmid,
                        "node": node,
                        "action": action,
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}",
                        "vmid": vmid,
                    }

        except Exception as e:
            return {"success": False, "error": str(e), "vmid": vmid}

    async def start_vm(self, vmid: int, node: str) -> dict:
        """Startet eine VM"""
        return await self._vm_power_action(vmid, node, "start")

    async def stop_vm(self, vmid: int, node: str) -> dict:
        """Stoppt eine VM sofort (force)"""
        return await self._vm_power_action(vmid, node, "stop")

    async def shutdown_vm(self, vmid: int, node: str) -> dict:
        """Fährt eine VM sauber herunter (ACPI shutdown)"""
        return await self._vm_power_action(vmid, node, "shutdown")

    async def reboot_vm(self, vmid: int, node: str) -> dict:
        """Startet eine VM neu (ACPI reboot)"""
        return await self._vm_power_action(vmid, node, "reboot")

    async def reset_vm(self, vmid: int, node: str) -> dict:
        """Hard-Reset einer VM"""
        return await self._vm_power_action(vmid, node, "reset")

    # ========== Templates ==========

    async def get_templates(self) -> list[dict]:
        """
        Holt alle VM-Templates aus dem Cluster.
        Templates haben VMID >= 900000 und template=1
        """
        if not self.is_configured():
            return []

        try:
            resources = await self.get_cluster_resources("vm")
            templates = []

            for r in resources:
                vmid = r.get("vmid", 0)
                # Templates haben VMID >= 900000 oder template flag
                if vmid >= 900000 or r.get("template"):
                    templates.append({
                        "vmid": vmid,
                        "name": r.get("name", ""),
                        "node": r.get("node", ""),
                        "status": r.get("status", "stopped"),
                        "maxdisk": r.get("maxdisk", 0),
                        "maxmem": r.get("maxmem", 0),
                    })

            return sorted(templates, key=lambda x: x["vmid"])

        except Exception:
            return []

    # ========== Storage ==========

    async def get_storage_pools(self, node: Optional[str] = None) -> list[dict]:
        """
        Holt verfügbare Storage-Pools.

        Args:
            node: Optionaler Node-Filter
        """
        if not self.is_configured():
            return []

        try:
            resources = await self.get_cluster_resources("storage")
            storages = []

            for r in resources:
                # Content muss 'images' enthalten für VM-Disks
                content = r.get("content", "")
                if "images" not in content:
                    continue

                # Optional nach Node filtern
                if node and r.get("node") != node:
                    continue

                storages.append({
                    "id": r.get("storage", ""),
                    "node": r.get("node", ""),
                    "type": r.get("plugintype", ""),
                    "status": r.get("status", "unknown"),
                    "total": r.get("maxdisk", 0),
                    "used": r.get("disk", 0),
                    "available": r.get("maxdisk", 0) - r.get("disk", 0),
                    "content": content.split(",") if content else [],
                })

            return storages

        except Exception:
            return []

    # ========== Cluster Stats ==========

    async def get_node_stats(self) -> list[dict]:
        """Holt CPU/RAM-Statistiken für alle Nodes"""
        if not self.is_configured():
            return []

        try:
            resources = await self.get_cluster_resources("node")
            nodes = []

            for r in resources:
                if r.get("type") != "node":
                    continue

                maxcpu = r.get("maxcpu", 1)
                maxmem = r.get("maxmem", 1)

                nodes.append({
                    "name": r.get("node", ""),
                    "status": r.get("status", "unknown"),
                    # Proxmox gibt CPU als 0-1 zurueck, wir brauchen 0-100%
                    "cpu_usage": r.get("cpu", 0) * 100,
                    "cpu_total": maxcpu,
                    "memory_used": r.get("mem", 0),
                    "memory_total": maxmem,
                    "memory_percent": (r.get("mem", 0) / maxmem * 100) if maxmem > 0 else 0,
                    "uptime": r.get("uptime", 0),
                })

            return sorted(nodes, key=lambda x: x["name"])

        except Exception:
            return []

    async def get_cluster_stats(self) -> dict:
        """Holt aggregierte Cluster-Statistiken"""
        nodes = await self.get_node_stats()
        vms = await self.get_all_vms()

        total_cpu = sum(n["cpu_total"] for n in nodes)
        total_memory = sum(n["memory_total"] for n in nodes)
        used_memory = sum(n["memory_used"] for n in nodes)
        avg_cpu_usage = sum(n["cpu_usage"] for n in nodes) / len(nodes) if nodes else 0

        running_vms = len([v for v in vms if v.get("status") == "running"])

        return {
            "nodes_online": len([n for n in nodes if n["status"] == "online"]),
            "nodes_total": len(nodes),
            "cpu_total": total_cpu,
            "cpu_usage_avg": avg_cpu_usage,
            "memory_total": total_memory,
            "memory_used": used_memory,
            "memory_percent": (used_memory / total_memory * 100) if total_memory > 0 else 0,
            "vms_running": running_vms,
            "vms_total": len(vms),
            "nodes": nodes,
        }

    # ========== VM Cloning ==========

    async def clone_vm(
        self,
        source_vmid: int,
        target_vmid: int,
        target_name: str,
        node: str,
        full_clone: bool = True,
        target_storage: Optional[str] = None,
    ) -> dict:
        """Klont eine VM"""
        if not self.is_configured():
            return {"success": False, "error": "Proxmox API nicht konfiguriert"}

        try:
            headers = self._get_headers()
            data = {
                "newid": target_vmid,
                "name": target_name,
                "full": 1 if full_clone else 0,
            }
            if target_storage:
                data["storage"] = target_storage

            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.post(
                    f"{self.base_url}/nodes/{node}/qemu/{source_vmid}/clone",
                    headers=headers,
                    data=data,
                    timeout=60.0,
                )

                if response.status_code == 200:
                    return {"success": True, "task": response.json().get("data"), "message": "Clone-Task gestartet"}
                else:
                    return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Snapshot Management ==========

    async def list_snapshots(self, vmid: int, node: str) -> list[dict]:
        """Listet alle Snapshots einer VM"""
        if not self.is_configured():
            return []

        try:
            headers = self._get_headers()
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(
                    f"{self.base_url}/nodes/{node}/qemu/{vmid}/snapshot",
                    headers=headers,
                    timeout=30.0,
                )

                if response.status_code == 200:
                    data = response.json().get("data", [])
                    return [
                        {
                            "name": snap.get("name"),
                            "description": snap.get("description", ""),
                            "snaptime": snap.get("snaptime"),
                            "parent": snap.get("parent"),
                            "vmstate": snap.get("vmstate", False),
                        }
                        for snap in data
                        if snap.get("name") != "current"
                    ]
                return []
        except Exception as e:
            print(f"Fehler beim Laden der Snapshots: {e}")
            return []

    async def create_snapshot(
        self,
        vmid: int,
        node: str,
        name: str,
        description: str = "",
        include_ram: bool = False,
    ) -> dict:
        """Erstellt einen Snapshot einer VM"""
        if not self.is_configured():
            return {"success": False, "error": "Proxmox API nicht konfiguriert"}

        try:
            headers = self._get_headers()
            data = {"snapname": name}
            if description:
                data["description"] = description
            if include_ram:
                data["vmstate"] = 1

            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.post(
                    f"{self.base_url}/nodes/{node}/qemu/{vmid}/snapshot",
                    headers=headers,
                    data=data,
                    timeout=30.0,
                )

                if response.status_code == 200:
                    return {"success": True, "task": response.json().get("data")}
                else:
                    # Versuche Proxmox-Fehlermeldung zu extrahieren
                    error_msg = f"HTTP {response.status_code}"
                    try:
                        error_data = response.json()
                        if "errors" in error_data:
                            errors = error_data["errors"]
                            if isinstance(errors, dict):
                                error_msg = ", ".join(str(v) for v in errors.values())
                            else:
                                error_msg = str(errors)
                        elif "message" in error_data:
                            error_msg = error_data["message"]
                    except Exception:
                        error_msg = response.text or error_msg
                    return {"success": False, "error": error_msg}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def delete_snapshot(self, vmid: int, node: str, name: str) -> dict:
        """Löscht einen Snapshot"""
        if not self.is_configured():
            return {"success": False, "error": "Proxmox API nicht konfiguriert"}

        try:
            headers = self._get_headers()
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.delete(
                    f"{self.base_url}/nodes/{node}/qemu/{vmid}/snapshot/{name}",
                    headers=headers,
                    timeout=30.0,
                )

                if response.status_code == 200:
                    return {"success": True, "task": response.json().get("data")}
                else:
                    return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def rollback_snapshot(self, vmid: int, node: str, name: str) -> dict:
        """Rollt eine VM auf einen Snapshot zurück"""
        if not self.is_configured():
            return {"success": False, "error": "Proxmox API nicht konfiguriert"}

        try:
            headers = self._get_headers()
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.post(
                    f"{self.base_url}/nodes/{node}/qemu/{vmid}/snapshot/{name}/rollback",
                    headers=headers,
                    timeout=60.0,
                )

                if response.status_code == 200:
                    return {"success": True, "task": response.json().get("data")}
                else:
                    return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== VM Deletion ==========

    async def delete_vm(self, vmid: int, node: str, purge: bool = True) -> dict:
        """
        Löscht eine VM aus Proxmox.

        Args:
            vmid: VM-ID
            node: Proxmox-Node
            purge: Auch Disks löschen (Standard: True)

        Returns:
            dict mit success, task oder error
        """
        if not self.is_configured():
            return {"success": False, "error": "Proxmox API nicht konfiguriert"}

        try:
            headers = self._get_headers()

            # VM muss gestoppt sein
            vm_status = await self.check_vm_exists(vmid, node)
            if vm_status.get("status") == "running":
                # Erst stoppen
                stop_result = await self.stop_vm(vmid, node)
                if not stop_result.get("success"):
                    return {"success": False, "error": f"Konnte VM nicht stoppen: {stop_result.get('error')}"}
                # Kurz warten bis VM gestoppt ist
                import asyncio
                await asyncio.sleep(3)

            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                params = {}
                if purge:
                    params["purge"] = 1
                    params["destroy-unreferenced-disks"] = 1

                response = await client.delete(
                    f"{self.base_url}/nodes/{node}/qemu/{vmid}",
                    headers=headers,
                    params=params,
                    timeout=60.0,
                )

                if response.status_code == 200:
                    return {
                        "success": True,
                        "task": response.json().get("data"),
                        "vmid": vmid,
                        "node": node,
                    }
                else:
                    return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== VM Migration ==========

    async def wait_for_task(
        self,
        node: str,
        upid: str,
        timeout: int = 300,
        poll_interval: int = 5,
    ) -> dict:
        """
        Wartet auf den Abschluss eines Proxmox-Tasks.

        Args:
            node: Proxmox-Node auf dem der Task läuft
            upid: Task-ID (UPID)
            timeout: Maximale Wartezeit in Sekunden
            poll_interval: Abfrageintervall in Sekunden

        Returns:
            dict mit success, status, exitstatus oder error
        """
        if not self.is_configured():
            return {"success": False, "error": "Proxmox API nicht konfiguriert"}

        headers = self._get_headers()
        elapsed = 0
        consecutive_errors = 0
        max_consecutive_errors = 5

        while elapsed < timeout:
            try:
                # Neuer Client pro Request für mehr Stabilität bei langen Tasks
                async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                    response = await client.get(
                        f"{self.base_url}/nodes/{node}/tasks/{upid}/status",
                        headers=headers,
                        timeout=30.0,
                    )

                    if response.status_code == 200:
                        consecutive_errors = 0  # Reset error counter
                        data = response.json().get("data", {})
                        status = data.get("status")

                        if status == "stopped":
                            exitstatus = data.get("exitstatus", "")
                            if exitstatus == "OK":
                                return {
                                    "success": True,
                                    "status": "completed",
                                    "exitstatus": exitstatus,
                                }
                            else:
                                return {
                                    "success": False,
                                    "status": "failed",
                                    "exitstatus": exitstatus,
                                    "error": f"Task fehlgeschlagen: {exitstatus}",
                                }
                        # Task läuft noch - weiter warten
                    else:
                        consecutive_errors += 1
                        print(f"Task-Status HTTP {response.status_code} (Versuch {consecutive_errors})")

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                consecutive_errors += 1
                print(f"Task-Status Fehler: {e} (Versuch {consecutive_errors})")

            except Exception as e:
                consecutive_errors += 1
                print(f"Task-Status unerwarteter Fehler: {e} (Versuch {consecutive_errors})")

            # Zu viele aufeinanderfolgende Fehler
            if consecutive_errors >= max_consecutive_errors:
                return {
                    "success": False,
                    "error": f"Zu viele Fehler beim Abfragen des Task-Status ({consecutive_errors})",
                }

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        return {"success": False, "error": f"Timeout nach {timeout} Sekunden"}

    async def get_task_status(self, node: str, upid: str) -> dict:
        """
        Holt den aktuellen Status eines Proxmox-Tasks mit Fortschritt.

        Returns:
            dict mit status, progress (0-100), message, finished
        """
        if not self.is_configured():
            return {"success": False, "error": "Proxmox API nicht konfiguriert"}

        try:
            headers = self._get_headers()
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(
                    f"{self.base_url}/nodes/{node}/tasks/{upid}/status",
                    headers=headers,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json().get("data", {})
                    status = data.get("status", "unknown")
                    exitstatus = data.get("exitstatus", "")

                    # Task abgeschlossen?
                    finished = status == "stopped"
                    success = finished and exitstatus == "OK"

                    return {
                        "success": True,
                        "status": status,
                        "exitstatus": exitstatus,
                        "finished": finished,
                        "task_success": success,
                        "node": data.get("node", node),
                        "type": data.get("type", ""),
                        "starttime": data.get("starttime"),
                        "pid": data.get("pid"),
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}",
                    }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def start_migration(
        self,
        vmid: int,
        source_node: str,
        target_node: str,
    ) -> dict:
        """
        Startet eine VM-Migration und gibt sofort die UPID zurück (non-blocking).

        Die VM wird vorher gestoppt falls sie läuft.

        Returns:
            dict mit success, upid, was_running, source_node, target_node
        """
        if not self.is_configured():
            return {"success": False, "error": "Proxmox API nicht konfiguriert"}

        if source_node == target_node:
            return {"success": False, "error": "Quell- und Ziel-Node sind identisch"}

        # Node-Existenz dynamisch prüfen
        if not await self.validate_node_exists(target_node):
            cluster_nodes = await self.get_cluster_nodes()
            return {
                "success": False,
                "error": f"Unbekannter Ziel-Node: {target_node}. Verfügbare Nodes: {', '.join(cluster_nodes)}"
            }

        try:
            headers = self._get_headers()

            # 1. VM-Status prüfen
            vm_status = await self.check_vm_exists(vmid, source_node)
            if not vm_status.get("exists"):
                return {"success": False, "error": f"VM {vmid} nicht auf {source_node} gefunden"}

            was_running = vm_status.get("status") == "running"

            # 2. VM stoppen falls sie läuft
            if was_running:
                stop_result = await self.shutdown_vm(vmid, source_node)
                if not stop_result.get("success"):
                    return {
                        "success": False,
                        "error": f"Konnte VM nicht stoppen: {stop_result.get('error')}",
                    }
                # Warten bis VM gestoppt ist (max 60 Sekunden)
                for _ in range(30):
                    await asyncio.sleep(2)
                    status = await self.check_vm_exists(vmid, source_node)
                    if status.get("status") == "stopped":
                        break
                else:
                    return {"success": False, "error": "Timeout beim Warten auf VM-Stopp"}

            # 3. Migration starten (non-blocking)
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.post(
                    f"{self.base_url}/nodes/{source_node}/qemu/{vmid}/migrate",
                    headers=headers,
                    data={
                        "target": target_node,
                        "online": 0,
                        "with-local-disks": 1,
                    },
                    timeout=60.0,
                )

                if response.status_code != 200:
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    if was_running:
                        await self.start_vm(vmid, source_node)
                    return {"success": False, "error": error_msg}

                upid = response.json().get("data")

            return {
                "success": True,
                "upid": upid,
                "was_running": was_running,
                "source_node": source_node,
                "target_node": target_node,
                "vmid": vmid,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def migrate_vm(
        self,
        vmid: int,
        source_node: str,
        target_node: str,
        restart_after: bool = True,
    ) -> dict:
        """
        Migriert eine VM offline auf einen anderen Node.

        Die VM wird gestoppt (falls running), migriert und optional wieder gestartet.

        Args:
            vmid: VM-ID
            source_node: Aktueller Node
            target_node: Ziel-Node
            restart_after: VM nach Migration wieder starten (wenn sie vorher lief)

        Returns:
            dict mit success, source_node, target_node, upid oder error
        """
        if not self.is_configured():
            return {"success": False, "error": "Proxmox API nicht konfiguriert"}

        if source_node == target_node:
            return {"success": False, "error": "Quell- und Ziel-Node sind identisch"}

        # Node-Existenz dynamisch prüfen
        if not await self.validate_node_exists(target_node):
            cluster_nodes = await self.get_cluster_nodes()
            return {
                "success": False,
                "error": f"Unbekannter Ziel-Node: {target_node}. Verfügbare Nodes: {', '.join(cluster_nodes)}"
            }

        try:
            headers = self._get_headers()

            # 1. VM-Status prüfen
            vm_status = await self.check_vm_exists(vmid, source_node)
            if not vm_status.get("exists"):
                return {"success": False, "error": f"VM {vmid} nicht auf {source_node} gefunden"}

            was_running = vm_status.get("status") == "running"

            # 2. VM stoppen falls sie läuft
            if was_running:
                stop_result = await self.shutdown_vm(vmid, source_node)
                if not stop_result.get("success"):
                    return {
                        "success": False,
                        "error": f"Konnte VM nicht stoppen: {stop_result.get('error')}",
                    }
                # Warten bis VM gestoppt ist
                for _ in range(30):  # Max 60 Sekunden warten
                    await asyncio.sleep(2)
                    status = await self.check_vm_exists(vmid, source_node)
                    if status.get("status") == "stopped":
                        break
                else:
                    return {"success": False, "error": "Timeout beim Warten auf VM-Stopp"}

            # 3. Migration starten
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.post(
                    f"{self.base_url}/nodes/{source_node}/qemu/{vmid}/migrate",
                    headers=headers,
                    data={
                        "target": target_node,
                        "online": 0,  # Offline-Migration
                        "with-local-disks": 1,  # Lokale Disks mitnehmen
                    },
                    timeout=60.0,
                )

                if response.status_code != 200:
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    # Falls VM gestoppt wurde, wieder starten
                    if was_running:
                        await self.start_vm(vmid, source_node)
                    return {"success": False, "error": error_msg}

                upid = response.json().get("data")

            # 4. Auf Migration warten (15 Minuten Timeout für große VMs)
            wait_result = await self.wait_for_task(source_node, upid, timeout=900)
            if not wait_result.get("success"):
                # Bei Fehler: VM auf Source-Node wieder starten falls sie lief
                if was_running:
                    await self.start_vm(vmid, source_node)
                return {
                    "success": False,
                    "error": f"Migration fehlgeschlagen: {wait_result.get('error')}",
                    "upid": upid,
                }

            # 5. VM auf Ziel-Node starten (falls sie vorher lief)
            if was_running and restart_after:
                await asyncio.sleep(2)  # Kurz warten
                start_result = await self.start_vm(vmid, target_node)
                if not start_result.get("success"):
                    return {
                        "success": True,  # Migration war erfolgreich
                        "warning": f"VM konnte nicht gestartet werden: {start_result.get('error')}",
                        "source_node": source_node,
                        "target_node": target_node,
                        "upid": upid,
                        "was_running": was_running,
                    }

            return {
                "success": True,
                "message": "Migration erfolgreich",
                "source_node": source_node,
                "target_node": target_node,
                "upid": upid,
                "was_running": was_running,
                "restarted": was_running and restart_after,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Network/VLAN Scan ==========

    async def scan_network_vlans(self) -> list[dict]:
        """
        Scannt alle Proxmox-Nodes nach VLAN-Konfigurationen.

        Findet VLANs durch:
        1. Bridge-Namen (vmbr60 -> VLAN 60)
        2. VLAN-Tags in VM-Konfigurationen (net0: ...,tag=100)

        Returns:
            Liste von dicts mit:
            - vlan_id: int
            - bridge: str
            - nodes: list[str]
            - vm_count: int
        """
        import re

        if not self.is_configured():
            return []

        vlans = {}  # vlan_id -> {bridge, nodes, vm_count}

        try:
            headers = self._get_headers()

            # Cluster-Nodes dynamisch laden
            cluster_nodes = await self.get_cluster_nodes()

            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                # 1. Alle Nodes durchgehen und Bridges scannen
                for node in cluster_nodes:
                    try:
                        response = await client.get(
                            f"{self.base_url}/nodes/{node}/network",
                            headers=headers,
                            timeout=10.0,
                        )

                        if response.status_code == 200:
                            networks = response.json().get("data", [])

                            for net in networks:
                                iface = net.get("iface", "")
                                net_type = net.get("type", "")

                                # Bridge mit VLAN-Nummer? (vmbr60, vmbr99, etc.)
                                if net_type == "bridge" and iface.startswith("vmbr"):
                                    match = re.match(r"vmbr(\d+)", iface)
                                    if match:
                                        vlan_id = int(match.group(1))
                                        # vmbr0 ist Standard-Bridge, keine VLAN
                                        if vlan_id == 0:
                                            continue

                                        if vlan_id not in vlans:
                                            vlans[vlan_id] = {
                                                "vlan_id": vlan_id,
                                                "bridge": iface,
                                                "nodes": [],
                                                "vm_count": 0,
                                            }

                                        if node not in vlans[vlan_id]["nodes"]:
                                            vlans[vlan_id]["nodes"].append(node)

                    except Exception as e:
                        print(f"Fehler beim Scannen von Node {node}: {e}")
                        continue

                # 2. VMs scannen fuer VLAN-Tags und VM-Count
                all_vms = await self.get_all_vms()

                for vm in all_vms:
                    vmid = vm.get("vmid")
                    node = vm.get("node")

                    if not vmid or not node:
                        continue

                    try:
                        config_result = await self.get_vm_config(vmid, node)
                        if not config_result.get("success"):
                            continue

                        config = config_result.get("config", {})

                        # Alle net* Eintraege durchgehen
                        for key, value in config.items():
                            if not key.startswith("net") or not isinstance(value, str):
                                continue

                            # Bridge extrahieren (bridge=vmbr60)
                            bridge_match = re.search(r"bridge=(vmbr\d+)", value)
                            if bridge_match:
                                bridge = bridge_match.group(1)
                                vlan_match = re.match(r"vmbr(\d+)", bridge)
                                if vlan_match:
                                    vlan_id = int(vlan_match.group(1))
                                    if vlan_id > 0:
                                        if vlan_id in vlans:
                                            vlans[vlan_id]["vm_count"] += 1

                            # VLAN-Tag extrahieren (tag=100)
                            tag_match = re.search(r"tag=(\d+)", value)
                            if tag_match:
                                vlan_id = int(tag_match.group(1))
                                if vlan_id > 0:
                                    if vlan_id not in vlans:
                                        # VLAN nur durch Tag bekannt, Bridge ist vmbr0
                                        vlans[vlan_id] = {
                                            "vlan_id": vlan_id,
                                            "bridge": "vmbr0 (tagged)",
                                            "nodes": [node] if node else [],
                                            "vm_count": 1,
                                        }
                                    else:
                                        vlans[vlan_id]["vm_count"] += 1
                                        if node and node not in vlans[vlan_id]["nodes"]:
                                            vlans[vlan_id]["nodes"].append(node)

                    except Exception as e:
                        print(f"Fehler beim Scannen von VM {vmid}: {e}")
                        continue

            return sorted(vlans.values(), key=lambda x: x["vlan_id"])

        except Exception as e:
            print(f"Fehler beim VLAN-Scan: {e}")
            return []

    async def scan_vm_ips(self) -> list[dict]:
        """
        Scannt alle Proxmox-VMs nach IP-Adressen.

        Versucht IPs zu ermitteln via:
        1. QEMU Guest Agent (genaueste Methode)
        2. Cloud-Init Konfiguration (Fallback)

        Returns:
            Liste von dicts mit:
            - vmid: int
            - name: str
            - node: str
            - ip: str
            - source: str ('guest-agent' | 'cloud-init' | 'unknown')
        """
        import re

        if not self.is_configured():
            return []

        results = []

        try:
            all_vms = await self.get_all_vms()

            for vm in all_vms:
                vmid = vm.get("vmid")
                name = vm.get("name", f"VM-{vmid}")
                node = vm.get("node")
                status = vm.get("status")

                if not vmid or not node:
                    continue

                ip = None
                source = "unknown"

                # 1. Versuche QEMU Guest Agent (nur wenn VM laeuft)
                if status == "running":
                    try:
                        ip, source = await self._get_ip_from_guest_agent(vmid, node)
                    except Exception:
                        pass

                # 2. Fallback: Cloud-Init Config
                if not ip:
                    try:
                        ip, source = await self._get_ip_from_config(vmid, node)
                    except Exception:
                        pass

                if ip:
                    results.append({
                        "vmid": vmid,
                        "name": name,
                        "node": node,
                        "ip": ip,
                        "status": status,
                        "source": source,
                        "cpus": vm.get("maxcpu", 0),
                        "maxmem": vm.get("maxmem", 0),
                        "maxdisk": vm.get("maxdisk", 0),
                    })

            return sorted(results, key=lambda x: x["vmid"])

        except Exception as e:
            print(f"Fehler beim VM-IP-Scan: {e}")
            return []

    async def _get_ip_from_guest_agent(
        self, vmid: int, node: str
    ) -> tuple[Optional[str], str]:
        """
        Holt IP-Adresse via QEMU Guest Agent.

        Returns:
            Tuple (ip, source) oder (None, 'unknown')
        """
        import re

        headers = self._get_headers()

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.get(
                f"{self.base_url}/nodes/{node}/qemu/{vmid}/agent/network-get-interfaces",
                headers=headers,
                timeout=5.0,
            )

            if response.status_code != 200:
                return None, "unknown"

            data = response.json().get("data", {})
            result = data.get("result", [])

            # Suche nach nicht-localhost IPv4-Adresse
            for iface in result:
                iface_name = iface.get("name", "")
                # Ignoriere loopback
                if iface_name == "lo":
                    continue

                ip_addresses = iface.get("ip-addresses", [])
                for ip_info in ip_addresses:
                    ip_type = ip_info.get("ip-address-type", "")
                    ip_addr = ip_info.get("ip-address", "")

                    # Nur IPv4, keine Link-Local
                    if ip_type == "ipv4" and not ip_addr.startswith("127."):
                        return ip_addr, "guest-agent"

        return None, "unknown"

    async def _get_ip_from_config(
        self, vmid: int, node: str
    ) -> tuple[Optional[str], str]:
        """
        Holt IP-Adresse aus VM-Config (Cloud-Init ipconfig).

        Returns:
            Tuple (ip, source) oder (None, 'unknown')
        """
        import re

        config_result = await self.get_vm_config(vmid, node)
        if not config_result.get("success"):
            return None, "unknown"

        config = config_result.get("config", {})

        # Suche nach ipconfig0, ipconfig1, etc.
        for key, value in config.items():
            if not key.startswith("ipconfig") or not isinstance(value, str):
                continue

            # Format: ip=10.0.0.101/24,gw=10.0.0.1
            ip_match = re.search(r"ip=(\d+\.\d+\.\d+\.\d+)", value)
            if ip_match:
                return ip_match.group(1), "cloud-init"

        return None, "unknown"


# Singleton-Instanz
proxmox_service = ProxmoxService()


def get_proxmox_service() -> ProxmoxService:
    """Gibt die Singleton-Instanz des ProxmoxService zurueck."""
    return proxmox_service
