<template>
  <v-container fluid class="pa-4">
    <v-row>
      <v-col cols="12" lg="8" xl="6">
        <!-- Header -->
        <div class="d-flex align-center mb-4">
          <v-icon size="32" color="primary" class="mr-3">mdi-server</v-icon>
          <div>
            <h1 class="text-h5">Proxmox-Einstellungen</h1>
            <p class="text-body-2 text-grey mb-0">
              Konfiguriere die Verbindung zum Proxmox VE Server
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
            API-Verbindung
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
            <!-- Info-Hinweis -->
            <v-alert type="info" variant="tonal" class="mb-4">
              <v-icon start>mdi-information</v-icon>
              Aenderungen werden sofort uebernommen (Hot-Reload). Ein Container-Neustart ist nicht erforderlich.
            </v-alert>

            <v-text-field
              v-model="config.proxmox_host"
              label="Proxmox Host"
              placeholder="192.168.1.100 oder https://proxmox.example.com"
              prepend-inner-icon="mdi-ip-network"
              hint="Direkt: IP/Hostname (Port 8006 wird hinzugefuegt) | Reverse Proxy: https://hostname"
              persistent-hint
              variant="outlined"
              density="compact"
              class="mb-4"
              :error-messages="errors.proxmox_host"
              @update:model-value="markChanged"
            ></v-text-field>

            <v-text-field
              v-model="config.proxmox_token_id"
              label="API Token ID"
              placeholder="terraform@pve!terraform-token"
              prepend-inner-icon="mdi-identifier"
              hint="Format: benutzer@realm!token-name"
              persistent-hint
              variant="outlined"
              density="compact"
              class="mb-4"
              :error-messages="errors.proxmox_token_id"
              @update:model-value="markChanged"
            ></v-text-field>

            <v-text-field
              v-model="config.proxmox_token_secret"
              label="API Token Secret"
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              prepend-inner-icon="mdi-key"
              :type="showSecret ? 'text' : 'password'"
              :append-inner-icon="showSecret ? 'mdi-eye' : 'mdi-eye-off'"
              @click:append-inner="showSecret = !showSecret"
              hint="Das UUID-Secret des API-Tokens"
              persistent-hint
              variant="outlined"
              density="compact"
              class="mb-4"
              :error-messages="errors.proxmox_token_secret"
              @update:model-value="markChanged"
            ></v-text-field>

            <v-checkbox
              v-model="config.proxmox_verify_ssl"
              label="SSL-Zertifikat verifizieren"
              hint="Deaktivieren bei selbstsignierten Zertifikaten"
              persistent-hint
              density="compact"
              class="mb-4"
              @update:model-value="markChanged"
            ></v-checkbox>

            <v-divider class="my-4"></v-divider>

            <!-- Verbindungstest -->
            <div class="d-flex align-center gap-2">
              <v-btn
                color="secondary"
                variant="outlined"
                :loading="testing"
                @click="testConnection"
              >
                <v-icon start>mdi-connection</v-icon>
                Verbindung testen
              </v-btn>

              <v-chip
                v-if="testResult"
                :color="testResult.success ? 'success' : 'error'"
                variant="tonal"
              >
                <v-icon start size="small">
                  {{ testResult.success ? 'mdi-check-circle' : 'mdi-close-circle' }}
                </v-icon>
                {{ testResult.message }}
              </v-chip>
            </div>

            <!-- Cluster-Info bei erfolgreichen Test -->
            <v-alert
              v-if="testResult?.success && testResult.version"
              type="success"
              variant="tonal"
              class="mt-4"
            >
              <div class="font-weight-bold">Verbindung erfolgreich</div>
              <div class="text-body-2 mt-1">
                Proxmox VE {{ testResult.version }}
                <span v-if="testResult.cluster_name">
                  | Cluster: {{ testResult.cluster_name }}
                </span>
                <span v-if="testResult.node_count">
                  | {{ testResult.node_count }} Node(s)
                </span>
              </div>
            </v-alert>

            <v-alert
              v-if="testResult && !testResult.success"
              type="error"
              variant="tonal"
              class="mt-4"
            >
              <div class="font-weight-bold">{{ testResult.message }}</div>
              <div v-if="testResult.error" class="text-body-2 mt-1">
                {{ testResult.error }}
              </div>
            </v-alert>
          </v-card-text>

          <v-divider></v-divider>

          <v-card-actions>
            <v-btn
              variant="text"
              :disabled="!hasChanges"
              @click="resetChanges"
            >
              <v-icon start>mdi-undo</v-icon>
              Zuruecksetzen
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

        <!-- Hilfe-Karte -->
        <v-card class="mt-4">
          <v-card-title>
            <v-icon start>mdi-help-circle</v-icon>
            Hilfe
          </v-card-title>
          <v-card-text>
            <v-expansion-panels variant="accordion">
              <v-expansion-panel>
                <v-expansion-panel-title>
                  <v-icon start size="small">mdi-key-plus</v-icon>
                  Wie erstelle ich einen API-Token?
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <ol class="pl-4">
                    <li class="mb-2">
                      <strong>Proxmox Web-UI oeffnen:</strong>
                      <code>Datacenter</code> &rarr; <code>Permissions</code> &rarr; <code>API Tokens</code>
                    </li>
                    <li class="mb-2">
                      <strong>Token erstellen:</strong>
                      Klicke auf <code>Add</code> und waehle einen Benutzer
                    </li>
                    <li class="mb-2">
                      <strong>Privilege Separation:</strong>
                      <span class="text-error font-weight-bold">DEAKTIVIEREN!</span>
                    </li>
                    <li class="mb-2">
                      <strong>Secret kopieren:</strong>
                      Das Secret wird nur einmal angezeigt!
                    </li>
                  </ol>
                </v-expansion-panel-text>
              </v-expansion-panel>

              <v-expansion-panel>
                <v-expansion-panel-title>
                  <v-icon start size="small">mdi-shield-key</v-icon>
                  Welche Berechtigungen braucht der Token?
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <p class="mb-2">Empfohlene Rolle mit folgenden Berechtigungen:</p>
                  <v-chip-group class="mb-2">
                    <v-chip size="small">VM.Allocate</v-chip>
                    <v-chip size="small">VM.Clone</v-chip>
                    <v-chip size="small">VM.Config.*</v-chip>
                    <v-chip size="small">VM.PowerMgmt</v-chip>
                    <v-chip size="small">VM.Audit</v-chip>
                    <v-chip size="small">Datastore.*</v-chip>
                    <v-chip size="small">Sys.Audit</v-chip>
                  </v-chip-group>
                  <p class="text-body-2 text-grey">
                    Alternativ: Administrator-Rolle fuer volle Rechte
                  </p>
                </v-expansion-panel-text>
              </v-expansion-panel>

              <v-expansion-panel>
                <v-expansion-panel-title>
                  <v-icon start size="small">mdi-refresh</v-icon>
                  Token rotieren
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <p class="mb-2">Um einen Token zu rotieren:</p>
                  <ol class="pl-4">
                    <li>Erstelle einen neuen Token in Proxmox</li>
                    <li>Aktualisiere Token ID und Secret hier</li>
                    <li>Teste die Verbindung</li>
                    <li>Speichere die Konfiguration</li>
                    <li>Loesche den alten Token in Proxmox</li>
                  </ol>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
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
const testing = ref(false)
const showSecret = ref(false)
const hasChanges = ref(false)
const testResult = ref(null)

