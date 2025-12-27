/**
 * Roles Store - Pinia Store fuer Rollen-Verwaltung
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/api/client'

export const useRolesStore = defineStore('roles', () => {
  // State
  const roles = ref([])
  const permissions = ref([])
  const loading = ref(false)
  const currentRole = ref(null)

  // Getters
  const systemRoles = computed(() => roles.value.filter(r => r.is_system_role))
  const customRoles = computed(() => roles.value.filter(r => !r.is_system_role))
  const sortedRoles = computed(() =>
    [...roles.value].sort((a, b) => b.priority - a.priority)
  )

  // Permissions grouped by resource
  const permissionsByResource = computed(() => {
    const grouped = {}
    for (const perm of permissions.value) {
      if (!grouped[perm.resource]) {
        grouped[perm.resource] = []
      }
      grouped[perm.resource].push(perm)
    }
    return grouped
  })

  // Actions
  async function fetchRoles() {
    loading.value = true
    try {
      const response = await api.get('/api/roles')
      roles.value = response.data
      return response.data
    } finally {
      loading.value = false
    }
  }

  async function fetchRole(roleId) {
    const response = await api.get(`/api/roles/${roleId}`)
    currentRole.value = response.data
    return response.data
  }

  async function createRole(roleData) {
    const response = await api.post('/api/roles', roleData)
    await fetchRoles()
    return response.data
  }

  async function updateRole(roleId, roleData) {
    const response = await api.put(`/api/roles/${roleId}`, roleData)
    await fetchRoles()
    return response.data
  }

  async function deleteRole(roleId) {
    await api.delete(`/api/roles/${roleId}`)
    await fetchRoles()
  }

  async function fetchPermissions() {
    const response = await api.get('/api/roles/permissions/all')
    permissions.value = response.data
    return response.data
  }

  async function getRolePermissions(roleId) {
    const response = await api.get(`/api/roles/${roleId}/permissions`)
    return response.data
  }

  async function setRolePermissions(roleId, permissionIds) {
    const permissions = permissionIds.map(id => ({
      permission_id: id,
      scope: null,
      is_deny: false,
    }))
    const response = await api.put(`/api/roles/${roleId}/permissions`, {
      permissions,
    })
    return response.data
  }

  async function getRoleUsers(roleId) {
    const response = await api.get(`/api/roles/${roleId}/users`)
    return response.data.users
  }

  async function assignRoleToUser(userId, roleId) {
    const response = await api.post(`/api/users/${userId}/roles`, {
      role_id: roleId,
    })
    return response.data
  }

  async function removeRoleFromUser(userId, roleId) {
    await api.delete(`/api/users/${userId}/roles/${roleId}`)
  }

  function clearCurrentRole() {
    currentRole.value = null
  }

  return {
    // State
    roles,
    permissions,
    loading,
    currentRole,
    // Getters
    systemRoles,
    customRoles,
    sortedRoles,
    permissionsByResource,
    // Actions
    fetchRoles,
    fetchRole,
    createRole,
    updateRole,
    deleteRole,
    fetchPermissions,
    getRolePermissions,
    setRolePermissions,
    getRoleUsers,
    assignRoleToUser,
    removeRoleFromUser,
    clearCurrentRole,
  }
})
