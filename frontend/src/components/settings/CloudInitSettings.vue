<template>
  <v-card>
    <v-card-title class="pb-2">
      <v-icon start>mdi-cloud-cog</v-icon>
      Cloud-Init Konfiguration
    </v-card-title>
    <v-card-text class="pt-0">
      <v-row>
        <!-- SSH Authorized Keys -->
        <v-col cols="12" md="6">
          <div class="text-subtitle-2 mb-2">SSH Authorized Keys</div>
          <v-card variant="outlined" class="mb-0">
            <v-list density="compact" v-if="settings.ssh_authorized_keys?.length > 0" class="py-0">
              <v-list-item
                v-for="(key, index) in settings.ssh_authorized_keys"
                :key="index"
                density="compact"
              >
                <v-list-item-title class="text-caption font-monospace text-truncate">
                  {{ key }}
                </v-list-item-title>
                <template v-slot:append>
                  <v-btn icon size="x-small" variant="text" color="error" @click="removeKey(index)">
                    <v-icon size="16">mdi-delete</v-icon>
                  </v-btn>
                </template>
              </v-list-item>
            </v-list>
            <div v-else class="text-center text-grey pa-2 text-caption">Keine SSH Keys</div>
            <v-divider />
            <div class="pa-2">
              <v-btn variant="text" size="small" @click="showAddKeyDialog = true">
                <v-icon start size="small">mdi-key-plus</v-icon>
                Key hinzufuegen
              </v-btn>
            </div>
          </v-card>
        </v-col>

        <!-- Phone Home -->
        <v-col cols="12" md="6">
          <div class="text-subtitle-2 mb-2">Phone-Home</div>
          <v-switch
            v-model="settings.phone_home_enabled"
            label="Phone-Home aktivieren"
            density="compact"
            hide-details
            class="mb-2"
          />
          <v-text-field
            v-model="settings.phone_home_url"
            label="URL (optional)"
            placeholder="Auto-generiert wenn leer"
            variant="outlined"
            density="compact"
            :disabled="!settings.phone_home_enabled"
            hide-details
          />
        </v-col>
      </v-row>

      <v-row class="mt-2">
        <!-- Admin User -->
        <v-col cols="12" md="6">
          <div class="text-subtitle-2 mb-2">Admin-Benutzer</div>
          <v-row dense>
            <v-col cols="6">
              <v-text-field
                v-model="settings.admin_username"
                label="Benutzername"
                placeholder="ansible"
                variant="outlined"
                density="compact"
                hide-details
              />
            </v-col>
            <v-col cols="6">
              <v-text-field
                v-model="settings.admin_gecos"
                label="GECOS"
                placeholder="Ansible User"
                variant="outlined"
                density="compact"
                hide-details
              />
            </v-col>
          </v-row>
        </v-col>

        <!-- NAS Snippets -->
        <v-col cols="12" md="6">
          <div class="text-subtitle-2 mb-2">NAS Snippets</div>
          <v-row dense>
            <v-col cols="6">
              <v-text-field
                v-model="settings.nas_snippets_path"
                label="NAS Pfad"
                placeholder="/mnt/pve/nas/snippets"
                variant="outlined"
                density="compact"
                hide-details
              />
            </v-col>
            <v-col cols="6">
              <v-text-field
                v-model="settings.nas_snippets_ref"
                label="Storage Ref"
                placeholder="nas:snippets/"
                variant="outlined"
                density="compact"
                hide-details
              />
            </v-col>
          </v-row>
        </v-col>
      </v-row>
    </v-card-text>
    <v-card-actions class="pt-0">
      <v-spacer />
      <v-btn color="primary" :loading="saving" @click="saveSettings">
        Speichern
      </v-btn>
    </v-card-actions>
  </v-card>

  <!-- Add Key Dialog -->
  <v-dialog v-model="showAddKeyDialog" max-width="600">
    <v-card>
      <v-card-title>
        <v-icon start>mdi-key-plus</v-icon>
        SSH Public Key hinzufuegen
      </v-card-title>
      <v-card-text>
        <v-textarea
          v-model="newKey"
          label="SSH Public Key"
          placeholder="ssh-ed25519 AAAA... user@host"
          variant="outlined"
          rows="3"
          hint="Public Key im OpenSSH-Format einfuegen"
          persistent-hint
        />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="showAddKeyDialog = false">Abbrechen</v-btn>
        <v-btn
          color="primary"
          :disabled="!newKey.trim()"
          @click="addKey"
        >
          Hinzufuegen
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, onMounted, inject } from 'vue'
import api from '@/api/client'

const showSnackbar = inject('showSnackbar')

const loading = ref(false)
const saving = ref(false)
const showAddKeyDialog = ref(false)
const newKey = ref('')

const settings = ref({
  ssh_authorized_keys: [],
  phone_home_enabled: false,
  phone_home_url: '',
  admin_username: 'ansible',
  admin_gecos: 'Ansible User',
  nas_snippets_path: '',
  nas_snippets_ref: '',
})

async function loadSettings() {
  loading.value = true
  try {
    const response = await api.get('/api/cloud-init/settings')
    if (response.data) {
      settings.value = {
        ssh_authorized_keys: response.data.ssh_authorized_keys || [],
        phone_home_enabled: response.data.phone_home_enabled || false,
        phone_home_url: response.data.phone_home_url || '',
        admin_username: response.data.admin_username || 'ansible',
        admin_gecos: response.data.admin_gecos || 'Ansible User',
        nas_snippets_path: response.data.nas_snippets_path || '',
        nas_snippets_ref: response.data.nas_snippets_ref || '',
      }
    }
  } catch (e) {
    console.error('Cloud-Init Settings laden fehlgeschlagen:', e)
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  saving.value = true
  try {
    await api.put('/api/cloud-init/settings', settings.value)
    showSnackbar?.('Cloud-Init Einstellungen gespeichert', 'success')
  } catch (e) {
    showSnackbar?.('Speichern fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    saving.value = false
  }
}

function addKey() {
  if (newKey.value.trim()) {
    if (!settings.value.ssh_authorized_keys) {
      settings.value.ssh_authorized_keys = []
    }
    settings.value.ssh_authorized_keys.push(newKey.value.trim())
    newKey.value = ''
    showAddKeyDialog.value = false
  }
}

function removeKey(index) {
  settings.value.ssh_authorized_keys.splice(index, 1)
}

onMounted(() => {
  loadSettings()
})
</script>
