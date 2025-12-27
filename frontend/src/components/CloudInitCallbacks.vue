<template>
  <v-card>
    <v-toolbar flat density="compact">
      <v-icon class="ml-2 mr-2">mdi-phone-incoming</v-icon>
      <v-toolbar-title class="text-body-1">Cloud-Init Callbacks</v-toolbar-title>
      <v-spacer></v-spacer>

      <v-text-field
        v-model="searchQuery"
        prepend-inner-icon="mdi-magnify"
        label="Hostname suchen..."
        single-line
        hide-details
        density="compact"
        variant="outlined"
        style="max-width: 200px"
        class="mr-2"
        clearable
      />

      <v-btn
        icon
        size="small"
        variant="text"
        @click="loadCallbacks"
        :loading="loading"
        title="Aktualisieren"
      >
        <v-icon>mdi-refresh</v-icon>
      </v-btn>

      <v-btn
        v-if="isAdmin && callbacks.length > 0"
        icon
        size="small"
        variant="text"
        color="error"
        @click="confirmClear"
        title="Alle loeschen"
      >
        <v-icon>mdi-delete-sweep</v-icon>
      </v-btn>
    </v-toolbar>

    <v-data-table
      :headers="headers"
      :items="filteredCallbacks"
      :loading="loading"
      density="compact"
      :items-per-page="10"
      hover
    >
      <template v-slot:item.status="{ item }">
        <v-chip
          :color="getStatusColor(item.status)"
          size="small"
          variant="flat"
        >
          <v-icon start size="small">{{ getStatusIcon(item.status) }}</v-icon>
          {{ item.status }}
        </v-chip>
      </template>

      <template v-slot:item.hostname="{ item }">
        <div>
          <strong>{{ item.hostname }}</strong>
          <div v-if="item.fqdn && item.fqdn !== item.hostname" class="text-caption text-grey">
            {{ item.fqdn }}
          </div>
        </div>
      </template>

      <template v-slot:item.ip_address="{ item }">
        <code class="text-caption">{{ item.ip_address || item.client_ip || '-' }}</code>
      </template>

      <template v-slot:item.received_at="{ item }">
        <div>
          {{ formatDate(item.received_at) }}
          <div class="text-caption text-grey">
            {{ formatAge(item.received_at) }}
          </div>
        </div>
      </template>

      <template v-slot:item.actions="{ item }">
        <v-btn
          icon
          size="small"
          variant="text"
          @click="showDetails(item)"
          title="Details"
        >
          <v-icon size="18">mdi-information-outline</v-icon>
        </v-btn>
      </template>

      <template v-slot:no-data>
        <div class="text-center pa-4">
          <v-icon size="48" color="grey">mdi-phone-off</v-icon>
          <p class="mt-2">Keine Cloud-Init Callbacks empfangen.</p>
          <p class="text-caption text-grey">
            Callbacks werden empfangen, wenn VMs mit Cloud-Init booten.
          </p>
        </div>
      </template>
    </v-data-table>

    <!-- Details Dialog -->
    <v-dialog v-model="detailDialog" max-width="600">
      <v-card v-if="selectedCallback">
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2" color="success">mdi-check-circle</v-icon>
          {{ selectedCallback.hostname }}
        </v-card-title>
        <v-card-text>
          <v-table density="compact">
            <tbody>
              <tr>
                <td class="text-grey" width="150">Hostname</td>
                <td><strong>{{ selectedCallback.hostname }}</strong></td>
              </tr>
              <tr v-if="selectedCallback.fqdn">
                <td class="text-grey">FQDN</td>
                <td>{{ selectedCallback.fqdn }}</td>
              </tr>
              <tr>
                <td class="text-grey">IP-Adresse</td>
                <td><code>{{ selectedCallback.ip_address || selectedCallback.client_ip }}</code></td>
              </tr>
              <tr v-if="selectedCallback.instance_id">
                <td class="text-grey">Instance ID</td>
                <td><code class="text-caption">{{ selectedCallback.instance_id }}</code></td>
              </tr>
              <tr>
                <td class="text-grey">Status</td>
                <td>
                  <v-chip :color="getStatusColor(selectedCallback.status)" size="small">
                    {{ selectedCallback.status }}
                  </v-chip>
                </td>
              </tr>
              <tr>
                <td class="text-grey">Empfangen</td>
                <td>{{ formatDate(selectedCallback.received_at) }}</td>
              </tr>
              <tr v-if="selectedCallback.timestamp">
                <td class="text-grey">VM Timestamp</td>
                <td>{{ formatDate(selectedCallback.timestamp) }}</td>
              </tr>
              <tr v-if="selectedCallback.client_ip !== selectedCallback.ip_address">
                <td class="text-grey">Client IP</td>
                <td><code>{{ selectedCallback.client_ip }}</code></td>
              </tr>
            </tbody>
          </v-table>

          <v-alert v-if="selectedCallback.pub_key_ed25519" type="info" variant="tonal" class="mt-4">
            <div class="text-caption font-weight-bold mb-1">SSH Host Key (ED25519)</div>
            <code class="text-caption" style="word-break: break-all;">
              {{ selectedCallback.pub_key_ed25519 }}
            </code>
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn @click="detailDialog = false">Schliessen</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Loeschen Dialog -->
    <v-dialog v-model="clearDialog" max-width="400">
      <v-card>
        <v-card-title class="text-error">
          <v-icon start color="error">mdi-delete-sweep</v-icon>
          Alle Callbacks loeschen?
        </v-card-title>
        <v-card-text>
          Es werden alle {{ callbacks.length }} gespeicherten Callbacks geloescht.
          Diese Aktion kann nicht rueckgaengig gemacht werden.
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn @click="clearDialog = false">Abbrechen</v-btn>
          <v-btn
            color="error"
            variant="flat"
            @click="clearCallbacks"
            :loading="clearing"
          >
            Loeschen
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted, inject } from 'vue'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { formatDate, getStatusColor, getStatusIcon } from '@/utils/formatting'

