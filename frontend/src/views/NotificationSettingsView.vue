<template>
  <v-container fluid class="pa-4">
    <v-row>
      <v-col cols="12">
        <div class="d-flex align-center mb-4">
          <v-icon size="32" color="primary" class="mr-3">mdi-bell-cog</v-icon>
          <div>
            <h1 class="text-h4">Benachrichtigungen</h1>
            <p class="text-body-2 text-grey">E-Mail, Gotify und Webhook-Einstellungen</p>
          </div>
        </div>
      </v-col>
    </v-row>

    <v-row>
      <!-- Linke Spalte: SMTP & Gotify -->
      <v-col cols="12" md="6">
        <!-- SMTP Einstellungen -->
        <v-card class="mb-4">
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2">mdi-email</v-icon>
            E-Mail (SMTP)
            <v-spacer></v-spacer>
            <v-switch
              v-model="settings.smtp_enabled"
              color="primary"
              hide-details
              density="compact"
              @update:model-value="saveSettings"
            ></v-switch>
          </v-card-title>

          <v-card-text v-if="settings.smtp_enabled">
            <v-text-field
              v-model="settings.smtp_host"
              label="SMTP Server"
              placeholder="smtp.example.com"
              density="compact"
              class="mb-2"
            ></v-text-field>

            <v-row>
              <v-col cols="6">
                <v-text-field
                  v-model.number="settings.smtp_port"
                  label="Port"
                  type="number"
                  density="compact"
                ></v-text-field>
              </v-col>
              <v-col cols="6">
                <v-select
                  v-model="smtpSecurity"
                  label="Sicherheit"
                  :items="[
                    { title: 'STARTTLS (587)', value: 'starttls' },
                    { title: 'SSL/TLS (465)', value: 'ssl' },
                    { title: 'Keine', value: 'none' }
                  ]"
                  density="compact"
                ></v-select>
              </v-col>
            </v-row>

            <v-text-field
              v-model="settings.smtp_user"
              label="Benutzername"
              density="compact"
              class="mb-2"
            ></v-text-field>

            <v-text-field
              v-model="smtpPassword"
              label="Passwort"
              type="password"
              density="compact"
              :placeholder="settings.smtp_password_set ? '(gespeichert)' : ''"
              class="mb-2"
            ></v-text-field>

            <v-row>
              <v-col cols="6">
                <v-text-field
                  v-model="settings.smtp_from_email"
                  label="Absender E-Mail"
                  density="compact"
                ></v-text-field>
              </v-col>
              <v-col cols="6">
                <v-text-field
                  v-model="settings.smtp_from_name"
                  label="Absender Name"
                  density="compact"
                ></v-text-field>
              </v-col>
            </v-row>

            <div class="d-flex gap-2 mt-2">
              <v-btn
                color="primary"
                variant="tonal"
                size="small"
                :loading="savingSmtp"
                @click="saveSmtpSettings"
              >
                Speichern
              </v-btn>
              <v-btn
                variant="outlined"
                size="small"
                :loading="testingSmtp"
                @click="testSmtp"
              >
                Verbindung testen
              </v-btn>
              <v-btn
                color="success"
                variant="tonal"
                size="small"
                :loading="sendingTestEmail"
                @click="sendTestEmail"
              >
                <v-icon start size="small">mdi-email-send</v-icon>
                Test-Mail senden
              </v-btn>
            </div>

            <v-alert
              v-if="smtpTestResult"
              :type="smtpTestResult.success ? 'success' : 'error'"
              variant="tonal"
              density="compact"
              class="mt-3"
              closable
              @click:close="smtpTestResult = null"
            >
              {{ smtpTestResult.message }}
            </v-alert>
          </v-card-text>
        </v-card>

        <!-- Gotify Einstellungen -->
        <v-card class="mb-4">
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2">mdi-bell-ring</v-icon>
            Gotify
            <v-spacer></v-spacer>
            <v-switch
              v-model="settings.gotify_enabled"
              color="primary"
              hide-details
              density="compact"
              @update:model-value="saveSettings"
            ></v-switch>
          </v-card-title>

          <v-card-text v-if="settings.gotify_enabled">
            <v-text-field
              v-model="settings.gotify_url"
              label="Gotify URL"
              placeholder="https://gotify.example.com"
              density="compact"
              class="mb-2"
            ></v-text-field>

            <v-text-field
              v-model="gotifyToken"
              label="App Token"
              type="password"
              density="compact"
              :placeholder="settings.gotify_token_set ? '(gespeichert)' : ''"
              class="mb-2"
            ></v-text-field>

            <v-slider
              v-model="settings.gotify_priority"
              label="Standard-Prioritaet"
              :min="1"
              :max="10"
              :step="1"
              thumb-label
              density="compact"
            ></v-slider>

            <div class="d-flex gap-2 mt-2">
              <v-btn
                color="primary"
                variant="tonal"
                size="small"
                :loading="savingGotify"
                @click="saveGotifySettings"
              >
                Speichern
              </v-btn>
              <v-btn
                variant="outlined"
                size="small"
                :loading="testingGotify"
                @click="testGotify"
              >
                Verbindung testen
              </v-btn>
              <v-btn
                color="success"
                variant="tonal"
                size="small"
                :loading="sendingTestGotify"
                @click="sendTestGotify"
              >
                <v-icon start size="small">mdi-bell-ring</v-icon>
                Test-Nachricht
              </v-btn>
            </div>

            <v-alert
              v-if="gotifyTestResult"
              :type="gotifyTestResult.success ? 'success' : 'error'"
              variant="tonal"
              density="compact"
              class="mt-3"
              closable
              @click:close="gotifyTestResult = null"
            >
              {{ gotifyTestResult.message }}
            </v-alert>
          </v-card-text>
        </v-card>

        <!-- Allgemeine Einstellungen -->
        <v-card>
          <v-card-title>
            <v-icon class="mr-2">mdi-cog</v-icon>
            Allgemein
          </v-card-title>
          <v-card-text>
            <v-text-field
              v-model="settings.app_url"
              label="App URL (fuer Links in E-Mails)"
              placeholder="https://pve-commander.example.com"
              density="compact"
              class="mb-2"
            ></v-text-field>

            <v-text-field
              v-model.number="settings.password_reset_expiry_hours"
              label="Passwort-Reset Link Gueltigkeit (Stunden)"
              type="number"
              :min="1"
              :max="168"
              density="compact"
            ></v-text-field>

            <v-btn
              color="primary"
              variant="tonal"
              size="small"
              :loading="savingGeneral"
              @click="saveGeneralSettings"
            >
              Speichern
            </v-btn>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Rechte Spalte: Webhooks -->
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2">mdi-webhook</v-icon>
            Webhooks
            <v-spacer></v-spacer>
            <v-btn
              color="primary"
              variant="tonal"
              size="small"
              @click="openWebhookDialog()"
            >
              <v-icon start>mdi-plus</v-icon>
              Neu
            </v-btn>
          </v-card-title>

          <v-card-text>
            <v-alert
              v-if="webhooks.length === 0"
              type="info"
              variant="tonal"
              density="compact"
            >
              Keine Webhooks konfiguriert.
            </v-alert>

            <v-list v-else density="compact">
              <v-list-item
                v-for="webhook in webhooks"
                :key="webhook.id"
                :class="{ 'opacity-50': !webhook.enabled }"
              >
                <template v-slot:prepend>
                  <v-icon :color="webhook.enabled ? 'success' : 'grey'">
                    {{ webhook.enabled ? 'mdi-check-circle' : 'mdi-circle-outline' }}
                  </v-icon>
                </template>

                <v-list-item-title>{{ webhook.name }}</v-list-item-title>
                <v-list-item-subtitle class="text-truncate">
                  {{ webhook.url }}
                </v-list-item-subtitle>

                <template v-slot:append>
                  <v-chip
                    v-if="webhook.last_status"
                    size="x-small"
                    :color="webhook.last_status === 'success' ? 'success' : 'error'"
                    class="mr-2"
                  >
                    {{ webhook.last_status }}
                  </v-chip>
                  <v-btn
                    icon
                    variant="text"
                    size="small"
                    @click="testWebhook(webhook)"
                  >
                    <v-icon>mdi-play</v-icon>
                    <v-tooltip activator="parent" location="top">Testen</v-tooltip>
                  </v-btn>
                  <v-btn
                    icon
                    variant="text"
                    size="small"
                    @click="openWebhookDialog(webhook)"
                  >
                    <v-icon>mdi-pencil</v-icon>
                  </v-btn>
                  <v-btn
                    icon
                    variant="text"
                    size="small"
                    color="error"
                    @click="deleteWebhook(webhook)"
                  >
                    <v-icon>mdi-delete</v-icon>
                  </v-btn>
                </template>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>

        <!-- Log -->
        <v-card class="mt-4">
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2">mdi-history</v-icon>
            Benachrichtigungs-Log
            <v-spacer></v-spacer>
            <v-btn
              variant="text"
              size="small"
              @click="loadLog"
            >
              <v-icon>mdi-refresh</v-icon>
            </v-btn>
          </v-card-title>

          <v-card-text>
            <v-data-table
              :headers="logHeaders"
              :items="logEntries"
              :loading="loadingLog"
              density="compact"
              :items-per-page="10"
            >
              <template v-slot:item.channel="{ item }">
                <v-chip size="x-small" :color="getChannelColor(item.channel)">
                  {{ item.channel }}
                </v-chip>
              </template>
              <template v-slot:item.status="{ item }">
                <v-icon
                  :color="item.status === 'sent' ? 'success' : 'error'"
                  size="small"
                >
                  {{ item.status === 'sent' ? 'mdi-check' : 'mdi-close' }}
                </v-icon>
              </template>
              <template v-slot:item.created_at="{ item }">
                {{ formatDate(item.created_at) }}
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Webhook Dialog -->
    <v-dialog v-model="webhookDialog" max-width="600">
      <v-card>
        <v-card-title>
          {{ editingWebhook ? 'Webhook bearbeiten' : 'Neuer Webhook' }}
        </v-card-title>
        <v-card-text>
          <v-text-field
            v-model="webhookForm.name"
            label="Name"
            :rules="[v => !!v || 'Name erforderlich']"
            class="mb-2"
          ></v-text-field>

          <v-text-field
            v-model="webhookForm.url"
            label="URL"
            :rules="[v => !!v || 'URL erforderlich']"
            class="mb-2"
          ></v-text-field>

          <v-text-field
            v-model="webhookForm.secret"
            label="Secret (fuer HMAC-Signatur)"
            type="password"
            :placeholder="editingWebhook?.secret_set ? '(gespeichert)' : 'Optional'"
            class="mb-4"
          ></v-text-field>

          <v-switch
            v-model="webhookForm.enabled"
            label="Aktiviert"
            color="primary"
            class="mb-4"
          ></v-switch>

          <div class="text-subtitle-2 mb-2">Ereignisse</div>
          <v-row>
            <v-col cols="6">
              <v-checkbox
                v-model="webhookForm.on_vm_created"
                label="VM erstellt"
                density="compact"
                hide-details
              ></v-checkbox>
              <v-checkbox
                v-model="webhookForm.on_vm_deleted"
                label="VM geloescht"
                density="compact"
                hide-details
              ></v-checkbox>
              <v-checkbox
                v-model="webhookForm.on_vm_state_change"
                label="VM Status-Aenderung"
                density="compact"
                hide-details
              ></v-checkbox>
            </v-col>
            <v-col cols="6">
              <v-checkbox
                v-model="webhookForm.on_ansible_completed"
                label="Ansible erfolgreich"
                density="compact"
                hide-details
              ></v-checkbox>
              <v-checkbox
                v-model="webhookForm.on_ansible_failed"
                label="Ansible fehlgeschlagen"
                density="compact"
                hide-details
              ></v-checkbox>
              <v-checkbox
                v-model="webhookForm.on_system_alert"
                label="System-Alerts"
                density="compact"
                hide-details
              ></v-checkbox>
            </v-col>
          </v-row>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="webhookDialog = false">Abbrechen</v-btn>
          <v-btn color="primary" :loading="savingWebhook" @click="saveWebhook">
            Speichern
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000">
      {{ snackbar.text }}
    </v-snackbar>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useConfirmDialog, confirmPresets } from '@/composables/useConfirmDialog'

