/**
 * useVMActions - Composable fuer VM-Aktionen
 *
 * Extrahiert gemeinsame VM-Logik aus VMList.vue und anderen Komponenten.
 * Ermoeglicht Wiederverwendung und bessere Testbarkeit.
 *
 * Verwendung:
 *   import { useVMActions } from '@/composables/useVMActions'
 *
 *   const {
 *     startVM,
 *     stopVM,
 *     rebootVM,
 *     destroyVM,
 *     planVM,
 *     applyVM,
 *     loading,
 *     error
 *   } = useVMActions()
 */

import { ref } from 'vue'
import api from '@/api/client'

export function useVMActions() {
  const loading = ref(false)
  const error = ref(null)

  /**
   * Fuehrt eine Power-Aktion auf einer VM aus
   */
  async function powerAction(vmName, action) {
    loading.value = true
    error.value = null

    try {
      const response = await api.post(`/api/terraform/vms/${vmName}/power/${action}`)
      return { success: true, data: response.data }
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  async function startVM(vmName) {
    return powerAction(vmName, 'start')
  }

  async function stopVM(vmName) {
    return powerAction(vmName, 'stop')
  }

  async function shutdownVM(vmName) {
    return powerAction(vmName, 'shutdown')
  }

  async function rebootVM(vmName) {
    return powerAction(vmName, 'reboot')
  }

  async function resetVM(vmName) {
    return powerAction(vmName, 'reset')
  }

  /**
   * Plant Terraform fuer eine VM
   */
  async function planVM(vmName) {
    loading.value = true
    error.value = null

    try {
      const response = await api.post(`/api/terraform/vms/${vmName}/plan`)
      return { success: true, executionId: response.data.execution_id }
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  /**
   * Wendet Terraform auf eine VM an
   */
  async function applyVM(vmName) {
    loading.value = true
    error.value = null

    try {
      const response = await api.post(`/api/terraform/vms/${vmName}/apply`)
      return { success: true, executionId: response.data.execution_id }
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  /**
   * Zerstoert eine VM via Terraform
   */
  async function destroyVM(vmName) {
    loading.value = true
    error.value = null

    try {
      const response = await api.post(`/api/terraform/vms/${vmName}/destroy`)
      return { success: true, executionId: response.data.execution_id }
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  /**
   * Loescht VM-Konfiguration
   */
  async function deleteVMConfig(vmName) {
    loading.value = true
    error.value = null

    try {
      await api.delete(`/api/terraform/vms/${vmName}`)
      return { success: true }
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  /**
   * Gibt IP in NetBox frei
   */
  async function releaseIP(vmName) {
    loading.value = true
    error.value = null

    try {
      await api.post(`/api/terraform/vms/${vmName}/release-ip`)
      return { success: true }
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  /**
   * Vollstaendige VM-Loeschung (Destroy + Config + IP)
   */
  async function deleteVMComplete(vmName, options = {}) {
    loading.value = true
    error.value = null

    const { destroyProxmox = true, deleteConfig = true, releaseNetboxIP = true } = options

    try {
      const response = await api.delete(`/api/terraform/vms/${vmName}/complete`, {
        params: {
          destroy_proxmox: destroyProxmox,
          delete_config: deleteConfig,
          release_netbox_ip: releaseNetboxIP,
        }
      })
      return { success: true, data: response.data }
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  return {
    // State
    loading,
    error,

    // Power Actions
    startVM,
    stopVM,
    shutdownVM,
    rebootVM,
    resetVM,
    powerAction,

    // Terraform Actions
    planVM,
    applyVM,
    destroyVM,

    // Config Actions
    deleteVMConfig,
    releaseIP,
    deleteVMComplete,
  }
}

export default useVMActions
