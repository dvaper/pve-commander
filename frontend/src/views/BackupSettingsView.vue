<template>
  <v-container fluid class="pa-4">
    <v-row>
      <v-col cols="12">
        <div class="d-flex align-center mb-4">
          <v-icon size="32" color="primary" class="mr-3">mdi-backup-restore</v-icon>
          <div>
            <h1 class="text-h4">Backup & Restore</h1>
            <p class="text-body-2 text-grey">Datensicherung und Wiederherstellung</p>
          </div>
        </div>
      </v-col>
    </v-row>

    <v-row>
      <!-- Linke Spalte: Backup erstellen & Zeitplan -->
      <v-col cols="12" md="6">
        <!-- Backup erstellen -->
        <v-card class="mb-4">
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2">mdi-cloud-upload</v-icon>
            Backup erstellen
          </v-card-title>

          <v-card-text>
            <div class="text-subtitle-2 mb-2">Komponenten</div>

            <v-row>
              <v-col cols="6">
                <v-checkbox
                  v-model="backupOptions.include_app_db"
                  label="App-Datenbank"
                  density="compact"
                  hide-details
                  class="mb-1"
                >
                  <template v-slot:label>
                    <div>
                      <span>App-Datenbank</span>
                      <v-chip size="x-small" color="error" class="ml-2">Kritisch</v-chip>
                    </div>
                  </template>
                </v-checkbox>
                <v-checkbox
                  v-model="backupOptions.include_netbox_db"
                  label="NetBox-Datenbank"
                  density="compact"
                  hide-details
                  class="mb-1"
                >
                  <template v-slot:label>
                    <div>
                      <span>NetBox-Datenbank</span>
                      <v-chip size="x-small" color="error" class="ml-2">Kritisch</v-chip>
                    </div>
                  </template>
                </v-checkbox>
                <v-checkbox
                  v-model="backupOptions.include_terraform_state"
                  label="Terraform State"
                  density="compact"
                  hide-details
                  class="mb-1"
                >
                  <template v-slot:label>
                    <div>
                      <span>Terraform State</span>
                      <v-chip size="x-small" color="error" class="ml-2">Kritisch</v-chip>
                    </div>
                  </template>
                </v-checkbox>
                <v-checkbox
                  v-model="backupOptions.include_ssh_keys"
                  label="SSH-Keys"
                  density="compact"
                  hide-details
                  class="mb-1"
                >
                  <template v-slot:label>
                    <div>
                      <span>SSH-Keys</span>
                      <v-chip size="x-small" color="error" class="ml-2">Kritisch</v-chip>
                    </div>
                  </template>
                </v-checkbox>
                <v-checkbox
                  v-model="backupOptions.include_config"
                  label="Konfiguration (.env)"
                  density="compact"
                  hide-details
                  class="mb-1"
                >
                  <template v-slot:label>
                    <div>
                      <span>Konfiguration</span>
                      <v-chip size="x-small" color="warning" class="ml-2">Wichtig</v-chip>
                    </div>
                  </template>
                </v-checkbox>
              </v-col>
              <v-col cols="6">
                <v-checkbox
                  v-model="backupOptions.include_inventory"
                  label="Ansible Inventory"
                  density="compact"
                  hide-details
                  class="mb-1"
                >
                  <template v-slot:label>
                    <div>
                      <span>Ansible Inventory</span>
                      <v-chip size="x-small" color="warning" class="ml-2">Wichtig</v-chip>
                    </div>
                  </template>
                </v-checkbox>
                <v-checkbox
                  v-model="backupOptions.include_playbooks"
                  label="Playbooks"
                  density="compact"
                  hide-details
                  class="mb-1"
                >
                  <template v-slot:label>
                    <div>
                      <span>Playbooks</span>
                      <v-chip size="x-small" color="warning" class="ml-2">Wichtig</v-chip>
                    </div>
                  </template>
                </v-checkbox>
                <v-checkbox
                  v-model="backupOptions.include_terraform_modules"
                  label="Terraform Modules"
                  density="compact"
                  hide-details
                  class="mb-1"
                >
                  <template v-slot:label>
                    <div>
                      <span>Terraform Modules</span>
                      <v-chip size="x-small" color="warning" class="ml-2">Wichtig</v-chip>
                    </div>
                  </template>
                </v-checkbox>
                <v-checkbox
                  v-model="backupOptions.include_roles"
                  label="Ansible Roles"
                  density="compact"
                  hide-details
                  class="mb-1"
                >
                  <template v-slot:label>
                    <div>
                      <span>Ansible Roles</span>
                      <v-chip size="x-small" color="warning" class="ml-2">Wichtig</v-chip>
                    </div>
                  </template>
                </v-checkbox>
                <v-checkbox
                  v-model="backupOptions.include_netbox_media"
                  label="NetBox Media"
                  density="compact"
                  hide-details
                  class="mb-1"
                >
                  <template v-slot:label>
                    <div>
                      <span>NetBox Media</span>
                      <v-chip size="x-small" color="grey" class="ml-2">Optional</v-chip>
                    </div>
                  </template>
                </v-checkbox>
              </v-col>
            </v-row>

            <v-divider class="my-3"></v-divider>

            <div class="d-flex gap-2">
              <v-btn
                color="primary"
                :loading="creatingBackup"
                @click="createBackup"
              >
                <v-icon start>mdi-cloud-upload</v-icon>
                Backup erstellen
              </v-btn>
              <v-btn
                variant="outlined"
                @click="selectAllComponents"
              >
                Alle auswaehlen
              </v-btn>
              <v-btn
                variant="text"
                @click="selectCriticalComponents"
              >
                Nur kritische
              </v-btn>
            </div>

            <v-alert
              v-if="backupResult"
              :type="backupResult.success ? 'success' : 'error'"
              variant="tonal"
              density="compact"
              class="mt-3"
              closable
              @click:close="backupResult = null"
            >
              {{ backupResult.message }}
              <span v-if="backupResult.size_bytes">
                ({{ formatSize(backupResult.size_bytes) }})
              </span>
            </v-alert>
          </v-card-text>
        </v-card>

        <!-- Zeitplan -->
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2">mdi-calendar-clock</v-icon>
            Automatischer Zeitplan
            <v-spacer></v-spacer>
            <v-switch
              v-model="schedule.enabled"
              color="primary"
              hide-details
              density="compact"
              @update:model-value="saveSchedule"
            ></v-switch>
          </v-card-title>

          <v-card-text v-if="schedule.enabled">
            <v-row>
              <v-col cols="6">
                <v-select
                  v-model="schedule.frequency"
                  label="Frequenz"
                  :items="[
                    { title: 'Taeglich', value: 'daily' },
                    { title: 'Woechentlich', value: 'weekly' }
                  ]"
                  density="compact"
                ></v-select>
              </v-col>
              <v-col cols="6">
                <v-text-field
                  v-model="schedule.time"
                  label="Uhrzeit"
                  type="time"
                  density="compact"
                ></v-text-field>
              </v-col>
            </v-row>

            <v-slider
              v-model="schedule.retention_days"
              label="Aufbewahrung (Tage)"
              :min="1"
              :max="90"
              :step="1"
              thumb-label
              density="compact"
            >
              <template v-slot:append>
                <span class="text-body-2">{{ schedule.retention_days }} Tage</span>
              </template>
            </v-slider>

            <div v-if="schedule.last_run || schedule.next_run" class="text-body-2 text-grey mt-2">
              <div v-if="schedule.last_run">
                Letztes Backup: {{ formatDate(schedule.last_run) }}
              </div>
              <div v-if="schedule.next_run">
                Naechstes Backup: {{ formatDate(schedule.next_run) }}
              </div>
            </div>

            <v-btn
              color="primary"
              variant="tonal"
              size="small"
              :loading="savingSchedule"
              @click="saveSchedule"
              class="mt-3"
            >
              Zeitplan speichern
            </v-btn>
          </v-card-text>

          <v-card-text v-else>
            <v-alert type="info" variant="tonal" density="compact">
              Automatische Backups sind deaktiviert. Aktivieren Sie den Schalter oben, um einen Zeitplan einzurichten.
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Rechte Spalte: Backup-Liste & Restore -->
      <v-col cols="12" md="6">
        <!-- Vorhandene Backups -->
        <v-card class="mb-4">
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2">mdi-history</v-icon>
            Vorhandene Backups
            <v-spacer></v-spacer>
            <v-btn
              variant="text"
              size="small"
              @click="loadBackups"
            >
              <v-icon>mdi-refresh</v-icon>
            </v-btn>
          </v-card-title>

          <v-card-text>
            <v-alert
              v-if="backups.length === 0 && !loadingBackups"
              type="info"
              variant="tonal"
              density="compact"
            >
              Keine Backups vorhanden.
            </v-alert>

            <v-data-table
              v-else
              :headers="backupHeaders"
              :items="backups"
              :loading="loadingBackups"
              density="compact"
              :items-per-page="10"
            >
              <template v-slot:item.created_at="{ item }">
                <span class="text-no-wrap">{{ formatDate(item.created_at) }}</span>
              </template>
              <template v-slot:item.size_bytes="{ item }">
                {{ formatSize(item.size_bytes) }}
              </template>
              <template v-slot:item.components="{ item }">
                <div class="text-no-wrap">
                  <v-chip size="x-small" class="mr-1">
                    {{ getComponentLabel(item.components[0]) }}
                  </v-chip>
                  <v-chip
                    v-if="item.components.length > 1"
                    size="x-small"
                    color="grey"
                  >
                    +{{ item.components.length - 1 }}
                    <v-tooltip activator="parent" location="top">
                      {{ item.components.map(c => getComponentLabel(c)).join(', ') }}
                    </v-tooltip>
                  </v-chip>
                </div>
              </template>
              <template v-slot:item.is_scheduled="{ item }">
                <v-icon
                  :color="item.is_scheduled ? 'primary' : 'grey'"
                  size="small"
                >
                  {{ item.is_scheduled ? 'mdi-calendar-check' : 'mdi-hand-back-right' }}
                  <v-tooltip activator="parent" location="top">
                    {{ item.is_scheduled ? 'Geplantes Backup' : 'Manuelles Backup' }}
                  </v-tooltip>
                </v-icon>
              </template>
              <template v-slot:item.actions="{ item }">
                <div class="text-no-wrap">
                  <v-btn
                    icon
                    variant="text"
                    size="small"
                    @click="downloadBackup(item)"
                  >
                    <v-icon>mdi-download</v-icon>
                    <v-tooltip activator="parent" location="top">Herunterladen</v-tooltip>
                  </v-btn>
                  <v-btn
                    icon
                    variant="text"
                    size="small"
                    color="warning"
                    @click="restoreFromBackup(item)"
                  >
                    <v-icon>mdi-restore</v-icon>
                    <v-tooltip activator="parent" location="top">Wiederherstellen</v-tooltip>
                  </v-btn>
                  <v-btn
                    icon
                    variant="text"
                    size="small"
                    color="error"
                    @click="confirmDeleteBackup(item)"
                  >
                    <v-icon>mdi-delete</v-icon>
                    <v-tooltip activator="parent" location="top">Loeschen</v-tooltip>
                  </v-btn>
                </div>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>

        <!-- Backup wiederherstellen -->
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2">mdi-cloud-download</v-icon>
            Backup hochladen & wiederherstellen
          </v-card-title>

          <v-card-text>
            <v-alert type="warning" variant="tonal" density="compact" class="mb-3">
              <strong>Achtung:</strong> Die Wiederherstellung ueberschreibt die aktuellen Daten!
              Vor der Wiederherstellung werden .pre-restore Backups erstellt.
            </v-alert>

            <v-file-input
              v-model="restoreFile"
              label="Backup-Datei auswaehlen"
              accept=".zip"
              prepend-icon="mdi-file-upload"
              density="compact"
              :clearable="true"
            ></v-file-input>

            <v-btn
              color="warning"
              :loading="restoring"
              :disabled="!restoreFile"
              @click="restoreBackup"
            >
              <v-icon start>mdi-restore</v-icon>
              Wiederherstellen
            </v-btn>

            <v-alert
              v-if="restoreResult"
              :type="restoreResult.success ? 'success' : 'error'"
              variant="tonal"
              density="compact"
              class="mt-3"
              closable
              @click:close="restoreResult = null"
            >
              {{ restoreResult.message }}
              <div v-if="restoreResult.restored_components?.length" class="mt-1">
                <strong>Wiederhergestellt:</strong> {{ restoreResult.restored_components.join(', ') }}
              </div>
              <div v-if="restoreResult.warnings?.length" class="mt-1 text-warning">
                <strong>Warnungen:</strong>
                <ul class="mb-0">
                  <li v-for="w in restoreResult.warnings" :key="w">{{ w }}</li>
                </ul>
              </div>
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Loeschen-Bestaetigung -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-card-title>Backup loeschen?</v-card-title>
        <v-card-text>
          Soll das Backup <strong>{{ backupToDelete?.filename }}</strong> wirklich geloescht werden?
          Diese Aktion kann nicht rueckgaengig gemacht werden.
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="deleteDialog = false">Abbrechen</v-btn>
          <v-btn color="error" :loading="deleting" @click="deleteBackup">Loeschen</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Restore-Bestaetigung -->
    <v-dialog v-model="restoreDialog" max-width="500">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2" color="warning">mdi-alert</v-icon>
          Backup wiederherstellen?
        </v-card-title>
        <v-card-text>
          <v-alert type="warning" variant="tonal" density="compact" class="mb-3">
            Die Wiederherstellung ueberschreibt die aktuellen Daten!
          </v-alert>
          <p>
            Soll das Backup <strong>{{ backupToRestore?.filename }}</strong> wiederhergestellt werden?
          </p>
          <p class="text-body-2 text-grey mt-2" v-if="backupToRestore">
            Erstellt am: {{ formatDate(backupToRestore.created_at) }}<br>
            Komponenten: {{ backupToRestore.components?.join(', ') }}
          </p>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="restoreDialog = false">Abbrechen</v-btn>
          <v-btn color="warning" :loading="restoring" @click="confirmRestore">Wiederherstellen</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000">
      {{ snackbar.text }}
    </v-snackbar>
  </v-container>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import api from '@/api/client'

