<template>
  <v-container fluid>
    <!-- Header mit Aktionen -->
    <v-row class="mb-2" align="center">
      <v-col>
        <div class="d-flex align-center">
          <v-chip
            v-if="selectedGroup"
            color="primary"
            closable
            @click:close="selectedGroup = null"
            class="mr-2"
          >
            <v-icon start size="small">mdi-folder</v-icon>
            {{ selectedGroup.name }}
          </v-chip>
          <span v-else class="text-grey">Alle Hosts</span>
        </div>
      </v-col>
      <v-col cols="auto">
        <v-btn
          v-if="isSuperAdmin"
          color="success"
          variant="outlined"
          size="small"
          @click="syncInventory"
          :loading="syncing"
          class="mr-2"
        >
          <v-icon start>mdi-sync</v-icon>
          Sync von Proxmox
        </v-btn>
        <v-btn
          v-if="isSuperAdmin"
          variant="outlined"
          size="small"
          @click="showSyncSettingsDialog = true"
          class="mr-2"
        >
          <v-icon start>mdi-cog-sync</v-icon>
          Auto-Sync
          <v-chip
            v-if="syncStatus.running"
            color="success"
            size="x-small"
            class="ml-2"
          >
            Aktiv
          </v-chip>
        </v-btn>
        <v-btn
          v-if="isSuperAdmin"
          color="primary"
          variant="outlined"
          size="small"
          @click="openCreateGroup"
          class="mr-2"
        >
          <v-icon start>mdi-folder-plus</v-icon>
          Neue Gruppe
        </v-btn>
        <v-btn
          v-if="isSuperAdmin"
          variant="outlined"
          size="small"
          @click="showHistoryDialog = true"
        >
          <v-icon start>mdi-history</v-icon>
          Historie
        </v-btn>
      </v-col>
    </v-row>

    <v-row>
      <!-- Gruppen -->
      <v-col cols="12" md="4">
        <v-card>
          <v-data-table
            :headers="groupHeaders"
            :items="groups"
            :search="groupSearch"
            density="compact"
            class="elevation-0"
            :items-per-page="10"
            :row-props="getGroupRowProps"
            @click:row="(e, { item }) => selectGroup(item)"
          >
            <template v-slot:top>
              <v-toolbar flat density="compact">
                <v-icon class="ml-2 mr-2">mdi-folder-multiple</v-icon>
                <v-toolbar-title class="text-body-1">Gruppen</v-toolbar-title>
                <v-spacer></v-spacer>
                <v-btn icon variant="text" size="small" @click="reload" :loading="loading" title="Neu laden">
                  <v-icon size="small">mdi-refresh</v-icon>
                </v-btn>
              </v-toolbar>
              <v-text-field
                v-model="groupSearch"
                placeholder="Suchen..."
                prepend-inner-icon="mdi-magnify"
                variant="outlined"
                density="compact"
                hide-details
                class="mx-3 mb-2"
              ></v-text-field>
            </template>

            <template v-slot:item.name="{ item }">
              <v-chip
                size="small"
                :color="selectedGroup?.name === item.name ? 'primary' : 'default'"
                :variant="selectedGroup?.name === item.name ? 'flat' : 'outlined'"
              >
                {{ item.name }}
              </v-chip>
            </template>

            <template v-slot:item.total_hosts_count="{ item }">
              <v-chip size="x-small" variant="text">{{ item.total_hosts_count }}</v-chip>
            </template>

            <template v-slot:item.actions="{ item }">
              <div class="d-flex">
                <v-btn
                  v-if="isSuperAdmin && !isProtectedGroup(item.name)"
                  icon
                  size="x-small"
                  variant="text"
                  @click.stop="openHostAssignment(item)"
                  title="Hosts bearbeiten"
                >
                  <v-icon size="small">mdi-pencil</v-icon>
                </v-btn>
                <v-btn
                  v-if="isSuperAdmin && !isProtectedGroup(item.name)"
                  icon
                  size="x-small"
                  variant="text"
                  color="error"
                  @click.stop="confirmDeleteGroup(item)"
                  title="Löschen"
                >
                  <v-icon size="small">mdi-delete</v-icon>
                </v-btn>
              </div>
            </template>
          </v-data-table>
        </v-card>
      </v-col>

      <!-- Hosts -->
      <v-col cols="12" md="8">
        <v-card>
          <v-data-table
            :headers="hostHeaders"
            :items="filteredHosts"
            :search="hostSearch"
            density="compact"
            class="elevation-0"
            :items-per-page="10"
          >
            <template v-slot:top>
              <v-toolbar flat density="compact">
                <v-icon class="ml-2 mr-2">mdi-server</v-icon>
                <v-toolbar-title class="text-body-1">Hosts</v-toolbar-title>
                <v-spacer></v-spacer>
                <v-chip size="small" variant="text">{{ filteredHosts.length }}</v-chip>
              </v-toolbar>
              <v-text-field
                v-model="hostSearch"
                placeholder="Suchen..."
                prepend-inner-icon="mdi-magnify"
                variant="outlined"
                density="compact"
                hide-details
                class="mx-3 mb-2"
              ></v-text-field>
            </template>
            <template v-slot:item.name="{ item }">
              <v-chip
                size="small"
                color="primary"
                variant="outlined"
                @click="showHostDetail(item)"
              >
                {{ item.name }}
              </v-chip>
            </template>

            <template v-slot:item.status="{ item }">
              <v-chip
                size="small"
                :color="getStatusColor(getHostStatus(item))"
                variant="flat"
              >
                <v-icon start size="small">{{ getStatusIcon(getHostStatus(item)) }}</v-icon>
                {{ getHostStatus(item) }}
              </v-chip>
            </template>

            <template v-slot:item.groups="{ item }">
              <v-chip
                v-for="g in item.groups.slice(0, 3)"
                :key="g"
                size="x-small"
                class="mr-1"
              >
                {{ g }}
              </v-chip>
              <span v-if="item.groups.length > 3" class="text-grey">
                +{{ item.groups.length - 3 }}
              </span>
            </template>

            <template v-slot:item.actions="{ item }">
              <v-btn icon size="x-small" variant="text" @click="showHostDetail(item)">
                <v-icon>mdi-information</v-icon>
              </v-btn>
            </template>
          </v-data-table>
        </v-card>
      </v-col>
    </v-row>

    <!-- Host Detail Dialog -->
    <v-dialog v-model="hostDialog" max-width="500">
      <v-card v-if="selectedHost">
        <v-toolbar color="primary" dark flat>
          <v-toolbar-title>{{ selectedHost.name }}</v-toolbar-title>
          <v-spacer></v-spacer>
          <v-btn icon @click="hostDialog = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-toolbar>

        <v-card-text>
          <v-list density="compact">
            <v-list-item>
              <template v-slot:prepend><v-icon>mdi-ip</v-icon></template>
              <v-list-item-title>IP-Adresse</v-list-item-title>
              <v-list-item-subtitle>{{ selectedHost.ansible_host || '-' }}</v-list-item-subtitle>
            </v-list-item>

            <v-list-item>
              <template v-slot:prepend><v-icon>mdi-identifier</v-icon></template>
              <v-list-item-title>VMID</v-list-item-title>
              <v-list-item-subtitle>{{ selectedHost.vmid || '-' }}</v-list-item-subtitle>
            </v-list-item>

            <v-list-item>
              <template v-slot:prepend><v-icon>mdi-server-network</v-icon></template>
              <v-list-item-title>Proxmox Node</v-list-item-title>
              <v-list-item-subtitle>{{ selectedHost.pve_node || '-' }}</v-list-item-subtitle>
            </v-list-item>

            <v-list-item>
              <template v-slot:prepend><v-icon>mdi-folder-multiple</v-icon></template>
              <v-list-item-title>Gruppen</v-list-item-title>
              <v-list-item-subtitle>
                <v-chip
                  v-for="g in selectedHost.groups"
                  :key="g"
                  size="small"
                  class="mr-1 mb-1"
                >
                  {{ g }}
                </v-chip>
              </v-list-item-subtitle>
            </v-list-item>
          </v-list>

          <v-divider class="my-4"></v-divider>

          <div class="text-subtitle-2 mb-2">Variablen:</div>
          <pre class="vars-content">{{ JSON.stringify(selectedHost.vars, null, 2) }}</pre>
        </v-card-text>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="primary" @click="pingHost">
            <v-icon start>mdi-lan-check</v-icon>
            Ping
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Gruppe erstellen/umbenennen Dialog -->
    <GroupCreateDialog
      v-model="showGroupDialog"
      :edit-mode="groupEditMode"
      :original-name="groupEditName"
      :groups="groups"
      @created="onGroupCreated"
      @renamed="onGroupRenamed"
    />

    <!-- Host-Zuordnung Dialog -->
    <HostAssignmentDialog
      v-model="showHostAssignmentDialog"
      :group-name="hostAssignmentGroup?.name || ''"
      :hosts="hosts"
      :group-hosts="hostAssignmentGroup?.hosts || []"
      @updated="onHostAssignmentUpdated"
    />

    <!-- Historie Dialog -->
    <InventoryHistoryDialog
      v-model="showHistoryDialog"
      @rollback="onHistoryRollback"
    />

    <!-- Sync-Einstellungen Dialog -->
    <v-dialog v-model="showSyncSettingsDialog" max-width="500">
      <v-card>
        <v-toolbar color="primary" density="compact">
          <v-toolbar-title>
            <v-icon start>mdi-cog-sync</v-icon>
            Auto-Sync Einstellungen
          </v-toolbar-title>
          <v-spacer></v-spacer>
          <v-btn icon size="small" @click="showSyncSettingsDialog = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-toolbar>

        <v-card-text class="pa-4">
          <!-- Status-Anzeige -->
          <v-alert
            :type="syncStatus.running ? 'success' : 'info'"
            variant="tonal"
            density="compact"
            class="mb-4"
          >
            <div class="d-flex align-center justify-space-between">
              <div>
                <div class="font-weight-medium">
                  {{ syncStatus.running ? 'Auto-Sync aktiv' : 'Auto-Sync inaktiv' }}
                </div>
                <div v-if="syncStatus.last_sync" class="text-caption">
                  Letzter Sync: {{ formatSyncTime(syncStatus.last_sync) }}
                </div>
              </div>
              <v-btn
                :color="syncStatus.running ? 'error' : 'success'"
                variant="flat"
                size="small"
                :loading="syncToggling"
                @click="toggleBackgroundSync"
              >
                <v-icon start>{{ syncStatus.running ? 'mdi-stop' : 'mdi-play' }}</v-icon>
                {{ syncStatus.running ? 'Stoppen' : 'Starten' }}
              </v-btn>
            </div>
          </v-alert>

          <!-- Intervall-Einstellung -->
          <div class="text-subtitle-2 mb-2">Sync-Intervall</div>
          <v-slider
            v-model="syncIntervalMinutes"
            :min="1"
            :max="60"
            :step="1"
            thumb-label="always"
            :disabled="syncToggling"
          >
            <template v-slot:thumb-label="{ modelValue }">
              {{ modelValue }} min
            </template>
          </v-slider>
          <div class="text-caption text-grey mb-4">
            Das Inventory wird alle {{ syncIntervalMinutes }} Minute(n) mit Proxmox synchronisiert.
          </div>

          <v-btn
            color="primary"
            variant="outlined"
            block
            :loading="savingInterval"
            @click="saveSyncInterval"
          >
            <v-icon start>mdi-content-save</v-icon>
            Intervall speichern
          </v-btn>

          <v-divider class="my-4"></v-divider>

          <!-- Info -->
          <div class="text-caption text-grey">
            <v-icon size="small">mdi-information</v-icon>
            Der Auto-Sync erkennt neue VMs in Proxmox und fuegt sie automatisch
            zur Gruppe "proxmox_discovered" hinzu.
          </div>
        </v-card-text>
      </v-card>
    </v-dialog>

    <!-- Gruppe löschen Bestätigung -->
    <v-dialog v-model="showDeleteDialog" max-width="400">
      <v-card>
        <v-card-title class="text-h6">
          <v-icon start color="error">mdi-alert</v-icon>
          Gruppe löschen
        </v-card-title>
        <v-card-text>
          Möchtest du die Gruppe <strong>{{ deleteGroupTarget?.name }}</strong> wirklich löschen?
          <v-alert type="warning" variant="tonal" density="compact" class="mt-4">
            Diese Aktion kann nicht rückgängig gemacht werden.
            Die Hosts bleiben im Inventory, werden aber aus dieser Gruppe entfernt.
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="showDeleteDialog = false">
            Abbrechen
          </v-btn>
          <v-btn color="error" variant="flat" @click="deleteGroup" :loading="deleting">
            <v-icon start>mdi-delete</v-icon>
            Löschen
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted, onActivated, inject } from 'vue'
import { useRouter, onBeforeRouteUpdate } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/api/client'

