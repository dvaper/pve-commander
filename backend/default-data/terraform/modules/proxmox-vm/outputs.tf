# Proxmox VM Modul - Outputs (bpg/proxmox Provider)
# Automatisch verwaltet durch PVE Commander

output "vmid" {
  description = "VM-ID in Proxmox"
  value       = proxmox_virtual_environment_vm.vm.vm_id
}

output "name" {
  description = "VM-Name"
  value       = proxmox_virtual_environment_vm.vm.name
}

output "target_node" {
  description = "Proxmox-Node"
  value       = proxmox_virtual_environment_vm.vm.node_name
}

output "ip_address" {
  description = "IP-Adresse der VM"
  value       = var.ip_address
}

output "ssh_host" {
  description = "SSH-Host (IP)"
  value       = var.ip_address
}

output "ssh_user" {
  description = "SSH-Benutzer"
  value       = var.ssh_user
}
