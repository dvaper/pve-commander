<template>
  <v-container class="fill-height" fluid>
    <v-row align="center" justify="center">
      <v-col cols="12" sm="8" md="5" lg="4">
        <v-card class="elevation-12">
          <!-- Logo Banner im Card-Header -->
          <div class="d-flex justify-center py-6 bg-surface">
            <AppLogo variant="banner" size="md" />
          </div>

          <v-divider></v-divider>
          <v-card-text class="pt-6">
            <v-form @submit.prevent="handleLogin">
              <v-text-field
                v-model="username"
                label="Benutzername"
                prepend-icon="mdi-account"
                type="text"
                :disabled="loading"
                autofocus
              ></v-text-field>

              <v-text-field
                v-model="password"
                label="Passwort"
                prepend-icon="mdi-lock"
                :type="showPassword ? 'text' : 'password'"
                :append-inner-icon="showPassword ? 'mdi-eye' : 'mdi-eye-off'"
                @click:append-inner="showPassword = !showPassword"
                :disabled="loading"
              ></v-text-field>

              <v-alert v-if="error" type="error" class="mb-4" variant="tonal">
                {{ error }}
              </v-alert>

              <v-btn
                type="submit"
                color="primary"
                block
                size="large"
                :loading="loading"
              >
                Anmelden
              </v-btn>
            </v-form>
          </v-card-text>

          <v-divider></v-divider>

          <v-card-actions class="justify-space-between px-4 py-3">
            <router-link to="/forgot-password" class="text-caption text-primary">
              Passwort vergessen?
            </router-link>
            <v-btn
              variant="text"
              size="small"
              color="secondary"
              @click="initAdmin"
              :disabled="loading"
            >
              Admin initialisieren
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppLogo from '@/components/AppLogo.vue'

const router = useRouter()
const authStore = useAuthStore()

const username = ref('')
const password = ref('')
const showPassword = ref(false)
const loading = ref(false)
const error = ref(null)

async function handleLogin() {
  if (!username.value || !password.value) {
    error.value = 'Bitte Benutzername und Passwort eingeben'
    return
  }

  loading.value = true
  error.value = null

  try {
    await authStore.login(username.value, password.value)
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Anmeldung fehlgeschlagen'
  } finally {
    loading.value = false
  }
}

async function initAdmin() {
  loading.value = true
  error.value = null

  try {
    await authStore.initAdmin()
    username.value = 'admin'
    password.value = 'admin'
    error.value = null
    alert('Admin-User erstellt: admin / admin\nBitte Passwort nach Login ändern!')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Initialisierung fehlgeschlagen'
  } finally {
    loading.value = false
  }
}
</script>