const authStore = useAuthStore()
const { confirm: confirmDialog } = useConfirmDialog()

// Settings
const settings = ref({
  smtp_enabled: false,
  smtp_host: '',
  smtp_port: 587,
  smtp_user: '',
  smtp_from_email: '',
  smtp_from_name: 'PVE Commander',
  smtp_use_tls: true,
  smtp_use_ssl: false,
  smtp_password_set: false,
  gotify_enabled: false,
  gotify_url: '',
  gotify_priority: 5,
  gotify_token_set: false,
  app_url: 'http://localhost:8080',
  password_reset_expiry_hours: 24,
})

const smtpPassword = ref('')
const gotifyToken = ref('')

const smtpSecurity = computed({
  get: () => {
    if (settings.value.smtp_use_ssl) return 'ssl'
    if (settings.value.smtp_use_tls) return 'starttls'
    return 'none'
  },
  set: (val) => {
    settings.value.smtp_use_ssl = val === 'ssl'
    settings.value.smtp_use_tls = val === 'starttls'
    if (val === 'ssl') settings.value.smtp_port = 465
    else if (val === 'starttls') settings.value.smtp_port = 587
  }
})

// Loading states
const savingSmtp = ref(false)
const savingGotify = ref(false)
const savingGeneral = ref(false)
const testingSmtp = ref(false)
const testingGotify = ref(false)
const sendingTestEmail = ref(false)
const sendingTestGotify = ref(false)

