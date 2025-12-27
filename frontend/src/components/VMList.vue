<template>
  <v-card>
    <v-toolbar flat density="compact">
      <v-icon class="ml-2 mr-2">mdi-server-network</v-icon>
      <v-toolbar-title class="text-body-1">VM-Konfigurationen</v-toolbar-title>
      <v-spacer></v-spacer>
      <v-btn
        variant="outlined"
        size="small"
        @click="$emit('import')"
        class="mr-2"
      >
        <v-icon start>mdi-import</v-icon>
        Importieren
      </v-btn>
      <v-btn
        color="primary"
        size="small"
        @click="$emit('create')"
      >
        <v-icon start>mdi-plus</v-icon>
        Neue VM
      </v-btn>
      <v-btn
        icon
        size="small"
        variant="text"
        @click="loadVMs"
        :loading="loading"
        class="ml-2"
      >
        <v-icon>mdi-refresh</v-icon>
      </v-btn>
    </v-toolbar>

    <v-data-table
      v-model="selectedVMs"
      :headers="headers"
      :items="vms"
      :loading="loading"
      density="compact"
      :items-per-page="10"
      show-select
      item-value="name"
    >
      <template v-slot:item.name="{ item }">
        <div class="d-flex align-center">
          <v-chip color="primary" variant="outlined" size="small">
            {{ item.name }}
          </v-chip>
          <v-btn
            v-if="item.frontend_url"
            icon
            size="x-small"
            variant="text"
            color="primary"
            class="ml-1"
            @click.stop="openUrl(item.frontend_url)"
          >
            <v-icon size="16">mdi-open-in-new</v-icon>
            <v-tooltip activator="parent" location="top">Frontend oeffnen</v-tooltip>
          </v-btn>
        </div>
      </template>

      <template v-slot:item.status="{ item }">
        <v-chip :color="getStatusColor(item.status)" size="small">
          <v-icon start size="small">{{ getStatusIcon(item.status) }}</v-icon>
          {{ getStatusLabel(item.status) }}
        </v-chip>
      </template>

      <template v-slot:item.resources="{ item }">
        <span class="text-caption">
          {{ item.cores }} CPU, {{ item.memory_gb }} GB, {{ item.disk_size_gb }} GB
        </span>
      </template>

      <template v-slot:item.ansible_group="{ item }">
        <v-chip
          v-if="item.ansible_group"
          size="x-small"
          color="primary"
          variant="outlined"
        >
          <v-icon start size="x-small">mdi-ansible</v-icon>
          {{ item.ansible_group }}
        </v-chip>
        <span v-else class="text-grey-darken-1 text-caption">-</span>
      </template>

      <template v-slot:item.actions="{ item }">
        <div class="d-flex align-center ga-1">
          <!-- Power Controls: nur fuer deployed VMs -->
          <template v-if="isDeployed(item)">
            <v-btn
              icon
              size="x-small"
              variant="text"
              :color="item.status === 'running' ? 'grey' : 'success'"
              :disabled="item.status === 'running'"
              :loading="actionLoading === `power-start-${item.name}`"
              @click="powerAction(item, 'start')"
            >
              <v-icon size="18">mdi-play</v-icon>
              <v-tooltip activator="parent" location="top">Start</v-tooltip>
            </v-btn>
            <v-btn
              icon
              size="x-small"
              variant="text"
              :color="item.status !== 'running' ? 'grey' : 'warning'"
              :disabled="item.status !== 'running'"
              :loading="actionLoading === `power-shutdown-${item.name}`"
              @click="powerAction(item, 'shutdown')"
            >
              <v-icon size="18">mdi-stop</v-icon>
              <v-tooltip activator="parent" location="top">Shutdown</v-tooltip>
            </v-btn>
            <v-btn
              icon
              size="x-small"
              variant="text"
              :color="item.status !== 'running' ? 'grey' : 'info'"
              :disabled="item.status !== 'running'"
              :loading="actionLoading === `power-reboot-${item.name}`"
              @click="powerAction(item, 'reboot')"
            >
              <v-icon size="18">mdi-restart</v-icon>
              <v-tooltip activator="parent" location="top">Reboot</v-tooltip>
            </v-btn>
            <v-divider vertical class="mx-1" />
          </template>

          <!-- Action Menu -->
          <ActionMenu
            :actions="getActions(item)"
            :loading-action="actionLoading"
            @action="(key) => handleAction(key, item)"
          />
        </div>
      </template>

      <template v-slot:no-data>
        <div class="text-center py-8">
          <v-icon size="64" color="grey-lighten-1">mdi-server-off</v-icon>
          <div class="text-grey mt-2">Keine VM-Konfigurationen vorhanden</div>
          <v-btn
            color="primary"
            variant="tonal"
            class="mt-4"
            @click="$emit('create')"
          >
            <v-icon start>mdi-plus</v-icon>
            Erste VM erstellen
          </v-btn>
        </div>
      </template>
    </v-data-table>

    <!-- Batch Actions Toolbar -->
    <v-toolbar
      v-if="selectedVMs.length > 0"
      density="compact"
      class="batch-toolbar"
    >
      <v-toolbar-title class="text-body-2">
        {{ selectedVMs.length }} VM(s) ausgewaehlt
      </v-toolbar-title>
      <v-spacer></v-spacer>
      <v-btn
        color="info"
        size="small"
        variant="tonal"
        @click="batchPlan"
        :loading="batchLoading"
        class="mx-1"
      >
        <v-icon start>mdi-file-search</v-icon>
        Alle planen
      </v-btn>
      <v-btn
        color="success"
        size="small"
        variant="tonal"
        @click="batchApply"
        :loading="batchLoading"
        class="mx-1"
      >
        <v-icon start>mdi-play</v-icon>
        Alle deployen
      </v-btn>
      <v-btn
        color="error"
        size="small"
        variant="tonal"
        @click="confirmBatchDestroy"
        :loading="batchLoading"
        class="mx-1"
      >
        <v-icon start>mdi-delete</v-icon>
        Alle zerstoeren
      </v-btn>
      <v-btn
        icon
        size="small"
        variant="text"
        @click="selectedVMs = []"
        class="ml-2"
      >
        <v-icon>mdi-close</v-icon>
      </v-btn>
    </v-toolbar>

    <!-- Dialoge (behalten wie vorher) -->
    <VMCloneDialog ref="cloneDialogRef" @cloned="onVMCloned" />
    <VMSnapshotManager ref="snapshotManagerRef" @close="loadVMs" />
    <VMMigrateDialog ref="migrateDialogRef" @migrated="onVMMigrated" />
    <VMEditDialog ref="editDialogRef" @updated="onVMUpdated" />

    <!-- Delete Config Dialog -->
    <v-dialog v-model="deleteDialog" max-width="500">
      <v-card>
        <v-card-title>
          <v-icon start>mdi-file-remove</v-icon>
          Konfiguration loeschen
        </v-card-title>
        <v-card-text>
          <v-alert
            v-if="selectedVM?.status === 'deployed'"
            type="warning"
            variant="tonal"
            class="mb-4"
          >
            <strong>Achtung:</strong> VM ist deployed. Nutze "Vollstaendig loeschen" um VM auch aus Proxmox zu entfernen.
          </v-alert>
          <p>
            Config fuer <strong>{{ selectedVM?.name }}</strong> loeschen?
          </p>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">Abbrechen</v-btn>
          <v-btn
            color="warning"
            :loading="actionLoading === `delete-${selectedVM?.name}`"
            @click="deleteVMConfig"
          >
            Loeschen
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Complete Dialog -->
    <v-dialog v-model="deleteCompleteDialog" max-width="500" persistent>
      <v-card>
        <v-card-title class="text-error">
          <v-icon start color="error">mdi-delete-forever</v-icon>
          VM vollstaendig loeschen
        </v-card-title>
        <v-card-text>
          <template v-if="!deleteCompleteResult">
            <v-alert type="error" variant="tonal" class="mb-4">
              <strong>ACHTUNG:</strong> Loescht VM aus allen Systemen!
            </v-alert>
            <v-list density="compact" class="mb-4">
              <v-list-item prepend-icon="mdi-server">
                <v-list-item-title>Proxmox</v-list-item-title>
              </v-list-item>
              <v-list-item prepend-icon="mdi-database">
                <v-list-item-title>NetBox</v-list-item-title>
              </v-list-item>
              <v-list-item prepend-icon="mdi-terraform">
                <v-list-item-title>Terraform State</v-list-item-title>
              </v-list-item>
              <v-list-item prepend-icon="mdi-ansible">
                <v-list-item-title>Ansible Inventory</v-list-item-title>
              </v-list-item>
            </v-list>
            <p class="mb-4">
              VM: <strong>{{ selectedVM?.name }}</strong>
            </p>
            <v-text-field
              v-model="deleteCompleteConfirm"
              label="Tippe 'DELETE' zur Bestaetigung"
              variant="outlined"
              density="compact"
              color="error"
            />
          </template>
          <template v-else>
            <v-alert
              :type="deleteCompleteResult.success ? 'success' : 'warning'"
              variant="tonal"
              class="mb-4"
            >
              {{ deleteCompleteResult.message }}
            </v-alert>
          </template>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <template v-if="!deleteCompleteResult">
            <v-btn variant="text" @click="closeDeleteCompleteDialog">Abbrechen</v-btn>
            <v-btn
              color="error"
              :disabled="deleteCompleteConfirm !== 'DELETE'"
              :loading="actionLoading === `delete-complete-${selectedVM?.name}`"
              @click="executeDeleteComplete"
            >
              Vollstaendig loeschen
            </v-btn>
          </template>
          <template v-else>
            <v-btn color="primary" @click="closeDeleteCompleteDialog">Schliessen</v-btn>
          </template>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Frontend-URL Dialog -->
    <v-dialog v-model="frontendUrlDialog" max-width="400">
      <v-card>
        <v-card-title>
          <v-icon start>mdi-link-variant</v-icon>
          Frontend-URL
        </v-card-title>
        <v-card-text>
          <v-alert type="info" variant="tonal" density="compact" class="mb-4">
            <strong>{{ frontendUrlVm?.name }}</strong>
          </v-alert>
          <v-text-field
            v-model="frontendUrlInput"
            label="URL"
            placeholder="https://app.example.com"
            hint="Leer lassen zum Entfernen"
            persistent-hint
            clearable
            :loading="frontendUrlSaving"
            @keyup.enter="saveFrontendUrl"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="frontendUrlDialog = false">Abbrechen</v-btn>
          <v-btn color="primary" :loading="frontendUrlSaving" @click="saveFrontendUrl">
            Speichern
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { ref, onMounted, inject } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api/client'
import ActionMenu from '@/components/common/ActionMenu.vue'
import VMCloneDialog from '@/components/VMCloneDialog.vue'
import VMSnapshotManager from '@/components/VMSnapshotManager.vue'
import VMMigrateDialog from '@/components/VMMigrateDialog.vue'
import VMEditDialog from '@/components/VMEditDialog.vue'
import { getStatusColor, getStatusIcon } from '@/utils/formatting'
import { useConfirmDialog, confirmPresets } from '@/composables/useConfirmDialog'
import { getVMActions } from '@/composables/useActionMenu'

