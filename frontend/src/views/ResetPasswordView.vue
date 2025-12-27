<template>
  <v-container class="fill-height" fluid>
    <v-row align="center" justify="center">
      <v-col cols="12" sm="8" md="5" lg="4">
        <!-- Logo Banner -->
        <div class="d-flex justify-center mb-6">
          <AppLogo variant="banner" size="lg" />
        </div>

        <v-card elevation="12" class="pa-4">
          <v-card-title class="text-h5 text-center mb-4">
            <v-icon size="48" color="primary" class="mb-2">mdi-lock-reset</v-icon>
            <div>Neues Passwort setzen</div>
          </v-card-title>

          <v-card-text>
            <!-- Loading -->
            <div v-if="validating" class="text-center py-8">
              <v-progress-circular indeterminate color="primary" size="48"></v-progress-circular>
              <div class="mt-4 text-body-2">Token wird geprueft...</div>
            </div>

            <!-- Ungueltiger Token -->
            <v-alert
              v-else-if="!tokenValid && !success"
              type="error"
              variant="tonal"
              class="mb-4"
            >
              <div class="font-weight-medium">Ungueltiger Link</div>
              <div class="text-body-2">
                Dieser Link ist ungueltig oder abgelaufen.
                Bitte fordern Sie einen neuen Reset-Link an.
              </div>
            </v-alert>

            <!-- Erfolg -->
            <v-alert
              v-else-if="success"
              type="success"
              variant="tonal"
              class="mb-4"
            >
              <div class="font-weight-medium">Passwort geaendert</div>
              <div class="text-body-2">
                Ihr Passwort wurde erfolgreich geaendert.
                Sie koennen sich jetzt mit dem neuen Passwort anmelden.
              </div>
            </v-alert>

            <!-- Formular -->
            <v-form v-else-if="tokenValid" ref="form" @submit.prevent="submit">
              <p class="text-body-2 mb-4">
                Geben Sie Ihr neues Passwort ein.
              </p>

              <v-text-field
                v-model="password"
                label="Neues Passwort"
                :type="showPassword ? 'text' : 'password'"
                prepend-icon="mdi-lock"
                :append-inner-icon="showPassword ? 'mdi-eye-off' : 'mdi-eye'"
                @click:append-inner="showPassword = !showPassword"
                :rules="[
                  v => !!v || 'Passwort erforderlich',
                  v => v.length >= 8 || 'Mindestens 8 Zeichen'
                ]"
                :disabled="loading"
                autofocus
              ></v-text-field>

              <v-text-field
                v-model="confirmPassword"
                label="Passwort bestaetigen"
                :type="showPassword ? 'text' : 'password'"
                prepend-icon="mdi-lock-check"
                :rules="[
                  v => !!v || 'Bestaetigung erforderlich',
                  v => v === password || 'Passwoerter stimmen nicht ueberein'
                ]"
                :disabled="loading"
              ></v-text-field>

              <!-- Token-Ablauf Info -->
              <v-alert
                v-if="expiresAt"
                type="info"
                variant="tonal"
                density="compact"
                class="mb-4"
              >
                Link gueltig bis: {{ formatDate(expiresAt) }}
              </v-alert>

              <v-alert
                v-if="error"
                type="error"
                variant="tonal"
                class="mb-4"
                density="compact"
              >
                {{ error }}
              </v-alert>

              <v-btn
                type="submit"
                color="primary"
                block
                size="large"
                :loading="loading"
              >
                Passwort aendern
              </v-btn>
            </v-form>
          </v-card-text>

          <v-card-actions class="justify-center flex-column">
            <router-link v-if="!tokenValid || success" to="/login" class="text-caption">
              Zum Login
            </router-link>
            <router-link v-if="!tokenValid && !success" to="/forgot-password" class="text-caption mt-2">
              Neuen Link anfordern
            </router-link>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import AppLogo from '@/components/AppLogo.vue'

const route = useRoute()

const form = ref(null)
const password = ref('')
const confirmPassword = ref('')
const showPassword = ref(false)
const loading = ref(false)
const validating = ref(true)
const tokenValid = ref(false)
const expiresAt = ref(null)
const error = ref('')
const success = ref(false)

const token = route.query.token

onMounted(async () => {
  if (!token) {
    tokenValid.value = false
    validating.value = false
    return
  }

  try {
    const response = await axios.get(`/api/auth/validate-reset-token?token=${token}`)
    tokenValid.value = response.data.valid
    expiresAt.value = response.data.expires_at
  } catch (e) {
    tokenValid.value = false
  } finally {
    validating.value = false
  }
})

function formatDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

async function submit() {
  const { valid } = await form.value.validate()
  if (!valid) return

  loading.value = true
  error.value = ''

  try {
    await axios.post('/api/auth/reset-password', {
      token: token,
      new_password: password.value
    })
    success.value = true
  } catch (e) {
    error.value = e.response?.data?.detail || 'Ein Fehler ist aufgetreten'
  } finally {
    loading.value = false
  }
}
</script>