// Test results
const smtpTestResult = ref(null)
const gotifyTestResult = ref(null)

// Webhooks
const webhooks = ref([])
const webhookDialog = ref(false)
const editingWebhook = ref(null)
const webhookForm = ref({
  name: '',
  url: '',
  secret: '',
  enabled: true,
  on_vm_created: false,
  on_vm_deleted: false,
  on_vm_state_change: false,
  on_ansible_completed: false,
  on_ansible_failed: false,
  on_system_alert: false,
})
const savingWebhook = ref(false)

// Log
const logEntries = ref([])
const loadingLog = ref(false)
const logHeaders = [
  { title: 'Kanal', key: 'channel', width: 80 },
  { title: 'Empfaenger', key: 'recipient' },
  { title: 'Event', key: 'event_type' },
  { title: 'Status', key: 'status', width: 60 },
  { title: 'Zeit', key: 'created_at', width: 140 },
]

// Snackbar
const snackbar = ref({ show: false, text: '', color: 'success' })

function showSnackbar(text, color = 'success') {
  snackbar.value = { show: true, text, color }
}

onMounted(async () => {
  await Promise.all([
    loadSettings(),
    loadWebhooks(),
    loadLog(),
  ])
})

async function loadSettings() {
  try {
    const response = await api.get('/api/notifications/settings')
    settings.value = { ...settings.value, ...response.data }
  } catch (e) {
    console.error('Fehler beim Laden der Einstellungen:', e)
  }
}

