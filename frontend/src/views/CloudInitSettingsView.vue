<template>
  <v-container fluid class="pa-4">
    <v-row>
      <v-col cols="12">
        <div class="d-flex align-center mb-4">
          <v-icon size="32" color="primary" class="mr-3">mdi-cog</v-icon>
          <div>
            <h1 class="text-h4">Verwaltung</h1>
            <p class="text-body-2 text-grey">Cloud-Init, SSH-Keys und externe Dienste</p>
          </div>
        </div>
      </v-col>
    </v-row>

    <!-- Loading State -->
    <v-row v-if="loading">
      <v-col cols="12" class="text-center py-8">
        <v-progress-circular indeterminate color="primary" size="48"></v-progress-circular>
        <p class="mt-4 text-grey">Lade Einstellungen...</p>
      </v-col>
    </v-row>

    <v-row v-else>
      <!-- Linke Spalte: Admin-User & Phone-Home -->
      <v-col cols="12" md="6">
        <!-- Admin-User Einstellungen -->
        <v-card class="mb-4">
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2">mdi-account-cog</v-icon>
            Admin-Benutzer
          </v-card-title>

          <v-card-text>
            <v-alert type="info" variant="tonal" density="compact" class="mb-4">
              Diese Einstellungen werden fuer alle neuen VMs verwendet, die mit Cloud-Init erstellt werden.
            </v-alert>

            <v-text-field
              v-model="settings.admin_username"
              label="Benutzername"
              prepend-inner-icon="mdi-account"
              hint="Benutzername der auf neuen VMs erstellt wird"
              persistent-hint
              density="compact"
              class="mb-4"
            ></v-text-field>

            <v-text-field
              v-model="settings.admin_gecos"
              label="GECOS (Vollstaendiger Name)"
              prepend-inner-icon="mdi-card-account-details"
              hint="Angezeigter Name des Benutzers"
              persistent-hint
              density="compact"
            ></v-text-field>
          </v-card-text>
        </v-card>

        <!-- Phone-Home Einstellungen -->
        <v-card class="mb-4">
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2">mdi-phone-incoming</v-icon>
            Phone-Home Callback
            <v-spacer></v-spacer>
            <v-switch
              v-model="settings.phone_home_enabled"
              color="primary"
              hide-details
              density="compact"
            ></v-switch>
          </v-card-title>

          <v-card-text v-if="settings.phone_home_enabled">
            <v-alert type="info" variant="tonal" density="compact" class="mb-4">
              VMs melden sich nach der Erstellung beim Server. Die URL wird automatisch generiert,
              kann aber manuell ueberschrieben werden.
            </v-alert>

            <v-text-field
              v-model="settings.phone_home_url"
              label="Phone-Home URL (optional)"
              prepend-inner-icon="mdi-web"
              placeholder="Leer lassen fuer Auto-Generierung"
              hint="Format: http://server:8000/api/cloud-init/callback"
              persistent-hint
              density="compact"
              clearable
            ></v-text-field>
          </v-card-text>

          <v-card-text v-else>
            <v-alert type="warning" variant="tonal" density="compact">
              Phone-Home ist deaktiviert. VMs werden nicht zurueckmelden wenn Cloud-Init abgeschlossen ist.
            </v-alert>
          </v-card-text>
        </v-card>

        <!-- NetBox Externe URL -->
        <v-card class="mb-4">
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2">mdi-ip-network-outline</v-icon>
            NetBox Integration
            <v-spacer></v-spacer>
            <v-chip
              :color="netboxUrl ? 'success' : 'warning'"
              size="small"
              variant="tonal"
            >
              {{ netboxUrl ? 'Konfiguriert' : 'Nicht konfiguriert' }}
            </v-chip>
          </v-card-title>

          <v-card-text>
            <v-alert type="info" variant="tonal" density="compact" class="mb-4">
              Konfiguriere die externe URL unter der NetBox im Browser erreichbar ist.
              Diese wird fuer Links im UI verwendet (z.B. Dashboard, VM-Wizard).
            </v-alert>

            <v-text-field
              v-model="netboxUrl"
              label="NetBox Externe URL"
              prepend-inner-icon="mdi-open-in-new"
              placeholder="https://netbox.example.com oder http://192.168.1.100:8081"
              hint="URL unter der NetBox im Browser erreichbar ist"
              persistent-hint
              density="compact"
              clearable
            ></v-text-field>

            <v-btn
              color="primary"
              variant="tonal"
              size="small"
              class="mt-4"
              :loading="savingNetboxUrl"
              :disabled="netboxUrl === originalNetboxUrl"
              @click="saveNetboxUrl"
            >
              <v-icon start>mdi-content-save</v-icon>
              URL speichern
            </v-btn>
          </v-card-text>
        </v-card>

        <!-- NAS Snippets -->
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2">mdi-folder-network</v-icon>
            NAS Snippets
            <v-spacer></v-spacer>
            <v-chip
              :color="hasNasConfig ? 'success' : 'grey'"
              size="small"
              variant="tonal"
            >
              {{ hasNasConfig ? 'Konfiguriert' : 'Nicht konfiguriert' }}
            </v-chip>
          </v-card-title>

          <v-card-text>
            <v-alert type="info" variant="tonal" density="compact" class="mb-4">
              Optionale Konfiguration fuer Cloud-Init Snippets auf einem NAS-Storage.
              Nur erforderlich, wenn erweiterte Cloud-Init-Profile verwendet werden.
            </v-alert>

            <v-text-field
              v-model="settings.nas_snippets_path"
              label="NAS Snippets Pfad"
              prepend-inner-icon="mdi-folder"
              placeholder="/mnt/pve/nas/snippets"
              hint="Pfad zum Snippets-Verzeichnis auf dem Proxmox-Node"
              persistent-hint
              density="compact"
              class="mb-4"
              clearable
            ></v-text-field>

            <v-text-field
              v-model="settings.nas_snippets_ref"
              label="Proxmox Storage-Referenz"
              prepend-inner-icon="mdi-database"
              placeholder="nas:snippets"
              hint="Storage-Referenz fuer cicustom (z.B. nas:snippets)"
              persistent-hint
              density="compact"
              clearable
            ></v-text-field>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Rechte Spalte: SSH Keys -->
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2">mdi-key</v-icon>
            SSH Authorized Keys
            <v-spacer></v-spacer>
            <v-chip color="primary" size="small" variant="tonal">
              {{ sshKeyCount }} Key(s)
            </v-chip>
          </v-card-title>

          <v-card-text>
            <v-alert type="info" variant="tonal" density="compact" class="mb-4">
              Diese SSH Public Keys werden auf allen neuen VMs hinterlegt und ermoeglichen den Zugang via SSH.
            </v-alert>

            <!-- Bestehende Keys -->
            <v-list v-if="settings.ssh_authorized_keys?.length" lines="two" density="compact">
              <v-list-item
                v-for="(key, index) in settings.ssh_authorized_keys"
                :key="index"
                class="mb-2 rounded border"
              >
                <template v-slot:prepend>
                  <v-icon color="success">mdi-key-variant</v-icon>
                </template>
                <v-list-item-title class="text-body-2">
                  {{ getKeyType(key) }}
                </v-list-item-title>
                <v-list-item-subtitle class="text-caption font-monospace text-truncate">
                  {{ truncateKey(key) }}
                </v-list-item-subtitle>
                <template v-slot:append>
                  <v-btn
                    icon
                    variant="text"
                    color="error"
                    size="small"
                    :loading="deletingKey === key"
                    @click="removeKey(key)"
                  >
                    <v-icon>mdi-delete</v-icon>
                  </v-btn>
                </template>
              </v-list-item>
            </v-list>

            <v-alert v-else type="warning" variant="tonal" density="compact" class="mb-4">
              <v-icon start>mdi-alert</v-icon>
              Keine SSH-Keys konfiguriert. Ohne SSH-Keys ist kein Zugang zu neuen VMs moeglich!
            </v-alert>

            <v-divider class="my-4"></v-divider>

            <!-- Neuen Key hinzufuegen -->
            <h4 class="text-subtitle-2 mb-2">Neuen SSH-Key hinzufuegen</h4>
            <v-textarea
              v-model="newSshKey"
              label="SSH Public Key"
              placeholder="ssh-ed25519 AAAA... user@host"
              hint="Vollstaendiger SSH Public Key (ssh-ed25519 oder ssh-rsa)"
              persistent-hint
              density="compact"
              rows="2"
              class="mb-2"
              :error-messages="sshKeyError"
            ></v-textarea>
            <v-btn
              color="primary"
              variant="tonal"
              size="small"
              :loading="addingKey"
              :disabled="!newSshKey.trim()"
              @click="addKey"
            >
              <v-icon start>mdi-plus</v-icon>
              Key hinzufuegen
            </v-btn>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Speichern Button (fixiert unten) -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-actions class="pa-4">
            <v-spacer></v-spacer>
            <v-btn
              color="primary"
              size="large"
              :loading="saving"
              :disabled="!hasChanges"
              @click="saveSettings"
            >
              <v-icon start>mdi-content-save</v-icon>
              Einstellungen speichern
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>

    <!-- Snackbar fuer Feedback -->
    <v-snackbar v-model="showSnackbar" :color="snackbarColor" :timeout="3000">
      {{ snackbarMessage }}
      <template v-slot:actions>
        <v-btn variant="text" @click="showSnackbar = false">Schliessen</v-btn>
      </template>
    </v-snackbar>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import api from '@/api/client'

