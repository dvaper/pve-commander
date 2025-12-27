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
            <div>Passwort vergessen</div>
          </v-card-title>

          <v-card-text>
            <!-- Erfolgs-Meldung -->
            <v-alert
              v-if="submitted"
              type="success"
              variant="tonal"
              class="mb-4"
            >
              <div class="font-weight-medium">E-Mail gesendet</div>
              <div class="text-body-2">
                Falls die E-Mail-Adresse existiert, haben wir einen Link zum Zuruecksetzen
                des Passworts gesendet. Bitte pruefen Sie auch Ihren Spam-Ordner.
              </div>
            </v-alert>

            <!-- Formular -->
            <v-form v-else ref="form" @submit.prevent="submit">
              <p class="text-body-2 mb-4">
                Geben Sie Ihre E-Mail-Adresse ein. Wir senden Ihnen einen Link
                zum Zuruecksetzen Ihres Passworts.
              </p>

              <v-text-field
                v-model="email"
                label="E-Mail-Adresse"
                type="email"
                prepend-icon="mdi-email"
                :rules="[
                  v => !!v || 'E-Mail-Adresse erforderlich',
                  v => /.+@.+\..+/.test(v) || 'Ungueltige E-Mail-Adresse'
                ]"
                :disabled="loading"
                autofocus
              ></v-text-field>

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
                Link senden
              </v-btn>
            </v-form>
          </v-card-text>

          <v-card-actions class="justify-center">
            <router-link to="/login" class="text-caption">
              Zurueck zum Login
            </router-link>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'
import AppLogo from '@/components/AppLogo.vue'

const form = ref(null)
const email = ref('')
const loading = ref(false)
const error = ref('')
const submitted = ref(false)

async function submit() {
  const { valid } = await form.value.validate()
  if (!valid) return

  loading.value = true
  error.value = ''

  try {
    await axios.post('/api/auth/forgot-password', {
      email: email.value
    })
    submitted.value = true
  } catch (e) {
    if (e.response?.status === 429) {
      error.value = 'Zu viele Anfragen. Bitte warten Sie eine Minute.'
    } else {
      error.value = e.response?.data?.detail || 'Ein Fehler ist aufgetreten'
    }
  } finally {
    loading.value = false
  }
}
</script>
