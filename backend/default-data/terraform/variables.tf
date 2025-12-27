# PVE Commander - Terraform Variablen
# Automatisch verwaltet durch PVE Commander

# =============================================================================
# Proxmox API Konfiguration
# =============================================================================

variable "proxmox_api_url" {
  description = "Proxmox API URL (z.B. https://10.0.0.100:8006/api2/json)"
  type        = string
}

variable "proxmox_token_id" {
  description = "Proxmox API Token ID (z.B. terraform@pve!terraform-token)"
  type        = string
}

variable "proxmox_token_secret" {
  description = "Proxmox API Token Secret"
  type        = string
  sensitive   = true
}

variable "proxmox_tls_insecure" {
  description = "TLS-Zertifikat nicht verifizieren"
  type        = bool
  default     = true
}

# =============================================================================
# Standard VM-Einstellungen
# =============================================================================

variable "default_template" {
  description = "Standard VM-Template VMID"
  type        = number
  default     = 940001
}

variable "default_template_node" {
  description = "Node auf dem das Template liegt"
  type        = string
  default     = "pve-node-01"
}

variable "ssh_user" {
  description = "Standard SSH-Benutzer fuer Cloud-Init"
  type        = string
  default     = "deploy"
}

variable "ssh_public_key" {
  description = "SSH Public Key fuer Cloud-Init"
  type        = string
}

variable "default_dns" {
  description = "Standard DNS-Server"
  type        = list(string)
  default     = ["10.0.0.1", "1.1.1.1"]
}
