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
  description = "Storage-Pool fuer VM-Disk"
  type        = string
  default     = "local-ssd"
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
  description = "Netzwerk-Bridge (z.B. vmbr60)"
  type        = string
  default     = "vmbr60"
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
  description = "Template VMID zum Klonen"
  type        = number
  default     = 940001
}

variable "template_node" {
  description = "Node auf dem das Template liegt"
  type        = string
  default     = "pve-node-01"
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
  default     = ["10.0.0.1", "1.1.1.1"]
}

variable "cloud_init_user_data" {
  description = "Custom Cloud-Init User-Data (Base64)"
  type        = string
  default     = ""
}
