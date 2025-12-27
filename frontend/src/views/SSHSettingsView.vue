<template>
  <v-container fluid class="pa-4">
    <v-row>
      <v-col cols="12" lg="8" xl="6">
        <!-- Header -->
        <div class="d-flex align-center mb-4">
          <v-icon size="32" color="primary" class="mr-3">mdi-key-chain</v-icon>
          <div>
            <h1 class="text-h5">SSH-Einstellungen</h1>
            <p class="text-body-2 text-grey mb-0">
              Konfiguriere SSH-Keys und Benutzer fuer Ansible-Verbindungen
            </p>
          </div>
        </div>

        <!-- Hauptkarte -->
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon start>mdi-ansible</v-icon>
            SSH / Ansible Konfiguration
          </v-card-title>

          <v-card-text>
            <!-- Warnung bei Key-Aenderung -->
            <v-alert
              type="warning"
              variant="tonal"
              class="mb-4"
            >
              <v-icon start>mdi-alert</v-icon>
              <strong>Achtung:</strong> Das Aendern des SSH-Keys erfordert, dass der neue
              Public Key auf allen Ziel-VMs in <code>~/.ssh/authorized_keys</code> hinterlegt wird!
            </v-alert>

            <!-- SSH Key Manager Komponente -->
            <SSHKeyManager
              ref="sshKeyManager"
              :initial-user="currentUser"
              :show-warnings="true"
              api-prefix="/api/settings/ssh"
              endpoint-mode="settings"
              :inventory-hosts="inventoryHosts"
              @update:user="handleUserChange"
              @key-changed="handleKeyChanged"
              @config-loaded="handleConfigLoaded"
            />
          </v-card-text>

          <v-divider></v-divider>

          <v-card-actions>
            <v-spacer></v-spacer>
            <v-btn
              v-if="userChanged"
              color="primary"
              :loading="saving"
              @click="saveUserConfig"
            >
              <v-icon start>mdi-content-save</v-icon>
              Benutzer speichern
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
                  Wie richte ich SSH-Keys ein?
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <ol class="pl-4">
                    <li class="mb-2">
                      <strong>Key generieren oder importieren:</strong>
                      Nutze eine der Optionen oben um einen SSH-Key zu konfigurieren.
                    </li>
                    <li class="mb-2">
                      <strong>Public Key kopieren:</strong>
                      Nach der Generierung oder dem Import wird der Public Key angezeigt.
                    </li>
                    <li class="mb-2">
                      <strong>Auf Ziel-VMs hinterlegen:</strong>
                      Fuege den Public Key auf jeder VM in die Datei
                      <code>~/.ssh/authorized_keys</code> des SSH-Benutzers ein.
                    </li>
                    <li>
                      <strong>Verbindung testen:</strong>
                      Nutze den Verbindungstest um zu pruefen ob alles funktioniert.
                    </li>
                  </ol>
                </v-expansion-panel-text>
              </v-expansion-panel>

              <v-expansion-panel>
                <v-expansion-panel-title>
                  <v-icon start size="small">mdi-import</v-icon>
                  Wie importiere ich bestehende Keys?
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <p class="mb-2">
                    Um bestehende Keys aus deinem Host-System zu importieren:
                  </p>
                  <ol class="pl-4">
                    <li class="mb-2">
                      Fuege in <code>docker-compose.yml</code> ein Volume hinzu:
                      <pre class="bg-grey-lighten-4 pa-2 mt-1 rounded">- ~/.ssh:/host-ssh:ro</pre>
                    </li>
                    <li class="mb-2">
                      Starte die Container neu:
                      <pre class="bg-grey-lighten-4 pa-2 mt-1 rounded">docker compose down && docker compose up -d</pre>
                    </li>
                    <li>
                      Lade diese Seite neu - verfuegbare Keys werden angezeigt.
                    </li>
                  </ol>
                </v-expansion-panel-text>
              </v-expansion-panel>

              <v-expansion-panel>
                <v-expansion-panel-title>
                  <v-icon start size="small">mdi-alert-circle</v-icon>
                  Fehlerbehebung
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <div class="mb-3">
                    <strong>Permission denied:</strong>
                    <ul class="pl-4">
                      <li>Der SSH-Benutzer existiert nicht auf der Ziel-VM</li>
                      <li>Der Public Key ist nicht in authorized_keys hinterlegt</li>
                      <li>Die Berechtigungen von ~/.ssh sind falsch (sollte 700 sein)</li>
                    </ul>
                  </div>
                  <div>
                    <strong>Host nicht erreichbar:</strong>
                    <ul class="pl-4">
                      <li>Firewall blockiert Port 22</li>
                      <li>SSH-Dienst laeuft nicht auf der Ziel-VM</li>
                      <li>Netzwerkproblem zwischen Container und Ziel-VM</li>
                    </ul>
                  </div>
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
import { ref, onMounted, inject } from 'vue'
import api from '@/api/client'
import SSHKeyManager from '@/components/SSHKeyManager.vue'

const showSnackbar = inject('showSnackbar', null)

// Refs
const sshKeyManager = ref(null)
const saving = ref(false)
const currentUser = ref('')
const pendingUser = ref('')
const userChanged = ref(false)
const inventoryHosts = ref([])

// Snackbar (Fallback wenn inject nicht verfuegbar)
const snackbar = ref(false)
const snackbarText = ref('')
const snackbarColor = ref('success')

function showMessage(text, color = 'success') {
  if (showSnackbar) {
    showSnackbar(text, color)
  } else {
    snackbarText.value = text
    snackbarColor.value = color
    snackbar.value = true
  }
}

// Event Handler
function handleUserChange(newUser) {
  pendingUser.value = newUser
  userChanged.value = newUser !== currentUser.value
}

function handleKeyChanged(result) {
  showMessage('SSH-Key wurde aktualisiert')
}

function handleConfigLoaded(config) {
  if (config.ssh_user) {
    currentUser.value = config.ssh_user
    pendingUser.value = config.ssh_user
  }
}

// Benutzer speichern
async function saveUserConfig() {
  if (!pendingUser.value) return

  saving.value = true
  try {
    await api.put('/api/settings/ssh', {
      ssh_user: pendingUser.value,
    })

    currentUser.value = pendingUser.value
    userChanged.value = false
    showMessage('SSH-Benutzer wurde gespeichert')
  } catch (e) {
    showMessage(e.response?.data?.detail || 'Speichern fehlgeschlagen', 'error')
  } finally {
    saving.value = false
  }
}

// Inventory Hosts laden
async function loadInventoryHosts() {
  try {
    const response = await api.get('/api/inventory/hosts')
    inventoryHosts.value = response.data.map(host => ({
      name: host.name,
      ip: host.ansible_host || host.name,
    }))
  } catch (e) {
    console.debug('Inventory nicht geladen (optional):', e.message)
  }
}

// Lifecycle
onMounted(async () => {
  await loadInventoryHosts()
})
</script>