// Komponenten
import GroupCreateDialog from '@/components/GroupCreateDialog.vue'
import HostAssignmentDialog from '@/components/HostAssignmentDialog.vue'
import InventoryHistoryDialog from '@/components/InventoryHistoryDialog.vue'

const router = useRouter()
const authStore = useAuthStore()
const showSnackbar = inject('showSnackbar')

// Computed: Ist Super-Admin?
const isSuperAdmin = computed(() => authStore.isSuperAdmin)

// Geschützte Gruppen (können nicht gelöscht/umbenannt werden)
const protectedGroups = ['all', 'ungrouped', 'linux', 'windows']
const isProtectedGroup = (name) => protectedGroups.includes(name)

const loading = ref(false)
const hosts = ref([])
const groups = ref([])
const vmStatus = ref({})
const hostSearch = ref('')
const groupSearch = ref('')
const selectedGroup = ref(null)
const selectedHost = ref(null)
const hostDialog = ref(false)

// Dialog-State für Gruppen-Erstellung/Umbenennung
const showGroupDialog = ref(false)
const groupEditMode = ref(false)
const groupEditName = ref('')

// Dialog-State für Host-Zuordnung
const showHostAssignmentDialog = ref(false)
const hostAssignmentGroup = ref(null)

// Dialog-State für Historie
const showHistoryDialog = ref(false)

