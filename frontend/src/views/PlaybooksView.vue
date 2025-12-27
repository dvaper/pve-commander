<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <v-card>
          <v-card-title class="d-flex align-center">
            <span>Playbooks</span>
            <v-spacer></v-spacer>

            <!-- Batch Run Button -->
            <v-btn
              color="primary"
              variant="outlined"
              size="small"
              class="mr-2"
              @click="batchDialog = true"
            >
              <v-icon start>mdi-playlist-play</v-icon>
              Batch Run
            </v-btn>

            <!-- Neues Playbook Button (nur Super-Admin) -->
            <v-btn
              v-if="isSuperAdmin"
              color="success"
              variant="outlined"
              size="small"
              class="mr-2"
              @click="openCreateDialog"
            >
              <v-icon start>mdi-plus</v-icon>
              Neues Playbook
            </v-btn>

            <v-btn
              icon
              variant="text"
              @click="reload"
              :loading="loading"
            >
              <v-icon>mdi-refresh</v-icon>
            </v-btn>
          </v-card-title>

          <v-card-text>
            <v-data-table
              :headers="headers"
              :items="playbooks"
              :loading="loading"
              :search="search"
              :items-per-page="10"
              density="compact"
              class="elevation-0"
            >
              <template v-slot:top>
                <v-text-field
                  v-model="search"
                  label="Suchen"
                  prepend-inner-icon="mdi-magnify"
                  variant="outlined"
                  density="compact"
                  hide-details
                  class="mb-4"
                ></v-text-field>
              </template>

              <template v-slot:item.name="{ item }">
                <div class="d-flex align-center">
                  <v-chip
                    :color="item.is_system ? 'grey' : 'primary'"
                    variant="outlined"
                    size="small"
                  >
                    {{ item.name }}
                  </v-chip>
                  <v-tooltip v-if="item.is_system" location="top">
                    <template v-slot:activator="{ props }">
                      <v-icon
                        v-bind="props"
                        size="x-small"
                        color="grey"
                        class="ml-1"
                      >
                        mdi-lock
                      </v-icon>
                    </template>
                    System-Playbook (schreibgeschützt)
                  </v-tooltip>
                </div>
              </template>

              <template v-slot:item.hosts_target="{ item }">
                <v-tooltip location="top">
                  <template v-slot:activator="{ props }">
                    <code v-bind="props" class="cursor-pointer">{{ item.hosts_target || 'all' }}</code>
                  </template>
                  <span>Ziel-Hosts aus Playbook-Definition</span>
                </v-tooltip>
              </template>

              <template v-slot:item.actions="{ item }">
                <div class="d-flex">
                  <!-- Anzeigen -->
                  <v-btn
                    icon
                    size="small"
                    variant="text"
                    @click="showDetail(item)"
                    title="Details anzeigen"
                  >
                    <v-icon>mdi-eye</v-icon>
                  </v-btn>

                  <!-- Bearbeiten (nur custom Playbooks & Super-Admin) -->
                  <v-btn
                    v-if="isSuperAdmin && !item.is_system"
                    icon
                    size="small"
                    variant="text"
                    @click="openEditDialog(item)"
                    title="Bearbeiten"
                  >
                    <v-icon>mdi-pencil</v-icon>
                  </v-btn>

                  <!-- Metadaten (nur Super-Admin) -->
                  <v-btn
                    v-if="isSuperAdmin"
                    icon
                    size="small"
                    variant="text"
                    color="info"
                    @click="openMetadataDialog(item)"
                    title="Metadaten bearbeiten"
                  >
                    <v-icon>mdi-tag-multiple</v-icon>
                  </v-btn>

                  <!-- Ausführen -->
                  <v-btn
                    icon
                    size="small"
                    variant="text"
                    color="success"
                    @click="runPlaybook(item)"
                    title="Ausführen"
                  >
                    <v-icon>mdi-play</v-icon>
                  </v-btn>

                  <!-- Löschen (nur custom Playbooks & Super-Admin) -->
                  <v-btn
                    v-if="isSuperAdmin && !item.is_system"
                    icon
                    size="small"
                    variant="text"
                    color="error"
                    @click="confirmDelete(item)"
                    title="Löschen"
                  >
                    <v-icon>mdi-delete</v-icon>
                  </v-btn>
                </div>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Detail Dialog -->
    <v-dialog v-model="detailDialog" max-width="900">
      <v-card v-if="selectedPlaybook">
        <v-toolbar color="primary" density="compact">
          <v-toolbar-title>
            {{ selectedPlaybook.name }}
            <v-chip
              v-if="selectedPlaybook.is_system"
              size="x-small"
              color="grey"
              variant="tonal"
              class="ml-2"
            >
              <v-icon start size="x-small">mdi-lock</v-icon>
              System
            </v-chip>
          </v-toolbar-title>
          <v-spacer></v-spacer>
          <v-btn icon size="small" @click="detailDialog = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-toolbar>

        <v-card-text>
          <v-list density="compact">
            <v-list-item>
              <template v-slot:prepend>
                <v-icon>mdi-file-document</v-icon>
              </template>
              <v-list-item-title>Pfad</v-list-item-title>
              <v-list-item-subtitle>{{ selectedPlaybook.path }}</v-list-item-subtitle>
            </v-list-item>

            <v-list-item>
              <template v-slot:prepend>
                <v-icon>mdi-target</v-icon>
              </template>
              <v-list-item-title>Hosts</v-list-item-title>
              <v-list-item-subtitle>{{ selectedPlaybook.hosts_target || 'all' }}</v-list-item-subtitle>
            </v-list-item>

            <v-list-item v-if="playbookDetail?.tasks?.length">
              <template v-slot:prepend>
                <v-icon>mdi-format-list-checks</v-icon>
              </template>
              <v-list-item-title>Tasks ({{ playbookDetail.tasks.length }})</v-list-item-title>
              <v-list-item-subtitle>
                <v-chip
                  v-for="task in playbookDetail.tasks.slice(0, 5)"
                  :key="task"
                  size="x-small"
                  class="mr-1 mb-1"
                >
                  {{ task }}
                </v-chip>
                <span v-if="playbookDetail.tasks.length > 5">
                  ... +{{ playbookDetail.tasks.length - 5 }} weitere
                </span>
              </v-list-item-subtitle>
            </v-list-item>

            <v-list-item v-if="playbookDetail?.roles?.length">
              <template v-slot:prepend>
                <v-icon>mdi-account-group</v-icon>
              </template>
              <v-list-item-title>Roles ({{ playbookDetail.roles.length }})</v-list-item-title>
              <v-list-item-subtitle>
                <v-chip
                  v-for="role in playbookDetail.roles"
                  :key="role"
                  size="x-small"
                  color="secondary"
                  class="mr-1"
                >
                  {{ role }}
                </v-chip>
              </v-list-item-subtitle>
            </v-list-item>
          </v-list>

          <v-divider class="my-4"></v-divider>

          <div class="text-subtitle-2 mb-2">Inhalt:</div>
          <pre class="playbook-content">{{ playbookDetail?.content }}</pre>
        </v-card-text>

        <v-card-actions>
          <v-btn
            v-if="isSuperAdmin && !selectedPlaybook.is_system"
            variant="outlined"
            @click="openEditFromDetail"
          >
            <v-icon start>mdi-pencil</v-icon>
            Bearbeiten
          </v-btn>
          <v-spacer></v-spacer>
          <v-btn color="success" @click="runPlaybook(selectedPlaybook)">
            <v-icon start>mdi-play</v-icon>
            Ausführen
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Editor Dialog -->
    <PlaybookEditorDialog
      v-model="editorDialog"
      :is-edit="editorIsEdit"
      :playbook-name="editorPlaybookName"
      :initial-content="editorInitialContent"
      @saved="onPlaybookSaved"
    />

    <!-- Delete Confirm Dialog -->
    <v-dialog v-model="deleteDialog" max-width="450">
      <v-card>
        <v-toolbar color="error" density="compact">
          <v-toolbar-title>
            <v-icon start>mdi-delete-alert</v-icon>
            Playbook löschen?
          </v-toolbar-title>
        </v-toolbar>

        <v-card-text class="pa-4">
          <p>Soll das Playbook <strong>{{ deleteTarget?.name }}</strong> wirklich gelöscht werden?</p>
          <v-alert type="warning" variant="tonal" density="compact" class="mt-3">
            Diese Aktion kann nicht rückgängig gemacht werden!
          </v-alert>
        </v-card-text>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="deleteDialog = false">
            Abbrechen
          </v-btn>
          <v-btn color="error" variant="flat" @click="deletePlaybook" :loading="deleting">
            <v-icon start>mdi-delete</v-icon>
            Löschen
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Metadata Dialog -->
    <PlaybookMetadataDialog
      v-model="metadataDialog"
      :playbook="metadataPlaybook"
      @saved="loadPlaybooks"
    />

    <!-- Batch Dialog -->
    <PlaybookBatchDialog v-model="batchDialog" />

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar" :color="snackbarColor" timeout="3000">
      {{ snackbarText }}
    </v-snackbar>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted, provide } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/api/client'