async function loadWebhooks() {
  try {
    const response = await api.get('/api/notifications/webhooks')
    webhooks.value = response.data
  } catch (e) {
    console.error('Fehler beim Laden der Webhooks:', e)
  }
}

async function loadLog() {
  loadingLog.value = true
  try {
    const response = await api.get('/api/notifications/log?per_page=50')
    logEntries.value = response.data.items
  } catch (e) {
    console.error('Fehler beim Laden des Logs:', e)
  } finally {
    loadingLog.value = false
  }
}

async function saveSettings() {
  try {
    await api.put('/api/notifications/settings', {
      smtp_enabled: settings.value.smtp_enabled,
      gotify_enabled: settings.value.gotify_enabled,
    })
  } catch (e) {
    showSnackbar('Fehler beim Speichern', 'error')
  }
}

async function saveSmtpSettings() {
  savingSmtp.value = true
  try {
    const data = {
      smtp_enabled: settings.value.smtp_enabled,
      smtp_host: settings.value.smtp_host,
      smtp_port: settings.value.smtp_port,
      smtp_user: settings.value.smtp_user,
      smtp_from_email: settings.value.smtp_from_email,
      smtp_from_name: settings.value.smtp_from_name,
      smtp_use_tls: settings.value.smtp_use_tls,
      smtp_use_ssl: settings.value.smtp_use_ssl,
    }
    if (smtpPassword.value) {
      data.smtp_password = smtpPassword.value
    }
    await api.put('/api/notifications/settings', data)
    smtpPassword.value = ''
    await loadSettings()
    showSnackbar('SMTP-Einstellungen gespeichert')
  } catch (e) {
    showSnackbar('Fehler beim Speichern', 'error')
  } finally {
    savingSmtp.value = false
  }
}

async function saveGotifySettings() {
  savingGotify.value = true
  try {
    const data = {
      gotify_enabled: settings.value.gotify_enabled,
      gotify_url: settings.value.gotify_url,
      gotify_priority: settings.value.gotify_priority,
    }
    if (gotifyToken.value) {
      data.gotify_token = gotifyToken.value
    }
    await api.put('/api/notifications/settings', data)
    gotifyToken.value = ''
    await loadSettings()
    showSnackbar('Gotify-Einstellungen gespeichert')
  } catch (e) {
    showSnackbar('Fehler beim Speichern', 'error')
  } finally {
    savingGotify.value = false
  }
}

async function saveGeneralSettings() {
  savingGeneral.value = true
  try {
    await api.put('/api/notifications/settings', {
      app_url: settings.value.app_url,
      password_reset_expiry_hours: settings.value.password_reset_expiry_hours,
    })
    showSnackbar('Allgemeine Einstellungen gespeichert')
  } catch (e) {
    showSnackbar('Fehler beim Speichern', 'error')
  } finally {
    savingGeneral.value = false
  }
}