// Dialog-State für Löschen
const showDeleteDialog = ref(false)
const deleteGroupTarget = ref(null)
const deleting = ref(false)

// Sync-State
const syncing = ref(false)
const showSyncSettingsDialog = ref(false)
const syncStatus = ref({ running: false, last_sync: null, interval_seconds: 300 })
const syncIntervalMinutes = ref(5)
const syncToggling = ref(false)
const savingInterval = ref(false)

const groupHeaders = [
  { title: 'Name', key: 'name' },
  { title: 'Hosts', key: 'total_hosts_count', width: '60px' },
  { title: '', key: 'actions', sortable: false, width: '90px' },
]

const hostHeaders = [
  { title: 'Name', key: 'name' },
  { title: 'Status', key: 'status', width: '100px' },
  { title: 'IP', key: 'ansible_host' },
  { title: 'VMID', key: 'vmid', width: '80px' },
  { title: 'Node', key: 'pve_node' },
  { title: 'Gruppen', key: 'groups', sortable: false },
  { title: '', key: 'actions', sortable: false, width: '50px' },
]

// Zeilen-Styling für ausgewählte Gruppe
function getGroupRowProps({ item }) {
  return {
    class: selectedGroup.value?.name === item.name ? 'bg-primary-lighten-4' : '',
    style: 'cursor: pointer;'
  }
}