// Polling-Intervall fuer Backup-Liste (wenn Zeitplan aktiv)
let backupPollingInterval = null

// Backup-Optionen
const backupOptions = ref({
  include_app_db: true,
  include_netbox_db: true,
  include_terraform_state: true,
  include_ssh_keys: true,
  include_config: true,
  include_inventory: true,
  include_playbooks: true,
  include_terraform_modules: true,
  include_roles: true,
  include_netbox_media: false,
})

// Backup-Liste
const backups = ref([])
const loadingBackups = ref(false)
const backupHeaders = [
  { title: 'Datum', key: 'created_at', width: 145 },
  { title: 'Groesse', key: 'size_bytes', width: 80 },
  { title: 'Komponenten', key: 'components' },
  { title: 'Typ', key: 'is_scheduled', width: 50 },
  { title: 'Aktionen', key: 'actions', width: 130, sortable: false },
]

// Zeitplan
const schedule = ref({
  enabled: false,
  frequency: 'daily',
  time: '02:00',
  retention_days: 7,
  options: {},
  last_run: null,
  next_run: null,
})

// Loading states
const creatingBackup = ref(false)
const savingSchedule = ref(false)
const restoring = ref(false)
const deleting = ref(false)

// Results
const backupResult = ref(null)
const restoreResult = ref(null)

