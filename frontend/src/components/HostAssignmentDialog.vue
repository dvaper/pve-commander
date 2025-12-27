<template>
  <v-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" max-width="600" persistent>
    <v-card>
      <v-toolbar color="primary" density="compact">
        <v-toolbar-title>
          <v-icon start>mdi-account-multiple-plus</v-icon>
          Hosts zu "{{ groupName }}" zuweisen
        </v-toolbar-title>
        <v-spacer></v-spacer>
        <v-btn icon size="small" @click="close">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-toolbar>

      <v-card-text class="pa-4">
        <!-- Aktuell zugewiesene Hosts -->
        <div class="text-subtitle-2 mb-2">
          <v-icon size="small" class="mr-1">mdi-server</v-icon>
          Zugewiesene Hosts
          <v-chip size="x-small" color="primary" class="ml-2">
            {{ assignedHosts.length }}
          </v-chip>
        </div>

        <v-card variant="outlined" class="mb-4">
          <div v-if="assignedHosts.length === 0" class="pa-4 text-center text-grey">
            Keine Hosts zugewiesen
          </div>
          <v-list v-else density="compact" class="host-list">
            <v-list-item
              v-for="host in assignedHosts"
              :key="host.name"
              density="compact"
            >
              <template v-slot:prepend>
                <v-icon size="small">mdi-server</v-icon>
              </template>
              <v-list-item-title class="text-body-2">
                {{ host.name }}
                <span v-if="host.ansible_host" class="text-grey ml-2">
                  ({{ host.ansible_host }})
                </span>
              </v-list-item-title>
              <template v-slot:append>
                <v-btn
                  icon
                  size="x-small"
                  variant="text"
                  color="error"
                  @click="removeHost(host.name)"
                  :loading="loadingHost === host.name"
                  title="Aus Gruppe entfernen"
                >
                  <v-icon size="small">mdi-minus-circle</v-icon>
                </v-btn>
              </template>
            </v-list-item>
          </v-list>
        </v-card>

        <!-- Verfügbare Hosts hinzufügen -->
        <div class="text-subtitle-2 mb-2">
          <v-icon size="small" class="mr-1">mdi-plus-circle</v-icon>
          Host hinzufügen
        </div>

        <v-text-field
          v-model="hostSearch"
          placeholder="Host suchen..."
          prepend-inner-icon="mdi-magnify"
          variant="outlined"
          density="compact"
          hide-details
          class="mb-2"
        ></v-text-field>

        <v-card variant="outlined">
          <div v-if="availableHosts.length === 0" class="pa-4 text-center text-grey">
            Alle Hosts sind bereits zugewiesen
          </div>
          <v-list v-else density="compact" class="host-list">
            <v-list-item
              v-for="host in filteredAvailableHosts"
              :key="host.name"
              density="compact"
            >
              <template v-slot:prepend>
                <v-icon size="small" color="grey">mdi-server</v-icon>
              </template>
              <v-list-item-title class="text-body-2">
                {{ host.name }}
                <span v-if="host.ansible_host" class="text-grey ml-2">
                  ({{ host.ansible_host }})
                </span>
              </v-list-item-title>
              <template v-slot:append>
                <v-btn
                  icon
                  size="x-small"
                  variant="text"
                  color="success"
                  @click="addHost(host.name)"
                  :loading="loadingHost === host.name"
                  title="Zu Gruppe hinzufügen"
                >
                  <v-icon size="small">mdi-plus-circle</v-icon>
                </v-btn>
              </template>
            </v-list-item>
          </v-list>
        </v-card>
      </v-card-text>

      <v-divider></v-divider>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn variant="text" @click="close">
          Schliessen
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import api from '@/api/client'

const props = defineProps({
  modelValue: Boolean,
  groupName: {
    type: String,
    default: ''
  },
  hosts: {
    type: Array,
    default: () => []
  },
  groupHosts: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:modelValue', 'updated'])

const hostSearch = ref('')
const loadingHost = ref(null)

// Zugewiesene Hosts (in der Gruppe)
const assignedHosts = computed(() => {
  return props.hosts.filter(h => props.groupHosts.includes(h.name))
})

// Verfügbare Hosts (nicht in der Gruppe)
const availableHosts = computed(() => {
  return props.hosts.filter(h => !props.groupHosts.includes(h.name))
})

// Gefilterte verfügbare Hosts
const filteredAvailableHosts = computed(() => {
  if (!hostSearch.value) return availableHosts.value
  const search = hostSearch.value.toLowerCase()
  return availableHosts.value.filter(h =>
    h.name.toLowerCase().includes(search) ||
    (h.ansible_host && h.ansible_host.includes(search))
  )
})

// Reset bei Dialog-Öffnung
watch(() => props.modelValue, (open) => {
  if (open) {
    hostSearch.value = ''
    loadingHost.value = null
  }
})

async function addHost(hostName) {
  loadingHost.value = hostName
  try {
    await api.post(`/api/inventory/groups/${props.groupName}/hosts`, {
      host_name: hostName
    })
    emit('updated')
  } catch (e) {
    console.error('Fehler beim Hinzufügen:', e)
  } finally {
    loadingHost.value = null
  }
}

async function removeHost(hostName) {
  loadingHost.value = hostName
  try {
    await api.delete(`/api/inventory/groups/${props.groupName}/hosts/${hostName}`)
    emit('updated')
  } catch (e) {
    console.error('Fehler beim Entfernen:', e)
  } finally {
    loadingHost.value = null
  }
}

function close() {
  emit('update:modelValue', false)
}
</script>

<style scoped>
.host-list {
  max-height: 200px;
  overflow-y: auto;
}

.host-list .v-list-item {
  min-height: 36px;
}
</style>
