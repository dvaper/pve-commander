<template>
  <v-container fluid>
    <!-- Reboot-Dialog -->
    <v-dialog v-model="showRebootDialog" max-width="500">
      <v-card>
        <v-toolbar color="warning" density="compact">
          <v-icon class="ml-2">mdi-restart-alert</v-icon>
          <v-toolbar-title class="ml-2">Hosts neu starten</v-toolbar-title>
          <v-spacer></v-spacer>
          <v-btn icon size="small" @click="showRebootDialog = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-toolbar>

        <v-card-text class="pa-4">
          <v-alert type="warning" variant="tonal" density="compact" class="mb-4">
            Die ausgewählten Hosts werden neu gestartet. Laufende Dienste werden unterbrochen.
          </v-alert>

          <div class="text-subtitle-2 mb-2">Hosts für Neustart auswählen:</div>
          <v-list density="compact" class="reboot-host-list">
            <v-list-item
              v-for="host in hostsRequiringReboot"
              :key="host"
              @click="toggleRebootHost(host)"
            >
              <template v-slot:prepend>
                <v-checkbox-btn
                  :model-value="selectedRebootHosts.includes(host)"
                  @click.stop="toggleRebootHost(host)"
                ></v-checkbox-btn>
              </template>
              <v-list-item-title>{{ host }}</v-list-item-title>
              <template v-slot:append>
                <span class="text-medium-emphasis text-caption">{{ hostIpMap[host] }}</span>
              </template>
            </v-list-item>
          </v-list>

          <div class="d-flex justify-space-between mt-3">
            <v-btn size="small" variant="text" @click="selectAllRebootHosts">Alle auswählen</v-btn>
            <v-btn size="small" variant="text" @click="selectedRebootHosts = []">Keine auswählen</v-btn>
          </div>
        </v-card-text>

        <v-divider></v-divider>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="showRebootDialog = false">Abbrechen</v-btn>
          <v-btn
            color="warning"
            variant="flat"
            @click="executeReboot"
            :loading="rebootExecuting"
            :disabled="selectedRebootHosts.length === 0"
          >
            <v-icon start>mdi-restart</v-icon>
            {{ selectedRebootHosts.length }} Host(s) neu starten
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-row>
      <v-col cols="12">
        <v-card>
          <v-toolbar flat>
            <v-btn icon @click="$router.back()">
              <v-icon>mdi-arrow-left</v-icon>
            </v-btn>
            <v-toolbar-title>
              Ausführung #{{ executionId }}
            </v-toolbar-title>
            <v-spacer></v-spacer>
            <v-chip :color="getStatusColor(execution?.status)" class="mr-2">
              <v-icon start size="small">{{ getStatusIcon(execution?.status) }}</v-icon>
              {{ execution?.status || 'Loading...' }}
            </v-chip>
          </v-toolbar>

          <!-- Meta-Informationen -->
          <v-card-text v-if="execution">
            <v-row>
              <v-col cols="12" md="2">
                <div class="text-subtitle-2 text-grey">Typ</div>
                <div>{{ execution.execution_type }}</div>
              </v-col>
              <v-col cols="12" md="2">
                <div class="text-subtitle-2 text-grey">Playbook</div>
                <div>{{ execution.playbook_name || '-' }}</div>
              </v-col>
              <v-col cols="12" md="3">
                <div class="text-subtitle-2 text-grey">Ziel</div>
                <div>
                  <template v-if="execution.target_groups">
                    <v-tooltip
                      v-for="group in parseGroups(execution.target_groups)"
                      :key="group"
                      location="top"
                    >
                      <template v-slot:activator="{ props }">
                        <v-chip
                          v-bind="props"
                          size="x-small"
                          color="primary"
                          variant="outlined"
                          class="mr-1 mb-1 cursor-pointer"
                        >
                          <v-icon start size="x-small">mdi-folder-outline</v-icon>
                          {{ group }}
                        </v-chip>
                      </template>
                      <div class="text-caption">
                        <div class="font-weight-bold">{{ group }}</div>
                        <div v-if="groupHostsMap[group]?.length" class="ml-2">
                          <div v-for="host in groupHostsMap[group]" :key="host">
                            {{ host }} <span class="text-medium-emphasis">{{ hostIpMap[host] }}</span>
                          </div>
                        </div>
                        <div v-else class="text-medium-emphasis">(keine Hosts)</div>
                      </div>
                    </v-tooltip>
                  </template>
                  <template v-if="execution.target_hosts">
                    <v-chip
                      v-for="host in parseGroups(execution.target_hosts)"
                      :key="host"
                      size="x-small"
                      color="secondary"
                      variant="outlined"
                      class="mr-1 mb-1"
                    >
                      <v-icon start size="x-small">mdi-server</v-icon>
                      {{ host }}
                    </v-chip>
                  </template>
                  <span v-if="!execution.target_groups && !execution.target_hosts">-</span>
                </div>
              </v-col>
              <v-col cols="12" md="2">
                <div class="text-subtitle-2 text-grey">Gestartet</div>
                <div>{{ formatDate(execution.started_at) }}</div>
              </v-col>
              <v-col cols="12" md="2">
                <div class="text-subtitle-2 text-grey">Dauer</div>
                <div>{{ formatDuration(execution.duration_seconds) }}</div>
              </v-col>
            </v-row>
          </v-card-text>

          <v-divider></v-divider>

          <!-- Batch-Navigation -->
          <v-card-text v-if="batchSiblings.length > 1" class="py-2 batch-nav">
            <div class="d-flex align-center flex-wrap gap-2">
              <span class="text-caption text-grey mr-2">Batch:</span>
              <v-chip
                v-for="sibling in batchSiblings"
                :key="sibling.id"
                :color="sibling.id === executionId ? 'primary' : getStatusColor(sibling.status)"
                :variant="sibling.id === executionId ? 'flat' : 'outlined'"
                size="small"
                class="cursor-pointer"
                @click="navigateToSibling(sibling.id)"
              >
                <v-icon start size="x-small">{{ getStatusIcon(sibling.status) }}</v-icon>
                {{ sibling.batch_index + 1 }}. {{ sibling.playbook_name }}
              </v-chip>
            </div>
          </v-card-text>

          <v-divider v-if="batchSiblings.length > 1"></v-divider>

          <!-- Terminal Output -->
          <v-card-text>
            <div class="terminal" ref="terminalRef">
              <!-- Warte-Anzeige wenn noch keine Logs -->
              <div v-if="logs.length === 0 && isRunning" class="terminal-waiting">
                <v-progress-circular
                  indeterminate
                  size="20"
                  width="2"
                  color="primary"
                  class="mr-3"
                ></v-progress-circular>
                <span v-if="wsStatus === 'connecting'">Verbinde...</span>
                <span v-else-if="execution?.status === 'pending'">Warte auf Start...</span>
                <span v-else>Warte auf Ausgabe...</span>
              </div>
              <!-- Log-Ausgabe -->
              <div
                v-for="log in logs"
                :key="log.sequence_num"
                :class="['terminal-line', `terminal-${log.type}`]"
                v-html="parseAnsi(log.content)"
              ></div>
              <div v-if="wsStatus === 'connected' && logs.length > 0" class="terminal-cursor">█</div>
            </div>
          </v-card-text>

          <!-- Status Footer -->
          <v-card-actions v-if="isRunning">
            <v-progress-linear indeterminate color="primary"></v-progress-linear>
          </v-card-actions>

          <!-- Reboot-Hinweis wenn Hosts Neustart benötigen -->
          <v-card-actions v-if="hostsRequiringReboot.length > 0 && !isRunning" class="reboot-action">
            <v-alert
              type="warning"
              variant="tonal"
              density="compact"
              class="flex-grow-1 mr-3"
            >
              <div class="d-flex align-center">
                <v-icon class="mr-2">mdi-restart-alert</v-icon>
                <span>
                  <strong>{{ hostsRequiringReboot.length }}</strong> Host(s) benötigen einen Neustart:
                  {{ hostsRequiringReboot.join(', ') }}
                </span>
              </div>
            </v-alert>
            <v-btn
              color="warning"
              variant="flat"
              @click="openRebootDialog"
            >
              <v-icon start>mdi-restart</v-icon>
              Hosts neu starten
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useWebSocket } from '@/composables/useWebSocket'
import { useExecutionStore } from '@/stores/execution'
import api from '@/api/client'
import AnsiToHtml from 'ansi-to-html'
import { formatDate, formatDuration, getStatusColor, getStatusIcon } from '@/utils/formatting'

