"""
AppSettings Model - Anwendungsweite Einstellungen
"""
from sqlalchemy import Column, Integer, String, Text

from app.database import Base


class AppSettings(Base):
    """Key-Value Store für Anwendungseinstellungen"""
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)  # JSON für komplexe Werte
    description = Column(String(255), nullable=True)

    def __repr__(self):
        return f"<AppSettings(key={self.key})>"


# Bekannte Settings-Keys
SETTING_DEFAULT_GROUPS = "default_groups"  # JSON-Array der Standard-Gruppen
SETTING_DEFAULT_PLAYBOOKS = "default_playbooks"  # JSON-Array der Standard-Playbooks
SETTING_NETBOX_EXTERNAL_URL = "netbox_external_url"  # Externe URL fuer NetBox UI
