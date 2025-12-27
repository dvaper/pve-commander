<template>
  <v-container fluid>
    <!-- Health-Alert bei verwaisten VMs -->
    <v-alert
      v-if="terraformStore.orphanedCount > 0"
      type="warning"
      variant="tonal"
      closable
      class="mb-4"
    >
      <div class="d-flex align-center justify-space-between">
        <div>
          <strong>{{ terraformStore.orphanedCount }} verwaiste VM(s) im Terraform State</strong>
          <div class="text-caption">
            Diese VMs existieren im State, aber nicht mehr in Proxmox.
          </div>
        </div>
        <v-btn
          color="warning"
          variant="outlined"
          size="small"
          @click="showOrphanedDetails"
        >
          Details anzeigen
        </v-btn>
      </div>
    </v-alert>

    <v-tabs v-model="tab" color="primary">
      <v-tab value="vms">
        <v-icon start>mdi-server-network</v-icon>
        VMs
      </v-tab>
      <v-tab value="state">
        <v-icon start>mdi-database-eye</v-icon>
        State
      </v-tab>
    </v-tabs>

    <v-tabs-window v-model="tab" class="mt-4">
      <!-- Tab: VMs -->
      <v-tabs-window-item value="vms">
        <VMList ref="vmListRef" @create="openWizard" @import="openImportDialog" />
      </v-tabs-window-item>

      <!-- Tab: State -->
      <v-tabs-window-item value="state">
        <TerraformStateViewer ref="stateViewerRef" />
      </v-tabs-window-item>
    </v-tabs-window>

    <!-- VM Deployment Wizard -->
    <VMDeploymentWizard ref="wizardRef" @created="onVMCreated" />

    <!-- VM Import Dialog -->
    <VMImportDialog ref="importDialogRef" @imported="onVMImported" />

    <!-- Orphaned VMs Dialog -->
    <v-dialog v-model="orphanedDialog" max-width="800">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon start color="warning">mdi-alert</v-icon>
          Verwaiste VMs im Terraform State
        </v-card-title>
        <v-card-text>
          <v-alert type="info" variant="tonal" class="mb-4">
            Diese VMs existieren im Terraform State, sind aber nicht mehr in Proxmox vorhanden.
            Sie sollten aus dem State entfernt werden.
          </v-alert>

          <!-- Cleanup-Optionen -->
          <div class="d-flex flex-wrap gap-4 mb-4">
            <v-checkbox
              v-model="cleanupDeleteTfFile"
              label="TF-Datei loeschen"
              density="compact"
              hide-details
            />
            <v-checkbox
              v-model="cleanupNetbox"
              label="NetBox-Eintrag entfernen"
              density="compact"
              hide-details
            />
          </div>

          <v-table density="compact">
            <thead>
              <tr>
                <th>VM Name</th>
                <th>VMID</th>
                <th>Node</th>
                <th>Grund</th>
                <th style="width: 120px;">Aktion</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="vm in terraformStore.orphanedVms" :key="vm.address">
                <td>
                  <div class="font-weight-medium">{{ extractVmName(vm.address) }}</div>
                  <div class="text-caption text-grey">{{ vm.address }}</div>
                </td>
                <td>{{ vm.vmid || '-' }}</td>
                <td>{{ vm.node || '-' }}</td>
                <td>
                  <v-chip size="small" color="error" variant="flat">
                    {{ vm.reason || 'Nicht in Proxmox' }}
                  </v-chip>
                </td>
                <td>
                  <v-btn
                    size="small"
                    color="warning"
                    variant="tonal"
                    :loading="cleanupLoading === vm.address"
                    @click="cleanupOrphanedVm(vm)"
                  >
                    <v-icon start size="small">mdi-delete</v-icon>
                    Entfernen
                  </v-btn>
                </td>
              </tr>
            </tbody>
          </v-table>
        </v-card-text>
        <v-card-actions>
          <v-btn
            v-if="terraformStore.orphanedVms.length >= 1"
            color="error"
            variant="tonal"
            :loading="cleanupAllLoading"
            @click="cleanupAllOrphanedVms"
          >
            <v-icon start>mdi-delete-sweep</v-icon>
            Alle bereinigen ({{ terraformStore.orphanedVms.length }})
          </v-btn>
          <v-spacer></v-spacer>
          <v-btn @click="orphanedDialog = false">Schliessen</v-btn>
          <v-btn color="info" variant="flat" @click="goToStateTab">
            <v-icon start>mdi-database-eye</v-icon>
            Zum State-Tab
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, onMounted, inject } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import api from '@/api/client'
import { useTerraformStore } from '@/stores/terraform'
import { useAuthStore } from '@/stores/auth'
import { useConfirmDialog } from '@/composables/useConfirmDialog'
import VMList from '@/components/VMList.vue'
import VMDeploymentWizard from '@/components/VMDeploymentWizard.vue'
import TerraformStateViewer from '@/components/TerraformStateViewer.vue'
import VMImportDialog from '@/components/VMImportDialog.vue'

