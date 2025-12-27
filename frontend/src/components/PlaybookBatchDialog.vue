<template>
  <v-dialog :model-value="modelValue" max-width="800" @update:model-value="emit('update:modelValue', $event)">
    <v-card>
      <v-toolbar color="primary" density="compact">
        <v-toolbar-title>Batch-Ausfuehrung</v-toolbar-title>
        <v-spacer />
        <v-btn icon size="small" @click="emit('update:modelValue', false)">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-toolbar>

      <v-card-text class="pa-4">
        <v-alert type="info" variant="tonal" density="compact" class="mb-4">
          Waehlen Sie Playbooks aus und ordnen Sie die Ausfuehrungsreihenfolge per Drag & Drop.
        </v-alert>

        <v-row>
          <!-- Verfuegbare Playbooks -->
          <v-col cols="12" md="5">
            <div class="text-subtitle-2 mb-2">
              <v-icon start size="small">mdi-script-text-outline</v-icon>
              Verfuegbare Playbooks
            </div>
            <v-card variant="outlined" class="playbook-list">
              <v-text-field
                v-model="search"
                placeholder="Suchen..."
                prepend-inner-icon="mdi-magnify"
                density="compact"
                variant="plain"
                hide-details
                class="px-2"
              />
              <v-divider />
              <v-list density="compact">
                <v-list-item
                  v-for="playbook in filteredAvailablePlaybooks"
                  :key="playbook.name"
                  density="compact"
                  @click="addPlaybook(playbook)"
                >
                  <template v-slot:prepend>
                    <v-icon size="small" color="grey">mdi-script-text</v-icon>
                  </template>
                  <v-list-item-title class="text-body-2">{{ playbook.name }}</v-list-item-title>
                  <template v-slot:append>
                    <v-btn icon size="x-small" variant="text" color="primary" @click.stop="addPlaybook(playbook)">
                      <v-icon size="small">mdi-plus</v-icon>
                    </v-btn>
                  </template>
                </v-list-item>
                <v-list-item v-if="filteredAvailablePlaybooks.length === 0">
                  <v-list-item-title class="text-grey text-center">
                    Keine Playbooks verfuegbar
                  </v-list-item-title>
                </v-list-item>
              </v-list>
            </v-card>
          </v-col>

          <!-- Pfeil -->
          <v-col cols="12" md="2" class="d-flex align-center justify-center">
            <v-icon size="large" color="grey">mdi-arrow-right</v-icon>
          </v-col>

          <!-- Ausgewaehlte Playbooks (Drag & Drop) -->
          <v-col cols="12" md="5">
            <div class="text-subtitle-2 mb-2">
              <v-icon start size="small">mdi-playlist-play</v-icon>
              Ausfuehrungsreihenfolge
              <v-chip v-if="selectedPlaybooks.length" size="x-small" color="primary" class="ml-2">
                {{ selectedPlaybooks.length }}
              </v-chip>
            </div>
            <v-card variant="outlined" class="playbook-list">
              <draggable
                v-model="selectedPlaybooks"
                item-key="name"
                handle=".drag-handle"
                :animation="200"
              >
                <template #item="{ element, index }">
                  <v-list-item density="compact" class="draggable-item">
                    <template v-slot:prepend>
                      <v-icon class="drag-handle mr-2" size="small" style="cursor: grab;">mdi-drag</v-icon>
                      <v-chip size="x-small" color="primary" variant="flat" class="mr-2">{{ index + 1 }}</v-chip>
                    </template>
                    <v-list-item-title class="text-body-2">{{ element.name }}</v-list-item-title>
                    <template v-slot:append>
                      <v-btn icon size="x-small" variant="text" color="error" @click="removePlaybook(index)">
                        <v-icon size="small">mdi-close</v-icon>
                      </v-btn>
                    </template>
                  </v-list-item>
                </template>
              </draggable>
              <v-list-item v-if="selectedPlaybooks.length === 0">
                <v-list-item-title class="text-grey text-center py-4">
                  Playbooks hierher ziehen oder links auswaehlen
                </v-list-item-title>
              </v-list-item>
            </v-card>
          </v-col>
        </v-row>

        <!-- Zielauswahl -->
        <v-divider class="my-4" />
        <v-row>
          <v-col cols="12" md="6">
            <div class="text-subtitle-2 mb-2">
              <v-icon start size="small">mdi-folder-multiple</v-icon>
              Gruppen
            </div>
            <v-select
              v-model="selectedGroups"
              :items="groups"
              item-title="name"
              item-value="name"
              multiple
              chips
              closable-chips
              density="compact"
              variant="outlined"
              placeholder="Gruppen auswaehlen..."
              hide-details
            />
          </v-col>
          <v-col cols="12" md="6">
            <div class="text-subtitle-2 mb-2">
              <v-icon start size="small">mdi-server</v-icon>
              Hosts
            </div>
            <v-select
              v-model="selectedHosts"
              :items="hosts"
              item-title="name"
              item-value="name"
              multiple
              chips
              closable-chips
              density="compact"
              variant="outlined"
              placeholder="Hosts auswaehlen..."
              hide-details
            />
          </v-col>
        </v-row>

        <!-- Status -->
        <v-alert
          v-if="!canExecute"
          type="warning"
          variant="tonal"
          density="compact"
          class="mt-4"
        >
          <span v-if="selectedPlaybooks.length === 0">
            Mindestens ein Playbook muss ausgewaehlt werden.
          </span>
          <span v-else>
            Mindestens eine Gruppe oder ein Host muss ausgewaehlt werden.
          </span>
        </v-alert>
        <v-alert
          v-else
          type="success"
          variant="tonal"
          density="compact"
          class="mt-4"
        >
          <strong>{{ selectedPlaybooks.length }} Playbook(s)</strong> werden auf
          <span v-if="selectedGroups.length">{{ selectedGroups.length }} Gruppe(n)</span>
          <span v-if="selectedGroups.length && selectedHosts.length"> + </span>
          <span v-if="selectedHosts.length">{{ selectedHosts.length }} Host(s)</span>
          ausgefuehrt.
        </v-alert>

        <!-- Fortschrittsanzeige waehrend der Ausfuehrung -->
        <v-card v-if="executing" variant="outlined" class="mt-4">
          <v-card-text>
            <div class="text-subtitle-2 mb-2">Ausfuehrung laeuft...</div>
            <v-progress-linear
              :model-value="(currentPlaybookIndex / selectedPlaybooks.length) * 100"
              color="primary"
              height="20"
            >
              <template v-slot:default>
                {{ currentPlaybookIndex }}/{{ selectedPlaybooks.length }}
              </template>
            </v-progress-linear>
            <div class="text-caption text-grey mt-2">
              Aktuell: {{ selectedPlaybooks[currentPlaybookIndex]?.name || '-' }}
            </div>
          </v-card-text>
        </v-card>
      </v-card-text>

      <v-divider />

      <v-card-actions>
        <v-btn variant="text" @click="clearSelection">
          <v-icon start>mdi-playlist-remove</v-icon>
          Leeren
        </v-btn>
        <v-spacer />
        <v-btn variant="text" @click="emit('update:modelValue', false)">Abbrechen</v-btn>
        <v-btn
          color="success"
          variant="flat"
          :loading="executing"
          :disabled="!canExecute"
          @click="executeBatch"
        >
          <v-icon start>mdi-play</v-icon>
          Batch starten
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch, inject } from 'vue'
import { useRouter } from 'vue-router'
import draggable from 'vuedraggable'
import api from '@/api/client'

