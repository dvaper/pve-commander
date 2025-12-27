<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <h1 class="text-h4 mb-4">Audit-Log</h1>
      </v-col>
    </v-row>

    <!-- Stats Cards -->
    <v-row v-if="stats" class="mb-4">
      <v-col cols="12" md="3">
        <v-card>
          <v-card-text class="text-center">
            <div class="text-h4">{{ stats.total_entries }}</div>
            <div class="text-subtitle-1">Gesamt-Eintraege</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card>
          <v-card-text class="text-center">
            <div class="text-h4">{{ stats.entries_today }}</div>
            <div class="text-subtitle-1">Heute</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card>
          <v-card-text class="text-center">
            <div class="text-h4">{{ stats.unique_users }}</div>
            <div class="text-subtitle-1">Aktive Benutzer</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card :color="chainValid ? 'success' : 'error'" dark>
          <v-card-text class="text-center">
            <v-icon size="32">{{ chainValid ? 'mdi-check-circle' : 'mdi-alert-circle' }}</v-icon>
            <div class="text-subtitle-1 mt-2">
              {{ chainValid ? 'Chain intakt' : 'Chain kompromittiert' }}
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Filters -->
    <v-card class="mb-4">
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2">mdi-filter</v-icon>
        Filter
        <v-spacer />
        <v-btn
          v-if="auditStore.hasFilters"
          variant="text"
          color="primary"
          @click="clearFilters"
        >
          Filter zuruecksetzen
        </v-btn>
      </v-card-title>
      <v-card-text>
        <v-row>
          <v-col cols="12" md="3">
            <v-select
              v-model="filters.action_type"
              :items="actionTypeItems"
              label="Aktion"
              clearable
              density="compact"
              @update:model-value="applyFilter('action_type', $event)"
            />
          </v-col>
          <v-col cols="12" md="3">
            <v-select
              v-model="filters.resource_type"
              :items="resourceTypeItems"
              label="Ressource"
              clearable
              density="compact"
              @update:model-value="applyFilter('resource_type', $event)"
            />
          </v-col>
          <v-col cols="12" md="3">
            <v-text-field
              v-model="filters.start_date"
              label="Von"
              type="date"
              density="compact"
              @update:model-value="applyFilter('start_date', $event)"
            />
          </v-col>
          <v-col cols="12" md="3">
            <v-text-field
              v-model="filters.end_date"
              label="Bis"
              type="date"
              density="compact"
              @update:model-value="applyFilter('end_date', $event)"
            />
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Actions -->
    <v-row class="mb-4">
      <v-col cols="12" class="d-flex gap-2">
        <v-btn
          color="primary"
          variant="outlined"
          :loading="verifying"
          @click="verifyChain"
        >
          <v-icon start>mdi-shield-check</v-icon>
          Chain verifizieren
        </v-btn>
        <v-btn
          color="secondary"
          variant="outlined"
          @click="exportLogs('json')"
        >
          <v-icon start>mdi-download</v-icon>
          JSON Export
        </v-btn>
        <v-btn
          color="secondary"
          variant="outlined"
          @click="exportLogs('csv')"
        >
          <v-icon start>mdi-file-delimited</v-icon>
          CSV Export
        </v-btn>
        <v-spacer />
        <v-btn
          color="primary"
          variant="text"
          :loading="loading"
          @click="refresh"
        >
          <v-icon start>mdi-refresh</v-icon>
          Aktualisieren
        </v-btn>
      </v-col>
    </v-row>

    <!-- Log Table -->
    <v-card>
      <v-data-table-server
        v-model:page="currentPage"
        :headers="headers"
        :items="auditStore.logs"
        :items-length="auditStore.totalLogs"
        :loading="loading"
        :items-per-page="pageSize"
        :items-per-page-options="[25, 50, 100]"
        density="compact"
        @update:page="loadPage"
        @update:items-per-page="updatePageSize"
      >
        <template #item.timestamp="{ item }">
          {{ formatDate(item.timestamp) }}
        </template>

        <template #item.action_type="{ item }">
          <v-chip
            :color="getActionColor(item.action_type)"
            size="small"
            label
          >
            {{ item.action_type }}
          </v-chip>
        </template>

        <template #item.resource_type="{ item }">
          <v-chip size="small" variant="outlined">
            {{ item.resource_type }}
          </v-chip>
        </template>

        <template #item.resource="{ item }">
          <span v-if="item.resource_name">{{ item.resource_name }}</span>
          <span v-else-if="item.resource_id" class="text-grey">
            ID: {{ item.resource_id }}
          </span>
          <span v-else class="text-grey">-</span>
        </template>

        <template #item.is_rollbackable="{ item }">
          <v-icon
            v-if="item.is_rollbackable && !item.rollback_executed"
            color="success"
            size="small"
          >
            mdi-undo-variant
          </v-icon>
          <v-icon
            v-else-if="item.rollback_executed"
            color="grey"
            size="small"
          >
            mdi-check
          </v-icon>
        </template>

        <template #item.actions="{ item }">
          <v-btn
            icon
            variant="text"
            size="small"
            @click="showDetails(item)"
          >
            <v-icon>mdi-eye</v-icon>
          </v-btn>
        </template>
      </v-data-table-server>
    </v-card>

    <!-- Detail Dialog -->
    <v-dialog v-model="detailDialog" max-width="700">
      <v-card v-if="selectedLog">
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2">mdi-text-box-search</v-icon>
          Audit-Log Details
          <v-spacer />
          <v-btn icon variant="text" @click="detailDialog = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        <v-divider />
        <v-card-text>
          <v-list density="compact">
            <v-list-item>
              <v-list-item-title>Sequenz</v-list-item-title>
              <v-list-item-subtitle>{{ selectedLog.sequence }}</v-list-item-subtitle>
            </v-list-item>
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

          <v-divider class="my-3" />

          <div v-if="selectedLog.details" class="mb-3">
            <div class="text-subtitle-2 mb-2">Details</div>
            <v-code class="pa-2 d-block" style="white-space: pre-wrap; font-size: 12px;">{{ formatJson(selectedLog.details) }}</v-code>
          </div>

          <div class="mb-3">
            <div class="text-subtitle-2 mb-2">Hash-Chain</div>
            <v-list density="compact">
              <v-list-item>
                <v-list-item-title class="text-caption">Entry Hash</v-list-item-title>
                <v-list-item-subtitle class="text-mono" style="font-size: 10px;">
                  {{ selectedLog.entry_hash }}
                </v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <v-list-item-title class="text-caption">Previous Hash</v-list-item-title>
                <v-list-item-subtitle class="text-mono" style="font-size: 10px;">
                  {{ selectedLog.previous_hash || 'Genesis' }}
                </v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </div>

          <div v-if="selectedLog.is_rollbackable && !selectedLog.rollback_executed">
            <v-divider class="my-3" />
            <v-btn color="warning" variant="outlined" block>
              <v-icon start>mdi-undo</v-icon>
              Rollback anfordern
            </v-btn>
          </div>
        </v-card-text>
      </v-card>
    </v-dialog>

    <!-- Verification Result Dialog -->
    <v-dialog v-model="verificationDialog" max-width="500">
      <v-card>
        <v-card-title
          :class="verificationResult?.is_valid ? 'bg-success' : 'bg-error'"
          class="text-white"
        >
          <v-icon class="mr-2">
            {{ verificationResult?.is_valid ? 'mdi-check-circle' : 'mdi-alert-circle' }}
          </v-icon>
          Chain-Verifikation
        </v-card-title>
        <v-card-text class="pt-4">
          <template v-if="verificationResult">
            <v-list density="compact">
              <v-list-item>
                <v-list-item-title>Status</v-list-item-title>
                <v-list-item-subtitle>
                  {{ verificationResult.is_valid ? 'Intakt' : 'Kompromittiert oder Fehler' }}
                </v-list-item-subtitle>
              </v-list-item>
              <v-list-item v-if="verificationResult.entries_checked > 0">
                <v-list-item-title>Verifizierte Eintraege</v-list-item-title>
                <v-list-item-subtitle>{{ verificationResult.entries_checked }}</v-list-item-subtitle>
              </v-list-item>
              <v-list-item v-if="verificationResult.verification_time_ms > 0">
                <v-list-item-title>Verifikationszeit</v-list-item-title>
                <v-list-item-subtitle>
                  {{ verificationResult.verification_time_ms?.toFixed(2) }} ms
                </v-list-item-subtitle>
              </v-list-item>
            </v-list>

            <v-alert
              v-if="verificationResult.errors?.length"
              type="error"
              class="mt-4"
            >
              <div class="font-weight-bold mb-2">Fehler:</div>
              <div v-for="(entry, idx) in verificationResult.errors" :key="idx">
                <template v-if="entry.sequence > 0">Sequenz {{ entry.sequence }}: </template>
                {{ entry.error }}
              </div>
            </v-alert>
          </template>
          <template v-else>
            <v-alert type="warning">
              Keine Verifikationsdaten vorhanden.
            </v-alert>
          </template>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="verificationDialog = false">Schliessen</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuditStore } from '@/stores/audit'

