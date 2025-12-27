"""
CloudInitSettings Model - Cloud-Init Konfiguration

Speichert konfigurierbare Cloud-Init Einstellungen wie SSH-Keys,
Phone-Home URL und Admin-Username.
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.sql import func

from app.database import Base


class CloudInitSettings(Base):
    """
    Cloud-Init Konfiguration (Singleton)

    Ersetzt die hardcodierten Werte in cloud_init_service.py:
    - DEFAULT_SSH_KEYS
    - PHONE_HOME_URL
    - Admin-Username (z.B. "ansible", "admin")
    - NAS Snippets Pfad
    """
    __tablename__ = "cloud_init_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # SSH Authorized Keys (JSON-Array von Public Keys)
    ssh_authorized_keys = Column(Text, nullable=True)

    # Phone-Home Callback Konfiguration
    phone_home_enabled = Column(Boolean, default=True, nullable=False)
    phone_home_url = Column(String(255), nullable=True)  # None = auto-generate aus Request-Host

    # Admin User fuer Cloud-Init erstellte VMs
    admin_username = Column(String(64), default="ansible", nullable=False)
    admin_gecos = Column(String(128), default="Homelab Admin", nullable=False)

    # NAS Snippets Konfiguration (optional)
    # Pfad auf dem Proxmox-Node wo Cloud-Init Snippets gespeichert werden
    nas_snippets_path = Column(String(255), nullable=True)  # z.B. /mnt/pve/nas/snippets
    # Proxmox Storage-Referenz fuer cicustom
    nas_snippets_ref = Column(String(64), nullable=True)    # z.B. nas:snippets

    # Zeitstempel
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<CloudInitSettings id={self.id} admin={self.admin_username}>"
