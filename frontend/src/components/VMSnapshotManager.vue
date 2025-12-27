<template>
  <v-dialog v-model="dialog" max-width="700" persistent>
    <v-card>
      <v-toolbar color="primary" density="compact">
        <v-icon class="ml-2 mr-2">mdi-camera</v-icon>
        <v-toolbar-title>Snapshots - {{ vm?.name }}</v-toolbar-title>
        <v-spacer></v-spacer>
        <v-btn icon size="small" @click="close">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-toolbar>

      <v-card-text class="pt-4">
        <!-- Neuer Snapshot erstellen -->
        <v-card variant="outlined" class="mb-4">
          <v-card-text>
            <div class="d-flex align-center gap-2">
              <v-text-field
                v-model="newSnapshotName"
                label="Snapshot-Name"
                placeholder="z.B. backup_vor_update"
                prepend-inner-icon="mdi-camera-plus"
                variant="outlined"
                density="compact"
                hint="Nur Buchstaben, Zahlen und Unterstriche"
                persistent-hint
                class="flex-grow-1"
              ></v-text-field>
              <v-btn
                color="primary"
                @click="createSnapshot"
                :loading="creating"
                :disabled="!newSnapshotName"
              >
                <v-icon start>mdi-plus</v-icon>
                Erstellen
              </v-btn>
            </div>
            <v-text-field
              v-model="newSnapshotDescription"
              label="Beschreibung (optional)"
              variant="outlined"
              density="compact"
              hide-details
              class="mt-2"
            ></v-text-field>
            <v-checkbox
              v-model="includeRam"
              label="RAM-State mit sichern (nur für laufende VMs)"
              density="compact"
              hide-details
              class="mt-2"
            ></v-checkbox>
          </v-card-text>
        </v-card>

        <!-- Snapshot-Liste -->
        <v-data-table
          :headers="headers"
          :items="snapshots"
          :loading="loading"
          density="compact"
          :items-per-page="10"
        >
          <template v-slot:item.snaptime="{ item }">
            {{ formatDate(item.snaptime) }}
          </template>

          <template v-slot:item.vmstate="{ item }">
            <v-chip
              :color="item.vmstate ? 'info' : 'grey'"
              size="x-small"
              variant="flat"
            >
              {{ item.vmstate ? 'Mit RAM' : 'Ohne RAM' }}
            </v-chip>
          </template>

          <template v-slot:item.actions="{ item }">
            <v-btn
              icon
              size="x-small"
              variant="text"
              color="warning"
              @click="confirmRollback(item)"
              title="Rollback"
            >
              <v-icon>mdi-restore</v-icon>
            </v-btn>
            <v-btn
              icon
              size="x-small"
              variant="text"
              color="error"
              @click="confirmDelete(item)"
              title="Löschen"
            >
              <v-icon>mdi-delete</v-icon>
            </v-btn>
          </template>

          <template v-slot:no-data>
            <div class="text-center py-4">
              <v-icon size="48" color="grey-lighten-1">mdi-camera-off</v-icon>
              <div class="text-grey mt-2">Keine Snapshots vorhanden</div>
            </div>
          </template>
        </v-data-table>

        <!-- Feedback -->
        <v-alert
          v-if="message"
          :type="messageType"
          variant="tonal"
          density="compact"
          class="mt-4"
          closable
          @click:close="message = null"
        >
          {{ message }}
        </v-alert>
      </v-card-text>
    </v-card>

    <!-- Rollback-Bestätigung -->
    <v-dialog v-model="rollbackDialog" max-width="400">
      <v-card>
        <v-card-title class="text-warning">
          <v-icon start color="warning">mdi-alert</v-icon>
          Rollback bestätigen
        </v-card-title>
        <v-card-text>
          <p>
            Möchtest du <strong>{{ vm?.name }}</strong> wirklich auf den Snapshot
            <strong>{{ selectedSnapshot?.name }}</strong> zurücksetzen?
          </p>
          <v-alert type="warning" variant="tonal" density="compact" class="mt-4">
            Alle Änderungen seit diesem Snapshot gehen verloren!
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn @click="rollbackDialog = false">Abbrechen</v-btn>
          <v-btn color="warning" variant="flat" @click="executeRollback" :loading="rolling">
            Rollback
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Löschen-Bestätigung -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-card-title class="text-error">
          <v-icon start color="error">mdi-delete-alert</v-icon>
          Snapshot löschen
        </v-card-title>
        <v-card-text>
          <p>
            Möchtest du den Snapshot <strong>{{ selectedSnapshot?.name }}</strong>
            wirklich löschen?
          </p>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn @click="deleteDialog = false">Abbrechen</v-btn>
          <v-btn color="error" variant="flat" @click="executeDelete" :loading="deleting">
            Löschen
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-dialog>
</template>