// Dialoge
const deleteDialog = ref(false)
const backupToDelete = ref(null)
const restoreDialog = ref(false)
const backupToRestore = ref(null)
const restoreFile = ref(null)

// Snackbar
const snackbar = ref({ show: false, text: '', color: 'success' })

function showSnackbar(text, color = 'success') {
  snackbar.value = { show: true, text, color }
}

// Komponenten-Labels
const componentLabels = {
  app_db: 'App-DB',
  netbox_db: 'NetBox-DB',
  terraform_state: 'TF-State',
  ssh: 'SSH',
  config: 'Config',
  inventory: 'Inventory',
  playbooks: 'Playbooks',
  terraform_modules: 'TF-Modules',
  roles: 'Roles',
  netbox_media: 'Media',
}

function getComponentLabel(comp) {
  return componentLabels[comp] || comp
}

onMounted(async () => {
  await Promise.all([
    loadBackups(),
    loadSchedule(),
  ])
  // Polling starten wenn Zeitplan aktiv
  if (schedule.value.enabled) {
    startBackupPolling()
  }
})

onUnmounted(() => {
  stopBackupPolling()
})

// Polling starten/stoppen wenn Zeitplan aktiviert/deaktiviert wird
watch(() => schedule.value.enabled, (enabled) => {
  if (enabled) {
    startBackupPolling()
  } else {
    stopBackupPolling()
  }
})

