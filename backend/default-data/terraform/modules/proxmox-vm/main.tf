# Proxmox VM Modul (bpg/proxmox Provider)
# Erstellt eine VM aus einem Cloud-Init Template

terraform {
  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = ">= 0.89.0"
    }
  }
}

resource "proxmox_virtual_environment_vm" "vm" {
  name        = var.name
  node_name   = var.target_node
  vm_id       = var.vmid
  description = var.description

  # VM aus Template klonen
  clone {
    vm_id     = var.template_id
    node_name = var.template_node
    full      = true
  }

  # CPU Konfiguration
  cpu {
    cores = var.cores
    type  = "host"
  }

  # RAM
  memory {
    dedicated = var.memory
  }

  # Boot-Disk (wird vom Template geklont und resized)
  disk {
    interface    = "scsi0"
    size         = var.disk_size
    datastore_id = var.disk_storage
    file_format  = "qcow2"
  }

  # Netzwerk
  network_device {
    bridge = var.bridge
    model  = "virtio"
  }

  # Cloud-Init Konfiguration
  initialization {
    datastore_id = var.disk_storage

    # Hostname aus VM-Name setzen
    hostname = var.name

    ip_config {
      ipv4 {
        address = "${var.ip_address}/${var.netmask}"
        gateway = var.gateway
      }
    }

    user_account {
      username = var.ssh_user
      keys     = var.ssh_keys
    }

    dns {
      servers = var.dns_servers
    }
  }

  # QEMU Guest Agent
  agent {
    enabled = true
    timeout = "2m"
  }

  # Startup-Optionen
  on_boot = true
  started = true

  # Timeouts fuer langsame Storage-Operationen
  timeout_clone = 600

  lifecycle {
    ignore_changes = [
      initialization,
    ]
  }
}
