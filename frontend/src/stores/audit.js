/**
 * Audit Store - Pinia Store fuer Audit-Logs
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/api/client'

export const useAuditStore = defineStore('audit', () => {
  // State
  const logs = ref([])
  const totalLogs = ref(0)
  const loading = ref(false)
  const currentPage = ref(1)
  const pageSize = ref(50)
  const filters = ref({
    user_id: null,
    action_type: null,
    resource_type: null,
    start_date: null,
    end_date: null,
  })

  // Verification state
  const verificationResult = ref(null)
  const verifying = ref(false)

  // Stats
  const stats = ref(null)

  // Action types and resource types
  const actionTypes = ref([])
  const resourceTypes = ref([])

  // Getters
  const totalPages = computed(() => Math.ceil(totalLogs.value / pageSize.value))
  const hasFilters = computed(() => Object.values(filters.value).some(v => v !== null))

  // Actions
  async function fetchLogs(page = 1) {
    loading.value = true
    try {
      const params = new URLSearchParams()
      params.append('page', page)
      params.append('page_size', pageSize.value)

      if (filters.value.user_id) params.append('user_id', filters.value.user_id)
      if (filters.value.action_type) params.append('action_type', filters.value.action_type)
      if (filters.value.resource_type) params.append('resource_type', filters.value.resource_type)
      if (filters.value.start_date) params.append('start_date', filters.value.start_date)
      if (filters.value.end_date) params.append('end_date', filters.value.end_date)

      const response = await api.get(`/api/audit/logs?${params}`)
      logs.value = response.data.logs
      totalLogs.value = response.data.total
      currentPage.value = response.data.page
      return response.data
    } finally {
      loading.value = false
    }
  }

  async function fetchLog(logId) {
    const response = await api.get(`/api/audit/logs/${logId}`)
    return response.data
  }

  async function verifyChain(startSequence = null, endSequence = null) {
    verifying.value = true
    try {
      const params = new URLSearchParams()
      if (startSequence) params.append('start_sequence', startSequence)
      if (endSequence) params.append('end_sequence', endSequence)

      const response = await api.get(`/api/audit/verify?${params}`)
      verificationResult.value = response.data
      return response.data
    } catch (error) {
      // Fehler abfangen und als Ergebnis speichern
      const errorMessage = error.response?.data?.detail || error.message || 'Unbekannter Fehler'
      verificationResult.value = {
        is_valid: false,
        entries_checked: 0,
        errors: [{ sequence: 0, error: errorMessage }],
        verification_time_ms: 0,
      }
      return verificationResult.value
    } finally {
      verifying.value = false
    }
  }

  async function fetchStats(startDate = null, endDate = null) {
    const params = new URLSearchParams()
    if (startDate) params.append('start_date', startDate)
    if (endDate) params.append('end_date', endDate)

    const response = await api.get(`/api/audit/stats?${params}`)
    stats.value = response.data
    return response.data
  }

  async function fetchActionTypes() {
    const response = await api.get('/api/audit/action-types')
    actionTypes.value = response.data.action_types
    return response.data.action_types
  }

  async function fetchResourceTypes() {
    const response = await api.get('/api/audit/resource-types')
    resourceTypes.value = response.data.resource_types
    return response.data.resource_types
  }

  async function exportLogs(format = 'json') {
    const params = new URLSearchParams()
    params.append('format', format)

    if (filters.value.user_id) params.append('user_id', filters.value.user_id)
    if (filters.value.action_type) params.append('action_type', filters.value.action_type)
    if (filters.value.resource_type) params.append('resource_type', filters.value.resource_type)
    if (filters.value.start_date) params.append('start_date', filters.value.start_date)
    if (filters.value.end_date) params.append('end_date', filters.value.end_date)

    const response = await api.get(`/api/audit/export?${params}`, {
      responseType: 'blob',
    })

    // Download trigger
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `audit_export.${format}`)
    document.body.appendChild(link)
    link.click()
    link.remove()
  }

  function setFilter(key, value) {
    filters.value[key] = value
  }

  function clearFilters() {
    filters.value = {
      user_id: null,
      action_type: null,
      resource_type: null,
      start_date: null,
      end_date: null,
    }
  }

  return {
    // State
    logs,
    totalLogs,
    loading,
    currentPage,
    pageSize,
    filters,
    verificationResult,
    verifying,
    stats,
    actionTypes,
    resourceTypes,
    // Getters
    totalPages,
    hasFilters,
    // Actions
    fetchLogs,
    fetchLog,
    verifyChain,
    fetchStats,
    fetchActionTypes,
    fetchResourceTypes,
    exportLogs,
    setFilter,
    clearFilters,
  }
})