const terraformStore = useTerraformStore()
const authStore = useAuthStore()
const { confirm } = useConfirmDialog()

const router = useRouter()
const route = useRoute()
const showSnackbar = inject('showSnackbar')

const tab = ref('vms')
const orphanedDialog = ref(false)
const cleanupDeleteTfFile = ref(true)
const cleanupNetbox = ref(true)
const cleanupLoading = ref(null)
const cleanupAllLoading = ref(false)

const vmListRef = ref(null)
const wizardRef = ref(null)
const stateViewerRef = ref(null)
const importDialogRef = ref(null)

function openWizard() {
  wizardRef.value?.open()
}

function openImportDialog() {
  importDialogRef.value?.open()
}

function showOrphanedDetails() {
  orphanedDialog.value = true
}

function goToStateTab() {
  orphanedDialog.value = false
  tab.value = 'state'
}

function extractVmName(address) {
  if (!address) return '-'
  const match = address.match(/^module\.([^.]+)\./)
  return match ? match[1] : address
}

async function cleanupOrphanedVm(vm) {
  cleanupLoading.value = vm.address
  try {
    const params = new URLSearchParams({
      delete_tf_file: cleanupDeleteTfFile.value,
      cleanup_netbox: cleanupNetbox.value
    })
    await api.delete(`/api/terraform/state/${encodeURIComponent(vm.address)}?${params}`)
    showSnackbar?.(`${extractVmName(vm.address)} aus State entfernt`, 'success')
    await terraformStore.fetchHealthStatus()
    if (terraformStore.orphanedCount === 0) {
      orphanedDialog.value = false
    }
  } catch (error) {
    showSnackbar?.(`Fehler: ${error.response?.data?.detail || error.message}`, 'error')
  } finally {
    cleanupLoading.value = null
  }
}

async function cleanupAllOrphanedVms() {
  if (authStore.currentUiBeta) {
    const confirmed = await confirm({
      title: 'Alle verwaisten VMs bereinigen?',
      message: `${terraformStore.orphanedVms.length} VM(s) werden aus dem Terraform State entfernt.`,
      icon: 'mdi-broom',
      iconColor: 'warning',
      confirmLabel: 'Alle bereinigen',
      confirmColor: 'warning',
      confirmIcon: 'mdi-broom'
    })
    if (!confirmed) return
  } else {
    if (!window.confirm(`Wirklich alle ${terraformStore.orphanedVms.length} verwaisten VMs bereinigen?`)) {
      return
    }
  }

  cleanupAllLoading.value = true
  let successCount = 0
  let errorCount = 0

  for (const vm of terraformStore.orphanedVms) {
    try {
      const params = new URLSearchParams({
        delete_tf_file: cleanupDeleteTfFile.value,
        cleanup_netbox: cleanupNetbox.value
      })
      await api.delete(`/api/terraform/state/${encodeURIComponent(vm.address)}?${params}`)
      successCount++
    } catch {
      errorCount++
    }
  }

  cleanupAllLoading.value = false

  if (errorCount === 0) {
    showSnackbar?.(`${successCount} VMs erfolgreich bereinigt`, 'success')
  } else {
    showSnackbar?.(`${successCount} erfolgreich, ${errorCount} Fehler`, 'warning')
  }

  await terraformStore.fetchHealthStatus()

  if (terraformStore.orphanedCount === 0) {
    orphanedDialog.value = false
  }
}

async function onVMCreated(vm) {
  await vmListRef.value?.loadVMs()

  if (authStore.currentUiBeta) {
    const shouldDeploy = await confirm({
      title: 'VM erstellt',
      message: `VM "${vm.name}" wurde erfolgreich konfiguriert (IP: ${vm.ip_address}). Moechtest du die VM jetzt deployen?`,
      icon: 'mdi-rocket-launch',
      iconColor: 'success',
      confirmLabel: 'Jetzt deployen',
      confirmColor: 'success',
      confirmIcon: 'mdi-rocket-launch',
      cancelLabel: 'Spaeter'
    })

    if (shouldDeploy) {
      try {
        const response = await api.post(`/api/terraform/vms/${vm.name}/apply`)
        router.push(`/executions/${response.data.execution_id}`)
      } catch (e) {
        showSnackbar?.('Deploy fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
      }
    }
  } else {
    showSnackbar?.(`VM ${vm.name} erstellt (IP: ${vm.ip_address})`, 'success')
  }
}

function onVMImported(vm) {
  showSnackbar?.(`VM ${vm.vm_name} importiert (IP: ${vm.ip_address})`, 'success')
  vmListRef.value?.loadVMs()
  stateViewerRef.value?.loadResources()
}

onMounted(() => {
  if (route.query.action === 'create') {
    openWizard()
  }
})
</script>
