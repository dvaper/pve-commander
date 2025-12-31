# Changelog

## v1.1.0 (2025-12-31)

Erste stabile Version von PVE Commander - Proxmox VM Management System.

### VM-Management
- VM-Deployment via Proxmox und Terraform
- Power Control: Start, Stop, Shutdown, Reboot
- Snapshot Management: Erstellen, Loeschen, Rollback
- VM Cloning: Full Clone und Linked Clone
- VM Migration zwischen Proxmox-Nodes
- Backup & Restore fuer VMs und Container
- Dynamische Node-Erkennung aus Proxmox-Cluster
- Storage und Templates dynamisch aus Proxmox geladen
- Node-IP wird automatisch via DNS aufgeloest

### RBAC (Role-Based Access Control)
- Rollen und Berechtigungen verwalten
- Benutzer-Rollen-Zuweisung
- Gruppen- und Playbook-Zuordnung
- Host-Zuweisungen

### Audit-Logging
- Manipulationssichere Hash-Chain
- Chain-Verifikation im Frontend
- Export als JSON/CSV

### Ansible Integration
- Playbook Execution mit Live-Output via WebSocket
- Inventory Browser und Editor
- Playbook Editor mit YAML-Syntax-Highlighting
- Ansible remote_tmp Konfiguration (verhindert Warnings)
- Optimierte Ausfuehrung (Pipelining, SSH ControlPersist, Fact Caching)
- Ansible-Gruppe Option "Nicht ins Inventory aufnehmen"

### Cloud-Init
- 13 spezialisierte Profile (Docker, K8s, Web, DB, etc.)
- SSH-Hardening und Security Best Practices

### NetBox Integration
- Integrierte IPAM/DCIM Loesung
- Automatische IP-Vergabe aus konfigurierten Prefixes
- VLAN-Verwaltung
- NetBox Superuser und API-Token bei Erstinstallation automatisch erstellt
- Manueller NetBox-Admin Sync Button

### Benachrichtigungen
- E-Mail via SMTP
- Gotify Push-Benachrichtigungen
- Webhook-Integration mit HMAC-Signatur

### UI/UX
- 5 Farbthemes mit Light/Dark Mode
- Dashboard mit Cluster-Status und Speicherauslastung
- Command Palette (Cmd+K)
- Security Status Panel fuer Administratoren
- Backup-Tabelle mit Download und Loeschen-Buttons

### Infrastruktur
- Docker Compose Setup mit integriertem NetBox
- Non-root Container-Ausfuehrung
- HTTP Security Headers
- Rate-Limiting und Authentifizierung