// ANSI-Parser mit angepassten Farben (dunkleres Theme)
const ansiConverter = new AnsiToHtml({
  fg: '#d4d4d4',
  bg: '#1e1e1e',
  colors: {
    0: '#1e1e1e',  // Black
    1: '#f44747',  // Red
    2: '#6a9955',  // Green
    3: '#dcdcaa',  // Yellow
    4: '#569cd6',  // Blue
    5: '#c586c0',  // Magenta
    6: '#4ec9b0',  // Cyan
    7: '#d4d4d4',  // White
    8: '#808080',  // Bright Black (Gray)
    9: '#f44747',  // Bright Red
    10: '#6a9955', // Bright Green
    11: '#dcdcaa', // Bright Yellow
    12: '#569cd6', // Bright Blue
    13: '#c586c0', // Bright Magenta
    14: '#4ec9b0', // Bright Cyan
    15: '#ffffff', // Bright White
  },
  escapeXML: true,
})

// ANSI-Codes zu HTML konvertieren
function parseAnsi(text) {
  if (!text) return ''
  return ansiConverter.toHtml(text)
}

const route = useRoute()
const router = useRouter()
const executionStore = useExecutionStore()
const executionId = computed(() => parseInt(route.params.id))

const execution = ref(null)
const terminalRef = ref(null)
const batchSiblings = ref([])

