# Changelog

## v1.0.12 (2025-12-31)

### Bugfixes
- Backup-Loeschen-Button in Settings-Tab hinzugefuegt (war nicht vorhanden)
- Delete-Dialog und Funktion in SettingsView implementiert

## v1.0.11 (2025-12-31)

### Bugfixes
- Backup-Tabelle: Horizontales Scrolling fuer schmale Bildschirme
- Aktionen-Buttons (Download, Restore, Loeschen) immer sichtbar

## v1.0.10 (2025-12-31)

### Bugfixes
- NetBox Token/URL nach Setup-Wizard sofort verfuegbar (Hot-Reload Fix)
- NetBox User-Sync Timeout von 5 auf 10 Minuten erhoeht (fuer langsame Erstinstallation)
- Backup-Tabelle: Aktionen-Spalte verbreitert und rechtsbuendig

### Neue Features
- Manueller NetBox-Admin Sync Button (Einstellungen > NetBox > Benutzer verwalten)

## v1.0.9 (2025-12-31)

### Bugfixes
- Ansible Inventory: Deployed VMs werden automatisch zur "terraform" Gruppe hinzugefuegt
- CPU-Anzeige in Cluster-Kapazitaet korrigiert (Prozent statt Dezimalwert)
- Backup loeschen: Verbesserte Fehlerbehandlung und Dialog-Cleanup

### Verbesserungen
- Ansible remote_tmp Konfiguration hinzugefuegt (verhindert Warnings)
- Docker-Install Playbook: Hinweis zur erwarteten Dauer (2-4 Minuten)
- Neue Ansible-Gruppe Option "Nicht ins Inventory aufnehmen" fuer explizites Ausschliessen

## v1.0.8 (2025-12-31)

### Verbesserungen
- Storage und Templates werden dynamisch aus Proxmox geladen
- Node-IP wird automatisch via DNS aufgeloest
- Keine hardcodierten Defaults mehr (local-ssd, 940001, pve-node-01, VLAN 60)
- DNS-Default geaendert zu Cloudflare/Google (1.1.1.1, 8.8.8.8)

### Portabilitaet
- Installation auf anderen Systemen ohne Anpassung moeglich
- Alle Werte werden zur Laufzeit aus Proxmox/NetBox geladen

## v1.0.7 (2025-12-31)

### Bugfixes
- DOCKER_GID Default auf 989 geaendert (Debian Standard)
- NetBox Superuser und API-Token werden automatisch bei Erstinstallation erstellt

### Security
- NetBox API Token wird nun zufaellig generiert statt generischem Default-Wert

## v1.0.6 (2025-12-31)

### Aenderungen
- Docker Compose Profiles fuer NetBox entfernt (Rollback)
- Alle Services starten wieder gemeinsam mit `docker compose up -d`
- Stabilerer Installationsablauf

## v1.0.3 (2025-12-31)

### Bugfixes
- NetBox erstellt bei Erstinstallation keinen doppelten Admin-User mehr (SKIP_SUPERUSER=true)

## v1.0.2 (2025-12-31)

### Bugfixes
- Service-Status Dialog zeigt jetzt korrekt den Status aller Services (API, NetBox, Proxmox)
- Inventory View laedt Daten automatisch bei Navigation und Reaktivierung neu
- VM-Liste laedt Daten automatisch bei Reaktivierung neu
- NetBox External URL wird im Setup-Wizard automatisch basierend auf Browser-Adresse gesetzt
- Docker Socket Permissions fuer NetBox User Sync korrigiert
- SSH Public Key wird automatisch fuer add-ssh-key Playbook injiziert
- Korrekter Pfad fuer ansible.cfg (/data/config statt /data)

### Verbesserungen
- NetBox-Benutzerverwaltung in Einstellungen verlinkt (Settings > NetBox > Benutzer verwalten)
- Ansible-Ausfuehrung optimiert (Pipelining, SSH ControlPersist, Fact Caching)

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
