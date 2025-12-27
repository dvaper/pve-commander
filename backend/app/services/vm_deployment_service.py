"""
VM Deployment Service - Erstellt und verwaltet VM-Konfigurationen via Terraform
"""
import re
from pathlib import Path
from typing import Optional
from datetime import datetime

from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models.execution import Execution
from app.schemas.vm import (
    VMConfigCreate,
    VMConfigResponse,
    VMConfigListItem,
    VMStatus,
    VMValidationResult,
    TerraformPreview,
    calculate_vmid,
)
from app.services.netbox_service import netbox_service
from app.services.terraform_service import TerraformService
from app.services.ansible_inventory_service import ansible_inventory_service
from app.services.proxmox_service import proxmox_service
from app.services.vm_history_service import vm_history_service
from app.services.cloud_init_service import cloud_init_service
from app.services.notification_service import NotificationService
from app.schemas.cloud_init import CloudInitProfile


class VMDeploymentService:
    """Service für VM-Deployment via Terraform"""

    def __init__(self):
        self.terraform_dir = Path(settings.terraform_dir)
        self.terraform_service = TerraformService()

    def get_bridge_for_vlan(self, vlan: int) -> str:
        """
        Gibt die Bridge für ein VLAN zurück.

        Konvention: vmbr{vlan_id}
        """
        return f"vmbr{vlan}"

    def get_gateway_for_vlan(self, vlan: int) -> str:
        """
        Gibt das Gateway für ein VLAN zurück.

        Konvention: 192.168.{vlan_id}.1
        """
        return f"192.168.{vlan}.1"

    @property
    def vms_dir(self) -> Path:
        """VM TF-Dateien liegen im Hauptverzeichnis mit vm_ Prefix"""
        return self.terraform_dir

    def _sanitize_module_name(self, name: str) -> str:
        """Konvertiert VM-Name zu gültigem Terraform-Modul-Namen"""
        # Bindestriche durch Unterstriche ersetzen
        return name.replace("-", "_")

    def generate_tf_content(
        self,
        name: str,
        vmid: int,
        ip_address: str,
        target_node: str,
        description: str,
        cores: int,
        memory_gb: int,
        disk_size_gb: int,
        vlan: int = 60,
        ansible_group: str = "",
        template_id: int = None,
        storage: str = "local-ssd",
        cloud_init_user_data: str = "",
    ) -> str:
        """Generiert Terraform-Konfiguration für eine VM"""

        module_name = self._sanitize_module_name(name)
        memory_mb = memory_gb * 1024

        # Template: Verwende custom oder default
        template_line = f"template_id   = {template_id}" if template_id else "template_id   = var.default_template"

        # VLAN-spezifische Netzwerkkonfiguration
        bridge = self.get_bridge_for_vlan(vlan)
        gateway = self.get_gateway_for_vlan(vlan)

        # Cloud-Init: VM-spezifisch oder leer (dann wird Standard verwendet)
        cloud_init_line = f'cloud_init_user_data = "{cloud_init_user_data}"' if cloud_init_user_data else "# cloud_init_user_data = Standard (nas:snippets/cloud-config.yaml)"

        return f'''# VM: {name}
# Erstellt: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
# VMID: {vmid} (IP: {ip_address})
# VLAN: {vlan}
# Ansible-Gruppe: {ansible_group}

module "{module_name}" {{
  source = "./modules/proxmox-vm"

  # Basis-Konfiguration
  name        = "{name}"
  vmid        = {vmid}
  target_node = "{target_node}"
  description = "{description}"

  # Ressourcen
  cores        = {cores}
  memory       = {memory_mb}
  disk_size    = {disk_size_gb}
  disk_storage = "{storage}"

  # Netzwerk (VLAN {vlan})
  ip_address = "{ip_address}"
  gateway    = "{gateway}"
  bridge     = "{bridge}"

  # Cloud-Init
  {template_line}
  template_node = var.default_template_node
  ssh_user      = var.ssh_user
  ssh_keys      = [var.ssh_public_key]
  dns_servers   = var.default_dns
  {cloud_init_line}
}}
'''

    def get_tf_filename(self, name: str) -> str:
        """Gibt den Dateinamen für eine VM-Konfiguration zurück"""
        return f"vm_{name}.tf"

    def get_tf_filepath(self, name: str) -> Path:
        """Gibt den vollständigen Pfad zur TF-Datei zurück"""
        return self.vms_dir / self.get_tf_filename(name)

    async def validate_config(self, config: VMConfigCreate) -> VMValidationResult:
        """Validiert eine VM-Konfiguration"""
        errors = []
        warnings = []

        # Prüfe ob Name bereits existiert
        tf_file = self.get_tf_filepath(config.name)
        if tf_file.exists():
            errors.append(f"VM mit Namen '{config.name}' existiert bereits")

        # Prüfe Node (dynamisch aus Proxmox Cluster)
        node_stats = await proxmox_service.get_node_stats()
        node_names = [n["name"] for n in node_stats]

        if config.target_node not in node_names:
            errors.append(
                f"Unbekannter Proxmox-Node: {config.target_node}. "
                f"Verfügbare Nodes: {', '.join(node_names)}"
            )
        else:
            # Node-Ressourcen prüfen
            node_info = next((n for n in node_stats if n["name"] == config.target_node), None)
            if node_info:
                node_cpus = node_info["cpu_total"]
                node_ram_gb = int(node_info["memory_total"] / (1024 ** 3))

                if config.cores > node_cpus:
                    warnings.append(
                        f"Angeforderte Kerne ({config.cores}) überschreiten "
                        f"Node-Kapazität ({node_cpus})"
                    )
                if config.memory_gb > node_ram_gb:
                    warnings.append(
                        f"Angeforderter RAM ({config.memory_gb} GB) überschreitet "
                        f"Node-Kapazität ({node_ram_gb} GB)"
                    )

        # Prüfe IP falls angegeben
        if config.ip_address:
            # Prüfe ob IP im richtigen VLAN
            octets = config.ip_address.split(".")
            ip_vlan = int(octets[2])
            if ip_vlan != config.vlan:
                errors.append(
                    f"IP-Adresse {config.ip_address} gehört nicht zu VLAN {config.vlan}"
                )

            # Prüfe ob IP verfügbar
            try:
                is_available = await netbox_service.check_ip_available(config.ip_address)
                if not is_available:
                    errors.append(f"IP-Adresse {config.ip_address} ist bereits belegt")
            except Exception as e:
                warnings.append(f"NetBox-Prüfung fehlgeschlagen: {str(e)}")

        return VMValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    async def preview_config(self, config: VMConfigCreate) -> TerraformPreview:
        """Erstellt eine Vorschau der Terraform-Konfiguration"""

        # IP-Adresse bestimmen
        if config.ip_address:
            ip_address = config.ip_address
        else:
            # Nächste freie IP aus NetBox holen
            available = await netbox_service.get_available_ips(config.vlan, limit=1)
            if not available:
                raise ValueError(f"Keine freien IPs in VLAN {config.vlan} verfügbar")
            ip_address = available[0]["address"]

        vmid = calculate_vmid(ip_address)

        content = self.generate_tf_content(
            name=config.name,
            vmid=vmid,
            ip_address=ip_address,
            target_node=config.target_node,
            description=config.description or f"VM {config.name}",
            cores=config.cores,
            memory_gb=config.memory_gb,
            disk_size_gb=config.disk_size_gb,
            vlan=config.vlan,
            ansible_group=config.ansible_group or "",
            template_id=config.template_id,
            storage=config.storage,
        )

        return TerraformPreview(
            filename=self.get_tf_filename(config.name),
            content=content,
            vmid=vmid,
            ip_address=ip_address,
        )

    async def create_vm_config(
        self,
        config: VMConfigCreate,
        user_id: int,
    ) -> VMConfigResponse:
        """Erstellt eine neue VM-Konfiguration (TF-Datei)"""

        # Validieren
        validation = await self.validate_config(config)
        if not validation.valid:
            raise ValueError(f"Validierung fehlgeschlagen: {', '.join(validation.errors)}")

        # IP-Adresse bestimmen
        if config.ip_address:
            ip_address = config.ip_address
        else:
            # Nächste freie IP aus NetBox holen
            available = await netbox_service.get_available_ips(config.vlan, limit=1)
            if not available:
                raise ValueError(f"Keine freien IPs in VLAN {config.vlan} verfügbar")
            ip_address = available[0]["address"]

        vmid = calculate_vmid(ip_address)

        # HINWEIS: IP wird erst bei erfolgreichem Deploy reserviert (nicht hier)

        # Cloud-Init generieren und auf NAS schreiben
        cloud_init_ref = ""
        if config.cloud_init_profile:
            try:
                async with async_session() as db:
                    # Cloud-Init YAML mit korrektem Hostname generieren
                    profile = CloudInitProfile(config.cloud_init_profile) if isinstance(config.cloud_init_profile, str) else config.cloud_init_profile
                    cloud_init_yaml = await cloud_init_service.generate_user_data(
                        profile=profile,
                        hostname=config.name,
                        db=db,
                        enable_phone_home=True,
                    )

                    # Auf NAS schreiben (verwende ersten Node als Standard)
                    success = await cloud_init_service.write_snippet_to_nas(
                        vm_name=config.name,
                        content=cloud_init_yaml,
                        proxmox_node=config.target_node,
                        db=db,
                    )

                    if success:
                        cloud_init_ref = await cloud_init_service.get_snippet_proxmox_ref(config.name, db=db)
                        print(f"Cloud-Init fuer {config.name} erstellt: {cloud_init_ref}")
                    else:
                        print(f"Warnung: Cloud-Init konnte nicht auf NAS geschrieben werden, verwende Standard")
            except Exception as e:
                print(f"Fehler bei Cloud-Init Generierung: {e}")

        # Terraform-Datei generieren
        ansible_group = config.ansible_group or ""
        content = self.generate_tf_content(
            name=config.name,
            vmid=vmid,
            ip_address=ip_address,
            target_node=config.target_node,
            description=config.description or f"VM {config.name}",
            cores=config.cores,
            memory_gb=config.memory_gb,
            disk_size_gb=config.disk_size_gb,
            ansible_group=ansible_group,
            template_id=config.template_id,
            storage=config.storage,
            cloud_init_user_data=cloud_init_ref,
        )

        # Datei schreiben
        tf_file = self.get_tf_filepath(config.name)
        tf_file.write_text(content)

        # History-Eintrag erstellen
        await vm_history_service.log_change(
            vm_name=config.name,
            action="created",
            user_id=user_id,
            tf_config_after=content,
            metadata={
                "vmid": vmid,
                "ip_address": ip_address,
                "target_node": config.target_node,
                "cores": config.cores,
                "memory_gb": config.memory_gb,
                "disk_size_gb": config.disk_size_gb,
                "vlan": config.vlan,
                "ansible_group": ansible_group,
            },
        )

        return VMConfigResponse(
            name=config.name,
            vmid=vmid,
            ip_address=ip_address,
            target_node=config.target_node,
            description=config.description or "",
            cores=config.cores,
            memory_gb=config.memory_gb,
            disk_size_gb=config.disk_size_gb,
            vlan=config.vlan,
            status=VMStatus.PLANNED,
            tf_file=self.get_tf_filename(config.name),
            ansible_group=ansible_group,
        )

    async def deploy_vm(
        self,
        name: str,
        user_id: int,
        post_deploy_playbook: str = None,
        post_deploy_extra_vars: dict = None,
        wait_for_ssh: bool = True,
    ) -> int:
        """Führt terraform apply für eine VM aus

        Args:
            name: VM-Name
            user_id: User-ID für Audit
            post_deploy_playbook: Optionales Playbook für Post-Deploy Provisioning
            post_deploy_extra_vars: Extra-Variablen für das Post-Deploy Playbook
            wait_for_ssh: Auf SSH-Verbindung warten vor Playbook-Ausführung
        """
        from app.services.ansible_service import AnsibleService

        tf_file = self.get_tf_filepath(name)
        if not tf_file.exists():
            raise ValueError(f"VM-Konfiguration '{name}' nicht gefunden")

        # VM-Konfiguration lesen für IP-Reservierung
        vm_config = self.get_vm_config(name)
        if not vm_config:
            raise ValueError(f"VM-Konfiguration '{name}' konnte nicht gelesen werden")

        module_name = self._sanitize_module_name(name)

        # Execution erstellen
        async with async_session() as db:
            execution = Execution(
                execution_type="terraform",
                playbook_name=f"VM Deploy: {name}",
                target_hosts=name,
                status="pending",
                user_id=user_id,
                tf_action="apply",
                tf_module=module_name,
            )
            db.add(execution)
            await db.commit()
            await db.refresh(execution)
            execution_id = execution.id

        # IP sofort bei Deploy-Start reservieren (Status: reserved)
        await netbox_service.reserve_ip(
            ip_address=vm_config.ip_address,
            description=f"VM: {name} (deploying)",
            dns_name=f"{name}.example.com",
        )

        # Callback für IP-Aktivierung und Ansible-Inventory-Update bei Erfolg
        async def on_deploy_success():
            """Aktiviert die IP in NetBox und fügt VM zu Ansible-Inventory hinzu"""
            # 1. Beschreibung aktualisieren und IP aktivieren
            await netbox_service.reserve_ip(
                ip_address=vm_config.ip_address,
                description=f"VM: {name}",
                dns_name=f"{name}.example.com",
            )
            await netbox_service.activate_ip(vm_config.ip_address)

            # 2. VM-Objekt in NetBox erstellen und IP verknuepfen
            try:
                await netbox_service.create_vm_with_ip(
                    name=name,
                    ip_address=vm_config.ip_address,
                    vcpus=vm_config.cores,
                    memory_mb=vm_config.memory_gb * 1024,
                    disk_gb=vm_config.disk_size_gb,
                    cluster_name="Proxmox",
                    description=f"Deployed via PVE Commander (VMID: {vm_config.vmid})",
                )
            except Exception as e:
                # NetBox VM-Fehler loggen, aber Deploy als erfolgreich werten
                print(f"Warnung: NetBox VM-Erstellung fehlgeschlagen: {e}")

            # 3. VM zu Ansible-Inventory hinzufügen (wenn Gruppe konfiguriert)
            if vm_config.ansible_group:
                try:
                    ansible_inventory_service.add_host(
                        hostname=name,
                        ip_address=vm_config.ip_address,
                        group=vm_config.ansible_group,
                        vmid=vm_config.vmid,
                        pve_node=vm_config.target_node,
                    )
                except Exception as e:
                    # Inventory-Fehler loggen, aber Deploy als erfolgreich werten
                    print(f"Warnung: Ansible-Inventory-Update fehlgeschlagen: {e}")

            # 3. Post-Deploy Playbook ausführen (wenn konfiguriert)
            if post_deploy_playbook:
                ansible_service = AnsibleService()
                try:
                    # Auf SSH warten
                    if wait_for_ssh:
                        print(f"Warte auf SSH-Verbindung zu {vm_config.ip_address}...")
                        ssh_ready = await ansible_service.wait_for_ssh(
                            host=vm_config.ip_address,
                            timeout=300,
                            interval=10,
                        )
                        if not ssh_ready:
                            print(f"Warnung: SSH-Timeout für {vm_config.ip_address}")
                            return

                    # Playbook ausführen
                    print(f"Starte Post-Deploy Playbook '{post_deploy_playbook}' für {name}")
                    await ansible_service.create_and_run_playbook(
                        playbook_name=post_deploy_playbook,
                        target_host=name,
                        user_id=user_id,
                        extra_vars=post_deploy_extra_vars,
                        parent_execution_id=execution_id,
                    )
                except Exception as e:
                    print(f"Warnung: Post-Deploy Playbook fehlgeschlagen: {e}")

            # 4. History-Eintrag für Deploy erstellen
            try:
                tf_content = tf_file.read_text() if tf_file.exists() else None
                await vm_history_service.log_change(
                    vm_name=name,
                    action="deployed",
                    user_id=user_id,
                    tf_config_after=tf_content,
                    execution_id=execution_id,
                    metadata={
                        "vmid": vm_config.vmid,
                        "ip_address": vm_config.ip_address,
                        "target_node": vm_config.target_node,
                    },
                )
            except Exception as e:
                print(f"Warnung: History-Eintrag konnte nicht erstellt werden: {e}")

            # 5. Benachrichtigung senden
            try:
                async with async_session() as db:
                    notification_service = NotificationService(db)
                    await notification_service.notify(
                        event_type="vm_created",
                        subject=f"VM '{name}' erfolgreich erstellt",
                        message=(
                            f"Die VM '{name}' wurde erfolgreich deployed.\n\n"
                            f"Details:\n"
                            f"- VMID: {vm_config.vmid}\n"
                            f"- IP-Adresse: {vm_config.ip_address}\n"
                            f"- Node: {vm_config.target_node}\n"
                            f"- Ressourcen: {vm_config.cores} Kerne, {vm_config.memory_gb} GB RAM"
                        ),
                        payload={
                            "vm_name": name,
                            "vmid": vm_config.vmid,
                            "ip_address": vm_config.ip_address,
                            "target_node": vm_config.target_node,
                            "cores": vm_config.cores,
                            "memory_gb": vm_config.memory_gb,
                        }
                    )
            except Exception as e:
                print(f"Warnung: Benachrichtigung konnte nicht gesendet werden: {e}")

        # Callback für IP-Freigabe bei Fehler
        async def on_deploy_failure():
            """Gibt die IP in NetBox frei wenn Deploy fehlschlägt"""
            await netbox_service.release_ip(vm_config.ip_address)

        # Terraform apply im Hintergrund starten
        import asyncio
        asyncio.create_task(
            self.terraform_service.run_action(
                execution_id=execution_id,
                action="apply",
                module=module_name,
                on_success=on_deploy_success,
                on_failure=on_deploy_failure,
            )
        )

        return execution_id

    async def plan_vm(self, name: str, user_id: int) -> int:
        """Führt terraform plan für eine VM aus"""

        tf_file = self.get_tf_filepath(name)
        if not tf_file.exists():
            raise ValueError(f"VM-Konfiguration '{name}' nicht gefunden")

        module_name = self._sanitize_module_name(name)

        # Execution erstellen
        async with async_session() as db:
            execution = Execution(
                execution_type="terraform",
                playbook_name=f"VM Plan: {name}",
                target_hosts=name,
                status="pending",
                user_id=user_id,
                tf_action="plan",
                tf_module=module_name,
            )
            db.add(execution)
            await db.commit()
            await db.refresh(execution)
            execution_id = execution.id

        # Terraform plan im Hintergrund starten
        import asyncio
        asyncio.create_task(
            self.terraform_service.run_action(
                execution_id=execution_id,
                action="plan",
                module=module_name,
            )
        )

        return execution_id

    async def destroy_vm(self, name: str, user_id: int) -> int:
        """Führt terraform destroy für eine VM aus"""

        tf_file = self.get_tf_filepath(name)
        if not tf_file.exists():
            raise ValueError(f"VM-Konfiguration '{name}' nicht gefunden")

        # VM-Konfiguration lesen für IP-Freigabe
        vm_config = self.get_vm_config(name)
        if not vm_config:
            raise ValueError(f"VM-Konfiguration '{name}' konnte nicht gelesen werden")

        module_name = self._sanitize_module_name(name)

        # Execution erstellen
        async with async_session() as db:
            execution = Execution(
                execution_type="terraform",
                playbook_name=f"VM Destroy: {name}",
                target_hosts=name,
                status="pending",
                user_id=user_id,
                tf_action="destroy",
                tf_module=module_name,
            )
            db.add(execution)
            await db.commit()
            await db.refresh(execution)
            execution_id = execution.id

        # TF-Konfiguration vor Destroy speichern (für History)
        tf_content_before = tf_file.read_text() if tf_file.exists() else None

        # Callback für Cleanup bei erfolgreichem Destroy
        async def on_destroy_success():
            """Räumt alle Ressourcen auf: TF-Datei, NetBox, Ansible"""
            # 1. TF-Datei löschen
            try:
                if tf_file.exists():
                    tf_file.unlink()
            except Exception as e:
                print(f"Warnung: TF-Datei konnte nicht gelöscht werden: {e}")

            # 2. VM und IP in NetBox löschen
            try:
                await netbox_service.delete_vm_and_ip(name, vm_config.ip_address)
            except Exception as e:
                # Fallback: Nur IP freigeben wenn VM-Löschung fehlschlägt
                print(f"Warnung: NetBox VM-Löschung fehlgeschlagen: {e}")
                try:
                    await netbox_service.release_ip(vm_config.ip_address)
                except Exception:
                    pass

            # 3. VM aus Ansible-Inventory entfernen
            try:
                ansible_inventory_service.remove_host(name)
            except Exception as e:
                print(f"Warnung: Ansible-Inventory-Update fehlgeschlagen: {e}")

            # 3. History-Eintrag für Destroy erstellen
            try:
                await vm_history_service.log_change(
                    vm_name=name,
                    action="destroyed",
                    user_id=user_id,
                    tf_config_before=tf_content_before,
                    execution_id=execution_id,
                    metadata={
                        "vmid": vm_config.vmid,
                        "ip_address": vm_config.ip_address,
                        "target_node": vm_config.target_node,
                    },
                )
            except Exception as e:
                print(f"Warnung: History-Eintrag konnte nicht erstellt werden: {e}")

            # 4. Benachrichtigung senden
            try:
                async with async_session() as db:
                    notification_service = NotificationService(db)
                    await notification_service.notify(
                        event_type="vm_deleted",
                        subject=f"VM '{name}' wurde geloescht",
                        message=(
                            f"Die VM '{name}' wurde erfolgreich geloescht.\n\n"
                            f"Details:\n"
                            f"- VMID: {vm_config.vmid}\n"
                            f"- IP-Adresse: {vm_config.ip_address} (freigegeben)\n"
                            f"- Node: {vm_config.target_node}"
                        ),
                        payload={
                            "vm_name": name,
                            "vmid": vm_config.vmid,
                            "ip_address": vm_config.ip_address,
                            "target_node": vm_config.target_node,
                        }
                    )
            except Exception as e:
                print(f"Warnung: Benachrichtigung konnte nicht gesendet werden: {e}")

        # Terraform destroy im Hintergrund starten
        import asyncio
        asyncio.create_task(
            self.terraform_service.run_action(
                execution_id=execution_id,
                action="destroy",
                module=module_name,
                on_success=on_destroy_success,
            )
        )

        return execution_id

    async def clone_vm(
        self,
        source_name: str,
        target_name: str,
        full_clone: bool,
        user_id: int,
    ) -> dict:
        """
        Klont eine bestehende VM.

        Args:
            source_name: Name der Quell-VM
            target_name: Name des Klons
            full_clone: True für Full Clone, False für Linked Clone
            user_id: User-ID für Audit

        Returns:
            Dict mit success, message, target_name, target_vmid, target_ip
        """
        # Quell-VM Konfiguration holen
        source_config = self.get_vm_config(source_name)
        if not source_config:
            raise ValueError(f"Quell-VM '{source_name}' nicht gefunden")

        # Prüfen ob Ziel-Name bereits existiert
        if self.get_tf_filepath(target_name).exists():
            raise ValueError(f"VM '{target_name}' existiert bereits")

        # Prüfen ob Quell-VM deployed ist
        deployed_modules = await self.terraform_service.get_deployed_modules()
        source_module = self._sanitize_module_name(source_name)
        if source_module not in deployed_modules:
            raise ValueError(f"Quell-VM '{source_name}' ist nicht deployed")

        # Neue freie IP holen
        # VLAN aus der Quell-IP extrahieren
        source_octets = source_config.ip_address.split(".")
        vlan = int(source_octets[2])

        available_ips = await netbox_service.get_available_ips(vlan, limit=1)
        if not available_ips:
            raise ValueError(f"Keine freien IPs in VLAN {vlan} verfügbar")

        target_ip = available_ips[0]["address"]
        target_vmid = calculate_vmid(target_ip)

        # Terraform-Datei für den Klon erstellen
        content = self.generate_tf_content(
            name=target_name,
            vmid=target_vmid,
            ip_address=target_ip,
            target_node=source_config.target_node,
            description=f"Clone von {source_name}",
            cores=source_config.cores,
            memory_gb=source_config.memory_gb,
            disk_size_gb=source_config.disk_size_gb,
            vlan=vlan,
            ansible_group="",  # Klon nicht automatisch ins Inventory
        )

        # TF-Datei schreiben
        tf_file = self.get_tf_filepath(target_name)
        tf_file.write_text(content)

        # Proxmox Clone starten
        result = await proxmox_service.clone_vm(
            source_vmid=source_config.vmid,
            target_vmid=target_vmid,
            target_name=target_name,
            node=source_config.target_node,
            full_clone=full_clone,
        )

        if result.get("success"):
            # IP in NetBox reservieren
            try:
                await netbox_service.reserve_ip(
                    target_ip,
                    hostname=target_name,
                    description=f"Clone von {source_name}",
                )
            except Exception as e:
                print(f"NetBox IP-Reservierung fehlgeschlagen: {e}")

            return {
                "success": True,
                "message": f"VM '{target_name}' wird geklont",
                "target_name": target_name,
                "target_vmid": target_vmid,
                "target_ip": target_ip,
            }
        else:
            # TF-Datei wieder löschen bei Fehler
            tf_file.unlink()
            raise ValueError(f"Proxmox Clone fehlgeschlagen: {result.get('error')}")

    def delete_vm_config(self, name: str) -> bool:
        """Löscht eine VM-Konfiguration (TF-Datei)"""
        tf_file = self.get_tf_filepath(name)
        if tf_file.exists():
            tf_file.unlink()
            return True
        return False

    async def delete_vm_complete(self, name: str, user_id: int) -> dict:
        """
        Löscht eine VM vollständig aus allen Systemen.

        Orchestriert die Löschung aus:
        1. Proxmox (VM selbst)
        2. NetBox (VM-Eintrag + IP-Adresse)
        3. Terraform State (Modul entfernen)
        4. Terraform-Datei (.tf)
        5. Ansible Inventory (Host entfernen)
        6. Cloud-Init Snippet (NAS)

        Args:
            name: VM-Name
            user_id: User-ID für Audit

        Returns:
            dict mit Ergebnis pro System
        """
        result = {
            "vm_name": name,
            "proxmox": {"success": False, "skipped": False, "error": None},
            "netbox_vm": {"success": False, "skipped": False, "error": None},
            "netbox_ip": {"success": False, "skipped": False, "error": None},
            "terraform_state": {"success": False, "skipped": False, "error": None},
            "terraform_file": {"success": False, "skipped": False, "error": None},
            "ansible_inventory": {"success": False, "skipped": False, "error": None},
            "cloud_init_snippet": {"success": False, "skipped": False, "error": None},
        }

        # VM-Konfiguration laden
        vm_config = self.get_vm_config(name)
        if not vm_config:
            raise ValueError(f"VM-Konfiguration '{name}' nicht gefunden")

        module_name = self._sanitize_module_name(name)

        # 1. Proxmox: VM löschen (wenn vorhanden)
        try:
            # Prüfen ob VM in Proxmox existiert
            proxmox_status = await proxmox_service.check_vm_exists(vm_config.vmid)

            if proxmox_status.get("exists"):
                node = proxmox_status.get("node")
                delete_result = await proxmox_service.delete_vm(vm_config.vmid, node)
                result["proxmox"]["success"] = delete_result.get("success", False)
                if not delete_result.get("success"):
                    result["proxmox"]["error"] = delete_result.get("error")
            else:
                result["proxmox"]["skipped"] = True
                result["proxmox"]["success"] = True
        except Exception as e:
            result["proxmox"]["error"] = str(e)

        # 2. NetBox: VM löschen
        try:
            deleted = await netbox_service.delete_vm(name)
            result["netbox_vm"]["success"] = deleted
            if not deleted:
                result["netbox_vm"]["skipped"] = True
        except Exception as e:
            result["netbox_vm"]["error"] = str(e)

        # 3. NetBox: IP freigeben
        try:
            released = await netbox_service.release_ip(vm_config.ip_address)
            result["netbox_ip"]["success"] = released
            if not released:
                result["netbox_ip"]["skipped"] = True
        except Exception as e:
            result["netbox_ip"]["error"] = str(e)

        # 4. Terraform State: Modul entfernen
        try:
            tf_state_result = await self.terraform_service.remove_module_from_state(module_name)
            result["terraform_state"]["success"] = tf_state_result.get("success", False)
            if not tf_state_result.get("success"):
                result["terraform_state"]["error"] = tf_state_result.get("error")
            if "nicht im State" in tf_state_result.get("message", ""):
                result["terraform_state"]["skipped"] = True
        except Exception as e:
            result["terraform_state"]["error"] = str(e)

        # 5. Terraform-Datei löschen
        try:
            deleted = self.delete_vm_config(name)
            result["terraform_file"]["success"] = deleted
            if not deleted:
                result["terraform_file"]["skipped"] = True
        except Exception as e:
            result["terraform_file"]["error"] = str(e)

        # 6. Ansible Inventory: Host entfernen
        try:
            ansible_inventory_service.remove_host(name)
            result["ansible_inventory"]["success"] = True
        except Exception as e:
            # Host war vermutlich nicht im Inventory
            result["ansible_inventory"]["skipped"] = True
            result["ansible_inventory"]["success"] = True

        # 7. Cloud-Init Snippet vom NAS loeschen
        try:
            deleted = await cloud_init_service.delete_snippet_from_nas(name)
            result["cloud_init_snippet"]["success"] = deleted
            if not deleted:
                result["cloud_init_snippet"]["skipped"] = True
                result["cloud_init_snippet"]["success"] = True  # Nicht kritisch
        except Exception as e:
            # Snippet existierte vermutlich nicht
            result["cloud_init_snippet"]["skipped"] = True
            result["cloud_init_snippet"]["success"] = True

        # Gesamtergebnis berechnen
        all_success = all(
            r.get("success", False) or r.get("skipped", False)
            for r in [
                result["proxmox"],
                result["netbox_vm"],
                result["netbox_ip"],
                result["terraform_state"],
                result["terraform_file"],
                result["ansible_inventory"],
                result["cloud_init_snippet"],
            ]
        )

        result["success"] = all_success
        result["message"] = "VM vollständig gelöscht" if all_success else "VM teilweise gelöscht (siehe Details)"

        return result

    def get_vm_configs(self) -> list[VMConfigListItem]:
        """Gibt alle VM-Konfigurationen zurück"""
        vms = []

        for tf_file in self.vms_dir.glob("vm_*.tf"):
            content = tf_file.read_text()

            # Parse VM-Informationen aus TF-Datei
            vm_info = self._parse_tf_file(content)
            if vm_info:
                vms.append(VMConfigListItem(
                    name=vm_info["name"],
                    vmid=vm_info["vmid"],
                    ip_address=vm_info["ip_address"],
                    target_node=vm_info["target_node"],
                    cores=vm_info["cores"],
                    memory_gb=vm_info["memory_gb"],
                    disk_size_gb=vm_info["disk_size_gb"],
                    status=VMStatus.PLANNED,  # TODO: Status aus State ermitteln
                    ansible_group=vm_info.get("ansible_group", ""),
                    frontend_url=vm_info.get("frontend_url"),
                ))

        return sorted(vms, key=lambda x: x.name)

    async def get_vm_configs_with_status(self) -> list[VMConfigListItem]:
        """Gibt VM-Konfigurationen mit korrektem Status aus Terraform State und Proxmox zurück"""
        vms = self.get_vm_configs()  # Bestehende Methode

        # Deployed Module aus Terraform State holen
        deployed_modules = await self.terraform_service.get_deployed_modules()

        # Proxmox Live-Status für deployed VMs holen
        proxmox_vms = {}
        try:
            all_vms = await proxmox_service.get_all_vms()
            proxmox_vms = {vm["vmid"]: vm["status"] for vm in all_vms if vm.get("vmid")}
        except Exception:
            # Falls Proxmox nicht erreichbar, nur Terraform State verwenden
            pass

        # Status aktualisieren basierend auf State und Proxmox
        for vm in vms:
            module_name = self._sanitize_module_name(vm.name)
            if module_name in deployed_modules:
                # VM ist deployed, prüfe Proxmox Live-Status
                live_status = proxmox_vms.get(vm.vmid)
                if live_status == "running":
                    vm.status = VMStatus.RUNNING
                elif live_status == "stopped":
                    vm.status = VMStatus.STOPPED
                elif live_status == "paused":
                    vm.status = VMStatus.PAUSED
                else:
                    vm.status = VMStatus.DEPLOYED
            else:
                vm.status = VMStatus.PLANNED

        return vms

    def get_vm_config(self, name: str) -> Optional[VMConfigResponse]:
        """Gibt eine einzelne VM-Konfiguration zurück"""
        tf_file = self.get_tf_filepath(name)
        if not tf_file.exists():
            return None

        content = tf_file.read_text()
        vm_info = self._parse_tf_file(content)

        if not vm_info:
            return None

        return VMConfigResponse(
            name=vm_info["name"],
            vmid=vm_info["vmid"],
            ip_address=vm_info["ip_address"],
            target_node=vm_info["target_node"],
            description=vm_info.get("description", ""),
            cores=vm_info["cores"],
            memory_gb=vm_info["memory_gb"],
            disk_size_gb=vm_info["disk_size_gb"],
            vlan=int(vm_info["ip_address"].split(".")[2]),
            status=VMStatus.PLANNED,
            tf_file=self.get_tf_filename(name),
            ansible_group=vm_info.get("ansible_group", ""),
            frontend_url=vm_info.get("frontend_url"),
        )

    def _parse_tf_file(self, content: str) -> Optional[dict]:
        """Parst VM-Informationen aus TF-Datei-Inhalt"""
        try:
            # Name
            name_match = re.search(r'name\s*=\s*"([^"]+)"', content)
            name = name_match.group(1) if name_match else None

            # VMID
            vmid_match = re.search(r'vmid\s*=\s*(\d+)', content)
            vmid = int(vmid_match.group(1)) if vmid_match else None

            # IP
            ip_match = re.search(r'ip_address\s*=\s*"([^"]+)"', content)
            ip_address = ip_match.group(1) if ip_match else None

            # Node
            node_match = re.search(r'target_node\s*=\s*"([^"]+)"', content)
            target_node = node_match.group(1) if node_match else None

            # Cores
            cores_match = re.search(r'cores\s*=\s*(\d+)', content)
            cores = int(cores_match.group(1)) if cores_match else 2

            # Memory (in MB in TF-Datei)
            memory_match = re.search(r'memory\s*=\s*(\d+)', content)
            memory_mb = int(memory_match.group(1)) if memory_match else 2048
            memory_gb = memory_mb // 1024

            # Disk
            disk_match = re.search(r'disk_size\s*=\s*(\d+)', content)
            disk_size_gb = int(disk_match.group(1)) if disk_match else 20

            # Description
            desc_match = re.search(r'description\s*=\s*"([^"]*)"', content)
            description = desc_match.group(1) if desc_match else ""

            # Ansible-Gruppe aus Kommentar (# Ansible-Gruppe: xxx)
            # Nur horizontale Whitespace matchen, nicht Newlines
            ansible_group_match = re.search(r'^# Ansible-Gruppe:[ \t]*(\S*)$', content, re.MULTILINE)
            ansible_group = ansible_group_match.group(1) if ansible_group_match else ""

            # Frontend-URL aus Kommentar (# Frontend-URL: https://...)
            frontend_url_match = re.search(r'^# Frontend-URL:\s*(.+)$', content, re.MULTILINE)
            frontend_url = frontend_url_match.group(1).strip() if frontend_url_match else None

            if name and vmid and ip_address and target_node:
                return {
                    "name": name,
                    "vmid": vmid,
                    "ip_address": ip_address,
                    "target_node": target_node,
                    "cores": cores,
                    "memory_gb": memory_gb,
                    "disk_size_gb": disk_size_gb,
                    "description": description,
                    "ansible_group": ansible_group,
                    "frontend_url": frontend_url,
                }
        except Exception:
            pass

        return None


    async def get_unmanaged_vms(self) -> list[dict]:
        """
        Holt alle VMs aus Proxmox die nicht von Terraform verwaltet werden.

        Filtert:
        - Templates (VMID >= 900000)
        - Bereits verwaltete VMs (im Terraform State)

        Returns:
            Liste von VMs mit vmid, name, node, status, cores, memory, disk, ip_address
        """
        # Alle VMs aus Proxmox
        all_vms = await proxmox_service.get_all_vms()

        # IP-Adressen via QEMU Guest Agent holen
        vm_ips = await proxmox_service.scan_vm_ips()
        ip_by_vmid = {vm.get("vmid"): vm.get("ip") for vm in vm_ips}

        # Deployed Module aus Terraform State
        deployed_modules = await self.terraform_service.get_deployed_modules()

        # Existierende TF-Dateien
        existing_tf_files = {
            self._sanitize_module_name(tf.stem.replace("vm_", ""))
            for tf in self.vms_dir.glob("vm_*.tf")
        }

        # Kombinieren: State + TF-Dateien
        managed_modules = set(deployed_modules) | existing_tf_files

        # VMs ermitteln die bereits verwaltet werden
        managed_vmids = set()
        for name in managed_modules:
            # Versuche VMID aus existierender TF-Datei zu lesen
            vm_name = name.replace("_", "-")
            vm_config = self.get_vm_config(vm_name)
            if vm_config:
                managed_vmids.add(vm_config.vmid)

        unmanaged = []
        for vm in all_vms:
            vmid = vm.get("vmid", 0)

            # Templates überspringen
            if vmid >= 900000:
                continue

            # Bereits verwaltete VMs überspringen
            if vmid in managed_vmids:
                continue

            unmanaged.append({
                "vmid": vmid,
                "name": vm.get("name", f"vm-{vmid}"),
                "node": vm.get("node", ""),
                "status": vm.get("status", "unknown"),
                "maxcpu": vm.get("maxcpu", 1),
                "maxmem": vm.get("maxmem", 0),
                "maxdisk": vm.get("maxdisk", 0),
                "ip_address": ip_by_vmid.get(vmid),
            })

        return sorted(unmanaged, key=lambda x: x["vmid"])

    async def import_existing_vm(
        self,
        vmid: int,
        node: str,
        vm_name: str,
        ansible_group: str = "",
        register_netbox: bool = True,
        user_id: int = 1,
    ) -> dict:
        """
        Importiert eine existierende Proxmox-VM in Terraform-Verwaltung.

        Schritte:
        1. VM-Konfiguration aus Proxmox lesen
        2. TF-Datei generieren
        3. terraform import ausführen
        4. Optional: In Ansible-Inventory eintragen
        5. Optional: IP in NetBox registrieren

        Args:
            vmid: Proxmox VM-ID
            node: Proxmox-Node
            vm_name: Name für die importierte VM
            ansible_group: Optional Ansible-Gruppe
            register_netbox: IP in NetBox registrieren
            user_id: User-ID für Audit

        Returns:
            dict mit success, message, vm_name, vmid, ip_address
        """
        # Prüfen ob TF-Datei bereits existiert
        if self.get_tf_filepath(vm_name).exists():
            return {"success": False, "error": f"VM '{vm_name}' existiert bereits als TF-Datei"}

        # VM-Konfiguration aus Proxmox holen
        config_result = await proxmox_service.get_vm_config(vmid, node)
        if not config_result.get("success"):
            return {"success": False, "error": f"VM-Konfiguration nicht lesbar: {config_result.get('error')}"}

        config = config_result.get("config", {})

        # IP-Adresse extrahieren
        # 1. Versuch: Cloud-Init Konfiguration (ipconfig0/ipconfig1)
        ip_address = None
        for key in ["ipconfig0", "ipconfig1"]:
            if key in config:
                ipconfig = config[key]
                # Format: ip=10.0.0.100/24,gw=10.0.0.1
                match = re.search(r'ip=(\d+\.\d+\.\d+\.\d+)', ipconfig)
                if match:
                    ip_address = match.group(1)
                    break

        # 2. Versuch: QEMU Guest Agent (fuer VMs ohne Cloud-Init)
        if not ip_address:
            agent_result = await proxmox_service.get_vm_agent_network(vmid, node)
            if agent_result.get("success") and agent_result.get("primary_ip"):
                ip_address = agent_result["primary_ip"]

        if not ip_address:
            return {"success": False, "error": "IP-Adresse konnte nicht aus VM-Konfiguration extrahiert werden (weder Cloud-Init noch Guest Agent)"}

        # VLAN aus IP extrahieren
        vlan = int(ip_address.split(".")[2])

        # Ressourcen aus Konfiguration (Werte koennen als String kommen)
        cores = int(config.get("cores", 2))
        memory_mb = int(config.get("memory", 2048))
        memory_gb = memory_mb // 1024

        # Disk-Größe aus scsi0/virtio0/ide0 extrahieren
        disk_size_gb = 20  # Default
        for disk_key in ["scsi0", "virtio0", "ide0", "sata0"]:
            if disk_key in config:
                disk_config = config[disk_key]
                # Format: local-ssd:vm-60100-disk-0,size=20G
                size_match = re.search(r'size=(\d+)G?', disk_config)
                if size_match:
                    disk_size_gb = int(size_match.group(1))
                    break

        # Storage aus Disk extrahieren
        storage = "local-ssd"  # Default
        for disk_key in ["scsi0", "virtio0", "ide0", "sata0"]:
            if disk_key in config:
                disk_config = config[disk_key]
                # Format: local-ssd:vm-60100-disk-0,size=20G
                storage_match = re.search(r'^([^:]+):', disk_config)
                if storage_match:
                    storage = storage_match.group(1)
                    break

        # TF-Datei generieren
        # Description bereinigen: Newlines escapen fuer Terraform
        raw_description = config.get("description", "Importiert aus Proxmox")
        # Newlines durch escaped Newlines ersetzen (Terraform-kompatibel)
        sanitized_description = raw_description.replace("\n", "\\n").replace("\r", "")

        content = self.generate_tf_content(
            name=vm_name,
            vmid=vmid,
            ip_address=ip_address,
            target_node=node,
            description=sanitized_description,
            cores=cores,
            memory_gb=memory_gb,
            disk_size_gb=disk_size_gb,
            vlan=vlan,
            ansible_group=ansible_group,
            storage=storage,
        )

        # TF-Datei schreiben
        tf_file = self.get_tf_filepath(vm_name)
        tf_file.write_text(content)

        # Terraform import ausführen
        module_name = self._sanitize_module_name(vm_name)
        address = f"module.{module_name}.proxmox_virtual_environment_vm.vm"
        resource_id = f"{node}/{vmid}"

        import_result = await self.terraform_service.import_resource(address, resource_id)

        if not import_result.get("success"):
            # TF-Datei wieder löschen bei Fehler
            tf_file.unlink()
            return {
                "success": False,
                "error": f"Terraform Import fehlgeschlagen: {import_result.get('error')}",
            }

        # Optional: IP und VM in NetBox registrieren
        if register_netbox:
            try:
                await netbox_service.reserve_ip(
                    ip_address=ip_address,
                    description=f"VM: {vm_name} (importiert)",
                    dns_name=f"{vm_name}.example.com",
                )
                await netbox_service.activate_ip(ip_address)

                # VM-Device in NetBox erstellen und IP verknuepfen
                await netbox_service.create_vm_with_ip(
                    name=vm_name,
                    ip_address=ip_address,
                    vcpus=cores,
                    memory_mb=int(memory_gb * 1024),
                    disk_gb=disk_size_gb,
                    cluster_name="Proxmox",
                    description=f"Importiert via PVE Commander (VMID: {vmid}, Node: {node})",
                )
            except Exception as e:
                # Nicht kritisch, nur warnen
                print(f"NetBox-Registrierung fehlgeschlagen: {e}")

        # Optional: Ansible-Inventory
        if ansible_group:
            try:
                ansible_inventory_service.add_host(
                    hostname=vm_name,
                    ip_address=ip_address,
                    group=ansible_group,
                    vmid=vmid,
                    pve_node=node,
                )
            except Exception as e:
                print(f"Ansible-Inventory-Update fehlgeschlagen: {e}")

        # History-Eintrag für Import erstellen
        try:
            await vm_history_service.log_change(
                vm_name=vm_name,
                action="imported",
                user_id=user_id,
                tf_config_after=content,
                metadata={
                    "vmid": vmid,
                    "ip_address": ip_address,
                    "node": node,
                    "cores": cores,
                    "memory_gb": memory_gb,
                    "disk_size_gb": disk_size_gb,
                    "vlan": vlan,
                    "ansible_group": ansible_group,
                },
            )
        except Exception as e:
            print(f"Warnung: History-Eintrag konnte nicht erstellt werden: {e}")

        return {
            "success": True,
            "message": f"VM '{vm_name}' erfolgreich importiert",
            "vm_name": vm_name,
            "vmid": vmid,
            "ip_address": ip_address,
            "node": node,
            "cores": cores,
            "memory_gb": memory_gb,
            "disk_size_gb": disk_size_gb,
        }

    def update_target_node(self, vm_name: str, new_node: str) -> dict:
        """
        Aktualisiert den target_node in der TF-Datei einer VM.

        Wird nach erfolgreicher Migration aufgerufen, um die TF-Konfiguration
        mit dem neuen Node synchron zu halten.

        Args:
            vm_name: Name der VM
            new_node: Neuer Proxmox-Node

        Returns:
            dict mit success, old_node, new_node oder error
        """
        tf_file = self.get_tf_filepath(vm_name)

        if not tf_file.exists():
            return {"success": False, "error": f"TF-Datei für '{vm_name}' nicht gefunden"}

        try:
            content = tf_file.read_text()

            # Alten Node extrahieren
            old_node_match = re.search(r'target_node\s*=\s*"([^"]+)"', content)
            old_node = old_node_match.group(1) if old_node_match else "unknown"

            if old_node == new_node:
                return {
                    "success": True,
                    "message": "Node bereits korrekt",
                    "old_node": old_node,
                    "new_node": new_node,
                }

            # target_node ersetzen
            new_content = re.sub(
                r'(target_node\s*=\s*)"[^"]+"',
                f'\\1"{new_node}"',
                content,
            )

            # Datei speichern
            tf_file.write_text(new_content)

            return {
                "success": True,
                "message": f"target_node von '{old_node}' auf '{new_node}' aktualisiert",
                "old_node": old_node,
                "new_node": new_node,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_frontend_url(self, vm_name: str, url: Optional[str]) -> dict:
        """
        Aktualisiert oder entfernt die Frontend-URL in der TF-Datei einer VM.

        Die URL wird als Kommentar am Anfang der Datei gespeichert:
        # Frontend-URL: https://app.example.com

        Args:
            vm_name: Name der VM
            url: Neue URL oder None zum Entfernen

        Returns:
            dict mit success, message, frontend_url oder error
        """
        tf_file = self.get_tf_filepath(vm_name)

        if not tf_file.exists():
            return {"success": False, "error": f"TF-Datei für '{vm_name}' nicht gefunden"}

        try:
            content = tf_file.read_text()

            # Existierende Frontend-URL Zeile suchen
            frontend_url_pattern = r'^# Frontend-URL:\s*.+\n'
            has_frontend_url = re.search(frontend_url_pattern, content, re.MULTILINE)

            if url:
                # URL hinzufügen oder aktualisieren
                new_line = f"# Frontend-URL: {url}\n"

                if has_frontend_url:
                    # Bestehende Zeile ersetzen
                    new_content = re.sub(
                        frontend_url_pattern,
                        new_line,
                        content,
                        count=1,
                        flags=re.MULTILINE,
                    )
                else:
                    # Neue Zeile nach dem ersten Kommentar-Block einfügen
                    # Finde die Zeile "# VM: ..." und füge danach ein
                    vm_comment_match = re.search(r'^# VM: .+\n', content, re.MULTILINE)
                    if vm_comment_match:
                        insert_pos = vm_comment_match.end()
                        new_content = content[:insert_pos] + new_line + content[insert_pos:]
                    else:
                        # Falls kein VM-Kommentar, am Anfang einfügen
                        new_content = new_line + content
            else:
                # URL entfernen
                if has_frontend_url:
                    new_content = re.sub(
                        frontend_url_pattern,
                        "",
                        content,
                        count=1,
                        flags=re.MULTILINE,
                    )
                else:
                    # Nichts zu entfernen
                    return {
                        "success": True,
                        "message": "Keine Frontend-URL vorhanden",
                        "vm_name": vm_name,
                        "frontend_url": None,
                    }

            # Datei speichern
            tf_file.write_text(new_content)

            return {
                "success": True,
                "message": "Frontend-URL aktualisiert" if url else "Frontend-URL entfernt",
                "vm_name": vm_name,
                "frontend_url": url,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_vm_config(self, vm_name: str, updates: dict) -> dict:
        """
        Aktualisiert die VM-Konfiguration in der TF-Datei.

        Args:
            vm_name: Name der VM
            updates: Dict mit zu ändernden Feldern:
                     cores, memory_gb, disk_size_gb, description, target_node

        Returns:
            dict mit success, message, updated_fields oder error
        """
        tf_file = self.get_tf_filepath(vm_name)

        if not tf_file.exists():
            return {"success": False, "error": f"TF-Datei für '{vm_name}' nicht gefunden"}

        try:
            content = tf_file.read_text()
            updated_fields = {}

            # Cores aktualisieren
            if "cores" in updates:
                old_match = re.search(r'cores\s*=\s*(\d+)', content)
                old_value = int(old_match.group(1)) if old_match else None
                content = re.sub(
                    r'(cores\s*=\s*)\d+',
                    f'\\g<1>{updates["cores"]}',
                    content,
                )
                updated_fields["cores"] = {"old": old_value, "new": updates["cores"]}

            # Memory aktualisieren (memory_gb -> memory in MB)
            if "memory_gb" in updates:
                memory_mb = updates["memory_gb"] * 1024
                old_match = re.search(r'memory\s*=\s*(\d+)', content)
                old_mb = int(old_match.group(1)) if old_match else None
                old_gb = old_mb // 1024 if old_mb else None
                content = re.sub(
                    r'(memory\s*=\s*)\d+',
                    f'\\g<1>{memory_mb}',
                    content,
                )
                updated_fields["memory_gb"] = {"old": old_gb, "new": updates["memory_gb"]}

            # Disk Size aktualisieren
            if "disk_size_gb" in updates:
                old_match = re.search(r'disk_size\s*=\s*(\d+)', content)
                old_value = int(old_match.group(1)) if old_match else None
                content = re.sub(
                    r'(disk_size\s*=\s*)\d+',
                    f'\\g<1>{updates["disk_size_gb"]}',
                    content,
                )
                updated_fields["disk_size_gb"] = {"old": old_value, "new": updates["disk_size_gb"]}

            # Description aktualisieren
            if "description" in updates:
                old_match = re.search(r'description\s*=\s*"([^"]*)"', content)
                old_value = old_match.group(1) if old_match else ""
                # Escaping für Terraform-String
                new_desc = updates["description"].replace('\\', '\\\\').replace('"', '\\"')
                content = re.sub(
                    r'(description\s*=\s*)"[^"]*"',
                    f'\\g<1>"{new_desc}"',
                    content,
                )
                updated_fields["description"] = {"old": old_value, "new": updates["description"]}

            # Target Node aktualisieren
            if "target_node" in updates:
                old_match = re.search(r'target_node\s*=\s*"([^"]+)"', content)
                old_value = old_match.group(1) if old_match else None
                content = re.sub(
                    r'(target_node\s*=\s*)"[^"]+"',
                    f'\\g<1>"{updates["target_node"]}"',
                    content,
                )
                updated_fields["target_node"] = {"old": old_value, "new": updates["target_node"]}

            # Datei speichern
            tf_file.write_text(content)

            # Änderungen zusammenfassen
            changes = []
            for field, vals in updated_fields.items():
                if vals["old"] != vals["new"]:
                    changes.append(f"{field}: {vals['old']} → {vals['new']}")

            return {
                "success": True,
                "message": f"VM-Konfiguration aktualisiert: {', '.join(changes)}" if changes else "Keine Änderungen",
                "updated_fields": updated_fields,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}


# Singleton-Instanz
vm_deployment_service = VMDeploymentService()