// Gruppen-Hosts-Map und Host-IP-Map für Tooltips
const groupHostsMap = ref({})
const hostIpMap = ref({})

// Reboot-Dialog State
const showRebootDialog = ref(false)
const selectedRebootHosts = ref([])
const rebootExecuting = ref(false)

// WebSocket
const { connected, logs, status: wsStatus, connect, disconnect } = useWebSocket(executionId.value)

// Computed: Läuft die Ausführung noch?
const isRunning = computed(() => {
  // Beendet laut WebSocket?
  if (['success', 'failed', 'cancelled'].includes(wsStatus.value)) {
    return false
  }
  // Beendet laut Execution-Daten?
  if (execution.value && ['success', 'failed', 'cancelled'].includes(execution.value.status)) {
    return false
  }
  // Sonst: läuft noch (oder pending)
  return execution.value?.status === 'running' || execution.value?.status === 'pending'
})

// Computed: Hosts die Neustart benötigen (aus Logs extrahieren)
const hostsRequiringReboot = computed(() => {
  const hosts = new Set()
  let currentHost = null

  for (const log of logs.value) {
    if (!log.content) continue

    // Task-Name enthält Hostname: "TASK [hostname]" oder "ok: [hostname]"
    const taskMatch = log.content.match(/^(?:ok|changed|fatal|skipping):\s*\[([^\]]+)\]/)
    if (taskMatch) {
      currentHost = taskMatch[1]
    }

    // Neustart erforderlich erkennen
    if (log.content.includes('NEUSTART ERFORDERLICH') && currentHost) {
      hosts.add(currentHost)
    }
  }

  return Array.from(hosts)
})

async function loadExecution() {
  try {
    const response = await api.get(`/api/executions/${executionId.value}`)
    execution.value = response.data
  } catch (e) {
    console.error('Laden fehlgeschlagen:', e)
  }
}

async function loadBatchSiblings() {
  try {
    const response = await api.get(`/api/executions/${executionId.value}/batch-siblings`)
    batchSiblings.value = response.data
  } catch (e) {
    // Kein Batch - ignorieren
    batchSiblings.value = []
  }
}

function navigateToSibling(siblingId) {
  if (siblingId !== executionId.value) {
    router.push(`/executions/${siblingId}`)
  }
}

