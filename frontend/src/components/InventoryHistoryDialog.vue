<template>
  <v-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" max-width="700">
    <v-card>
      <v-toolbar color="primary" density="compact">
        <v-toolbar-title>
          <v-icon start>mdi-history</v-icon>
          Inventory-Historie
        </v-toolbar-title>
        <v-spacer></v-spacer>
        <v-btn icon size="small" @click="close">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-toolbar>

      <v-card-text class="pa-0">
        <v-progress-linear v-if="loading" indeterminate></v-progress-linear>

        <v-list v-if="!loading && commits.length > 0" density="compact">
          <v-list-item
            v-for="(commit, index) in commits"
            :key="commit.commit_hash"
            :class="{ 'bg-blue-lighten-5': index === 0 }"
          >
            <template v-slot:prepend>
              <v-icon :color="index === 0 ? 'primary' : 'grey'">
                {{ index === 0 ? 'mdi-circle' : 'mdi-circle-outline' }}
              </v-icon>
            </template>

            <v-list-item-title class="text-body-2">
              <code class="commit-hash mr-2">{{ commit.commit_hash.slice(0, 8) }}</code>
              {{ commit.message }}
            </v-list-item-title>

            <v-list-item-subtitle class="text-caption">
              <v-icon size="x-small" class="mr-1">mdi-account</v-icon>
              {{ commit.author }}
              <v-icon size="x-small" class="ml-2 mr-1">mdi-clock-outline</v-icon>
              {{ formatDate(commit.timestamp) }}
            </v-list-item-subtitle>

            <template v-slot:append>
              <v-btn
                v-if="index > 0"
                size="small"
                variant="outlined"
                color="warning"
                @click="confirmRollback(commit)"
                :loading="rollingBack === commit.commit_hash"
                :disabled="!!rollingBack"
              >
                <v-icon start size="small">mdi-restore</v-icon>
                Wiederherstellen
              </v-btn>
              <v-chip v-else size="small" color="success" variant="outlined">
                Aktuell
              </v-chip>
            </template>
          </v-list-item>
        </v-list>

        <div v-else-if="!loading" class="pa-8 text-center text-grey">
          <v-icon size="64" color="grey">mdi-history</v-icon>
          <p class="mt-4">Keine Historie verfügbar</p>
        </div>
      </v-card-text>

      <v-divider></v-divider>

      <v-card-actions>
        <v-chip size="small" variant="text">
          {{ commits.length }} Einträge
        </v-chip>
        <v-spacer></v-spacer>
        <v-btn variant="text" @click="close">
          Schliessen
        </v-btn>
      </v-card-actions>
    </v-card>

    <!-- Rollback-Bestätigung -->
    <v-dialog v-model="showConfirm" max-width="400">
      <v-card>
        <v-card-title class="text-h6">
          <v-icon start color="warning">mdi-alert</v-icon>
          Rollback bestätigen
        </v-card-title>
        <v-card-text>
          <p>
            Möchtest du das Inventory auf die Version
            <code>{{ selectedCommit?.commit_hash?.slice(0, 8) }}</code>
            zurücksetzen?
          </p>
          <p class="text-grey mt-2">
            {{ selectedCommit?.message }}
          </p>
          <v-alert type="warning" variant="tonal" density="compact" class="mt-4">
            Diese Aktion überschreibt alle aktuellen Änderungen.
            Ein Backup wird vorher erstellt.
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="showConfirm = false">
            Abbrechen
          </v-btn>
          <v-btn
            color="warning"
            variant="flat"
            @click="doRollback"
            :loading="rollingBack === selectedCommit?.commit_hash"
          >
            <v-icon start>mdi-restore</v-icon>
            Wiederherstellen
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import api from '@/api/client'
import { formatDate } from '@/utils/formatting'

const props = defineProps({
  modelValue: Boolean
})

const emit = defineEmits(['update:modelValue', 'rollback'])

const loading = ref(false)
const commits = ref([])
const rollingBack = ref(null)
const showConfirm = ref(false)
const selectedCommit = ref(null)

// Historie laden bei Dialog-Öffnung
watch(() => props.modelValue, async (open) => {
  if (open) {
    await loadHistory()
  }
})

async function loadHistory() {
  loading.value = true
  try {
    const response = await api.get('/api/inventory/history?limit=30')
    commits.value = response.data.commits
  } catch (e) {
    console.error('Fehler beim Laden der Historie:', e)
    commits.value = []
  } finally {
    loading.value = false
  }
}

function confirmRollback(commit) {
  selectedCommit.value = commit
  showConfirm.value = true
}

async function doRollback() {
  if (!selectedCommit.value) return

  rollingBack.value = selectedCommit.value.commit_hash
  try {
    await api.post(`/api/inventory/rollback/${selectedCommit.value.commit_hash}`)
    showConfirm.value = false
    emit('rollback')
    // Historie neu laden
    await loadHistory()
  } catch (e) {
    console.error('Fehler beim Rollback:', e)
  } finally {
    rollingBack.value = null
  }
}

function close() {
  emit('update:modelValue', false)
}
</script>

<style scoped>
.commit-hash {
  font-family: monospace;
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}
</style>