const auditStore = useAuditStore()

// State
const loading = computed(() => auditStore.loading)
const verifying = computed(() => auditStore.verifying)
const currentPage = ref(1)
const pageSize = ref(50)
const stats = ref(null)
const chainValid = ref(true)

// Filters
const filters = ref({
  action_type: null,
  resource_type: null,
  start_date: null,
  end_date: null,
})

// Action/Resource types for dropdowns
const actionTypeItems = ref([])
const resourceTypeItems = ref([])

// Dialogs
const detailDialog = ref(false)
const selectedLog = ref(null)
const verificationDialog = ref(false)
const verificationResult = computed(() => auditStore.verificationResult)

// Table headers
const headers = [
  { title: 'Zeit', key: 'timestamp', width: '180px' },
  { title: 'Benutzer', key: 'username', width: '120px' },
  { title: 'Aktion', key: 'action_type', width: '100px' },
  { title: 'Ressource', key: 'resource_type', width: '120px' },
  { title: 'Name/ID', key: 'resource', sortable: false },
  { title: 'Undo', key: 'is_rollbackable', width: '60px', align: 'center' },
  { title: '', key: 'actions', width: '60px', sortable: false },
]

// Methods
function formatDate(dateStr) {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function formatJson(obj) {
  if (!obj) return ''
  if (typeof obj === 'string') {
    try {
      obj = JSON.parse(obj)
    } catch {
      return obj
    }
  }
  return JSON.stringify(obj, null, 2)
}

function getActionColor(action) {
  const colors = {
    CREATE: 'success',
    READ: 'info',
    UPDATE: 'warning',
    DELETE: 'error',
    EXECUTE: 'purple',
    LOGIN: 'primary',
    LOGIN_FAILED: 'error',
    LOGOUT: 'grey',
    RESTORE: 'teal',
  }
  return colors[action] || 'grey'
}

function applyFilter(key, value) {
  auditStore.setFilter(key, value || null)
  loadPage(1)
}

function clearFilters() {
  filters.value = {
    action_type: null,
    resource_type: null,
    start_date: null,
    end_date: null,
  }
  auditStore.clearFilters()
  loadPage(1)
}

async function loadPage(page) {
  currentPage.value = page
  await auditStore.fetchLogs(page)
}

function updatePageSize(size) {
  pageSize.value = size
  auditStore.pageSize = size
  loadPage(1)
}

function showDetails(log) {
  selectedLog.value = log
  detailDialog.value = true
}

async function verifyChain() {
  await auditStore.verifyChain()
  chainValid.value = auditStore.verificationResult?.is_valid ?? true
  verificationDialog.value = true
}

function exportLogs(format) {
  auditStore.exportLogs(format)
}

async function refresh() {
  await Promise.all([
    auditStore.fetchLogs(currentPage.value),
    loadStats(),
  ])
}

async function loadStats() {
  stats.value = await auditStore.fetchStats()
}

async function loadFilterOptions() {
  const [actionTypes, resourceTypes] = await Promise.all([
    auditStore.fetchActionTypes(),
    auditStore.fetchResourceTypes(),
  ])
  actionTypeItems.value = actionTypes.map(t => ({ title: t, value: t }))
  resourceTypeItems.value = resourceTypes.map(t => ({ title: t, value: t }))
}

// Lifecycle
onMounted(async () => {
  await Promise.all([
    auditStore.fetchLogs(1),
    loadStats(),
    loadFilterOptions(),
    auditStore.verifyChain(),
  ])
  chainValid.value = auditStore.verificationResult?.is_valid ?? true
})
</script>

<style scoped>
.text-mono {
  font-family: monospace;
}
</style>
