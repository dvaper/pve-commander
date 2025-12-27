/**
 * Inventory Store - Hosts und Gruppen
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api/client'

export const useInventoryStore = defineStore('inventory', () => {
  // State
  const hosts = ref([])
  const groups = ref([])
  const loading = ref(false)
  const error = ref(null)

  // Actions
  async function fetchHosts() {
    loading.value = true
    error.value = null

    try {
      const response = await api.get('/api/inventory/hosts')
      hosts.value = response.data
      return response.data
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchGroups() {
    loading.value = true
    error.value = null

    try {
      const response = await api.get('/api/inventory/groups')
      groups.value = response.data
      return response.data
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchAll() {
    await Promise.all([fetchHosts(), fetchGroups()])
  }

  async function reload() {
    await api.post('/api/inventory/reload')
    await fetchAll()
  }

  return {
    hosts,
    groups,
    loading,
    error,
    fetchHosts,
    fetchGroups,
    fetchAll,
    reload,
  }
})
