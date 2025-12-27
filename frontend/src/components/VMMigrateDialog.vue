<template>
  <v-dialog v-model="dialog" max-width="650" persistent>
    <v-card>
      <v-toolbar color="primary" density="compact">
        <v-icon class="ml-2 mr-2">mdi-server-network</v-icon>
        <v-toolbar-title>VM migrieren</v-toolbar-title>
        <v-spacer></v-spacer>
        <v-btn icon size="small" @click="close" :disabled="migrating">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-toolbar>

      <v-card-text class="pt-4">
        <!-- Aktuelle VM-Info -->
        <v-alert type="info" variant="tonal" density="compact" class="mb-4">
          <div class="d-flex align-center">
            <div class="flex-grow-1">
              <strong>{{ vm?.name }}</strong> auf Node <strong>{{ vm?.target_node }}</strong>
            </div>
            <v-chip
              :color="getStatusColor(vm?.status)"
              size="small"
              variant="flat"
            >
              {{ vm?.status }}
            </v-chip>
          </div>
          <div class="text-caption mt-1">
            VMID: {{ vm?.vmid }} | {{ vm?.cores }} CPUs, {{ vm?.memory_gb }} GB RAM
          </div>
        </v-alert>

        <!-- Migration läuft -->
        <template v-if="migrating">
          <v-card variant="outlined" class="pa-4">
            <div class="text-center">
              <v-progress-circular
                indeterminate
                color="primary"
                size="64"
                width="6"
              ></v-progress-circular>

              <div class="text-h6 mt-4">Migration läuft...</div>
              <div class="text-body-2 text-grey mt-2">
                {{ vm?.name }} → {{ targetNode }}
              </div>

              <v-chip
                :color="migrationStatus === 'running' ? 'info' : 'grey'"
                variant="tonal"
                class="mt-4"
              >
                <v-icon start size="small">mdi-sync</v-icon>
                {{ migrationStatusText }}
              </v-chip>

              <div class="text-caption text-grey mt-4">
                Verstrichene Zeit: {{ elapsedTime }}
              </div>
            </div>
          </v-card>
        </template>

        <!-- Node-Auswahl (wenn nicht migrierend) -->
        <template v-else-if="!result">
          <!-- Loading Cluster-Stats -->
          <div v-if="loadingStats" class="text-center py-4">
            <v-progress-circular indeterminate color="primary"></v-progress-circular>
            <div class="text-caption mt-2">Lade Node-Statistiken...</div>
          </div>

          <template v-else>
            <div class="text-subtitle-2 mb-2">Ziel-Node auswählen</div>

            <v-radio-group v-model="targetNode" class="mt-0">
              <v-card
                v-for="node in sortedNodes"
                :key="node.name"
                :variant="targetNode === node.name ? 'tonal' : 'outlined'"
                :color="targetNode === node.name ? 'primary' : undefined"
                class="mb-2 pa-2"
                :class="{ 'node-disabled': node.name === vm?.target_node }"
                @click="node.name !== vm?.target_node && (targetNode = node.name)"
                style="cursor: pointer;"
              >
                <div class="d-flex align-center">
                  <v-radio
                    :value="node.name"
                    :disabled="node.name === vm?.target_node"
                    hide-details
                    class="mr-2"
                  ></v-radio>

                  <div class="flex-grow-1">
                    <div class="d-flex align-center">
                      <v-icon
                        :color="node.status === 'online' ? 'success' : 'error'"
                        size="small"
                        class="mr-1"
                      >
                        {{ node.status === 'online' ? 'mdi-check-circle' : 'mdi-alert-circle' }}
                      </v-icon>
                      <strong>{{ node.name }}</strong>
                      <span v-if="node.name === vm?.target_node" class="text-grey ml-2">(aktuell)</span>
                      <v-chip
                        v-if="node.name === recommendedNode?.name && node.name !== vm?.target_node"
                        color="success"
                        size="x-small"
                        variant="flat"
                        class="ml-2"
                      >
                        Empfohlen
                      </v-chip>
                    </div>
                  </div>

                  <!-- CPU/RAM Statistiken -->
                  <div class="d-flex align-center gap-4" style="min-width: 200px;">
                    <div class="text-center" style="width: 85px;">
                      <div class="text-caption text-grey">CPU</div>
                      <v-progress-linear
                        :model-value="node.cpu_usage * 100"
                        :color="getCpuColor(node.cpu_usage * 100)"
                        height="6"
                        rounded
                      ></v-progress-linear>
                      <div class="text-caption">{{ (node.cpu_usage * 100).toFixed(0) }}%</div>
                    </div>
                    <div class="text-center" style="width: 85px;">
                      <div class="text-caption text-grey">RAM</div>
                      <v-progress-linear
                        :model-value="node.memory_percent"
                        :color="getMemoryColor(node.memory_percent)"
                        height="6"
                        rounded
                      ></v-progress-linear>
                      <div class="text-caption">{{ node.memory_percent.toFixed(0) }}%</div>
                    </div>
                  </div>
                </div>
              </v-card>
            </v-radio-group>

            <!-- Migrations-Hinweis -->
            <v-alert type="warning" variant="tonal" density="compact" class="mt-4">
              <v-icon start size="small">mdi-information</v-icon>
              Die VM wird während der Migration gestoppt und danach automatisch wieder gestartet.
            </v-alert>
          </template>
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

        <!-- Erfolg -->
        <v-alert
          v-if="result"
          type="success"
          variant="tonal"
          density="compact"
          class="mt-4"
        >
          <div><strong>{{ result.vm_name }}</strong> erfolgreich migriert</div>
          <div class="text-caption">
            {{ result.source_node }} → {{ result.target_node }}
            <span v-if="result.restarted"> | VM wurde neu gestartet</span>
          </div>
        </v-alert>
      </v-card-text>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn @click="close" :disabled="migrating">
          {{ result ? 'Schließen' : 'Abbrechen' }}
        </v-btn>
        <v-btn
          v-if="!result && !migrating"
          color="primary"
          variant="flat"
          @click="startMigration"
          :loading="loading"
          :disabled="!targetNode || targetNode === vm?.target_node"
        >
          <v-icon start>mdi-server-network</v-icon>
          Migrieren
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import api from '@/api/client'

