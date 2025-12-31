#!/bin/bash
# Entrypoint Script fuer PVE Commander API

# Config-Verzeichnis sicherstellen
mkdir -p /data/config

# Ansible Fact-Cache Verzeichnis erstellen
mkdir -p /tmp/ansible_facts_cache

# Ansible-Konfiguration kopieren (optimierte Einstellungen)
if [ -f "/app/default-data/ansible.cfg" ] && [ ! -f "/data/config/ansible.cfg" ]; then
    echo "Kopiere Ansible-Konfiguration..."
    cp /app/default-data/ansible.cfg /data/config/ansible.cfg
    echo "Ansible-Konfiguration installiert."
fi

# Default-Playbooks synchronisieren (neue kopieren, existierende nicht ueberschreiben)
if [ -d "/app/default-data/playbooks" ] && [ -d "/data/playbooks" ]; then
    echo "Synchronisiere Playbooks..."
    # cp -n = no-clobber, ueberschreibt keine existierenden Dateien
    cp -n /app/default-data/playbooks/*.yml /data/playbooks/ 2>/dev/null || true
    cp -n /app/default-data/playbooks/*.yaml /data/playbooks/ 2>/dev/null || true
    echo "Playbooks synchronisiert."
fi

# Terraform-Module kopieren falls nicht vorhanden
if [ -d "/app/default-data/terraform" ] && [ -d "/data/terraform" ]; then
    # Immer sicherstellen dass modules/ existiert
    if [ ! -d "/data/terraform/modules" ]; then
        echo "Kopiere Terraform-Module nach /data/terraform..."
        cp -r /app/default-data/terraform/modules /data/terraform/
        echo "Terraform-Module installiert."
    fi
    # Provider und Variables kopieren falls nicht vorhanden
    if [ ! -f "/data/terraform/provider.tf" ]; then
        cp /app/default-data/terraform/provider.tf /data/terraform/
        echo "Terraform provider.tf installiert."
    fi
    if [ ! -f "/data/terraform/variables.tf" ]; then
        cp /app/default-data/terraform/variables.tf /data/terraform/
        echo "Terraform variables.tf installiert."
    fi
fi

# Starte die Anwendung
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
