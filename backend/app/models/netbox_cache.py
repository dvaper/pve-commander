"""
NetBox Scan Cache Model - Cached Proxmox scan results
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime

from app.database import Base


class NetBoxScanCache(Base):
    """Cache fuer Proxmox-Scan-Ergebnisse (VLANs und VMs)"""
    __tablename__ = "netbox_scan_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cache_type = Column(String(50), nullable=False, index=True)  # 'vlans' oder 'vms'
    data = Column(Text, nullable=False)  # JSON-encoded scan results
    data_hash = Column(String(64), nullable=True)  # SHA256 hash for change detection
    scanned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    items_count = Column(Integer, default=0)  # Anzahl der Eintraege

    def __repr__(self):
        return f"<NetBoxScanCache(type={self.cache_type}, items={self.items_count}, scanned_at={self.scanned_at})>"


# Cache Types
CACHE_TYPE_VLANS = "vlans"
CACHE_TYPE_VMS = "vms"
