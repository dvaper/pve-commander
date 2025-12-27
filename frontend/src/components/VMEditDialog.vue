<!-- VM Edit Dialog -->
<template>
  <v-dialog v-model="dialog" max-width="550" persistent>
    <v-card>
      <v-toolbar color="primary" density="compact">
        <v-icon class="ml-2 mr-2">mdi-pencil</v-icon>
        <v-toolbar-title>VM bearbeiten: {{ vm?.name }}</v-toolbar-title>
        <v-spacer></v-spacer>
        <v-btn icon size="small" @click="close" :disabled="saving">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-toolbar>

      <v-card-text class="pt-4">
        <!-- Aktuelle VM-Info -->
        <v-alert type="info" variant="tonal" density="compact" class="mb-4">
          <div class="d-flex align-center">
            <div class="flex-grow-1">
              <strong>{{ vm?.name }}</strong>
              <span class="text-grey ml-2">(VMID: {{ vm?.vmid }})</span>
            </div>
            <v-chip
              :color="getStatusColor(vm?.status)"
              size="small"
              variant="flat"
            >
              {{ vm?.status }}
            </v-chip>
          </div>
        </v-alert>

        <!-- Warnung für deployed VMs -->
        <v-alert
          v-if="isDeployed"
          type="warning"
          variant="tonal"
          density="compact"
          class="mb-4"
        >
          <v-icon start size="small">mdi-information</v-icon>
          Änderungen werden erst nach "Apply" wirksam.
        </v-alert>

        <!-- Loading -->
        <div v-if="loadingNodes" class="text-center py-4">
          <v-progress-circular indeterminate color="primary"></v-progress-circular>
          <div class="text-caption mt-2">Lade Node-Informationen...</div>
        </div>

        <!-- Formular -->
        <template v-else>
          <!-- Target Node -->
          <v-select
            v-model="form.target_node"
            :items="nodeItems"
            item-title="label"
            item-value="name"
            label="Ziel-Node"
            density="compact"
            variant="outlined"
            class="mb-2"
          ></v-select>

          <!-- CPU Cores -->
          <div class="mb-4">
            <div class="d-flex justify-space-between align-center mb-1">
              <span class="text-body-2">CPU Kerne</span>
              <v-chip size="small" color="primary" variant="flat">{{ form.cores }}</v-chip>
            </div>
            <v-slider
              v-model="form.cores"
              :min="1"
              :max="16"
              :step="1"
              color="primary"
              track-color="grey-lighten-2"
              hide-details
            ></v-slider>
          </div>

          <!-- RAM -->
          <div class="mb-4">
            <div class="d-flex justify-space-between align-center mb-1">
              <span class="text-body-2">RAM (GB)</span>
              <v-chip size="small" color="primary" variant="flat">{{ form.memory_gb }} GB</v-chip>
            </div>
            <v-slider
              v-model="form.memory_gb"
              :min="1"
              :max="64"
              :step="1"
              color="primary"
              track-color="grey-lighten-2"
              hide-details
            ></v-slider>
          </div>

          <!-- Disk Size -->
          <div class="mb-4">
            <div class="d-flex justify-space-between align-center mb-1">
              <span class="text-body-2">Disk (GB)</span>
              <v-chip size="small" color="primary" variant="flat">{{ form.disk_size_gb }} GB</v-chip>
            </div>
            <v-slider
              v-model="form.disk_size_gb"
              :min="minDiskSize"
              :max="200"
              :step="10"
              color="primary"
              track-color="grey-lighten-2"
              hide-details
            ></v-slider>
            <div v-if="minDiskSize > 10" class="text-caption text-grey mt-1">
              Minimum: {{ minDiskSize }} GB (Verkleinerung nicht möglich)
            </div>
          </div>

          <!-- Description -->
          <v-textarea
            v-model="form.description"
            label="Beschreibung"
            variant="outlined"
            density="compact"
            rows="2"
            hide-details
          ></v-textarea>
        </template>

        <!-- Fehler -->
        <v-alert
          v-if="error"
          type="error"
          variant="tonal"
          density="compact"
          class="mt-4"
        >
          {{ error }}
        </v-alert>

        <!-- Erfolg nach Speichern -->
        <v-alert
          v-if="result && !applyResult"
          type="success"
          variant="tonal"
          density="compact"
          class="mt-4"
        >
          <div><strong>{{ result.vm_name }}</strong> aktualisiert</div>
          <div v-if="result.needs_apply" class="text-caption mt-1">
            <v-icon size="small" class="mr-1">mdi-information</v-icon>
            Klicke "Apply" um die Änderungen in Proxmox zu übernehmen.
          </div>
        </v-alert>

        <!-- Apply läuft -->
        <v-alert
          v-if="applying"
          type="info"
          variant="tonal"
          density="compact"
          class="mt-4"
        >
          <div class="d-flex align-center">
            <v-progress-circular indeterminate size="20" width="2" class="mr-3"></v-progress-circular>
            <div>Terraform Apply läuft...</div>
          </div>
        </v-alert>

        <!-- Apply erfolgreich -->
        <v-alert
          v-if="applyResult"
          type="success"
          variant="tonal"
          density="compact"
          class="mt-4"
        >
          <div><strong>{{ result.vm_name }}</strong> Änderungen angewendet</div>
          <div v-if="wasRunning" class="text-caption mt-1">
            <v-icon size="small" class="mr-1">mdi-information</v-icon>
            VM muss neu gestartet werden damit CPU/RAM-Änderungen wirksam werden.
          </div>
        </v-alert>
      </v-card-text>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn @click="close" :disabled="saving || applying">
          {{ (result && !result.needs_apply) || applyResult ? 'Schließen' : 'Abbrechen' }}
        </v-btn>
        <!-- Speichern Button -->
        <v-btn
          v-if="!result"
          color="primary"
          variant="flat"
          @click="save"
          :loading="saving"
          :disabled="!hasChanges || loadingNodes"
        >
          <v-icon start>mdi-content-save</v-icon>
          Speichern
        </v-btn>
        <!-- Apply Button -->
        <v-btn
          v-if="result && result.needs_apply && !applyResult"
          color="warning"
          variant="flat"
          @click="applyChanges"
          :loading="applying"
        >
          <v-icon start>mdi-rocket-launch</v-icon>
          Apply
        </v-btn>
        <!-- Reboot Button -->
        <v-btn
          v-if="applyResult && wasRunning"
          color="error"
          variant="flat"
          @click="rebootVM"
          :loading="rebooting"
        >
          <v-icon start>mdi-restart</v-icon>
          Reboot
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import api from '@/api/client'