async function loadInventoryData() {
  try {
    const [groupsResponse, hostsResponse] = await Promise.all([
      api.get('/api/inventory/groups'),
      api.get('/api/inventory/hosts'),
    ])

    // Gruppen-Hosts-Map aufbauen
    const gMap = {}
    for (const group of groupsResponse.data) {
      gMap[group.name] = group.hosts || []
    }
    groupHostsMap.value = gMap

    // Host-IP-Map aufbauen
    const hMap = {}
    for (const host of hostsResponse.data) {
      hMap[host.name] = host.ansible_host || host.ip || ''
    }
    hostIpMap.value = hMap
  } catch (e) {
    console.error('Inventory laden fehlgeschlagen:', e)
  }
}

function parseGroups(jsonStr) {
  if (!jsonStr) return []
  try {
    return JSON.parse(jsonStr)
  } catch {
    // Fallback: Komma-separiert
    return jsonStr.split(',').map(s => s.trim()).filter(Boolean)
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (terminalRef.value) {
      terminalRef.value.scrollTop = terminalRef.value.scrollHeight
    }
  })
}

// Auto-scroll bei neuen Logs
watch(logs, scrollToBottom, { deep: true })

// Bei Route-Wechsel (Batch-Navigation) Daten neu laden
watch(executionId, async (newId) => {
  disconnect()
  logs.value = []
  execution.value = null
  batchSiblings.value = []
  await Promise.all([
    loadExecution(),
    loadBatchSiblings(),
  ])
  connect(newId)
})

// Bei "finished" Status die Execution-Daten neu laden
watch(wsStatus, (newStatus) => {
  if (newStatus === 'success' || newStatus === 'failed' || newStatus === 'cancelled') {
    loadExecution()
    loadBatchSiblings() // Batch-Status aktualisieren
  }
})

// Reboot-Dialog Funktionen
function openRebootDialog() {
  selectedRebootHosts.value = [...hostsRequiringReboot.value]
  showRebootDialog.value = true
}

function toggleRebootHost(host) {
  const index = selectedRebootHosts.value.indexOf(host)
  if (index === -1) {
    selectedRebootHosts.value.push(host)
  } else {
    selectedRebootHosts.value.splice(index, 1)
  }
}

function selectAllRebootHosts() {
  selectedRebootHosts.value = [...hostsRequiringReboot.value]
}

async function executeReboot() {
  rebootExecuting.value = true
  try {
    const result = await executionStore.runAnsible({
      playbook_name: 'reboot',
      target_hosts: selectedRebootHosts.value,
      target_groups: null,
    })

    showRebootDialog.value = false
    // Zur neuen Execution navigieren
    router.push(`/executions/${result.id}`)
  } catch (e) {
    console.error('Reboot-Ausführung fehlgeschlagen:', e)
  } finally {
    rebootExecuting.value = false
  }
}

onMounted(async () => {
  await Promise.all([
    loadExecution(),
    loadInventoryData(),
    loadBatchSiblings(),
  ])
  connect()
})
</script>

<style scoped>
.terminal {
  background: #1e1e1e;
  color: #d4d4d4;
  font-family: 'JetBrains Mono', 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
  padding: 16px;
  border-radius: 4px;
  min-height: 400px;
  max-height: 600px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.terminal-line {
  margin: 0;
}

.terminal-waiting {
  display: flex;
  align-items: center;
  color: #808080;
  padding: 8px 0;
}

/* Fallback-Farben wenn keine ANSI-Codes vorhanden */
.terminal-stdout {
  color: #d4d4d4;
}

.terminal-stderr {
  color: #f48771;
}

.terminal-cursor {
  display: inline;
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

/* Bold/Bright Text */
.terminal :deep(b),
.terminal :deep(strong) {
  font-weight: 600;
}

.cursor-pointer {
  cursor: pointer;
}

.reboot-action {
  background: rgba(251, 140, 0, 0.05);
  border-top: 1px solid rgba(251, 140, 0, 0.2);
}

.reboot-host-list {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 4px;
  max-height: 250px;
  overflow-y: auto;
}

.batch-nav {
  background: rgba(var(--v-theme-surface-variant), 0.3);
}

.gap-2 {
  gap: 8px;
}
</style>
