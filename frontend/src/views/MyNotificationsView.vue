<template>
  <v-container fluid class="pa-4">
    <v-row>
      <v-col cols="12" md="8" lg="6">
        <v-card>
          <v-card-title>
            <v-icon start>mdi-bell-cog</v-icon>
            Meine Benachrichtigungen
          </v-card-title>
          <v-card-subtitle>
            Persoenliche Einstellungen fuer E-Mail und Push-Benachrichtigungen
          </v-card-subtitle>

          <v-card-text v-if="loading" class="text-center py-8">
            <v-progress-circular indeterminate />
          </v-card-text>

          <v-card-text v-else>
            <!-- Kanaele -->
            <div class="text-subtitle-1 mb-3">
              <v-icon start size="small">mdi-broadcast</v-icon>
              Kanaele
            </div>

            <v-switch
              v-model="prefs.email_enabled"
              label="E-Mail-Benachrichtigungen"
              :hint="authStore.user?.email || 'Keine E-Mail hinterlegt'"
              persistent-hint
              density="compact"
              color="primary"
              class="mb-2"
              @update:model-value="savePrefs"
            />

            <v-switch
              v-model="prefs.gotify_enabled"
              label="Gotify Push-Benachrichtigungen"
              hint="Erfordert globale Gotify-Konfiguration durch Admin"
              persistent-hint
              density="compact"
              color="primary"
              class="mb-4"
              @update:model-value="savePrefs"
            />

            <v-divider class="my-4" />

            <!-- Ereignisse -->
            <div class="text-subtitle-1 mb-3">
              <v-icon start size="small">mdi-bell</v-icon>
              Ereignisse
            </div>

            <v-row>
              <v-col cols="12" sm="6">
                <div class="text-caption text-grey mb-2">VMs</div>
                <v-checkbox
                  v-model="prefs.notify_vm_created"
                  label="VM erstellt"
                  density="compact"
                  hide-details
                  @update:model-value="savePrefs"
                />
                <v-checkbox
                  v-model="prefs.notify_vm_deleted"
                  label="VM geloescht"
                  density="compact"
                  hide-details
                  @update:model-value="savePrefs"
                />
                <v-checkbox
                  v-model="prefs.notify_vm_state_change"
                  label="VM Status-Aenderung"
                  density="compact"
                  hide-details
                  @update:model-value="savePrefs"
                />
              </v-col>
              <v-col cols="12" sm="6">
                <div class="text-caption text-grey mb-2">Ansible & System</div>
                <v-checkbox
                  v-model="prefs.notify_ansible_completed"
                  label="Playbook erfolgreich"
                  density="compact"
                  hide-details
                  @update:model-value="savePrefs"
                />
                <v-checkbox
                  v-model="prefs.notify_ansible_failed"
                  label="Playbook fehlgeschlagen"
                  density="compact"
                  hide-details
                  @update:model-value="savePrefs"
                />
                <v-checkbox
                  v-model="prefs.notify_system_alerts"
                  label="System-Warnungen"
                  density="compact"
                  hide-details
                  @update:model-value="savePrefs"
                />
              </v-col>
            </v-row>

            <v-alert
              v-if="saved"
              type="success"
              variant="tonal"
              density="compact"
              class="mt-4"
            >
              Einstellungen gespeichert
            </v-alert>

            <v-alert
              v-if="error"
              type="error"
              variant="tonal"
              density="compact"
              class="mt-4"
            >
              {{ error }}
            </v-alert>
          </v-card-text>
        </v-card>

        <!-- Zurueck Button -->
        <v-btn
          variant="text"
          class="mt-4"
          @click="goBack"
        >
          <v-icon start>mdi-arrow-left</v-icon>
          Zurueck
        </v-btn>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/api/client'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const loading = ref(true)
const saved = ref(false)
const error = ref(null)

const prefs = ref({
  email_enabled: true,
  gotify_enabled: false,
  notify_vm_created: true,
  notify_vm_deleted: true,
  notify_vm_state_change: false,
  notify_ansible_completed: true,
  notify_ansible_failed: true,
  notify_system_alerts: true,
})

function goBack() {
  // Wenn von Profil-Dialog kommend, zum Dashboard zurueck
  if (route.query.from === 'profile') {
    router.push('/')
  } else if (window.history.length > 2) {
    // Standard: History zurueck navigieren
    router.back()
  } else {
    // Fallback: zur Startseite
    router.push('/')
  }
}

async function loadPrefs() {
  loading.value = true
  error.value = null
  try {
    const response = await api.get('/api/notifications/preferences')
    prefs.value = {
      email_enabled: response.data.email_enabled,
      gotify_enabled: response.data.gotify_enabled,
      notify_vm_created: response.data.notify_vm_created,
      notify_vm_deleted: response.data.notify_vm_deleted,
      notify_vm_state_change: response.data.notify_vm_state_change,
      notify_ansible_completed: response.data.notify_ansible_completed,
      notify_ansible_failed: response.data.notify_ansible_failed,
      notify_system_alerts: response.data.notify_system_alerts,
    }
  } catch (e) {
    error.value = 'Einstellungen konnten nicht geladen werden'
    console.error('Fehler beim Laden:', e)
  } finally {
    loading.value = false
  }
}

async function savePrefs() {
  error.value = null
  try {
    await api.put('/api/notifications/preferences', prefs.value)
    saved.value = true
    setTimeout(() => { saved.value = false }, 2000)
  } catch (e) {
    error.value = 'Speichern fehlgeschlagen'
    console.error('Fehler beim Speichern:', e)
  }
}

onMounted(loadPrefs)
</script>