import PlaybookEditorDialog from '@/components/PlaybookEditorDialog.vue'
import PlaybookMetadataDialog from '@/components/PlaybookMetadataDialog.vue'
import PlaybookBatchDialog from '@/components/PlaybookBatchDialog.vue'

const router = useRouter()
const authStore = useAuthStore()

// State
const loading = ref(false)
const playbooks = ref([])
const search = ref('')
const detailDialog = ref(false)
const batchDialog = ref(false)
const selectedPlaybook = ref(null)
const playbookDetail = ref(null)

// Editor Dialog State
const editorDialog = ref(false)
const editorIsEdit = ref(false)
const editorPlaybookName = ref('')
const editorInitialContent = ref('')

// Delete Dialog State
const deleteDialog = ref(false)
const deleteTarget = ref(null)
const deleting = ref(false)

// Metadata Dialog State
const metadataDialog = ref(false)
const metadataPlaybook = ref('')

// Snackbar
const snackbar = ref(false)
const snackbarText = ref('')
const snackbarColor = ref('success')

function showSnackbar(text, color = 'success') {
  snackbarText.value = text
  snackbarColor.value = color
  snackbar.value = true
}

provide('showSnackbar', showSnackbar)

// Computed
const isSuperAdmin = computed(() => authStore.isSuperAdmin)