const emit = defineEmits(['migrated', 'close'])

const dialog = ref(false)
const vm = ref(null)
const targetNode = ref('')
const loading = ref(false)
const loadingStats = ref(false)
const error = ref(null)
const result = ref(null)
const clusterStats = ref(null)

// Migration State
const migrating = ref(false)
const migrationUpid = ref(null)
const migrationNode = ref(null)
const migrationStatus = ref('pending')
const wasRunning = ref(false)
const startTime = ref(null)
const elapsedTime = ref('0:00')
let statusPollInterval = null
let elapsedInterval = null

// Nodes nach RAM-Auslastung sortiert (niedrigste zuerst)
const sortedNodes = computed(() => {
  if (!clusterStats.value?.nodes) return []
  return [...clusterStats.value.nodes].sort((a, b) => a.memory_percent - b.memory_percent)
})

// Node mit geringster Auslastung (außer aktuellem)
const recommendedNode = computed(() => {
  return sortedNodes.value.find(n => n.name !== vm.value?.target_node && n.status === 'online')
})

const migrationStatusText = computed(() => {
  switch (migrationStatus.value) {
    case 'running': return 'Daten werden übertragen...'
    case 'stopped': return 'Abgeschlossen'
    default: return 'Wird vorbereitet...'
  }
})

function getStatusColor(status) {
  const colors = {
    running: 'success',
    stopped: 'grey',
    deployed: 'info',
    planned: 'warning',
  }
  return colors[status] || 'grey'
}

function getCpuColor(percent) {
  if (percent > 80) return 'error'
  if (percent > 60) return 'warning'
  return 'success'
}

function getMemoryColor(percent) {
  if (percent > 85) return 'error'
  if (percent > 70) return 'warning'
  return 'success'
}