function startBackupPolling() {
  if (backupPollingInterval) return
  // Alle 30 Sekunden Backup-Liste aktualisieren
  backupPollingInterval = setInterval(async () => {
    await loadBackups()
    await loadSchedule()  // Auch next_run aktualisieren
  }, 30000)
}

function stopBackupPolling() {
  if (backupPollingInterval) {
    clearInterval(backupPollingInterval)
    backupPollingInterval = null
  }
}

async function loadBackups() {
  loadingBackups.value = true
  try {
    const response = await api.get('/api/backup/list')
    backups.value = response.data
  } catch (e) {
    console.error('Fehler beim Laden der Backups:', e)
    showSnackbar('Fehler beim Laden der Backups', 'error')
  } finally {
    loadingBackups.value = false
  }
}

async function loadSchedule() {
  try {
    const response = await api.get('/api/backup/schedule')
    schedule.value = response.data
  } catch (e) {
    console.error('Fehler beim Laden des Zeitplans:', e)
  }
}

async function createBackup() {
  creatingBackup.value = true
  backupResult.value = null
  try {
    const response = await api.post('/api/backup/create', backupOptions.value)
    backupResult.value = response.data
    if (response.data.success) {
      showSnackbar('Backup erfolgreich erstellt')
      await loadBackups()
    }
  } catch (e) {
    backupResult.value = {
      success: false,
      message: e.response?.data?.detail || 'Backup fehlgeschlagen'
    }
    showSnackbar('Backup fehlgeschlagen', 'error')
  } finally {
    creatingBackup.value = false
  }
}

