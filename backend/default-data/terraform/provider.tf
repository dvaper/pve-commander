# PVE Commander - Terraform Provider Konfiguration
# Automatisch verwaltet durch PVE Commander

terraform {
  required_version = ">= 1.0.0"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.70"
    }
  }
}

# Proxmox Provider (bpg) - kompatibel mit Proxmox VE 8.x und 9.x
provider "proxmox" {
  endpoint  = var.proxmox_api_url
  api_token = "${var.proxmox_token_id}=${var.proxmox_token_secret}"
  insecure  = var.proxmox_tls_insecure

  ssh {
    agent = false
  }
}
