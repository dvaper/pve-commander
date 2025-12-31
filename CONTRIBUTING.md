# Beitragen zu PVE Commander

Vielen Dank für Ihr Interesse, zu PVE Commander beizutragen! Dieses Dokument beschreibt die Richtlinien und den Prozess für Beiträge.

## Inhaltsverzeichnis

- [Verhaltenskodex](#verhaltenskodex)
- [Wie kann ich beitragen?](#wie-kann-ich-beitragen)
- [Entwicklungsumgebung](#entwicklungsumgebung)
- [Pull Request Prozess](#pull-request-prozess)
- [Coding Standards](#coding-standards)
- [Commit Messages](#commit-messages)

## Verhaltenskodex

Dieses Projekt und alle Teilnehmer unterliegen unserem [Verhaltenskodex](CODE_OF_CONDUCT.md). Durch die Teilnahme wird erwartet, dass Sie diesen Kodex einhalten.

## Wie kann ich beitragen?

### Bugs melden

- Stellen Sie sicher, dass der Bug nicht bereits gemeldet wurde
- Erstellen Sie ein Issue mit dem Bug Report Template
- Beschreiben Sie das Problem detailliert mit Schritten zur Reproduktion

### Features vorschlagen

- Prüfen Sie, ob das Feature bereits vorgeschlagen wurde
- Erstellen Sie ein Issue mit dem Feature Request Template
- Beschreiben Sie den Anwendungsfall und den erwarteten Nutzen

### Code beitragen

1. Forken Sie das Repository
2. Erstellen Sie einen Feature-Branch (`git checkout -b feature/mein-feature`)
3. Implementieren Sie Ihre Änderungen
4. Schreiben Sie Tests falls anwendbar
5. Erstellen Sie einen Pull Request

## Entwicklungsumgebung

### Voraussetzungen

- Docker und Docker Compose
- Node.js 18+ (für Frontend-Entwicklung)
- Python 3.11+ (für Backend-Entwicklung)

### Setup

```bash
# Repository klonen
git clone https://github.com/dvaper/pve-commander.git
cd pve-commander

# Entwicklungsumgebung starten
docker compose -f docker-compose.dev.yml up -d

# Frontend-Entwicklung
cd frontend
npm install
npm run dev

# Backend-Entwicklung
cd backend
pip install -r requirements-dev.txt
```

### Projektstruktur

```
pve-commander/
├── backend/           # FastAPI Backend
│   ├── app/
│   │   ├── routers/   # API Endpoints
│   │   ├── services/  # Business Logic
│   │   ├── models/    # SQLAlchemy Models
│   │   └── schemas/   # Pydantic Schemas
│   └── tests/
├── frontend/          # Vue.js Frontend
│   ├── src/
│   │   ├── components/
│   │   ├── views/
│   │   ├── stores/
│   │   └── composables/
│   └── tests/
└── docs/
```

## Pull Request Prozess

1. **Branch erstellen**: Basierend auf `main`
2. **Änderungen implementieren**: Mit aussagekräftigen Commits
3. **Tests**: Stellen Sie sicher, dass alle Tests bestehen
4. **Pull Request erstellen**: Mit ausgefülltem Template
5. **Review**: Warten Sie auf Code Review
6. **Merge**: Nach Genehmigung wird der PR gemergt

### PR Checkliste

- [ ] Code folgt den Coding Standards
- [ ] Tests wurden hinzugefügt/aktualisiert
- [ ] Dokumentation wurde aktualisiert (falls nötig)
- [ ] Commit Messages folgen den Konventionen
- [ ] PR Template wurde ausgefüllt

## Coding Standards

### Python (Backend)

- PEP 8 Style Guide
- Type Hints verwenden
- Docstrings für öffentliche Funktionen
- Maximale Zeilenlänge: 100 Zeichen

```python
async def get_vm_by_id(vm_id: int, db: AsyncSession) -> VM | None:
    """
    Holt eine VM anhand ihrer ID.

    Args:
        vm_id: Die ID der VM
        db: Datenbank-Session

    Returns:
        Die VM oder None wenn nicht gefunden
    """
    ...
```

### TypeScript/Vue (Frontend)

- ESLint Konfiguration einhalten
- Composition API bevorzugen
- TypeScript für neue Komponenten

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'

interface Props {
  vmId: number
}

const props = defineProps<Props>()
const loading = ref(false)
</script>
```

## Commit Messages

Wir verwenden konventionelle Commit Messages:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

- `feat`: Neues Feature
- `fix`: Bugfix
- `docs`: Dokumentation
- `style`: Formatierung (kein Code-Change)
- `refactor`: Code-Refactoring
- `test`: Tests
- `chore`: Maintenance

### Beispiele

```
feat(vm): VM-Cloning Funktion hinzugefügt

fix(auth): Token-Refresh bei abgelaufenem JWT

docs: README Installation aktualisiert

chore: Dependencies aktualisiert
```

## Fragen?

Bei Fragen erstellen Sie bitte ein Issue oder starten eine Discussion.
