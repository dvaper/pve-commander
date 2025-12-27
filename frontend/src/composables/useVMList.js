/**
 * useVMList - Composable fuer VM-Liste und Filterung
 *
 * Extrahiert VM-Lade- und Filter-Logik aus VMList.vue.
 *
 * Verwendung:
 *   import { useVMList } from '@/composables/useVMList'
 *
 *   const {
 *     vms,
 *     filteredVMs,
 *     loading,
 *     error,
 *     loadVMs,
 *     filterByStatus,
 *     filterByNode,
 *     searchQuery
 *   } = useVMList()
 */

import { ref, computed, watch } from 'vue'
import api from '@/api/client'

export function useVMList(options = {}) {
  const {
    autoLoad = true,
    pollInterval = 0, // 0 = kein Polling
  } = options

  // State
  const vms = ref([])
  const loading = ref(false)
  const error = ref(null)

  // Filter State
  const searchQuery = ref('')
  const statusFilter = ref('all')
  const nodeFilter = ref('all')
  const stateFilter = ref('all')

  // Polling
  let pollTimer = null

  /**
   * Laedt alle VMs
   */
  async function loadVMs() {
    loading.value = true
    error.value = null

    try {
      const response = await api.get('/api/terraform/vms')
      vms.value = response.data
      return { success: true, data: response.data }
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  /**
   * Gefilterte VM-Liste
   */
  const filteredVMs = computed(() => {
    let result = [...vms.value]

    // Text-Suche
    if (searchQuery.value) {
      const query = searchQuery.value.toLowerCase()
      result = result.filter(vm =>
        vm.name.toLowerCase().includes(query) ||
        vm.ip_address?.toLowerCase().includes(query) ||
        vm.node?.toLowerCase().includes(query)
      )
    }

    // Status-Filter
    if (statusFilter.value !== 'all') {
      result = result.filter(vm => vm.status === statusFilter.value)
    }

    // Node-Filter
    if (nodeFilter.value !== 'all') {
      result = result.filter(vm => vm.node === nodeFilter.value)
    }

    // State-Filter (synced, drift, orphaned, new)
    if (stateFilter.value !== 'all') {
      result = result.filter(vm => vm.state_status === stateFilter.value)
    }

    return result
  })

  /**
   * Einzigartige Nodes aus VM-Liste
   */
  const availableNodes = computed(() => {
    const nodes = new Set(vms.value.map(vm => vm.node).filter(Boolean))
    return Array.from(nodes).sort()
  })

  /**
   * VM-Statistiken
   */
  const stats = computed(() => {
    const total = vms.value.length
    const running = vms.value.filter(vm => vm.status === 'running').length
    const stopped = vms.value.filter(vm => vm.status === 'stopped').length
    const orphaned = vms.value.filter(vm => vm.state_status === 'orphaned').length
    const synced = vms.value.filter(vm => vm.state_status === 'synced').length
    const drift = vms.value.filter(vm => vm.state_status === 'drift').length

    return {
      total,
      running,
      stopped,
      orphaned,
      synced,
      drift,
      healthy: synced,
      issues: orphaned + drift,
    }
  })

  /**
   * Startet Polling
   */
  function startPolling(interval = pollInterval) {
    if (interval > 0) {
      stopPolling()
      pollTimer = setInterval(loadVMs, interval)
    }
  }

  /**
   * Stoppt Polling
   */
  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  /**
   * Setzt Filter zurueck
   */
  function resetFilters() {
    searchQuery.value = ''
    statusFilter.value = 'all'
    nodeFilter.value = 'all'
    stateFilter.value = 'all'
  }

  /**
   * Findet VM nach Name
   */
  function findVM(name) {
    return vms.value.find(vm => vm.name === name)
  }

  /**
   * Aktualisiert eine einzelne VM im Cache
   */
  function updateVMInCache(name, updates) {
    const index = vms.value.findIndex(vm => vm.name === name)
    if (index !== -1) {
      vms.value[index] = { ...vms.value[index], ...updates }
    }
  }

  /**
   * Entfernt VM aus Cache
   */
  function removeVMFromCache(name) {
    const index = vms.value.findIndex(vm => vm.name === name)
    if (index !== -1) {
      vms.value.splice(index, 1)
    }
  }

  // Auto-Load wenn gewuenscht
  if (autoLoad) {
    loadVMs()
  }

  return {
    // State
    vms,
    loading,
    error,

    // Filter State
    searchQuery,
    statusFilter,
    nodeFilter,
    stateFilter,

    // Computed
    filteredVMs,
    availableNodes,
    stats,

    // Actions
    loadVMs,
    resetFilters,
    findVM,
    updateVMInCache,
    removeVMFromCache,

    // Polling
    startPolling,
    stopPolling,
  }
}

export default useVMList
