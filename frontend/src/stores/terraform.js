/**
 * Terraform Store - Pinia Store fuer Terraform Health-Status
 *
 * Verwaltet den Health-Status des Terraform State fuer app-weite Anzeige.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/api/client'

export const useTerraformStore = defineStore('terraform', () => {
  // State
  const healthStatus = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const pollingInterval = ref(null)

  // Getters
  const orphanedCount = computed(() => healthStatus.value?.orphaned_count || 0)
  const isHealthy = computed(() => healthStatus.value?.healthy ?? true)
  const totalVms = computed(() => healthStatus.value?.total_vms || 0)
  const orphanedVms = computed(() => healthStatus.value?.orphaned_vms || [])
  const lastCheck = computed(() => healthStatus.value?.last_check || null)
  const nextCheck = computed(() => healthStatus.value?.next_check || null)

  // Actions
  async function fetchHealthStatus() {
    loading.value = true
    error.value = null

    try {
      // Live-Check statt gecachtem Status
      const response = await api.get('/api/terraform/state/health')
      healthStatus.value = response.data
    } catch (err) {
      error.value = err.response?.data?.detail || err.message || 'Fehler beim Laden des Health-Status'
      console.error('Terraform Health-Status Fehler:', err)
    } finally {
      loading.value = false
    }
  }

  function startPolling(intervalMs = 60000) {
    // Nicht mehrfach starten
    if (pollingInterval.value) return

    // Sofort einmal abrufen
    fetchHealthStatus()

    // Dann periodisch
    pollingInterval.value = setInterval(() => {
      fetchHealthStatus()
    }, intervalMs)
  }

  function stopPolling() {
    if (pollingInterval.value) {
      clearInterval(pollingInterval.value)
      pollingInterval.value = null
    }
  }

  return {
    // State
    healthStatus,
    loading,
    error,
    // Getters
    orphanedCount,
    isHealthy,
    totalVms,
    orphanedVms,
    lastCheck,
    nextCheck,
    // Actions
    fetchHealthStatus,
    startPolling,
    stopPolling,
  }
})