async function saveSchedule() {
  savingSchedule.value = true
  try {
    const scheduleData = {
      ...schedule.value,
      options: backupOptions.value,
    }
    const response = await api.put('/api/backup/schedule', scheduleData)
    // Aktualisierte Daten (inkl. next_run) uebernehmen
    schedule.value = response.data
    showSnackbar('Zeitplan gespeichert')
    // Backup-Liste aktualisieren (falls geplantes Backup ausgefuehrt wurde)
    await loadBackups()
  } catch (e) {
    showSnackbar('Fehler beim Speichern des Zeitplans', 'error')
  } finally {
    savingSchedule.value = false
  }
}

function selectAllComponents() {
  Object.keys(backupOptions.value).forEach(key => {
    backupOptions.value[key] = true
  })
}

function selectCriticalComponents() {
  backupOptions.value = {
    include_app_db: true,
    include_netbox_db: true,
    include_terraform_state: true,
    include_ssh_keys: true,
    include_config: true,
    include_inventory: false,
    include_playbooks: false,
    include_terraform_modules: false,
    include_roles: false,
    include_netbox_media: false,
  }
}

async function downloadBackup(backup) {
  try {
    const response = await api.get(`/api/backup/download/${backup.id}`, {
      responseType: 'blob'
    })

    // Download starten
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', backup.filename)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)

    showSnackbar('Download gestartet')
  } catch (e) {
    showSnackbar('Download fehlgeschlagen', 'error')
  }
}

function confirmDeleteBackup(backup) {
  backupToDelete.value = backup
  deleteDialog.value = true
}

async function deleteBackup() {
  if (!backupToDelete.value) return

  deleting.value = true
  try {
    await api.delete(`/api/backup/${backupToDelete.value.id}`)
    showSnackbar('Backup geloescht')
    deleteDialog.value = false
    await loadBackups()
  } catch (e) {
    showSnackbar('Loeschen fehlgeschlagen', 'error')
  } finally {
    deleting.value = false
  }
}

function restoreFromBackup(backup) {
  backupToRestore.value = backup
  restoreDialog.value = true
}

async function confirmRestore() {
  if (!backupToRestore.value) return

  restoring.value = true
  restoreResult.value = null
  try {
    const response = await api.post(`/api/backup/restore/${backupToRestore.value.id}`)
    restoreResult.value = response.data
    if (response.data.success) {
      showSnackbar('Wiederherstellung erfolgreich')
    }
    restoreDialog.value = false
  } catch (e) {
    restoreResult.value = {
      success: false,
      message: e.response?.data?.detail || 'Wiederherstellung fehlgeschlagen'
    }
    showSnackbar('Wiederherstellung fehlgeschlagen', 'error')
  } finally {
    restoring.value = false
  }
}

async function restoreBackup() {
  if (!restoreFile.value) return

  restoring.value = true
  restoreResult.value = null
  try {
    const formData = new FormData()
    formData.append('file', restoreFile.value)

    const response = await api.post('/api/backup/restore', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })

    restoreResult.value = response.data
    if (response.data.success) {
      showSnackbar('Wiederherstellung erfolgreich')
      restoreFile.value = null
    }
  } catch (e) {
    restoreResult.value = {
      success: false,
      message: e.response?.data?.detail || 'Wiederherstellung fehlgeschlagen'
    }
    showSnackbar('Wiederherstellung fehlgeschlagen', 'error')
  } finally {
    restoring.value = false
  }
}

function formatSize(bytes) {
  if (!bytes) return '-'
  const units = ['B', 'KB', 'MB', 'GB']
  let unitIndex = 0
  let size = bytes

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }

  return `${size.toFixed(1)} ${units[unitIndex]}`
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>
