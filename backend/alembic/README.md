# Alembic Migrationen

## Verwendung

### Neue Migration erstellen (Autogenerate)
```bash
cd backend
alembic revision --autogenerate -m "Beschreibung der Aenderung"
```

### Migration anwenden
```bash
alembic upgrade head
```

### Migration rueckgaengig machen
```bash
alembic downgrade -1
```

### Status anzeigen
```bash
alembic current
alembic history
```

## Hinweise

- Migrationen werden automatisch aus Model-Aenderungen generiert
- Manuelle Anpassungen sind manchmal noetig (z.B. Daten-Migration)
- Vor dem Deploy immer `alembic upgrade head` ausfuehren

## Struktur

```
alembic/
  env.py              # Konfiguration
  script.py.mako      # Migration-Template
  versions/           # Migration-Dateien
    xxx_description.py
```

## Integration mit bestehenden Migrationen

Die bestehenden manuellen Migrationen in `app/database.py` (`run_migrations()`)
bleiben vorerst bestehen fuer Abwaertskompatibilitaet. Neue Schema-Aenderungen
sollten ueber Alembic erfolgen.
