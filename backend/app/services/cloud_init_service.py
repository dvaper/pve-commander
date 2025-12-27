"""
Cloud-Init Service - Generiert Cloud-Init User-Data fuer VMs

Die Konfiguration (SSH-Keys, Phone-Home URL, Admin-Username) wird aus der
Datenbank geladen (CloudInitSettings). Fallback-Defaults werden verwendet,
wenn keine DB-Session verfuegbar ist.
"""
import yaml
import subprocess
import tempfile
import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.cloud_init import CloudInitProfile, CLOUD_INIT_PROFILES
from app.services.cloud_init_settings_service import CloudInitSettingsService

logger = logging.getLogger(__name__)


class CloudInitService:
    """Service fuer Cloud-Init Konfiguration"""

    # Fallback-Defaults (nur wenn DB nicht verfuegbar)
    FALLBACK_SSH_KEYS: List[str] = []
    FALLBACK_ADMIN_USERNAME = "ansible"
    FALLBACK_ADMIN_GECOS = "Homelab Admin"
    FALLBACK_PHONE_HOME_URL: Optional[str] = None
    FALLBACK_NAS_SNIPPETS_PATH: Optional[str] = None
    FALLBACK_NAS_SNIPPETS_REF: Optional[str] = None

    def get_profiles(self) -> List[Dict[str, Any]]:
        """Gibt alle verfuegbaren Profile zurueck"""
        return [
            {
                "id": profile_id,
                "name": info["name"],
                "description": info["description"],
                "packages": info.get("packages", []),
                "groups": info.get("groups", []),
                "services": info.get("services", []),
            }
            for profile_id, info in CLOUD_INIT_PROFILES.items()
        ]

    def get_profile_info(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Gibt Details zu einem spezifischen Profil zurueck"""
        if profile_id in CLOUD_INIT_PROFILES:
            info = CLOUD_INIT_PROFILES[profile_id]
            return {
                "id": profile_id,
                "name": info["name"],
                "description": info["description"],
                "packages": info.get("packages", []),
                "groups": info.get("groups", []),
                "services": info.get("services", []),
                "sysctl": info.get("sysctl", {}),
                "apt_sources": info.get("apt_sources", {}),
            }
        return None

    async def generate_user_data(
        self,
        profile: CloudInitProfile,
        hostname: str,
        db: Optional[AsyncSession] = None,
        request_host: Optional[str] = None,
        additional_packages: Optional[List[str]] = None,
        additional_ssh_keys: Optional[List[str]] = None,
        additional_runcmd: Optional[List[str]] = None,
        enable_phone_home: bool = True,
    ) -> str:
        """
        Generiert Cloud-Init User-Data YAML fuer ein Profil.

        Args:
            profile: Das zu verwendende Cloud-Init Profil
            hostname: Hostname der VM
            db: Datenbank-Session (fuer Settings aus DB)
            request_host: Host aus HTTP-Request (fuer auto-generierte Phone-Home URL)
            additional_packages: Zusaetzliche Pakete
            additional_ssh_keys: Zusaetzliche SSH-Keys
            additional_runcmd: Zusaetzliche Befehle nach dem Boot
            enable_phone_home: Phone-Home Callback aktivieren

        Returns:
            Cloud-Init User-Data als YAML-String
        """
        if profile == CloudInitProfile.NONE or not profile:
            return ""

        # Settings aus DB laden oder Fallbacks verwenden
        if db:
            settings_service = CloudInitSettingsService(db)
            ssh_keys = await settings_service.get_ssh_keys()
            admin_username = await settings_service.get_admin_username()
            admin_gecos = await settings_service.get_admin_gecos()
            phone_home_url = await settings_service.get_phone_home_url(request_host) if enable_phone_home else None
        else:
            logger.warning("Keine DB-Session - verwende Fallback-Defaults fuer Cloud-Init")
            ssh_keys = list(self.FALLBACK_SSH_KEYS)
            admin_username = self.FALLBACK_ADMIN_USERNAME
            admin_gecos = self.FALLBACK_ADMIN_GECOS
            phone_home_url = self.FALLBACK_PHONE_HOME_URL

        profile_key = profile.value if isinstance(profile, CloudInitProfile) else profile
        profile_info = CLOUD_INIT_PROFILES.get(profile_key, {})

        # Basis-Konfiguration
        user_data: Dict[str, Any] = {
            "hostname": hostname,
            "manage_etc_hosts": True,
            "preserve_hostname": False,
            "locale": "de_DE.UTF-8",
            "locale_configfile": "/etc/locale.gen",
            "timezone": "Europe/Berlin",
            "package_update": True,
            "package_upgrade": True,
        }

        # SSH-Keys (aus Settings + zusaetzliche)
        all_ssh_keys = list(ssh_keys)
        if additional_ssh_keys:
            all_ssh_keys.extend(additional_ssh_keys)

        # User-Gruppen basierend auf Profil
        user_groups = ["sudo", "users", "adm", "systemd-journal"]
        profile_groups = profile_info.get("groups", [])
        if profile_groups:
            user_groups.extend(profile_groups)

        user_data["users"] = [
            {
                "name": admin_username,
                "gecos": admin_gecos,
                "groups": user_groups,
                "shell": "/bin/bash",
                "sudo": "ALL=(ALL) NOPASSWD:ALL",
                "lock_passwd": True,
                "ssh_authorized_keys": all_ssh_keys,
            }
        ]

        # SSH Hardening
        user_data["ssh_pwauth"] = False
        user_data["disable_root"] = True

        # Pakete
        packages = ["qemu-guest-agent", "curl", "wget", "wtmpdb", "locales"]
        packages.extend(profile_info.get("packages", []))
        if additional_packages:
            packages.extend(additional_packages)
        user_data["packages"] = list(set(packages))

        # APT Sources (fuer Docker, GitLab Runner, etc.)
        apt_sources = profile_info.get("apt_sources", {})
        if apt_sources:
            user_data["apt"] = {"sources": {}}
            for source_name, source_config in apt_sources.items():
                user_data["apt"]["sources"][source_name] = {
                    "source": source_config["source"],
                }
                if "keyid" in source_config:
                    user_data["apt"]["sources"][source_name]["keyid"] = source_config["keyid"]
                if "keyring" in source_config:
                    user_data["apt"]["sources"][source_name]["keyserver"] = "hkp://keyserver.ubuntu.com:80"

        # Write Files (Profil-spezifisch)
        write_files = []

        # Login Welcome Script (profile.d) - zeigt Last Login + Banner bei jedem Login
        welcome_script = f'''#!/bin/bash
# Login Welcome - Ansible Commander
# Wird bei jedem Login ausgefuehrt

# Nur bei interaktiven Shells
[[ $- != *i* ]] && return

# Bildschirm leeren
clear

# Last Login Info (vorheriger Login, nicht aktueller)
# Zweite Zeile = vorheriger Login (erste Zeile ist aktueller)
LAST_INFO=$(last -2 -F $USER 2>/dev/null | sed -n '2p')
if [ -n "$LAST_INFO" ] && [[ "$LAST_INFO" != *"wtmpdb begins"* ]]; then
    LAST_IP=$(echo "$LAST_INFO" | awk '{{print $3}}')
    LAST_DATE=$(echo "$LAST_INFO" | awk '{{print $4, $5, $6, $7, $8}}')

    # Falls IP ein tty ist, als "console" anzeigen
    if [[ "$LAST_IP" == pts/* ]] || [[ "$LAST_IP" == tty* ]]; then
        LAST_IP="console"
    fi

    echo "Last login: $LAST_DATE from $LAST_IP"
    echo ""
fi

# OS-Info laden
. /etc/os-release 2>/dev/null || PRETTY_NAME="Linux"

# Banner anzeigen
cat << EOF
===============================================
   Homelab VM - Managed by Ansible Commander
===============================================

Hostname: $(hostname)
System:   ${{PRETTY_NAME}}
Admin:    {admin_username}

Useful commands:
  htop          - Process monitor
  btop          - Resource monitor
  journalctl -f - Live system logs

===============================================
EOF
'''
        write_files.append({
            "path": "/etc/profile.d/00-welcome.sh",
            "content": welcome_script,
            "permissions": "0755",
        })

        # MOTD deaktivieren (wir nutzen profile.d stattdessen)
        write_files.append({
            "path": "/etc/motd",
            "content": "",
            "permissions": "0644",
        })

        # Locale-Generierung sicherstellen
        write_files.append({
            "path": "/etc/locale.gen",
            "content": "de_DE.UTF-8 UTF-8\nen_US.UTF-8 UTF-8\n",
            "permissions": "0644",
        })

        profile_write_files = profile_info.get("write_files", [])
        if profile_write_files:
            write_files.extend(profile_write_files)

        # Sysctl Settings
        sysctl_settings = profile_info.get("sysctl", {})
        if sysctl_settings:
            sysctl_content = "\n".join([f"{k} = {v}" for k, v in sysctl_settings.items()])
            write_files.append({
                "path": f"/etc/sysctl.d/99-{profile_key}.conf",
                "content": f"# Cloud-Init Profile: {profile_key}\n{sysctl_content}\n",
            })

        # Limits (fuer Database-Profil)
        limits = profile_info.get("limits", [])
        if limits:
            write_files.append({
                "path": "/etc/security/limits.d/99-cloud-init.conf",
                "content": "\n".join(limits) + "\n",
            })

        if write_files:
            user_data["write_files"] = write_files

        # Run Commands
        runcmd = []

        # Locale generieren (muss frueh passieren)
        runcmd.append("locale-gen")
        runcmd.append("update-locale LANG=de_DE.UTF-8")

        # Sysctl laden wenn vorhanden
        if sysctl_settings:
            runcmd.append("sysctl --system")

        # Services aktivieren
        services = profile_info.get("services", [])
        for service in services:
            runcmd.append(f"systemctl enable {service}")
            runcmd.append(f"systemctl start {service}")

        # QEMU Guest Agent immer aktivieren
        runcmd.extend([
            "systemctl enable qemu-guest-agent",
            "systemctl start qemu-guest-agent",
        ])

        # Profil-spezifische Extra-Commands
        extra_runcmd = profile_info.get("runcmd_extra", [])
        if extra_runcmd:
            runcmd.extend(extra_runcmd)

        # Zusaetzliche Befehle
        if additional_runcmd:
            runcmd.extend(additional_runcmd)

        # Phone Home Callback
        if enable_phone_home and phone_home_url:
            phone_home_cmd = f'''curl -sf -X POST "{phone_home_url}" \\
  -H "Content-Type: application/json" \\
  -d '{{"hostname": "$(hostname)", "instance_id": "$(cat /var/lib/cloud/data/instance-id 2>/dev/null || echo unknown)", "ip_address": "$(hostname -I | awk '{{print $1}}')", "status": "completed", "timestamp": "$(date -Iseconds)"}}' \\
  || echo "Phone-home callback failed"'''
            runcmd.append(phone_home_cmd)

        if runcmd:
            user_data["runcmd"] = runcmd

        # Phone Home (natives Cloud-Init Modul als Backup)
        if enable_phone_home and phone_home_url:
            user_data["phone_home"] = {
                "url": phone_home_url,
                "post": ["instance_id", "hostname", "fqdn"],
                "tries": 3,
            }

        # Final message
        user_data["final_message"] = f"Cloud-Init completed for {hostname} with profile '{profile_key}'"

        # YAML generieren mit #cloud-config Header
        yaml_content = yaml.dump(user_data, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return f"#cloud-config\n{yaml_content}"

    async def generate_merged_config(
        self,
        profiles: List[CloudInitProfile],
        hostname: str,
        db: Optional[AsyncSession] = None,
        request_host: Optional[str] = None,
        additional_packages: Optional[List[str]] = None,
        additional_ssh_keys: Optional[List[str]] = None,
        additional_runcmd: Optional[List[str]] = None,
        enable_phone_home: bool = True,
    ) -> str:
        """
        Generiert Cloud-Init Config durch Zusammenfuehren mehrerer Profile.

        Args:
            profiles: Liste von Profilen die kombiniert werden sollen
            hostname: Hostname der VM
            db: Datenbank-Session (fuer Settings aus DB)
            request_host: Host aus HTTP-Request (fuer auto-generierte Phone-Home URL)
            additional_packages: Zusaetzliche Pakete
            additional_ssh_keys: Zusaetzliche SSH-Keys
            additional_runcmd: Zusaetzliche Befehle
            enable_phone_home: Phone-Home Callback aktivieren

        Returns:
            Kombinierte Cloud-Init User-Data als YAML-String
        """
        # Settings aus DB laden oder Fallbacks verwenden
        if db:
            settings_service = CloudInitSettingsService(db)
            ssh_keys = await settings_service.get_ssh_keys()
            admin_username = await settings_service.get_admin_username()
            admin_gecos = await settings_service.get_admin_gecos()
            phone_home_url = await settings_service.get_phone_home_url(request_host) if enable_phone_home else None
        else:
            logger.warning("Keine DB-Session - verwende Fallback-Defaults fuer Cloud-Init (merged)")
            ssh_keys = list(self.FALLBACK_SSH_KEYS)
            admin_username = self.FALLBACK_ADMIN_USERNAME
            admin_gecos = self.FALLBACK_ADMIN_GECOS
            phone_home_url = self.FALLBACK_PHONE_HOME_URL

        merged_packages = set()
        merged_groups = set(["sudo", "users", "adm", "systemd-journal"])
        merged_services = set()
        merged_sysctl = {}
        merged_apt_sources = {}
        merged_write_files = []
        merged_runcmd_extra = []
        merged_limits = []

        for profile in profiles:
            if profile == CloudInitProfile.NONE:
                continue

            profile_key = profile.value if isinstance(profile, CloudInitProfile) else profile
            profile_info = CLOUD_INIT_PROFILES.get(profile_key, {})

            merged_packages.update(profile_info.get("packages", []))
            merged_groups.update(profile_info.get("groups", []))
            merged_services.update(profile_info.get("services", []))
            merged_sysctl.update(profile_info.get("sysctl", {}))
            merged_apt_sources.update(profile_info.get("apt_sources", {}))
            merged_write_files.extend(profile_info.get("write_files", []))
            merged_runcmd_extra.extend(profile_info.get("runcmd_extra", []))
            merged_limits.extend(profile_info.get("limits", []))

        # Basis-Konfiguration
        user_data: Dict[str, Any] = {
            "hostname": hostname,
            "manage_etc_hosts": True,
            "preserve_hostname": False,
            "locale": "de_DE.UTF-8",
            "locale_configfile": "/etc/locale.gen",
            "timezone": "Europe/Berlin",
            "package_update": True,
            "package_upgrade": True,
        }

        # SSH Keys (aus Settings + zusaetzliche)
        all_ssh_keys = list(ssh_keys)
        if additional_ssh_keys:
            all_ssh_keys.extend(additional_ssh_keys)

        user_data["users"] = [
            {
                "name": admin_username,
                "gecos": admin_gecos,
                "groups": list(merged_groups),
                "shell": "/bin/bash",
                "sudo": "ALL=(ALL) NOPASSWD:ALL",
                "lock_passwd": True,
                "ssh_authorized_keys": all_ssh_keys,
            }
        ]

        user_data["ssh_pwauth"] = False
        user_data["disable_root"] = True

        # Pakete
        packages = {"qemu-guest-agent", "curl", "wget", "wtmpdb", "locales"}
        packages.update(merged_packages)
        if additional_packages:
            packages.update(additional_packages)
        user_data["packages"] = list(packages)

        # APT Sources
        if merged_apt_sources:
            user_data["apt"] = {"sources": merged_apt_sources}

        # Write Files
        write_files = list(merged_write_files)

        # Login Welcome Script (profile.d) - zeigt Last Login + Banner bei jedem Login
        welcome_script = f'''#!/bin/bash
# Login Welcome - Ansible Commander
# Wird bei jedem Login ausgefuehrt

# Nur bei interaktiven Shells
[[ $- != *i* ]] && return

# Bildschirm leeren
clear

# Last Login Info (vorheriger Login, nicht aktueller)
# Zweite Zeile = vorheriger Login (erste Zeile ist aktueller)
LAST_INFO=$(last -2 -F $USER 2>/dev/null | sed -n '2p')
if [ -n "$LAST_INFO" ] && [[ "$LAST_INFO" != *"wtmpdb begins"* ]]; then
    LAST_IP=$(echo "$LAST_INFO" | awk '{{print $3}}')
    LAST_DATE=$(echo "$LAST_INFO" | awk '{{print $4, $5, $6, $7, $8}}')

    # Falls IP ein tty ist, als "console" anzeigen
    if [[ "$LAST_IP" == pts/* ]] || [[ "$LAST_IP" == tty* ]]; then
        LAST_IP="console"
    fi

    echo "Last login: $LAST_DATE from $LAST_IP"
    echo ""
fi

# OS-Info laden
. /etc/os-release 2>/dev/null || PRETTY_NAME="Linux"

# Banner anzeigen
cat << EOF
===============================================
   Homelab VM - Managed by Ansible Commander
===============================================

Hostname: $(hostname)
System:   ${{PRETTY_NAME}}
Admin:    {admin_username}

Useful commands:
  htop          - Process monitor
  btop          - Resource monitor
  journalctl -f - Live system logs

===============================================
EOF
'''
        write_files.append({
            "path": "/etc/profile.d/00-welcome.sh",
            "content": welcome_script,
            "permissions": "0755",
        })

        # MOTD deaktivieren (wir nutzen profile.d stattdessen)
        write_files.append({
            "path": "/etc/motd",
            "content": "",
            "permissions": "0644",
        })

        # Locale-Generierung sicherstellen
        write_files.append({
            "path": "/etc/locale.gen",
            "content": "de_DE.UTF-8 UTF-8\nen_US.UTF-8 UTF-8\n",
            "permissions": "0644",
        })

        if merged_sysctl:
            sysctl_content = "\n".join([f"{k} = {v}" for k, v in merged_sysctl.items()])
            write_files.append({
                "path": "/etc/sysctl.d/99-cloud-init.conf",
                "content": f"# Cloud-Init merged profiles\n{sysctl_content}\n",
            })
        if merged_limits:
            write_files.append({
                "path": "/etc/security/limits.d/99-cloud-init.conf",
                "content": "\n".join(merged_limits) + "\n",
            })
        if write_files:
            user_data["write_files"] = write_files

        # Run Commands
        runcmd = []

        # Locale generieren (muss frueh passieren)
        runcmd.append("locale-gen")
        runcmd.append("update-locale LANG=de_DE.UTF-8")

        if merged_sysctl:
            runcmd.append("sysctl --system")
        for service in merged_services:
            runcmd.append(f"systemctl enable {service}")
            runcmd.append(f"systemctl start {service}")
        runcmd.extend(["systemctl enable qemu-guest-agent", "systemctl start qemu-guest-agent"])
        runcmd.extend(merged_runcmd_extra)
        if additional_runcmd:
            runcmd.extend(additional_runcmd)

        # Phone Home Callback
        if enable_phone_home and phone_home_url:
            phone_home_cmd = f'''curl -sf -X POST "{phone_home_url}" \\
  -H "Content-Type: application/json" \\
  -d '{{"hostname": "$(hostname)", "instance_id": "$(cat /var/lib/cloud/data/instance-id 2>/dev/null || echo unknown)", "ip_address": "$(hostname -I | awk '{{print $1}}')", "status": "completed", "timestamp": "$(date -Iseconds)"}}' \\
  || echo "Phone-home callback failed"'''
            runcmd.append(phone_home_cmd)

        if runcmd:
            user_data["runcmd"] = runcmd

        # Phone Home (natives Cloud-Init Modul als Backup)
        if enable_phone_home and phone_home_url:
            user_data["phone_home"] = {
                "url": phone_home_url,
                "post": ["instance_id", "hostname", "fqdn"],
                "tries": 3,
            }

        profile_names = ", ".join([p.value for p in profiles if p != CloudInitProfile.NONE])
        user_data["final_message"] = f"Cloud-Init completed for {hostname} with profiles: {profile_names}"

        yaml_content = yaml.dump(user_data, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return f"#cloud-config\n{yaml_content}"

    def get_snippet_filename(self, vm_name: str) -> str:
        """Gibt den Dateinamen fuer einen VM-spezifischen Cloud-Init Snippet zurueck"""
        return f"cloud-init-{vm_name}.yaml"

    async def get_snippet_proxmox_ref(
        self,
        vm_name: str,
        db: Optional[AsyncSession] = None,
    ) -> Optional[str]:
        """
        Gibt die Proxmox-Referenz fuer einen VM-spezifischen Cloud-Init Snippet zurueck.

        Args:
            vm_name: Name der VM
            db: Datenbank-Session (fuer Settings aus DB)

        Returns:
            Proxmox-Referenz (z.B. "nas:snippets/cloud-init-vm.yaml") oder None wenn nicht konfiguriert
        """
        if db:
            settings_service = CloudInitSettingsService(db)
            nas_config = await settings_service.get_nas_snippets_config()
            nas_ref = nas_config.get("ref")
            if nas_ref:
                return f"{nas_ref}/{self.get_snippet_filename(vm_name)}"
        elif self.FALLBACK_NAS_SNIPPETS_REF:
            return f"{self.FALLBACK_NAS_SNIPPETS_REF}/{self.get_snippet_filename(vm_name)}"

        return None

    async def write_snippet_to_nas(
        self,
        vm_name: str,
        content: str,
        proxmox_node: str,
        db: Optional[AsyncSession] = None,
    ) -> bool:
        """
        Schreibt einen Cloud-Init Snippet auf das NAS via SSH zum Proxmox-Node.

        Args:
            vm_name: Name der VM (wird fuer Dateiname verwendet)
            content: Cloud-Init YAML Inhalt
            proxmox_node: Proxmox-Node mit NAS-Zugriff
            db: Datenbank-Session (fuer Settings aus DB)

        Returns:
            True bei Erfolg, False bei Fehler
        """
        # NAS-Pfad aus Settings laden
        if db:
            settings_service = CloudInitSettingsService(db)
            nas_config = await settings_service.get_nas_snippets_config()
            nas_path = nas_config.get("path")
        else:
            nas_path = self.FALLBACK_NAS_SNIPPETS_PATH

        if not nas_path:
            logger.warning("NAS Snippets-Pfad nicht konfiguriert - ueberspringe Snippet-Upload")
            return False

        filename = self.get_snippet_filename(vm_name)
        remote_path = f"{nas_path}/{filename}"

        try:
            # Schreibe Content in temporaere Datei
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                f.write(content)
                temp_path = f.name

            # Kopiere via SCP zum Proxmox-Node
            node_ip = self._get_node_ip(proxmox_node)
            scp_cmd = [
                "scp",
                "-i", "/root/.ssh/ansible_id",
                "-o", "StrictHostKeyChecking=no",
                "-o", "BatchMode=yes",
                temp_path,
                f"root@{node_ip}:{remote_path}"
            ]

            result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=30)

            # Temporaere Datei loeschen
            os.unlink(temp_path)

            if result.returncode != 0:
                logger.error(f"SCP Fehler: {result.stderr}")
                return False

            logger.info(f"Cloud-Init Snippet {filename} erfolgreich auf NAS geschrieben")
            return True

        except Exception as e:
            logger.error(f"Fehler beim Schreiben des Cloud-Init Snippets: {e}")
            return False

    async def delete_snippet_from_nas(
        self,
        vm_name: str,
        proxmox_node: str,
        db: Optional[AsyncSession] = None,
    ) -> bool:
        """
        Loescht einen Cloud-Init Snippet vom NAS.

        Args:
            vm_name: Name der VM
            proxmox_node: Proxmox-Node mit NAS-Zugriff
            db: Datenbank-Session (fuer Settings aus DB)

        Returns:
            True bei Erfolg oder wenn Datei nicht existiert
        """
        # NAS-Pfad aus Settings laden
        if db:
            settings_service = CloudInitSettingsService(db)
            nas_config = await settings_service.get_nas_snippets_config()
            nas_path = nas_config.get("path")
        else:
            nas_path = self.FALLBACK_NAS_SNIPPETS_PATH

        if not nas_path:
            logger.warning("NAS Snippets-Pfad nicht konfiguriert - ueberspringe Snippet-Loeschung")
            return True  # Kein Fehler, nur nicht konfiguriert

        filename = self.get_snippet_filename(vm_name)
        remote_path = f"{nas_path}/{filename}"

        try:
            node_ip = self._get_node_ip(proxmox_node)
            ssh_cmd = [
                "ssh",
                "-i", "/root/.ssh/ansible_id",
                "-o", "StrictHostKeyChecking=no",
                "-o", "BatchMode=yes",
                f"root@{node_ip}",
                f"rm -f {remote_path}"
            ]

            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                logger.error(f"SSH Fehler beim Loeschen: {result.stderr}")
                return False

            logger.info(f"Cloud-Init Snippet {filename} vom NAS geloescht")
            return True

        except Exception as e:
            logger.error(f"Fehler beim Loeschen des Cloud-Init Snippets: {e}")
            return False

    def _get_node_ip(self, node_name: str) -> str:
        """Gibt die IP-Adresse eines Proxmox-Nodes zurueck (Beispiel-Konfiguration)"""
        node_ips = {
            "pve-node-01": "10.0.0.101",
            "pve-node-02": "10.0.0.102",
            "pve-node-03": "10.0.0.103",
            "pve-node-04": "10.0.0.104",
            "pve-node-05": "10.0.0.105",
            "pve-node-06": "10.0.0.106",
        }
        return node_ips.get(node_name, "10.0.0.101")  # Default: pve-node-01


# Singleton-Instanz
cloud_init_service = CloudInitService()