const emit = defineEmits(['create', 'import'])
const router = useRouter()
const showSnackbar = inject('showSnackbar')
const { confirm } = useConfirmDialog()

const loading = ref(false)
const actionLoading = ref(null)
const vms = ref([])
const selectedVMs = ref([])
const batchLoading = ref(false)

// Dialoge
const deleteDialog = ref(false)
const deleteCompleteDialog = ref(false)
const deleteCompleteConfirm = ref('')
const deleteCompleteResult = ref(null)
const selectedVM = ref(null)

const frontendUrlDialog = ref(false)
const frontendUrlInput = ref('')
const frontendUrlVm = ref(null)
const frontendUrlSaving = ref(false)

// Dialog Refs
const cloneDialogRef = ref(null)
const snapshotManagerRef = ref(null)
const migrateDialogRef = ref(null)
const editDialogRef = ref(null)

const headers = [
  { title: 'Name', key: 'name', width: '180px' },
  { title: 'VMID', key: 'vmid', width: '70px' },
  { title: 'IP', key: 'ip_address', width: '130px' },
  { title: 'Node', key: 'target_node', width: '90px' },
  { title: 'Ressourcen', key: 'resources', width: '160px' },
  { title: 'Ansible', key: 'ansible_group', width: '100px' },
  { title: 'Status', key: 'status', width: '110px' },
  { title: '', key: 'actions', sortable: false, width: '160px' },
]

