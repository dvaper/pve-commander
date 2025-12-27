<template>
  <v-container fluid class="pa-4">
    <v-row>
      <v-col cols="12" lg="8" xl="6">
        <!-- Header -->
        <div class="d-flex align-center mb-4">
          <v-icon size="32" color="primary" class="mr-3">mdi-ip-network</v-icon>
          <div>
            <h1 class="text-h5">NetBox-Verbindung</h1>
            <p class="text-body-2 text-grey mb-0">
              IPAM/DCIM Konfiguration
            </p>
          </div>
        </div>

        <!-- Ladezustand -->
        <v-card v-if="loading" class="pa-8 text-center">
          <v-progress-circular indeterminate color="primary" size="48"></v-progress-circular>
          <p class="mt-4 text-grey">Lade Konfiguration...</p>
        </v-card>

        <!-- Hauptkarte -->
        <v-card v-else>
          <v-card-title class="d-flex align-center">
            <v-icon start>mdi-connection</v-icon>
            Verbindungsstatus
            <v-spacer></v-spacer>
            <v-chip
              :color="connectionStatus.color"
              size="small"
              variant="tonal"
            >
              <v-icon start size="small">{{ connectionStatus.icon }}</v-icon>
              {{ connectionStatus.text }}
            </v-chip>
          </v-card-title>

          <v-card-text>
            <!-- Status-Info -->
            <v-alert
              v-if="netboxHealth.status === 'healthy'"
              type="success"
              variant="tonal"
              class="mb-4"
            >
              <v-icon start>mdi-check-circle</v-icon>
              NetBox ist erreichbar und betriebsbereit.
            </v-alert>
            <v-alert
              v-else-if="netboxHealth.status === 'starting'"
              type="warning"
              variant="tonal"
              class="mb-4"
            >
              <v-icon start>mdi-loading mdi-spin</v-icon>
              NetBox wird gestartet...
            </v-alert>
            <v-alert
              v-else-if="netboxHealth.status === 'error'"
              type="error"
              variant="tonal"
              class="mb-4"
            >
              <v-icon start>mdi-alert-circle</v-icon>
              NetBox nicht erreichbar: {{ netboxHealth.message }}
            </v-alert>

            <v-divider class="my-4"></v-divider>

            <!-- Externe URL -->
            <div class="text-subtitle-2 mb-2">Externe URL</div>
            <v-text-field
              v-model="externalUrl"
              label="NetBox URL (extern)"
              placeholder="http://10.0.0.100:8081"
              prepend-inner-icon="mdi-web"
              hint="URL unter der NetBox im Browser erreichbar ist"
              persistent-hint
              variant="outlined"
              density="compact"
              class="mb-4"
              @update:model-value="markChanged"
            ></v-text-field>

            <!-- Link zur NetBox UI -->
            <v-btn
              v-if="externalUrl"
              color="primary"
              variant="tonal"
              :href="externalUrl"
              target="_blank"
            >
              <v-icon start>mdi-open-in-new</v-icon>
              NetBox oeffnen
            </v-btn>
          </v-card-text>

          <v-divider></v-divider>

          <v-card-actions>
            <v-btn
              variant="text"
              @click="refreshStatus"
              :loading="refreshing"
            >
              <v-icon start>mdi-refresh</v-icon>
              Status aktualisieren
            </v-btn>
            <v-spacer></v-spacer>
            <v-btn
              color="primary"
              :loading="saving"
              :disabled="!hasChanges"
              @click="saveConfig"
            >
              <v-icon start>mdi-content-save</v-icon>
              Speichern
            </v-btn>
          </v-card-actions>
        </v-card>

        <!-- Info-Karte -->
        <v-card class="mt-4">
          <v-card-title>
            <v-icon start>mdi-information</v-icon>
            Hinweise
          </v-card-title>
          <v-card-text>
            <v-alert type="info" variant="tonal" class="mb-3">
              <strong>Integrierter NetBox-Container:</strong>
              NetBox laeuft als Teil von PVE Commander und ist intern unter
              <code>http://netbox:8080</code> erreichbar.
            </v-alert>
            <v-alert type="info" variant="tonal" class="mb-3">
              <strong>Externe URL:</strong>
              Die externe URL wird verwendet, um Links zur NetBox-Oberflaeche anzuzeigen.
              Diese sollte die URL sein, unter der NetBox von aussen erreichbar ist
              (z.B. ueber den konfigurierten Port oder einen Reverse Proxy).
            </v-alert>
            <v-alert type="info" variant="tonal">
              <strong>Externe NetBox-Instanz:</strong>
              Um eine bestehende NetBox-Installation zu verwenden, setze folgende
              Umgebungsvariablen in <code>docker-compose.yml</code>:
              <pre class="mt-2 text-caption">NETBOX_URL=http://deine-netbox:8080
