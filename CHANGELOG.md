# Changelog

## v1.2.2 (2025-12-31)

- Terraform State: Raw State Data ohne Hoehenbegrenzung (min 500px)

## v1.2.1 (2025-12-31)

- Terraform State: Raw State Data Bereich vergroessert

## v1.2.0 (2025-12-31)

- NetBox Scan-Cache: Persistente Speicherung in Datenbank
- Auto-Scan beim Laden mit Delta-Erkennung (neue/entfernte VLANs/VMs)

## v1.1.0 (2025-12-31)

Erste stabile Version - Proxmox VM Management System.

**Kernfunktionen:**
- VM-Lifecycle: Deployment, Power Control, Snapshots, Cloning, Migration, Backup
- Ansible: Playbook-Ausfuehrung mit Live-Output (WebSocket)
- NetBox: Integriertes IPAM mit automatischer IP-Vergabe
- RBAC: Rollen, Berechtigungen, Gruppen- und Host-Zuweisungen
- Audit: Manipulationssichere Hash-Chain mit Export

**Infrastruktur:**
- Docker Compose mit integriertem NetBox
- 13 Cloud-Init Profile (Docker, K8s, Web, DB, etc.)
- 5 Farbthemes, Command Palette, Security Panel
