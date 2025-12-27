/**
 * Execution Store - Ausführungen
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api/client'

export const useExecutionStore = defineStore('execution', () => {
  // State
  const executions = ref([])
  const currentExecution = ref(null)
  const total = ref(0)
  const loading = ref(false)
  const error = ref(null)

  // Actions
  async function fetchExecutions(page = 1, pageSize = 20, filters = {}) {
    loading.value = true
    error.value = null

    try {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: pageSize.toString(),
        ...filters,
      })

      const response = await api.get(`/api/executions?${params}`)
      executions.value = response.data.items
      total.value = response.data.total
      return response.data
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchExecution(id) {
    loading.value = true
    error.value = null

    try {
      const response = await api.get(`/api/executions/${id}`)
      currentExecution.value = response.data
      return response.data
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function runAnsible(data) {
    loading.value = true
    error.value = null

    try {
      const response = await api.post('/api/executions/ansible', data)
      return response.data
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function runTerraform(data) {
    loading.value = true
    error.value = null

    try {
      const response = await api.post('/api/executions/terraform', data)
      return response.data
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function cancelExecution(id) {
    await api.delete(`/api/executions/${id}`)
    await fetchExecutions()
  }

  return {
    executions,
    currentExecution,
    total,
    loading,
    error,
    fetchExecutions,
    fetchExecution,
    runAnsible,
    runTerraform,
    cancelExecution,
  }
})