<script setup>
import { ref } from 'vue'
import api from '@/api/client'

const emit = defineEmits(['close'])

const dialog = ref(false)
const vm = ref(null)
const snapshots = ref([])
const loading = ref(false)
const creating = ref(false)
const rolling = ref(false)
const deleting = ref(false)

const newSnapshotName = ref('')
const newSnapshotDescription = ref('')
const includeRam = ref(false)

const message = ref(null)
const messageType = ref('info')

const rollbackDialog = ref(false)
const deleteDialog = ref(false)
const selectedSnapshot = ref(null)

const headers = [
  { title: 'Name', key: 'name' },
  { title: 'Beschreibung', key: 'description' },
  { title: 'Erstellt', key: 'snaptime', width: '160px' },
  { title: 'RAM', key: 'vmstate', width: '100px' },
  { title: '', key: 'actions', sortable: false, width: '100px' },
]

const rules = {
  required: v => !!v || 'Pflichtfeld',
  snapshotName: v => /^[a-zA-Z][a-zA-Z0-9_]*$/.test(v) || 'Muss mit Buchstabe beginnen, nur Buchstaben/Zahlen/Unterstriche',
}

async function open(vmData) {
  vm.value = vmData
  newSnapshotName.value = ''
  newSnapshotDescription.value = ''
  includeRam.value = false
  message.value = null
  dialog.value = true
  await loadSnapshots()
}

function close() {
  dialog.value = false
  emit('close')
}

async function loadSnapshots() {
  loading.value = true
  try {
    const response = await api.get(`/api/terraform/vms/${vm.value.name}/snapshots`)
    snapshots.value = response.data
  } catch (e) {
    showMessage('Fehler beim Laden der Snapshots', 'error')
    console.error('Snapshot-Laden fehlgeschlagen:', e)
  } finally {
    loading.value = false
  }
}

async function createSnapshot() {
  if (!newSnapshotName.value) return

  creating.value = true
  try {
    await api.post(`/api/terraform/vms/${vm.value.name}/snapshots`, {
      name: newSnapshotName.value,
      description: newSnapshotDescription.value,
      include_ram: includeRam.value,
    })

    showMessage(`Snapshot '${newSnapshotName.value}' wird erstellt`, 'success')
    newSnapshotName.value = ''
    newSnapshotDescription.value = ''

    // Nach kurzer Verzögerung neu laden
    setTimeout(() => loadSnapshots(), 2000)
  } catch (e) {
    showMessage(e.response?.data?.detail || 'Snapshot-Erstellung fehlgeschlagen', 'error')
    console.error('Snapshot-Erstellung fehlgeschlagen:', e)
  } finally {
    creating.value = false
  }
}

function confirmRollback(snapshot) {
  selectedSnapshot.value = snapshot
  rollbackDialog.value = true
}

async function executeRollback() {
  rolling.value = true
  try {
    await api.post(`/api/terraform/vms/${vm.value.name}/snapshots/${selectedSnapshot.value.name}/rollback`)
    showMessage(`Rollback auf '${selectedSnapshot.value.name}' wird ausgeführt`, 'success')
    rollbackDialog.value = false
  } catch (e) {
    showMessage(e.response?.data?.detail || 'Rollback fehlgeschlagen', 'error')
    console.error('Rollback fehlgeschlagen:', e)
  } finally {
    rolling.value = false
  }
}

function confirmDelete(snapshot) {
  selectedSnapshot.value = snapshot
  deleteDialog.value = true
}

async function executeDelete() {
  deleting.value = true
  try {
    await api.delete(`/api/terraform/vms/${vm.value.name}/snapshots/${selectedSnapshot.value.name}`)
    showMessage(`Snapshot '${selectedSnapshot.value.name}' wird gelöscht`, 'success')
    deleteDialog.value = false

    // Nach kurzer Verzögerung neu laden
    setTimeout(() => loadSnapshots(), 2000)
  } catch (e) {
    showMessage(e.response?.data?.detail || 'Löschen fehlgeschlagen', 'error')
    console.error('Snapshot-Löschung fehlgeschlagen:', e)
  } finally {
    deleting.value = false
  }
}

function showMessage(text, type = 'info') {
  message.value = text
  messageType.value = type
}

function formatDate(timestamp) {
  if (!timestamp) return '-'
  return new Date(timestamp * 1000).toLocaleString('de-DE')
}

defineExpose({ open })
</script>