const filteredHosts = computed(() => {
  let result = hosts.value

  // Nach Gruppe filtern
  if (selectedGroup.value) {
    result = result.filter(h => h.groups.includes(selectedGroup.value.name))
  }

  return result
})

async function loadData() {
  loading.value = true
  try {
    const [hostsRes, groupsRes, statusRes] = await Promise.all([
      api.get('/api/inventory/hosts'),
      api.get('/api/inventory/groups'),
      api.get('/api/inventory/vm-status'),
    ])
    hosts.value = hostsRes.data
    groups.value = groupsRes.data
    vmStatus.value = statusRes.data.vms || {}
  } catch (e) {
    console.error('Laden fehlgeschlagen:', e)
  } finally {
    loading.value = false
  }
}

// Hilfsfunktion: Status für einen Host ermitteln
function getHostStatus(host) {
  if (!host.vmid) return 'unknown'
  const status = vmStatus.value[String(host.vmid)]
  return status?.status || 'unknown'
}

// Hilfsfunktion: Status-Farbe ermitteln
function getStatusColor(status) {
  switch (status) {
    case 'running': return 'success'
    case 'stopped': return 'error'
    case 'paused': return 'warning'
    default: return 'grey'
  }
}

// Hilfsfunktion: Status-Icon ermitteln
function getStatusIcon(status) {
  switch (status) {
    case 'running': return 'mdi-play-circle'
    case 'stopped': return 'mdi-stop-circle'
    case 'paused': return 'mdi-pause-circle'
    default: return 'mdi-help-circle'
  }
}