const props = defineProps({
  modelValue: Boolean,
})

const emit = defineEmits(['update:modelValue'])
const router = useRouter()
const showSnackbar = inject('showSnackbar')

const search = ref('')
const executing = ref(false)
const currentPlaybookIndex = ref(0)

const playbooks = ref([])
const groups = ref([])
const hosts = ref([])

const selectedPlaybooks = ref([])
const selectedGroups = ref([])
const selectedHosts = ref([])

const filteredAvailablePlaybooks = computed(() => {
  const selected = new Set(selectedPlaybooks.value.map(p => p.name))
  let available = playbooks.value.filter(p => !selected.has(p.name))

  if (search.value) {
    const s = search.value.toLowerCase()
    available = available.filter(p => p.name.toLowerCase().includes(s))
  }

  return available
})

const canExecute = computed(() => {
  return selectedPlaybooks.value.length > 0 &&
         (selectedGroups.value.length > 0 || selectedHosts.value.length > 0)
})

watch(() => props.modelValue, async (open) => {
  if (open) {
    await loadData()
  }
})

async function loadData() {
  try {
    const [playbooksRes, groupsRes, hostsRes] = await Promise.all([
      api.get('/api/playbooks'),
      api.get('/api/inventory/groups'),
      api.get('/api/inventory/hosts'),
    ])
    playbooks.value = playbooksRes.data
    groups.value = groupsRes.data
    hosts.value = hostsRes.data
  } catch (e) {
    console.error('Laden fehlgeschlagen:', e)
  }
}

function addPlaybook(playbook) {
  if (!selectedPlaybooks.value.find(p => p.name === playbook.name)) {
    selectedPlaybooks.value.push({ ...playbook })
  }
}

function removePlaybook(index) {
  selectedPlaybooks.value.splice(index, 1)
}

function clearSelection() {
  selectedPlaybooks.value = []
}

async function executeBatch() {
  executing.value = true
  currentPlaybookIndex.value = 0

  try {
    const response = await api.post('/api/executions/ansible/batch', {
      playbooks: selectedPlaybooks.value.map(p => p.name),
      target_hosts: selectedHosts.value.length ? selectedHosts.value : null,
      target_groups: selectedGroups.value.length ? selectedGroups.value : null,
    })

    showSnackbar?.(`Batch gestartet: ${response.data.total} Playbooks`, 'success')
    emit('update:modelValue', false)

    // Zur ersten Execution navigieren
    if (response.data.executions?.length > 0) {
      router.push(`/executions/${response.data.executions[0].id}`)
    } else {
      router.push('/executions')
    }
  } catch (e) {
    showSnackbar?.('Batch-Start fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    executing.value = false
  }
}
</script>

<style scoped>
.playbook-list {
  max-height: 280px;
  overflow-y: auto;
}

.draggable-item {
  background: rgba(var(--v-theme-surface), 1);
  border-bottom: 1px solid rgba(var(--v-border-color), 0.12);
}

.draggable-item:hover {
  background: rgba(var(--v-theme-primary), 0.04);
}

.drag-handle:hover {
  color: rgb(var(--v-theme-primary));
}
</style>