// Hilfsfunktionen
function isDeployed(vm) {
  return ['deployed', 'running', 'stopped', 'paused'].includes(vm.status)
}

function getStatusLabel(status) {
  const labels = {
    planned: 'Geplant',
    deploying: 'Deploying...',
    deployed: 'Deployed',
    failed: 'Fehler',
    destroying: 'Destroying...',
    running: 'Running',
    stopped: 'Stopped',
    paused: 'Paused',
  }
  return labels[status] || status
}

function getActions(vm) {
  return getVMActions(vm, { loadingAction: actionLoading.value })
}

function openUrl(url) {
  window.open(url, '_blank')
}

// API Funktionen
async function loadVMs() {
  loading.value = true
  try {
    const response = await api.get(`/api/terraform/vms?_t=${Date.now()}`)
    vms.value = response.data
  } catch (e) {
    showSnackbar?.('Laden fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    loading.value = false
  }
}

// Action Handler
async function handleAction(key, vm) {
  switch (key) {
    case 'edit':
      editDialogRef.value?.open(vm)
      break
    case 'clone':
      cloneDialogRef.value?.open(vm)
      break
    case 'snapshots':
      snapshotManagerRef.value?.open(vm)
      break
    case 'migrate':
      migrateDialogRef.value?.open(vm)
      break
    case 'plan':
      await planVM(vm)
      break
    case 'apply':
      await applyVM(vm)
      break
    case 'destroy':
      await confirmDestroy(vm)
      break
    case 'release-ip':
      await confirmReleaseIP(vm)
      break
    case 'delete-config':
      confirmDelete(vm)
      break
    case 'delete-complete':
      confirmDeleteComplete(vm)
      break
    case 'open-frontend':
      openUrl(vm.frontend_url)
      break
    case 'edit-frontend-url':
      openFrontendUrlDialog(vm)
      break
  }
}

async function powerAction(vm, action) {
  const labels = { start: 'Start', stop: 'Stop', shutdown: 'Shutdown', reboot: 'Reboot' }
  actionLoading.value = `power-${action}-${vm.name}`
  try {
    await api.post(`/api/terraform/vms/${vm.name}/power/${action}`)
    showSnackbar?.(`${labels[action]} fuer ${vm.name} ausgefuehrt`, 'success')
    // Polling
    setTimeout(loadVMs, 2000)
  } catch (e) {
    showSnackbar?.(`${labels[action]} fehlgeschlagen: ` + (e.response?.data?.detail || e.message), 'error')
  } finally {
    actionLoading.value = null
  }
}

async function planVM(vm) {
  actionLoading.value = `plan-${vm.name}`
  try {
    const response = await api.post(`/api/terraform/vms/${vm.name}/plan`)
    router.push(`/executions/${response.data.execution_id}`)
  } catch (e) {
    showSnackbar?.('Plan fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    actionLoading.value = null
  }
}

async function applyVM(vm) {
  actionLoading.value = `apply-${vm.name}`
  try {
    const response = await api.post(`/api/terraform/vms/${vm.name}/apply`)
    router.push(`/executions/${response.data.execution_id}`)
  } catch (e) {
    showSnackbar?.('Deploy fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    actionLoading.value = null
  }
}

async function confirmDestroy(vm) {
  const confirmed = await confirm(confirmPresets.destroyVM(vm.name))
  if (!confirmed) return

  actionLoading.value = `destroy-${vm.name}`
  try {
    const response = await api.post(`/api/terraform/vms/${vm.name}/destroy`)
    router.push(`/executions/${response.data.execution_id}`)
  } catch (e) {
    showSnackbar?.('Destroy fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    actionLoading.value = null
  }
}

async function confirmReleaseIP(vm) {
  const confirmed = await confirm(confirmPresets.releaseIP(vm.name, vm.ip_address))
  if (!confirmed) return

  actionLoading.value = `release-${vm.name}`
  try {
    await api.post(`/api/terraform/vms/${vm.name}/release-ip`)
    showSnackbar?.(`IP ${vm.ip_address} freigegeben`, 'success')
    loadVMs()
  } catch (e) {
    showSnackbar?.('IP-Freigabe fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    actionLoading.value = null
  }
}

function confirmDelete(vm) {
  selectedVM.value = vm
  deleteDialog.value = true
}

async function deleteVMConfig() {
  if (!selectedVM.value) return
  actionLoading.value = `delete-${selectedVM.value.name}`
  try {
    await api.delete(`/api/terraform/vms/${selectedVM.value.name}`)
    showSnackbar?.(`Config fuer ${selectedVM.value.name} geloescht`, 'success')
    deleteDialog.value = false
    loadVMs()
  } catch (e) {
    showSnackbar?.('Loeschen fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    actionLoading.value = null
  }
}

function confirmDeleteComplete(vm) {
  selectedVM.value = vm
  deleteCompleteConfirm.value = ''
  deleteCompleteResult.value = null
  deleteCompleteDialog.value = true
}

function closeDeleteCompleteDialog() {
  deleteCompleteDialog.value = false
  if (deleteCompleteResult.value?.success) {
    loadVMs()
  }
}

async function executeDeleteComplete() {
  if (!selectedVM.value) return
  actionLoading.value = `delete-complete-${selectedVM.value.name}`
  try {
    const response = await api.delete(`/api/terraform/vms/${selectedVM.value.name}/complete`)
    deleteCompleteResult.value = response.data
    showSnackbar?.(
      response.data.success ? `VM ${selectedVM.value.name} vollstaendig geloescht` : `Teilweise geloescht`,
      response.data.success ? 'success' : 'warning'
    )
  } catch (e) {
    showSnackbar?.('Loeschung fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
    deleteCompleteDialog.value = false
  } finally {
    actionLoading.value = null
  }
}

function openFrontendUrlDialog(vm) {
  frontendUrlVm.value = vm
  frontendUrlInput.value = vm.frontend_url || ''
  frontendUrlDialog.value = true
}

async function saveFrontendUrl() {
  if (!frontendUrlVm.value) return
  frontendUrlSaving.value = true
  try {
    await api.patch(`/api/terraform/vms/${frontendUrlVm.value.name}/frontend-url`, {
      frontend_url: frontendUrlInput.value || null
    })
    showSnackbar?.(frontendUrlInput.value ? 'URL gespeichert' : 'URL entfernt', 'success')
    frontendUrlDialog.value = false
    loadVMs()
  } catch (e) {
    showSnackbar?.('Fehler: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    frontendUrlSaving.value = false
  }
}

// Dialog Callbacks
function onVMCloned(result) {
  showSnackbar?.(`VM '${result.target_name}' wird geklont`, 'success')
  loadVMs()
}

function onVMMigrated(result) {
  showSnackbar?.(`VM '${result.vm_name}' migriert nach ${result.target_node}`, 'success')
  loadVMs()
}

function onVMUpdated(result) {
  showSnackbar?.(result.needs_apply ? `VM aktualisiert - Apply erforderlich` : `VM aktualisiert`, 'success')
  loadVMs()
}

// Batch Operations
async function batchPlan() {
  batchLoading.value = true
  try {
    const response = await api.post('/api/terraform/vms/batch/plan', { vm_names: selectedVMs.value })
    showSnackbar?.(`Plan fuer ${response.data.successful.length} VM(s) gestartet`, 'success')
    selectedVMs.value = []
    loadVMs()
  } catch (e) {
    showSnackbar?.('Batch Plan fehlgeschlagen', 'error')
  } finally {
    batchLoading.value = false
  }
}

async function batchApply() {
  batchLoading.value = true
  try {
    const response = await api.post('/api/terraform/vms/batch/apply', { vm_names: selectedVMs.value })
    showSnackbar?.(`Deploy fuer ${response.data.successful.length} VM(s) gestartet`, 'success')
    selectedVMs.value = []
    loadVMs()
  } catch (e) {
    showSnackbar?.('Batch Apply fehlgeschlagen', 'error')
  } finally {
    batchLoading.value = false
  }
}

async function confirmBatchDestroy() {
  const confirmed = await confirm(confirmPresets.batchDestroy(selectedVMs.value.length))
  if (!confirmed) return

  batchLoading.value = true
  try {
    const response = await api.post('/api/terraform/vms/batch/destroy', { vm_names: selectedVMs.value })
    showSnackbar?.(`Destroy fuer ${response.data.successful.length} VM(s) gestartet`, 'success')
    selectedVMs.value = []
    loadVMs()
  } catch (e) {
    showSnackbar?.('Batch Destroy fehlgeschlagen', 'error')
  } finally {
    batchLoading.value = false
  }
}

defineExpose({ loadVMs })

onMounted(loadVMs)
</script>
