<template>
  <v-dialog v-model="dialog" max-width="400">
    <v-card>
      <!-- Header mit Avatar -->
      <div class="pa-4 text-center">
        <v-avatar
          size="64"
          :color="authStore.isSuperAdmin ? 'warning' : 'primary'"
          class="mb-3"
        >
          <v-icon size="36">
            {{ authStore.isSuperAdmin ? 'mdi-shield-crown' : 'mdi-account' }}
          </v-icon>
        </v-avatar>
        <div class="text-h6">{{ authStore.user?.username }}</div>
        <div class="text-caption text-grey">
          {{ authStore.user?.email || 'Keine E-Mail' }}
        </div>
        <v-chip
          size="small"
          :color="authStore.isSuperAdmin ? 'warning' : 'grey'"
          variant="tonal"
          class="mt-2"
        >
          {{ authStore.isSuperAdmin ? 'Super-Admin' : 'Benutzer' }}
        </v-chip>
      </div>

      <v-divider />

      <!-- Dark Mode Toggle -->
      <div class="pa-4">
        <div class="text-caption text-grey mb-2">Erscheinungsbild</div>
        <v-btn-toggle
          :model-value="authStore.currentDarkMode"
          mandatory
          density="compact"
          class="w-100"
          divided
          @update:model-value="selectDarkMode"
        >
          <v-btn value="light" class="flex-grow-1">
            <v-icon start size="small">mdi-white-balance-sunny</v-icon>
            Hell
          </v-btn>
          <v-btn value="system" class="flex-grow-1">
            <v-icon start size="small">mdi-laptop</v-icon>
            System
          </v-btn>
          <v-btn value="dark" class="flex-grow-1">
            <v-icon start size="small">mdi-weather-night</v-icon>
            Dunkel
          </v-btn>
        </v-btn-toggle>

        <div class="text-caption text-grey mb-2 mt-4">Farbschema</div>
        <div class="d-flex gap-2 justify-center">
          <v-btn
            v-for="t in themes"
            :key="t.value"
            icon
            size="small"
            :color="t.color"
            :variant="authStore.currentTheme === t.value ? 'flat' : 'outlined'"
            @click="selectTheme(t.value)"
          >
            <v-icon v-if="authStore.currentTheme === t.value" size="16">mdi-check</v-icon>
          </v-btn>
        </div>
      </div>

      <v-divider />

      <!-- Aktionen -->
      <v-list density="compact">
        <v-list-item
          prepend-icon="mdi-bell-cog"
          title="Benachrichtigungen"
          subtitle="E-Mail und Push-Einstellungen"
          @click="goToNotifications"
        >
          <template v-slot:append>
            <v-icon size="small">mdi-chevron-right</v-icon>
          </template>
        </v-list-item>

        <v-list-item
          prepend-icon="mdi-lock"
          title="Passwort aendern"
          @click="showPasswordDialog = true"
        >
          <template v-slot:append>
            <v-icon size="small">mdi-chevron-right</v-icon>
          </template>
        </v-list-item>

        <v-list-item
          v-if="authStore.isSuperAdmin"
          prepend-icon="mdi-cog"
          title="App-Einstellungen"
          subtitle="Theme, Features, System"
          @click="goToSettings"
        >
          <template v-slot:append>
            <v-icon size="small">mdi-chevron-right</v-icon>
          </template>
        </v-list-item>
      </v-list>

      <v-divider />

      <!-- Footer -->
      <v-card-actions>
        <v-btn
          color="error"
          variant="text"
          @click="logout"
        >
          <v-icon start>mdi-logout</v-icon>
          Abmelden
        </v-btn>
        <v-spacer />
        <v-btn
          variant="text"
          @click="dialog = false"
        >
          Schliessen
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Passwort Dialog -->
  <v-dialog v-model="showPasswordDialog" max-width="400" persistent>
    <v-card>
      <v-card-title>
        <v-icon start>mdi-lock</v-icon>
        Passwort aendern
      </v-card-title>
      <v-card-text>
        <v-form ref="passwordForm" @submit.prevent="changePassword">
          <v-text-field
            v-model="passwordData.currentPassword"
            label="Aktuelles Passwort"
            type="password"
            :rules="[v => !!v || 'Pflichtfeld']"
            prepend-icon="mdi-lock"
            variant="outlined"
            density="compact"
            class="mb-2"
          />

          <v-text-field
            v-model="passwordData.newPassword"
            label="Neues Passwort"
            type="password"
            :rules="[
              v => !!v || 'Pflichtfeld',
              v => v.length >= 8 || 'Mindestens 8 Zeichen'
            ]"
            prepend-icon="mdi-lock-plus"
            variant="outlined"
            density="compact"
            class="mb-2"
          />

          <v-text-field
            v-model="passwordData.confirmPassword"
            label="Passwort bestaetigen"
            type="password"
            :rules="[
              v => !!v || 'Pflichtfeld',
              v => v === passwordData.newPassword || 'Passwoerter stimmen nicht'
            ]"
            prepend-icon="mdi-lock-check"
            variant="outlined"
            density="compact"
          />

          <v-checkbox
            v-model="passwordData.syncToNetbox"
            label="Auch in NetBox aendern"
            density="compact"
            hide-details
            class="mt-2"
          />
        </v-form>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn
          variant="text"
          @click="closePasswordDialog"
        >
          Abbrechen
        </v-btn>
        <v-btn
          color="primary"
          :loading="savingPassword"
          @click="changePassword"
        >
          Speichern
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, inject } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const showSnackbar = inject('showSnackbar')

