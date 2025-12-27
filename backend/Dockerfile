# =============================================================================
# Stage 1: Builder - Downloads und Python-Dependencies
# =============================================================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Build-Tools installieren
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Terraform herunterladen
RUN curl -fsSL https://releases.hashicorp.com/terraform/1.10.3/terraform_1.10.3_linux_amd64.zip -o terraform.zip \
    && unzip terraform.zip \
    && rm terraform.zip

# Docker CLI herunterladen
RUN curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.4.1.tgz -o docker.tgz \
    && tar -xzf docker.tgz --strip-components=1 docker/docker \
    && rm docker.tgz

# Python-Dependencies installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ansible-Collections installieren (ansible.posix wird in Playbooks verwendet)
RUN ansible-galaxy collection install ansible.posix

# =============================================================================
# Stage 2: Final - Schlankes Runtime-Image
# =============================================================================
FROM python:3.11-slim

WORKDIR /app

# Timezone
ENV TZ=Europe/Berlin

# Runtime-Dependencies (curl fuer Healthcheck, HIGH-06)
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    git \
    tzdata \
    sshpass \
    curl \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# Binaries aus Builder kopieren
COPY --from=builder /build/terraform /usr/local/bin/
COPY --from=builder /build/docker /usr/local/bin/

# Python-Packages aus Builder kopieren
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/ansible* /usr/local/bin/
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/

# =============================================================================
# HIGH-04: Non-root User fuer bessere Sicherheit
# =============================================================================
# User und Gruppe erstellen (UID/GID 1000 fuer Kompatibilitaet mit Host-Mounts)
RUN groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# App kopieren
COPY app/ ./app/
COPY default-data/ ./default-data/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Verzeichnisse erstellen mit korrekten Berechtigungen
RUN mkdir -p /data/db /data/inventory /data/playbooks /data/roles /data/terraform /data/ssh /data/config \
    && mkdir -p /home/appuser/.ssh /home/appuser/.ansible \
    && chmod 700 /home/appuser/.ssh \
    && chown -R appuser:appgroup /app /data /home/appuser

# Ansible-Collections fuer appuser kopieren
COPY --from=builder /root/.ansible/collections /home/appuser/.ansible/collections
RUN chown -R appuser:appgroup /home/appuser/.ansible

# Git-Konfiguration fuer appuser
RUN su - appuser -c "git config --global --add safe.directory /repo" \
    && su - appuser -c "git config --global credential.helper store"

# Auf non-root User wechseln
USER appuser

# HOME fuer appuser setzen
ENV HOME=/home/appuser

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