const showSnackbar = inject('showSnackbar')
const authStore = useAuthStore()

const loading = ref(false)
const clearing = ref(false)
const callbacks = ref([])
const searchQuery = ref('')
const detailDialog = ref(false)
const selectedCallback = ref(null)
const clearDialog = ref(false)

const isAdmin = computed(() => authStore.isSuperAdmin)

const headers = [
  { title: 'Status', key: 'status', width: '120px' },
  { title: 'Hostname', key: 'hostname' },
  { title: 'IP', key: 'ip_address', width: '140px' },
  { title: 'Empfangen', key: 'received_at', width: '180px' },
  { title: '', key: 'actions', width: '60px', sortable: false },
]

const filteredCallbacks = computed(() => {
  if (!searchQuery.value) return callbacks.value

  const query = searchQuery.value.toLowerCase()
  return callbacks.value.filter(c =>
    c.hostname?.toLowerCase().includes(query) ||
    c.ip_address?.toLowerCase().includes(query) ||
    c.fqdn?.toLowerCase().includes(query)
  )
})

async function loadCallbacks() {
  loading.value = true
  try {
    const response = await api.get('/api/cloud-init/callbacks')
    callbacks.value = response.data.callbacks || []
  } catch (e) {
    console.error('Callbacks laden fehlgeschlagen:', e)
    showSnackbar?.('Callbacks konnten nicht geladen werden', 'error')
  } finally {
    loading.value = false
  }
}

function showDetails(callback) {
  selectedCallback.value = callback
  detailDialog.value = true
}

function confirmClear() {
  clearDialog.value = true
}

async function clearCallbacks() {
  clearing.value = true
  try {
    await api.delete('/api/cloud-init/callbacks')
    showSnackbar?.('Alle Callbacks geloescht', 'success')
    clearDialog.value = false
    await loadCallbacks()
  } catch (e) {
    console.error('Loeschen fehlgeschlagen:', e)
    showSnackbar?.('Loeschen fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    clearing.value = false
  }
}

function formatAge(dateStr) {
  if (!dateStr) return ''
  const now = new Date()
  const then = new Date(dateStr)
  const diffMs = now - then
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffDays > 0) return `vor ${diffDays} Tag${diffDays > 1 ? 'en' : ''}`
  if (diffHours > 0) return `vor ${diffHours} Stunde${diffHours > 1 ? 'n' : ''}`
  if (diffMins > 0) return `vor ${diffMins} Minute${diffMins > 1 ? 'n' : ''}`
  return 'gerade eben'
}

onMounted(() => {
  loadCallbacks()
})

defineExpose({ loadCallbacks })
</script>
