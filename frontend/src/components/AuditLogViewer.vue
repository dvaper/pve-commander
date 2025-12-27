<template>
  <v-card>
    <v-toolbar flat density="compact">
      <v-icon class="ml-2 mr-2">mdi-clipboard-text-clock</v-icon>
      <v-toolbar-title class="text-body-1">Audit-Log</v-toolbar-title>
      <v-spacer />
      <v-chip
        :color="chainValid ? 'success' : 'error'"
        size="small"
        class="mr-2"
      >
        <v-icon start size="small">
          {{ chainValid ? 'mdi-check-circle' : 'mdi-alert-circle' }}
        </v-icon>
        {{ chainValid ? 'Chain intakt' : 'Kompromittiert' }}
      </v-chip>
      <v-btn
        variant="text"
        size="small"
        :loading="verifying"
        @click="verifyChain"
      >
        <v-icon start>mdi-shield-check</v-icon>
        Pruefen
      </v-btn>
      <v-btn
        variant="text"
        size="small"
        @click="loadData"
        :loading="loading"
      >
        <v-icon>mdi-refresh</v-icon>
      </v-btn>
    </v-toolbar>

    <!-- Filters -->
    <v-card-text class="pb-0">
      <v-row dense>
        <v-col cols="12" sm="3">
          <v-select
            v-model="filters.action_type"
            :items="['CREATE', 'UPDATE', 'DELETE', 'EXECUTE', 'LOGIN', 'LOGOUT']"
            label="Aktion"
            clearable
            density="compact"
            hide-details
            @update:model-value="loadData"
          />
        </v-col>
        <v-col cols="12" sm="3">
          <v-select
            v-model="filters.resource_type"
            :items="['vm', 'user', 'playbook', 'execution', 'setting']"
            label="Ressource"
            clearable
            density="compact"
            hide-details
            @update:model-value="loadData"
          />
        </v-col>
        <v-col cols="12" sm="3">
          <v-text-field
            v-model="filters.start_date"
            label="Von"
            type="date"
            density="compact"
            hide-details
            @update:model-value="loadData"
          />
        </v-col>
        <v-col cols="12" sm="3">
          <v-text-field
            v-model="filters.end_date"
            label="Bis"
            type="date"
            density="compact"
            hide-details
            @update:model-value="loadData"
          />
        </v-col>
      </v-row>
    </v-card-text>

    <v-data-table
      :headers="headers"
      :items="logs"
      :loading="loading"
      :items-per-page="10"
      density="compact"
    >
      <template v-slot:item.timestamp="{ item }">
        <span class="text-caption">{{ formatDate(item.timestamp) }}</span>
      </template>

      <template v-slot:item.action_type="{ item }">
        <v-chip :color="getActionColor(item.action_type)" size="x-small" label>
          {{ item.action_type }}
        </v-chip>
      </template>

      <template v-slot:item.resource_type="{ item }">
        <v-chip size="x-small" variant="outlined">
          {{ item.resource_type }}
        </v-chip>
      </template>

      <template v-slot:item.resource="{ item }">
        <span v-if="item.resource_name">{{ item.resource_name }}</span>
        <span v-else class="text-grey">-</span>
      </template>

      <template v-slot:item.actions="{ item }">
        <v-btn icon variant="text" size="x-small" @click="showDetails(item)">
          <v-icon>mdi-eye</v-icon>
        </v-btn>
      </template>
    </v-data-table>

    <!-- Detail Dialog -->
    <v-dialog v-model="detailDialog" max-width="600">
      <v-card v-if="selectedLog">
        <v-card-title>
          <v-icon start>mdi-text-box-search</v-icon>
          Audit-Details
        </v-card-title>
        <v-card-text>
          <v-list density="compact">
            <v-list-item>
              <v-list-item-title>Zeitstempel</v-list-item-title>
              <v-list-item-subtitle>{{ formatDate(selectedLog.timestamp) }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <v-list-item-title>Benutzer</v-list-item-title>
              <v-list-item-subtitle>{{ selectedLog.username || 'System' }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <v-list-item-title>Aktion</v-list-item-title>
              <v-list-item-subtitle>
                <v-chip :color="getActionColor(selectedLog.action_type)" size="small" label>
                  {{ selectedLog.action_type }}
                </v-chip>
              </v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <v-list-item-title>Ressource</v-list-item-title>
              <v-list-item-subtitle>
                {{ selectedLog.resource_type }}
                <span v-if="selectedLog.resource_name">: {{ selectedLog.resource_name }}</span>
              </v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <v-list-item-title>IP-Adresse</v-list-item-title>
              <v-list-item-subtitle>{{ selectedLog.ip_address || '-' }}</v-list-item-subtitle>
            </v-list-item>
          </v-list>

          <div v-if="selectedLog.details" class="mt-4">
            <div class="text-subtitle-2 mb-2">Details</div>
            <v-code class="pa-2 d-block" style="white-space: pre-wrap; font-size: 11px;">{{ formatJson(selectedLog.details) }}</v-code>
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="detailDialog = false">Schliessen</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuditStore } from '@/stores/audit'

const auditStore = useAuditStore()

const loading = ref(false)
const verifying = ref(false)
const chainValid = ref(true)
const logs = ref([])

const filters = ref({
  action_type: null,
  resource_type: null,
  start_date: null,
  end_date: null,
})

const detailDialog = ref(false)
const selectedLog = ref(null)

const headers = [
  { title: 'Zeit', key: 'timestamp', width: '150px' },
  { title: 'Benutzer', key: 'username', width: '100px' },
  { title: 'Aktion', key: 'action_type', width: '90px' },
  { title: 'Ressource', key: 'resource_type', width: '100px' },
  { title: 'Name', key: 'resource' },
  { title: '', key: 'actions', width: '50px', sortable: false },
]

function formatDate(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('de-DE', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  })
}

function formatJson(obj) {
  if (!obj) return ''
  if (typeof obj === 'string') {
    try { obj = JSON.parse(obj) } catch { return obj }
  }
  return JSON.stringify(obj, null, 2)
}

function getActionColor(action) {
  const colors = {
    CREATE: 'success', UPDATE: 'warning', DELETE: 'error',
    EXECUTE: 'purple', LOGIN: 'primary', LOGOUT: 'grey'
  }
  return colors[action] || 'grey'
}

function showDetails(log) {
  selectedLog.value = log
  detailDialog.value = true
}

async function loadData() {
  loading.value = true
  try {
    // Filter setzen
    for (const [key, value] of Object.entries(filters.value)) {
      auditStore.setFilter(key, value)
    }
    await auditStore.fetchLogs(1)
    logs.value = auditStore.logs
  } catch (e) {
    console.error('Laden fehlgeschlagen:', e)
  } finally {
    loading.value = false
  }
}

async function verifyChain() {
  verifying.value = true
  try {
    await auditStore.verifyChain()
    chainValid.value = auditStore.verificationResult?.is_valid ?? true
  } finally {
    verifying.value = false
  }
}

onMounted(loadData)
</script>