async function reload() {
  await api.post('/api/inventory/reload')
  await loadData()
}

function selectGroup(group) {
  if (selectedGroup.value?.name === group.name) {
    selectedGroup.value = null
  } else {
    selectedGroup.value = group
  }
}

function showHostDetail(host) {
  selectedHost.value = host
  hostDialog.value = true
}

function pingHost() {
  router.push(`/executions?new=1&playbook=ping&host=${selectedHost.value.name}`)
}

// ========================================
// Gruppen-Verwaltung
// ========================================

function openCreateGroup() {
  groupEditMode.value = false
  groupEditName.value = ''
  showGroupDialog.value = true
}

function openRenameGroup(group) {
  groupEditMode.value = true
  groupEditName.value = group.name
  showGroupDialog.value = true
}

async function onGroupCreated(groupName) {
  showSnackbar?.(`Gruppe '${groupName}' erstellt`, 'success')
  await loadData()
}

async function onGroupRenamed({ oldName, newName }) {
  showSnackbar?.(`Gruppe '${oldName}' in '${newName}' umbenannt`, 'success')
  // Wenn die umbenannte Gruppe ausgewählt war, Selection aktualisieren
  if (selectedGroup.value?.name === oldName) {
    selectedGroup.value = null
  }
  await loadData()
}

function confirmDeleteGroup(group) {
  deleteGroupTarget.value = group
  showDeleteDialog.value = true
}

async function deleteGroup() {
  if (!deleteGroupTarget.value) return

  deleting.value = true
  try {
    await api.delete(`/api/inventory/groups/${deleteGroupTarget.value.name}`)
    showSnackbar?.(`Gruppe '${deleteGroupTarget.value.name}' gelöscht`, 'success')

    // Wenn die gelöschte Gruppe ausgewählt war, Selection aufheben
    if (selectedGroup.value?.name === deleteGroupTarget.value.name) {
      selectedGroup.value = null
    }

    showDeleteDialog.value = false
    await loadData()
  } catch (e) {
    console.error('Fehler beim Löschen:', e)
    showSnackbar?.(`Fehler: ${e.response?.data?.detail || e.message}`, 'error')
  } finally {
    deleting.value = false
  }
}