// Original config (for reset)
const originalConfig = ref({})

// Config
const config = ref({
  proxmox_host: '',
  proxmox_token_id: '',
  proxmox_token_secret: '',
  proxmox_verify_ssl: false,
})

// Errors
const errors = ref({
  proxmox_host: '',
  proxmox_token_id: '',
  proxmox_token_secret: '',
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
  if (testResult.value?.success) {
    return { color: 'success', icon: 'mdi-check-circle', text: 'Verbunden' }
  }
  if (testResult.value && !testResult.value.success) {
    return { color: 'error', icon: 'mdi-close-circle', text: 'Fehler' }
  }
  return { color: 'grey', icon: 'mdi-help-circle', text: 'Nicht getestet' }
})

// Methods
function markChanged() {
  hasChanges.value = true
  // Clear test result when config changes
  testResult.value = null
}

function resetChanges() {
  config.value = { ...originalConfig.value }
  hasChanges.value = false
  testResult.value = null
}

async function loadConfig() {
  loading.value = true
  try {
    const response = await api.get('/api/settings/proxmox')
    config.value = {
      proxmox_host: response.data.proxmox_host || '',
      proxmox_token_id: response.data.proxmox_token_id || '',
      proxmox_token_secret: response.data.proxmox_token_secret || '',
      proxmox_verify_ssl: response.data.proxmox_verify_ssl ?? false,
    }
    originalConfig.value = { ...config.value }

    // Auto-Test bei geladen
    if (config.value.proxmox_host && config.value.proxmox_token_id) {
      await testConnection()
    }
  } catch (e) {
    showMessage('Fehler beim Laden der Konfiguration', 'error')
  } finally {
    loading.value = false
  }
}

async function testConnection() {
  testing.value = true
  testResult.value = null

  try {
    const response = await api.post('/api/settings/proxmox/test', {
      host: config.value.proxmox_host,
      token_id: config.value.proxmox_token_id,
      token_secret: config.value.proxmox_token_secret,
      verify_ssl: config.value.proxmox_verify_ssl,
    })
    testResult.value = response.data
  } catch (e) {
    testResult.value = {
      success: false,
      message: 'Verbindungstest fehlgeschlagen',
      error: e.response?.data?.detail || e.message,
    }
  } finally {
    testing.value = false
  }
}

async function saveConfig() {
  // Validate
  errors.value = { proxmox_host: '', proxmox_token_id: '', proxmox_token_secret: '' }

  if (!config.value.proxmox_host) {
    errors.value.proxmox_host = 'Proxmox Host ist erforderlich'
    return
  }
  if (!config.value.proxmox_token_id) {
    errors.value.proxmox_token_id = 'Token ID ist erforderlich'
    return
  }
  if (!config.value.proxmox_token_id.includes('!')) {
    errors.value.proxmox_token_id = 'Token ID muss das Format user@realm!token-name haben'
    return
  }

  saving.value = true
  try {
    await api.put('/api/settings/proxmox', config.value)

    originalConfig.value = { ...config.value }
    hasChanges.value = false
    showMessage('Proxmox-Einstellungen gespeichert (Hot-Reload aktiv)')

    // Test connection after save
    await testConnection()
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
