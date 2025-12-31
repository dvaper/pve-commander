# Proxmox VM Modul - Variablen
# Automatisch verwaltet durch PVE Commander

# =============================================================================
# Basis-Konfiguration
# =============================================================================

variable "name" {
  description = "VM-Name (Hostname)"
  type        = string
}

variable "vmid" {
  description = "VM-ID in Proxmox"
  type        = number
}

variable "target_node" {
  description = "Proxmox-Node fuer die VM"
  type        = string
}

variable "description" {
  description = "VM-Beschreibung"
  type        = string
  default     = ""
}

# =============================================================================
# Ressourcen
# =============================================================================

variable "cores" {
  description = "Anzahl CPU-Kerne"
  type        = number
  default     = 2
}

variable "memory" {
  description = "RAM in MB"
  type        = number
  default     = 2048
}

variable "disk_size" {
  description = "Disk-Groesse in GB"
  type        = number
  default     = 20
}

variable "disk_storage" {
  description = "Storage-Pool fuer VM-Disk (aus Proxmox)"
  type        = string
  # Kein Default - wird dynamisch aus Proxmox geladen
}

# =============================================================================
# Netzwerk
# =============================================================================

variable "ip_address" {
  description = "IP-Adresse der VM"
  type        = string
}

variable "gateway" {
  description = "Gateway-IP"
  type        = string
}

variable "bridge" {
  description = "Netzwerk-Bridge (z.B. vmbr0, vmbr60)"
  type        = string
  default     = "vmbr0"  # Standard-Bridge
}

variable "netmask" {
  description = "Netzmaske in CIDR-Notation"
  type        = number
  default     = 24
}

# =============================================================================
# Template & Cloud-Init
# =============================================================================

variable "template_id" {
  description = "Template VMID zum Klonen (aus Proxmox)"
  type        = number
  # Kein Default - wird dynamisch aus Proxmox geladen
}

variable "template_node" {
  description = "Node auf dem das Template liegt (aus Proxmox)"
  type        = string
  # Kein Default - wird dynamisch ermittelt
}

variable "ssh_user" {
  description = "SSH-Benutzer fuer Cloud-Init"
  type        = string
  default     = "deploy"
}

variable "ssh_keys" {
  description = "SSH Public Keys"
  type        = list(string)
  default     = []
}

variable "dns_servers" {
  description = "DNS-Server"
  type        = list(string)
  default     = ["1.1.1.1", "8.8.8.8"]  # Cloudflare + Google als universelle Defaults
}

variable "cloud_init_user_data" {
  description = "Custom Cloud-Init User-Data (Base64)"
  type        = string
  default     = ""
}
