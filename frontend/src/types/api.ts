/**
 * PVE Commander - API Type Definitions
 *
 * Diese Datei definiert TypeScript-Typen fuer die API-Responses.
 * Kann schrittweise verwendet werden waehrend der JS->TS Migration.
 */

// =============================================================================
// Auth & User Types
// =============================================================================

export interface User {
  id: number
  username: string
  email: string
  is_admin: boolean
  is_super_admin: boolean
  is_active: boolean
  theme: string
  dark_mode: 'dark' | 'light' | 'system'
  sidebar_logo: 'icon' | 'full'
  ui_beta: boolean
  created_at: string
  updated_at?: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: 'bearer'
}

export interface UserSettings {
  theme: string
  dark_mode: 'dark' | 'light' | 'system'
  sidebar_logo: 'icon' | 'full'
  ui_beta: boolean
}

// =============================================================================
// VM & Terraform Types
// =============================================================================

export interface VM {
  name: string
  vmid: number
  node: string
  ip_address: string
  status: 'running' | 'stopped' | 'paused' | 'unknown'
  template_id: number
  template_name?: string
  cpus: number
  memory: number
  disk_size: number
  vlan: number
  storage: string
  ansible_groups: string[]
  ssh_user: string
  created_at: string
  updated_at?: string
  // State-bezogen
  state_status?: 'synced' | 'drift' | 'orphaned' | 'new'
  proxmox_status?: 'exists' | 'missing' | 'unknown'
}

export interface VMCreateRequest {
  name: string
  node: string
  ip_address: string
  template_id: number
  cpus?: number
  memory?: number
  disk_size?: number
  vlan?: number
  storage?: string
  ansible_groups?: string[]
  ssh_user?: string
}

export interface VMTemplate {
  id: number
  name: string
  template_id: number
  description?: string
  cpus: number
  memory: number
  disk_size: number
  storage: string
  os_type?: string
}

export interface TerraformExecution {
  id: number
  action: 'plan' | 'apply' | 'destroy'
  vm_name?: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  output?: string
  started_at: string
  completed_at?: string
}

// =============================================================================
// Proxmox Types
// =============================================================================

export interface ProxmoxNode {
  name: string
  status: 'online' | 'offline' | 'unknown'
  cpu_usage: number
  cpu_total: number
  memory_used: number
  memory_total: number
  memory_percent: number
  uptime: number
}

export interface ClusterStats {
  nodes_online: number
  nodes_total: number
  cpu_total: number
  cpu_usage_avg: number
  memory_total: number
  memory_used: number
  memory_percent: number
  vms_running: number
  vms_total: number
  nodes: ProxmoxNode[]
}

// =============================================================================
// Inventory Types
// =============================================================================

export interface InventoryHost {
  name: string
  ip?: string
  groups: string[]
  vars?: Record<string, unknown>
  managed: boolean
}

export interface InventoryGroup {
  name: string
  hosts: string[]
  vars?: Record<string, unknown>
  children?: string[]
}

// =============================================================================
// Execution Types
// =============================================================================

export interface Execution {
  id: number
  playbook: string
  targets: string[]
  started_at: string
  completed_at?: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  exit_code?: number
  output?: string
  user_id: number
  username?: string
}

export interface ExecutionLog {
  id: number
  execution_id: number
  timestamp: string
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'
  message: string
}

// =============================================================================
// NetBox Types
// =============================================================================

export interface NetBoxVM {
  id: number
  name: string
  status: string
  primary_ip4?: string
  cluster?: string
  site?: string
  role?: string
  platform?: string
  vcpus?: number
  memory?: number
  disk?: number
}

export interface NetBoxPrefix {
  id: number
  prefix: string
  vlan?: {
    id: number
    vid: number
    name: string
  }
  site?: string
  status: string
  description?: string
}

export interface NetBoxIPAddress {
  id: number
  address: string
  status: string
  assigned_object_type?: string
  assigned_object_id?: number
  dns_name?: string
}

// =============================================================================
// Notification Types
// =============================================================================

export interface Notification {
  id: string
  title: string
  message?: string
  type: 'success' | 'error' | 'warning' | 'info' | 'loading'
  persistent: boolean
  timeout?: number
  createdAt: number
}

// =============================================================================
// API Response Types
// =============================================================================

export interface ApiError {
  error: {
    error_code: string
    message: string
    details?: Record<string, unknown>
  }
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'starting'
  services: {
    api: ServiceStatus
    netbox: ServiceStatus
    proxmox: ServiceStatus
  }
}

export interface ServiceStatus {
  status: 'healthy' | 'degraded' | 'error' | 'starting' | 'not_configured' | 'unknown'
  message: string
  nodes?: number
}