NETBOX_TOKEN=dein-api-token</pre>
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar" :color="snackbarColor" :timeout="3000">
      {{ snackbarText }}
    </v-snackbar>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted, inject } from 'vue'
import api from '@/api/client'

const showSnackbarGlobal = inject('showSnackbar', null)

// State
const loading = ref(true)
const saving = ref(false)
const refreshing = ref(false)
const hasChanges = ref(false)

// Config
const externalUrl = ref('')
const originalUrl = ref('')

// Health
const netboxHealth = ref({
  status: 'unknown',
  message: ''
})

// Snackbar
const snackbar = ref(false)
const snackbarText = ref('')
const snackbarColor = ref('success')

function showMessage(text, color = 'success') {
  if (showSnackbarGlobal) {
    showSnackbarGlobal(text, color)
  } else {
    snackbarText.value = text
    snackbarColor.value = color
    snackbar.value = true
  }
}

// Connection Status
const connectionStatus = computed(() => {
  switch (netboxHealth.value.status) {
    case 'healthy':
      return { color: 'success', icon: 'mdi-check-circle', text: 'Verbunden' }
    case 'starting':
      return { color: 'warning', icon: 'mdi-loading', text: 'Startet...' }
    case 'degraded':
      return { color: 'warning', icon: 'mdi-alert', text: 'Eingeschraenkt' }
    case 'error':
      return { color: 'error', icon: 'mdi-close-circle', text: 'Fehler' }
    default:
      return { color: 'grey', icon: 'mdi-help-circle', text: 'Unbekannt' }
  }
})

// Methods
function markChanged() {
  hasChanges.value = externalUrl.value !== originalUrl.value
}

async function loadConfig() {
  loading.value = true
  try {
    // Externe URL laden
    const urlResponse = await api.get('/api/settings/netbox-url')
    externalUrl.value = urlResponse.data.url || ''
    originalUrl.value = externalUrl.value

    // Health-Status laden
    await refreshStatus()
  } catch (e) {
    showMessage('Fehler beim Laden der Konfiguration', 'error')
  } finally {
    loading.value = false
  }
}

async function refreshStatus() {
  refreshing.value = true
  try {
    const response = await api.get('/api/health')
    if (response.data.services?.netbox) {
      netboxHealth.value = response.data.services.netbox
    }
  } catch (e) {
    netboxHealth.value = { status: 'error', message: 'Health-Check fehlgeschlagen' }
  } finally {
    refreshing.value = false
  }
}

async function saveConfig() {
  saving.value = true
  try {
    await api.put('/api/settings/netbox-url', { url: externalUrl.value })
    originalUrl.value = externalUrl.value
    hasChanges.value = false
    showMessage('NetBox-Einstellungen gespeichert')
  } catch (e) {
    showMessage(e.response?.data?.detail || 'Speichern fehlgeschlagen', 'error')
  } finally {
    saving.value = false
  }
}

// Lifecycle
onMounted(() => {
  loadConfig()
})
</script>