// State
const loading = ref(true)
const saving = ref(false)
const addingKey = ref(false)
const deletingKey = ref(null)
const newSshKey = ref('')
const sshKeyError = ref('')
const savingNetboxUrl = ref(false)
const netboxUrl = ref('')
const originalNetboxUrl = ref('')

// Settings
const settings = ref({
  admin_username: 'ansible',
  admin_gecos: 'Homelab Admin',
  phone_home_enabled: true,
  phone_home_url: null,
  nas_snippets_path: null,
  nas_snippets_ref: null,
  ssh_authorized_keys: [],
})

// Original settings for change detection
const originalSettings = ref(null)

// Snackbar
const showSnackbar = ref(false)
const snackbarMessage = ref('')
const snackbarColor = ref('success')

// Computed
const sshKeyCount = computed(() => settings.value.ssh_authorized_keys?.length || 0)
const hasNasConfig = computed(() => !!settings.value.nas_snippets_path && !!settings.value.nas_snippets_ref)
const hasChanges = computed(() => {
  if (!originalSettings.value) return false
  return JSON.stringify(settings.value) !== JSON.stringify(originalSettings.value)
})

// Methods
function showMessage(message, color = 'success') {
  snackbarMessage.value = message
  snackbarColor.value = color
  showSnackbar.value = true
}