// ========================================
// Host-Zuordnung
// ========================================

function openHostAssignment(group) {
  hostAssignmentGroup.value = group
  showHostAssignmentDialog.value = true
}

async function onHostAssignmentUpdated() {
  await loadData()
  // Aktualisiere die Gruppe im Dialog
  if (hostAssignmentGroup.value) {
    const updated = groups.value.find(g => g.name === hostAssignmentGroup.value.name)
    if (updated) {
      hostAssignmentGroup.value = updated
    }
  }
}

// ========================================
// Historie
// ========================================

async function onHistoryRollback() {
  showSnackbar?.('Inventory wiederhergestellt', 'success')
  await loadData()
}

// ========================================
// Inventory Sync
// ========================================

async function syncInventory() {
  syncing.value = true
  try {
    // Sync VMs aus Proxmox (erkennt neue VMs und fügt sie hinzu)
    const response = await api.post('/api/inventory/sync-vms')
    const details = response.data.details ? JSON.parse(response.data.details) : {}

    let message = response.data.message || 'Inventory synchronisiert'
    if (details.added && details.added.length > 0) {
      message = `${details.added.length} neue VM(s) hinzugefügt: ${details.added.map(v => v.name || v).join(', ')}`
    }

    showSnackbar?.(message, 'success')
    await loadData()
  } catch (e) {
    console.error('Sync fehlgeschlagen:', e)
    showSnackbar?.(`Sync fehlgeschlagen: ${e.response?.data?.detail || e.message}`, 'error')
  } finally {
    syncing.value = false
  }
}

// ========================================
// Background Sync Einstellungen
// ========================================

async function loadSyncStatus() {
  try {
    const response = await api.get('/api/inventory/sync-status')
    syncStatus.value = response.data
    syncIntervalMinutes.value = Math.round(response.data.interval_seconds / 60)
  } catch (e) {
    // Nicht kritisch - Status bleibt auf Default
    console.debug('Sync-Status nicht verfuegbar:', e)
  }
}

async function toggleBackgroundSync() {
  syncToggling.value = true
  try {
    if (syncStatus.value.running) {
      await api.post('/api/inventory/sync-background/stop')
      showSnackbar?.('Auto-Sync gestoppt', 'info')
    } else {
      await api.post('/api/inventory/sync-background/start')
      showSnackbar?.('Auto-Sync gestartet', 'success')
    }
    await loadSyncStatus()
  } catch (e) {
    console.error('Fehler beim Toggle:', e)
    showSnackbar?.(`Fehler: ${e.response?.data?.detail || e.message}`, 'error')
  } finally {
    syncToggling.value = false
  }
}

async function saveSyncInterval() {
  savingInterval.value = true
  try {
    const intervalSeconds = syncIntervalMinutes.value * 60
    await api.patch(`/api/inventory/sync-settings?interval_seconds=${intervalSeconds}`)
    showSnackbar?.(`Intervall auf ${syncIntervalMinutes.value} Minute(n) gesetzt`, 'success')
    await loadSyncStatus()
  } catch (e) {
    console.error('Fehler beim Speichern:', e)
    showSnackbar?.(`Fehler: ${e.response?.data?.detail || e.message}`, 'error')
  } finally {
    savingInterval.value = false
  }
}

function formatSyncTime(isoString) {
  if (!isoString) return '-'
  const date = new Date(isoString)
  return date.toLocaleString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

onMounted(async () => {
  await loadData()
  if (isSuperAdmin.value) {
    await loadSyncStatus()
  }
})

// Daten neu laden wenn Komponente reaktiviert wird (keep-alive Cache)
onActivated(async () => {
  await loadData()
})

// Daten neu laden bei Route-Update (z.B. Query-Parameter Aenderung)
onBeforeRouteUpdate(async () => {
  await loadData()
})
</script>

<style scoped>
.inventory-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.vars-content {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 200px;
  overflow: auto;
}
</style>