const headers = [
  { title: 'Name', key: 'name' },
  { title: 'Beschreibung', key: 'description' },
  { title: 'Hosts', key: 'hosts_target' },
  { title: 'Pfad', key: 'path' },
  { title: '', key: 'actions', sortable: false, width: '200px' },
]

// Load Playbooks
async function loadPlaybooks() {
  loading.value = true
  try {
    const response = await api.get('/api/playbooks')
    playbooks.value = response.data
  } catch (e) {
    console.error('Laden fehlgeschlagen:', e)
  } finally {
    loading.value = false
  }
}

// Reload
async function reload() {
  await api.post('/api/playbooks/reload')
  await loadPlaybooks()
}

// Show Detail
async function showDetail(playbook) {
  selectedPlaybook.value = playbook
  detailDialog.value = true

  try {
    const response = await api.get(`/api/playbooks/${playbook.name}`)
    playbookDetail.value = response.data
  } catch (e) {
    console.error('Detail laden fehlgeschlagen:', e)
  }
}

// Run Playbook
function runPlaybook(playbook) {
  router.push(`/executions?new=1&playbook=${playbook.name}`)
}

// Create Dialog
function openCreateDialog() {
  editorIsEdit.value = false
  editorPlaybookName.value = ''
  editorInitialContent.value = ''
  editorDialog.value = true
}

// Edit Dialog
async function openEditDialog(playbook) {
  editorIsEdit.value = true
  editorPlaybookName.value = playbook.name

  // Content laden falls nicht vorhanden
  try {
    const response = await api.get(`/api/playbooks/${playbook.name}`)
    editorInitialContent.value = response.data.content
  } catch (e) {
    console.error('Content laden fehlgeschlagen:', e)
    editorInitialContent.value = ''
  }

  editorDialog.value = true
}

// Edit from Detail Dialog
function openEditFromDetail() {
  if (playbookDetail.value) {
    editorIsEdit.value = true
    editorPlaybookName.value = selectedPlaybook.value.name
    editorInitialContent.value = playbookDetail.value.content
    detailDialog.value = false
    editorDialog.value = true
  }
}

// Playbook saved callback
async function onPlaybookSaved() {
  await loadPlaybooks()
}

// Confirm Delete
function confirmDelete(playbook) {
  deleteTarget.value = playbook
  deleteDialog.value = true
}

// Open Metadata Dialog
function openMetadataDialog(playbook) {
  metadataPlaybook.value = playbook.name
  metadataDialog.value = true
}

// Delete Playbook
async function deletePlaybook() {
  if (!deleteTarget.value) return

  deleting.value = true
  try {
    await api.delete(`/api/playbooks/${deleteTarget.value.name}`)
    deleteDialog.value = false
    deleteTarget.value = null
    await loadPlaybooks()
  } catch (e) {
    console.error('Löschen fehlgeschlagen:', e)
  } finally {
    deleting.value = false
  }
}

// Mount
onMounted(loadPlaybooks)
</script>

<style scoped>
.playbook-content {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 16px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 400px;
  overflow: auto;
  font-family: monospace;
}

.cursor-pointer {
  cursor: pointer;
}
</style>