function getKeyType(key) {
  if (key.startsWith('ssh-ed25519')) return 'ED25519'
  if (key.startsWith('ssh-rsa')) return 'RSA'
  if (key.startsWith('ecdsa')) return 'ECDSA'
  return 'SSH'
}

function truncateKey(key) {
  if (key.length > 80) {
    return key.substring(0, 40) + '...' + key.substring(key.length - 30)
  }
  return key
}

async function loadSettings() {
  loading.value = true
  try {
    const response = await api.get('/api/cloud-init/settings')
    settings.value = response.data
    originalSettings.value = JSON.parse(JSON.stringify(response.data))
  } catch (error) {
    console.error('Fehler beim Laden:', error)
    showMessage('Fehler beim Laden der Einstellungen', 'error')
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  saving.value = true
  try {
    await api.put('/api/cloud-init/settings', {
      admin_username: settings.value.admin_username,
      admin_gecos: settings.value.admin_gecos,
      phone_home_enabled: settings.value.phone_home_enabled,
      phone_home_url: settings.value.phone_home_url || null,
      nas_snippets_path: settings.value.nas_snippets_path || null,
      nas_snippets_ref: settings.value.nas_snippets_ref || null,
      ssh_authorized_keys: settings.value.ssh_authorized_keys,
    })
    originalSettings.value = JSON.parse(JSON.stringify(settings.value))
    showMessage('Einstellungen gespeichert')
  } catch (error) {
    console.error('Fehler beim Speichern:', error)
    showMessage(error.response?.data?.detail || 'Fehler beim Speichern', 'error')
  } finally {
    saving.value = false
  }
}

async function addKey() {
  const key = newSshKey.value.trim()
  sshKeyError.value = ''

  if (!key.startsWith('ssh-')) {
    sshKeyError.value = 'Ungueltiger SSH-Key. Muss mit ssh- beginnen.'
    return
  }

  addingKey.value = true
  try {
    const response = await api.post('/api/cloud-init/settings/ssh-keys', { key })
    settings.value.ssh_authorized_keys = response.data
    originalSettings.value.ssh_authorized_keys = [...response.data]
    newSshKey.value = ''
    showMessage('SSH-Key hinzugefuegt')
  } catch (error) {
    console.error('Fehler:', error)
    sshKeyError.value = error.response?.data?.detail || 'Fehler beim Hinzufuegen'
    showMessage('Fehler beim Hinzufuegen', 'error')
  } finally {
    addingKey.value = false
  }
}

async function removeKey(key) {
  deletingKey.value = key
  try {
    const response = await api.delete('/api/cloud-init/settings/ssh-keys', { data: { key } })
    settings.value.ssh_authorized_keys = response.data.remaining_keys
    originalSettings.value.ssh_authorized_keys = [...response.data.remaining_keys]
    showMessage('SSH-Key entfernt')
  } catch (error) {
    console.error('Fehler:', error)
    showMessage('Fehler beim Entfernen', 'error')
  } finally {
    deletingKey.value = null
  }
}

async function loadNetboxUrl() {
  try {
    const response = await api.get('/api/settings/netbox-url')
    netboxUrl.value = response.data.url || ''
    originalNetboxUrl.value = response.data.url || ''
  } catch (error) {
    console.error('Fehler beim Laden der NetBox URL:', error)
  }
}

async function saveNetboxUrl() {
  savingNetboxUrl.value = true
  try {
    await api.put('/api/settings/netbox-url', { url: netboxUrl.value || null })
    originalNetboxUrl.value = netboxUrl.value
    showMessage('NetBox URL gespeichert')
  } catch (error) {
    console.error('Fehler beim Speichern:', error)
    showMessage(error.response?.data?.detail || 'Fehler beim Speichern', 'error')
  } finally {
    savingNetboxUrl.value = false
  }
}

// Load on mount
onMounted(() => {
  loadSettings()
  loadNetboxUrl()
})
</script>

<style scoped>
.font-monospace {
  font-family: 'Courier New', monospace;
}
</style>