const emit = defineEmits(['updated', 'close'])

const dialog = ref(false)
const vm = ref(null)
const saving = ref(false)
const loadingNodes = ref(false)
const error = ref(null)
const result = ref(null)
const nodes = ref([])

// Apply/Reboot State
const applying = ref(false)
const applyResult = ref(null)
const rebooting = ref(false)
const wasRunning = ref(false)

// Formular-Daten
const form = ref({
  target_node: '',
  cores: 2,
  memory_gb: 2,
  disk_size_gb: 20,
  description: '',
})

// Ursprüngliche Werte für Vergleich
const originalValues = ref({})

// Computed Properties
const isDeployed = computed(() => {
  const status = vm.value?.status
  return status && !['planned', 'failed'].includes(status)
})

const minDiskSize = computed(() => {
  // Disk kann nicht verkleinert werden
  return originalValues.value.disk_size_gb || 10
})

const nodeItems = computed(() => {
  return nodes.value.map(n => ({
    ...n,
    label: `${n.name} (${n.cpus} CPUs, ${n.ram_gb} GB)`,
  }))
})

const hasChanges = computed(() => {
  return (
    form.value.target_node !== originalValues.value.target_node ||
    form.value.cores !== originalValues.value.cores ||
    form.value.memory_gb !== originalValues.value.memory_gb ||
    form.value.disk_size_gb !== originalValues.value.disk_size_gb ||
    form.value.description !== originalValues.value.description
  )
})

// Methoden
function getStatusColor(status) {
  const colors = {
    running: 'success',
    stopped: 'grey',
    deployed: 'info',
    planned: 'warning',
    failed: 'error',
  }
  return colors[status] || 'grey'
}

async function loadNodes() {
  loadingNodes.value = true
  try {
    const response = await api.get('/api/terraform/nodes')
    nodes.value = response.data
  } catch (e) {
    error.value = 'Node-Informationen konnten nicht geladen werden'
    console.error('Load nodes error:', e)
  } finally {
    loadingNodes.value = false
  }
}

async function open(vmData) {
  vm.value = vmData
  error.value = null
  result.value = null
  applyResult.value = null
  wasRunning.value = vmData.status === 'running'

  // Formular mit aktuellen Werten füllen
  form.value = {
    target_node: vmData.target_node || '',
    cores: vmData.cores || 2,
    memory_gb: vmData.memory_gb || 2,
    disk_size_gb: vmData.disk_size_gb || 20,
    description: vmData.description || '',
  }

  // Ursprüngliche Werte speichern
  originalValues.value = { ...form.value }

  dialog.value = true
  await loadNodes()
}

function close() {
  dialog.value = false
  if (result.value) {
    emit('updated', result.value)
  }
  emit('close')
}

async function save() {
  if (!hasChanges.value) return

  saving.value = true
  error.value = null

  try {
    // Nur geänderte Felder senden
    const updates = {}
    if (form.value.target_node !== originalValues.value.target_node) {
      updates.target_node = form.value.target_node
    }
    if (form.value.cores !== originalValues.value.cores) {
      updates.cores = form.value.cores
    }
    if (form.value.memory_gb !== originalValues.value.memory_gb) {
      updates.memory_gb = form.value.memory_gb
    }
    if (form.value.disk_size_gb !== originalValues.value.disk_size_gb) {
      updates.disk_size_gb = form.value.disk_size_gb
    }
    if (form.value.description !== originalValues.value.description) {
      updates.description = form.value.description
    }

    const response = await api.patch(`/api/terraform/vms/${vm.value.name}`, updates)
    result.value = response.data

  } catch (e) {
    error.value = e.response?.data?.detail || 'Fehler beim Speichern'
    console.error('Save error:', e)
  } finally {
    saving.value = false
  }
}

async function applyChanges() {
  applying.value = true
  error.value = null

  try {
    await api.post(`/api/terraform/vms/${vm.value.name}/apply`)
    applyResult.value = { success: true }
  } catch (e) {
    error.value = e.response?.data?.detail || 'Fehler beim Apply'
    console.error('Apply error:', e)
  } finally {
    applying.value = false
  }
}

async function rebootVM() {
  rebooting.value = true
  error.value = null

  try {
    await api.post(`/api/terraform/vms/${vm.value.name}/power/reboot`)
    // Dialog schließen nach erfolgreichem Reboot
    dialog.value = false
    emit('updated', { ...result.value, rebooted: true })
  } catch (e) {
    error.value = e.response?.data?.detail || 'Fehler beim Reboot'
    console.error('Reboot error:', e)
  } finally {
    rebooting.value = false
  }
}

defineExpose({ open })
</script>