const dialog = ref(false)
const showPasswordDialog = ref(false)
const savingPassword = ref(false)
const passwordForm = ref(null)

// Verfuegbare Farbthemes
const themes = [
  { value: 'blue', color: '#1976D2' },
  { value: 'orange', color: '#FB8C00' },
  { value: 'green', color: '#43A047' },
  { value: 'purple', color: '#8E24AA' },
  { value: 'teal', color: '#00897B' },
]

const passwordData = ref({
  currentPassword: '',
  newPassword: '',
  confirmPassword: '',
  syncToNetbox: true,
})

async function selectDarkMode(mode) {
  try {
    await authStore.updatePreferences(null, mode)
  } catch (e) {
    showSnackbar?.('Fehler beim Speichern', 'error')
  }
}

async function selectTheme(theme) {
  try {
    await authStore.updatePreferences(theme)
  } catch (e) {
    showSnackbar?.('Fehler beim Speichern', 'error')
  }
}

function goToNotifications() {
  dialog.value = false
  router.push({ path: '/my/notifications', query: { from: 'profile' } })
}

function goToSettings() {
  dialog.value = false
  router.push('/settings')
}

function closePasswordDialog() {
  showPasswordDialog.value = false
  passwordData.value = {
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
    syncToNetbox: true,
  }
}

async function changePassword() {
  const { valid } = await passwordForm.value.validate()
  if (!valid) return

  savingPassword.value = true
  try {
    const result = await authStore.changePassword(
      passwordData.value.currentPassword,
      passwordData.value.newPassword,
      passwordData.value.confirmPassword,
      passwordData.value.syncToNetbox
    )

    let message = 'Passwort geaendert'
    if (result?.netbox_synced) {
      message += ' (auch in NetBox)'
    }
    showSnackbar?.(message, 'success')
    closePasswordDialog()
  } catch (e) {
    showSnackbar?.(e.response?.data?.detail || 'Fehler beim Aendern', 'error')
  } finally {
    savingPassword.value = false
  }
}

function logout() {
  authStore.logout()
  dialog.value = false
  router.push('/login')
}

function open() {
  dialog.value = true
}

defineExpose({ open })
</script>
