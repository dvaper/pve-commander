# Sicherheitsrichtlinie / Security Policy

## Unterstützte Versionen

| Version | Unterstützt        |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Sicherheitslücke melden

Wir nehmen die Sicherheit von PVE Commander ernst. Wenn Sie eine Sicherheitslücke entdecken, bitten wir Sie, diese verantwortungsvoll zu melden.

### Meldeprozess

1. **Nicht öffentlich melden**: Erstellen Sie kein öffentliches GitHub Issue für Sicherheitslücken.

2. **Private Meldung**: Nutzen Sie GitHubs [Private Vulnerability Reporting](https://github.com/dvaper/pve-commander/security/advisories/new) oder kontaktieren Sie die Maintainer direkt.

3. **Informationen bereitstellen**:
   - Beschreibung der Sicherheitslücke
   - Schritte zur Reproduktion
   - Betroffene Version(en)
   - Mögliche Auswirkungen
   - Vorgeschlagene Lösung (falls vorhanden)

### Reaktionszeit

- **Bestätigung**: Innerhalb von 48 Stunden
- **Erste Einschätzung**: Innerhalb von 7 Tagen
- **Fix/Patch**: Abhängig von Schweregrad und Komplexität

### Nach der Meldung

- Wir werden Sie über den Fortschritt informieren
- Wir koordinieren die Veröffentlichung mit Ihnen
- Nach dem Fix werden Sie in den Release Notes erwähnt (falls gewünscht)

## Sicherheitsmaßnahmen

PVE Commander implementiert folgende Sicherheitsmaßnahmen:

### Authentifizierung & Autorisierung

- JWT-basierte Authentifizierung
- Role-Based Access Control (RBAC)
- Rate-Limiting für Login und sensible Endpoints

### Infrastruktur

- Non-root Container-Ausführung
- HTTP Security Headers (CSP, X-Frame-Options, etc.)
- Docker Healthchecks

### Best Practices für Produktionsumgebungen

```bash
# Sicheren SECRET_KEY generieren
echo "SECRET_KEY=$(openssl rand -hex 32)" >> data/config/.env

# CORS einschränken
echo 'CORS_ORIGINS=["https://your-domain.com"]' >> data/config/.env

# Container neu starten
docker compose restart dpc-api
```

## Bekannte Einschränkungen

- Die Anwendung sollte hinter einem Reverse Proxy mit SSL-Terminierung betrieben werden
- Proxmox API-Tokens sollten mit minimalen Berechtigungen konfiguriert werden
- Regelmäßige Backups der Datenbank werden empfohlen

## Sicherheits-Updates

Sicherheits-Updates werden als Patch-Releases veröffentlicht. Wir empfehlen:

```bash
# Regelmäßig aktualisieren
docker compose pull && docker compose up -d
```