async function testSmtp() {
  testingSmtp.value = true
  smtpTestResult.value = null
  try {
    const response = await api.post('/api/notifications/settings/test-smtp')
    smtpTestResult.value = response.data
  } catch (e) {
    smtpTestResult.value = {
      success: false,
      message: e.response?.data?.detail || 'Verbindungstest fehlgeschlagen'
    }
  } finally {
    testingSmtp.value = false
  }
}

async function sendTestEmail() {
  sendingTestEmail.value = true
  smtpTestResult.value = null
  try {
    const response = await api.post('/api/notifications/settings/send-test-email')
    smtpTestResult.value = response.data
    if (response.data.success) {
      loadLog() // Log aktualisieren
    }
  } catch (e) {
    smtpTestResult.value = {
      success: false,
      message: e.response?.data?.detail || 'Test-Mail konnte nicht gesendet werden'
    }
  } finally {
    sendingTestEmail.value = false
  }
}

async function testGotify() {
  testingGotify.value = true
  gotifyTestResult.value = null
  try {
    const response = await api.post('/api/notifications/settings/test-gotify')
    gotifyTestResult.value = response.data
  } catch (e) {
    gotifyTestResult.value = {
      success: false,
      message: e.response?.data?.detail || 'Verbindungstest fehlgeschlagen'
    }
  } finally {
    testingGotify.value = false
  }
}

async function sendTestGotify() {
  sendingTestGotify.value = true
  gotifyTestResult.value = null
  try {
    const response = await api.post('/api/notifications/settings/send-test-gotify')
    gotifyTestResult.value = response.data
    if (response.data.success) {
      loadLog() // Log aktualisieren
    }
  } catch (e) {
    gotifyTestResult.value = {
      success: false,
      message: e.response?.data?.detail || 'Test-Nachricht konnte nicht gesendet werden'
    }
  } finally {
    sendingTestGotify.value = false
  }
}

function openWebhookDialog(webhook = null) {
  editingWebhook.value = webhook
  if (webhook) {
    webhookForm.value = { ...webhook, secret: '' }
  } else {
    webhookForm.value = {
      name: '',
      url: '',
      secret: '',
      enabled: true,
      on_vm_created: false,
      on_vm_deleted: false,
      on_vm_state_change: false,
      on_ansible_completed: false,
      on_ansible_failed: false,
      on_system_alert: false,
    }
  }
  webhookDialog.value = true
}

async function saveWebhook() {
  savingWebhook.value = true
  try {
    const data = { ...webhookForm.value }
    if (!data.secret) delete data.secret

    if (editingWebhook.value) {
      await api.put(`/api/notifications/webhooks/${editingWebhook.value.id}`, data)
      showSnackbar('Webhook aktualisiert')
    } else {
      await api.post('/api/notifications/webhooks', data)
      showSnackbar('Webhook erstellt')
    }
    webhookDialog.value = false
    await loadWebhooks()
  } catch (e) {
    showSnackbar('Fehler beim Speichern', 'error')
  } finally {
    savingWebhook.value = false
  }
}

async function deleteWebhook(webhook) {
  // Beta UI: Styled Confirm Dialog
  if (authStore.currentUiBeta) {
    const confirmed = await confirmDialog({
      ...confirmPresets.delete(`Webhook "${webhook.name}"`),
    })
    if (!confirmed) return
  } else {
    // Classic UI: Browser confirm
    if (!window.confirm(`Webhook "${webhook.name}" wirklich loeschen?`)) return
  }

  try {
    await api.delete(`/api/notifications/webhooks/${webhook.id}`)
    showSnackbar('Webhook geloescht')
    await loadWebhooks()
  } catch (e) {
    showSnackbar('Fehler beim Loeschen', 'error')
  }
}

async function testWebhook(webhook) {
  try {
    const response = await api.post(`/api/notifications/webhooks/${webhook.id}/test`)
    if (response.data.success) {
      showSnackbar(`Webhook "${webhook.name}" erfolgreich`)
    } else {
      showSnackbar(`Webhook-Test fehlgeschlagen: ${response.data.message}`, 'error')
    }
    await loadWebhooks()
  } catch (e) {
    showSnackbar('Webhook-Test fehlgeschlagen', 'error')
  }
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function getChannelColor(channel) {
  const colors = {
    email: 'blue',
    gotify: 'orange',
    webhook: 'purple',
  }
  return colors[channel] || 'grey'
}
</script>
