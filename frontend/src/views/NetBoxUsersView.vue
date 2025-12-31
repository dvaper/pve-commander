<template>
  <v-container fluid class="pa-4">
    <v-row>
      <v-col cols="12" lg="10" xl="8">
        <!-- Header -->
        <div class="d-flex align-center mb-4">
          <v-icon size="32" color="primary" class="mr-3">mdi-account-network</v-icon>
          <div>
            <h1 class="text-h5">NetBox-Benutzer</h1>
            <p class="text-body-2 text-grey mb-0">
              Verwalte Benutzer fuer die NetBox IPAM/DCIM Integration
            </p>
          </div>
          <v-spacer></v-spacer>
          <v-btn
            variant="outlined"
            class="mr-2"
            :loading="syncingAdmin"
            @click="syncAdminUser"
          >
            <v-icon start>mdi-sync</v-icon>
            Admin synchronisieren
            <v-tooltip activator="parent" location="bottom">
              Synchronisiert den NetBox-Admin mit den Setup-Wizard Credentials
            </v-tooltip>
          </v-btn>
          <v-btn
            color="primary"
            @click="openCreateDialog"
          >
            <v-icon start>mdi-account-plus</v-icon>
            Neuer Benutzer
          </v-btn>
        </div>

        <!-- Ladezustand -->
        <v-card v-if="loading" class="pa-8 text-center">
          <v-progress-circular indeterminate color="primary" size="48"></v-progress-circular>
          <p class="mt-4 text-grey">Lade Benutzer...</p>
        </v-card>

        <!-- NetBox nicht verfuegbar -->
        <v-alert v-else-if="netboxError" type="warning" variant="tonal" class="mb-4">
          <v-icon start>mdi-alert</v-icon>
          <strong>NetBox nicht erreichbar:</strong> {{ netboxError }}
          <br>
          <span class="text-body-2">Stelle sicher, dass der NetBox-Container laeuft.</span>
        </v-alert>

        <!-- Benutzer-Tabelle -->
        <v-card v-else>
          <v-card-title class="d-flex align-center">
            <v-icon start>mdi-account-group</v-icon>
            Benutzer ({{ users.length }})
            <v-spacer></v-spacer>
            <v-btn
              icon
              variant="text"
              size="small"
              @click="loadUsers"
              :loading="loading"
            >
              <v-icon>mdi-refresh</v-icon>
              <v-tooltip activator="parent" location="top">Aktualisieren</v-tooltip>
            </v-btn>
          </v-card-title>

          <v-table>
            <thead>
              <tr>
                <th>Benutzername</th>
                <th>E-Mail</th>
                <th>Status</th>
                <th>Superuser</th>
                <th class="text-right">Aktionen</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="users.length === 0">
                <td colspan="5" class="text-center text-grey pa-4">
                  Keine Benutzer gefunden
                </td>
              </tr>
              <tr v-for="user in users" :key="user.id">
                <td>
                  <v-icon start size="small" :color="user.is_superuser ? 'warning' : 'grey'">
                    {{ user.is_superuser ? 'mdi-shield-crown' : 'mdi-account' }}
                  </v-icon>
                  {{ user.username }}
                </td>
                <td>{{ user.email || '-' }}</td>
                <td>
                  <v-chip
                    :color="user.is_active ? 'success' : 'grey'"
                    size="small"
                    variant="tonal"
                  >
                    {{ user.is_active ? 'Aktiv' : 'Inaktiv' }}
                  </v-chip>
                </td>
                <td>
                  <v-chip
                    v-if="user.is_superuser"
                    color="warning"
                    size="small"
                    variant="tonal"
                  >
                    <v-icon start size="small">mdi-shield-crown</v-icon>
                    Superuser
                  </v-chip>
                  <span v-else class="text-grey">-</span>
                </td>
                <td class="text-right">
                  <v-btn
                    icon
                    variant="text"
                    size="small"
                    color="primary"
                    @click="openEditDialog(user)"
                  >
                    <v-icon>mdi-pencil</v-icon>
                    <v-tooltip activator="parent" location="top">Bearbeiten</v-tooltip>
                  </v-btn>
                  <v-btn
                    icon
                    variant="text"
                    size="small"
                    color="warning"
                    @click="openPasswordDialog(user)"
                  >
                    <v-icon>mdi-key</v-icon>
                    <v-tooltip activator="parent" location="top">Passwort aendern</v-tooltip>
                  </v-btn>
                  <v-btn
                    icon
                    variant="text"
                    size="small"
                    color="error"
                    :disabled="user.is_superuser && superuserCount <= 1"
                    @click="confirmDelete(user)"
                  >
                    <v-icon>mdi-delete</v-icon>
                    <v-tooltip activator="parent" location="top">
                      {{ user.is_superuser && superuserCount <= 1 ? 'Letzter Superuser' : 'Loeschen' }}
                    </v-tooltip>
                  </v-btn>
                </td>
              </tr>
            </tbody>
          </v-table>
        </v-card>

        <!-- Hinweis-Karte -->
        <v-card class="mt-4">
          <v-card-title>
            <v-icon start>mdi-information</v-icon>
            Hinweise
          </v-card-title>
          <v-card-text>
            <v-alert type="info" variant="tonal" density="compact" class="mb-2">
              <strong>NetBox-Benutzer</strong> werden fuer den direkten Zugriff auf die NetBox Web-UI verwendet.
              PVE Commander kommuniziert ueber einen API-Token mit NetBox.
            </v-alert>
            <v-alert type="warning" variant="tonal" density="compact">
              <strong>Mindestens ein Superuser</strong> muss immer vorhanden sein.
              Der letzte Superuser kann nicht geloescht werden.
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Create/Edit Dialog -->
    <v-dialog v-model="userDialog" max-width="500" persistent>
      <v-card>
        <v-card-title>
          <v-icon start>{{ editMode ? 'mdi-account-edit' : 'mdi-account-plus' }}</v-icon>
          {{ editMode ? 'Benutzer bearbeiten' : 'Neuer Benutzer' }}
        </v-card-title>

        <v-card-text>
          <v-text-field
            v-model="userForm.username"
            label="Benutzername"
            prepend-inner-icon="mdi-account"
            variant="outlined"
            density="compact"
            class="mb-4"
            :disabled="editMode"
            :rules="[v => !!v || 'Benutzername erforderlich']"
          ></v-text-field>

          <v-text-field
            v-model="userForm.email"
            label="E-Mail"
            prepend-inner-icon="mdi-email"
            variant="outlined"
            density="compact"
            class="mb-4"
          ></v-text-field>

          <v-text-field
            v-if="!editMode"
            v-model="userForm.password"
            label="Passwort"
            prepend-inner-icon="mdi-lock"
            :type="showPassword ? 'text' : 'password'"
            :append-inner-icon="showPassword ? 'mdi-eye' : 'mdi-eye-off'"
            @click:append-inner="showPassword = !showPassword"
            variant="outlined"
            density="compact"
            class="mb-4"
            :rules="[v => !!v || 'Passwort erforderlich', v => (v && v.length >= 4) || 'Min. 4 Zeichen']"
          ></v-text-field>

          <v-checkbox
            v-model="userForm.is_superuser"
            label="Superuser (Administrator)"
            hint="Superuser haben vollen Zugriff auf NetBox"
            persistent-hint
            density="compact"
            class="mb-4"
          ></v-checkbox>

          <v-checkbox
            v-model="userForm.is_active"
            label="Aktiv"
            hint="Inaktive Benutzer koennen sich nicht anmelden"
            persistent-hint
            density="compact"
          ></v-checkbox>
        </v-card-text>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="userDialog = false">Abbrechen</v-btn>
          <v-btn
            color="primary"
            :loading="saving"
            @click="saveUser"
          >
            {{ editMode ? 'Speichern' : 'Erstellen' }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Password Dialog -->
    <v-dialog v-model="passwordDialog" max-width="400" persistent>
      <v-card>
        <v-card-title>
          <v-icon start>mdi-key</v-icon>
          Passwort aendern
        </v-card-title>

        <v-card-text>
          <p class="mb-4">
            Neues Passwort fuer <strong>{{ selectedUser?.username }}</strong>:
          </p>

          <v-text-field
            v-model="newPassword"
            label="Neues Passwort"
            prepend-inner-icon="mdi-lock"
            :type="showNewPassword ? 'text' : 'password'"
            :append-inner-icon="showNewPassword ? 'mdi-eye' : 'mdi-eye-off'"
            @click:append-inner="showNewPassword = !showNewPassword"
            variant="outlined"
            density="compact"
            :rules="[v => !!v || 'Passwort erforderlich', v => (v && v.length >= 4) || 'Min. 4 Zeichen']"
          ></v-text-field>
        </v-card-text>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="passwordDialog = false">Abbrechen</v-btn>
          <v-btn
            color="primary"
            :loading="saving"
            :disabled="!newPassword || newPassword.length < 4"
            @click="changePassword"
          >
            Passwort aendern
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirmation Dialog -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-card-title class="text-error">
          <v-icon start color="error">mdi-alert</v-icon>
          Benutzer loeschen
        </v-card-title>

        <v-card-text>
          <p>
            Moechtest du den Benutzer <strong>{{ selectedUser?.username }}</strong> wirklich loeschen?
          </p>
          <p class="text-grey">
            Diese Aktion kann nicht rueckgaengig gemacht werden.
          </p>
        </v-card-text>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="deleteDialog = false">Abbrechen</v-btn>
          <v-btn
            color="error"
            :loading="deleting"
            @click="deleteUser"
          >
            Loeschen
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

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
const deleting = ref(false)
const syncingAdmin = ref(false)
const users = ref([])
const netboxError = ref(null)

// Dialogs
const userDialog = ref(false)
const passwordDialog = ref(false)
const deleteDialog = ref(false)
const editMode = ref(false)
const selectedUser = ref(null)

// Forms
const userForm = ref({
  username: '',
  email: '',
  password: '',
  is_superuser: false,
  is_active: true,
})
const newPassword = ref('')
const showPassword = ref(false)
const showNewPassword = ref(false)

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

// Computed
const superuserCount = computed(() => {
  return users.value.filter(u => u.is_superuser).length
})

// Methods
async function loadUsers() {
  loading.value = true
  netboxError.value = null

  try {
    const response = await api.get('/api/settings/netbox-users')
    users.value = response.data
  } catch (e) {
    netboxError.value = e.response?.data?.detail || e.message
    users.value = []
  } finally {
    loading.value = false
  }
}

async function syncAdminUser() {
  syncingAdmin.value = true
  try {
    const response = await api.post('/api/settings/netbox-users/sync-admin')
    showMessage(response.data.message || 'Admin synchronisiert')
    await loadUsers()
  } catch (e) {
    const errorMsg = e.response?.data?.detail || 'Synchronisierung fehlgeschlagen'
    showMessage(errorMsg, 'error')
  } finally {
    syncingAdmin.value = false
  }
}

function openCreateDialog() {
  editMode.value = false
  selectedUser.value = null
  userForm.value = {
    username: '',
    email: '',
    password: '',
    is_superuser: false,
    is_active: true,
  }
  showPassword.value = false
  userDialog.value = true
}

function openEditDialog(user) {
  editMode.value = true
  selectedUser.value = user
  userForm.value = {
    username: user.username,
    email: user.email || '',
    password: '',
    is_superuser: user.is_superuser,
    is_active: user.is_active,
  }
  userDialog.value = true
}

function openPasswordDialog(user) {
  selectedUser.value = user
  newPassword.value = ''
  showNewPassword.value = false
  passwordDialog.value = true
}

function confirmDelete(user) {
  selectedUser.value = user
  deleteDialog.value = true
}

async function saveUser() {
  if (!userForm.value.username) {
    showMessage('Benutzername erforderlich', 'error')
    return
  }

  if (!editMode.value && (!userForm.value.password || userForm.value.password.length < 4)) {
    showMessage('Passwort erforderlich (min. 4 Zeichen)', 'error')
    return
  }

  saving.value = true
  try {
    if (editMode.value) {
      await api.put(`/api/settings/netbox-users/${selectedUser.value.id}`, {
        email: userForm.value.email,
        is_superuser: userForm.value.is_superuser,
        is_active: userForm.value.is_active,
      })
      showMessage('Benutzer aktualisiert')
    } else {
      await api.post('/api/settings/netbox-users', userForm.value)
      showMessage('Benutzer erstellt')
    }

    userDialog.value = false
    await loadUsers()
  } catch (e) {
    showMessage(e.response?.data?.detail || 'Speichern fehlgeschlagen', 'error')
  } finally {
    saving.value = false
  }
}

async function changePassword() {
  if (!newPassword.value || newPassword.value.length < 4) {
    showMessage('Passwort muss mindestens 4 Zeichen haben', 'error')
    return
  }

  saving.value = true
  try {
    await api.put(`/api/settings/netbox-users/${selectedUser.value.id}/password`, {
      password: newPassword.value,
    })

    passwordDialog.value = false
    showMessage('Passwort geaendert')
  } catch (e) {
    showMessage(e.response?.data?.detail || 'Passwort aendern fehlgeschlagen', 'error')
  } finally {
    saving.value = false
  }
}

async function deleteUser() {
  deleting.value = true
  try {
    await api.delete(`/api/settings/netbox-users/${selectedUser.value.id}`)

    deleteDialog.value = false
    showMessage('Benutzer geloescht')
    await loadUsers()
  } catch (e) {
    showMessage(e.response?.data?.detail || 'Loeschen fehlgeschlagen', 'error')
  } finally {
    deleting.value = false
  }
}

// Lifecycle
onMounted(() => {
  loadUsers()
})
</script>