function updateElapsedTime() {
  if (!startTime.value) return
  const seconds = Math.floor((Date.now() - startTime.value) / 1000)
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  elapsedTime.value = `${mins}:${secs.toString().padStart(2, '0')}`
}

async function loadClusterStats() {
  loadingStats.value = true
  try {
    const response = await api.get('/api/terraform/cluster/stats')
    clusterStats.value = response.data
  } catch (e) {
    error.value = 'Cluster-Statistiken konnten nicht geladen werden'
    console.error('Cluster stats error:', e)
  } finally {
    loadingStats.value = false
  }
}

async function open(vmData) {
  vm.value = vmData
  targetNode.value = ''
  error.value = null
  result.value = null
  clusterStats.value = null
  migrating.value = false
  migrationUpid.value = null
  migrationStatus.value = 'pending'
  dialog.value = true

  await loadClusterStats()

  if (recommendedNode.value) {
    targetNode.value = recommendedNode.value.name
  }
}

function close() {
  stopPolling()
  dialog.value = false
  if (result.value) {
    emit('migrated', result.value)
  }
  emit('close')
}

function stopPolling() {
  if (statusPollInterval) {
    clearInterval(statusPollInterval)
    statusPollInterval = null
  }
  if (elapsedInterval) {
    clearInterval(elapsedInterval)
    elapsedInterval = null
  }
}

async function pollMigrationStatus() {
  if (!migrationUpid.value || !migrationNode.value) return

  try {
    const response = await api.get(
      `/api/terraform/tasks/${migrationNode.value}/${encodeURIComponent(migrationUpid.value)}/status`
    )

    const data = response.data
    migrationStatus.value = data.status

    if (data.finished) {
      stopPolling()

      if (data.task_success) {
        // Migration erfolgreich - abschließen
        await completeMigration()
      } else {
        // Migration fehlgeschlagen
        migrating.value = false
        error.value = `Migration fehlgeschlagen: ${data.exitstatus || 'Unbekannter Fehler'}`
      }
    }
  } catch (e) {
    console.error('Status poll error:', e)
    // Bei Fehler weiter versuchen, nicht abbrechen
  }
}

async function completeMigration() {
  try {
    const response = await api.post(`/api/terraform/vms/${vm.value.name}/migrate/complete`, {
      target_node: targetNode.value,
      was_running: wasRunning.value,
    })

    result.value = response.data
    migrating.value = false
  } catch (e) {
    error.value = 'Migration abgeschlossen, aber Nachbearbeitung fehlgeschlagen: ' +
      (e.response?.data?.detail || e.message)
    migrating.value = false
  }
}

async function startMigration() {
  if (!targetNode.value || targetNode.value === vm.value?.target_node) return

  loading.value = true
  error.value = null

  try {
    // 1. Migration starten
    const response = await api.post(`/api/terraform/vms/${vm.value.name}/migrate/start`, {
      target_node: targetNode.value,
    })

    const data = response.data

    if (!data.success) {
      error.value = data.error || 'Migration konnte nicht gestartet werden'
      loading.value = false
      return
    }

    // 2. Polling starten
    migrationUpid.value = data.upid
    migrationNode.value = data.source_node
    wasRunning.value = data.was_running
    migrating.value = true
    loading.value = false
    startTime.value = Date.now()

    // Timer für verstrichene Zeit
    elapsedInterval = setInterval(updateElapsedTime, 1000)

    // Status alle 3 Sekunden abfragen
    statusPollInterval = setInterval(pollMigrationStatus, 3000)

    // Ersten Status sofort abfragen
    await pollMigrationStatus()

  } catch (e) {
    error.value = e.response?.data?.detail || 'Migration konnte nicht gestartet werden'
    loading.value = false
  }
}

onUnmounted(() => {
  stopPolling()
})

defineExpose({ open })
</script>

<style scoped>
.node-disabled {
  opacity: 0.5;
  cursor: not-allowed !important;
}

.gap-4 {
  gap: 16px;
}
</style>
