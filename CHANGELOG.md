# Changelog

## v1.0.1 (2025-12-31)

### Bugfixes
- Verfuegbare IP-Adressen werden beim Oeffnen des VM-Erstellungsdialogs korrekt geladen
  - Problem: Wenn kein Default-Preset existierte, wurde `loadAvailableIPs()` nie aufgerufen
  - Loesung: Fallback-Aufruf nach dem Laden der Basisdaten hinzugefuegt

## v1.0.0 - Initial Release (2025-12-31)

### VM-Management
- VM-Deployment via Proxmox und Terraform
- Power Control: Start, Stop, Shutdown, Reboot
- Snapshot Management: Erstellen, Loeschen, Rollback
- VM Cloning: Full Clone und Linked Clone
- VM Migration zwischen Proxmox-Nodes
- Backup & Restore fuer VMs und Container
- Dynamische Node-Erkennung aus Proxmox-Cluster

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

### Cloud-Init
- 13 spezialisierte Profile (Docker, K8s, Web, DB, etc.)
- SSH-Hardening und Security Best Practices

### NetBox Integration
- Integrierte IPAM/DCIM Loesung
- Automatische IP-Vergabe aus konfigurierten Prefixes
- VLAN-Verwaltung

### Benachrichtigungen
- E-Mail via SMTP
- Gotify Push-Benachrichtigungen
- Webhook-Integration mit HMAC-Signatur

### UI/UX
- 5 Farbthemes mit Light/Dark Mode
- Dashboard mit Cluster-Status und Speicherauslastung
- Command Palette (Cmd+K)
- Security Status Panel fuer Administratoren

### Infrastruktur
- Docker Compose Setup mit integriertem NetBox
- Non-root Container-Ausfuehrung
- HTTP Security Headers
- Rate-Limiting und Authentifizierung
