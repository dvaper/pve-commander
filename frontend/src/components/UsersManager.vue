<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-account-group</v-icon>
      Benutzer ({{ users.length }})
      <v-spacer />
      <v-btn color="primary" size="small" @click="openCreate">
        <v-icon start>mdi-plus</v-icon>
        Neuer Benutzer
      </v-btn>
    </v-card-title>

    <v-text-field
      v-model="search"
      label="Suchen..."
      prepend-inner-icon="mdi-magnify"
      variant="outlined"
      density="compact"
      hide-details
      class="mx-4 mb-2"
    />

    <v-data-table
      :headers="headers"
      :items="users"
      :loading="loading"
      :search="search"
      density="compact"
    >
      <template v-slot:item.username="{ item }">
        <v-chip
          size="small"
          :color="item.is_super_admin ? 'warning' : 'primary'"
          variant="outlined"
        >
          <v-icon start size="x-small">
            {{ item.is_super_admin ? 'mdi-shield-crown' : 'mdi-account' }}
          </v-icon>
          {{ item.username }}
        </v-chip>
      </template>

      <template v-slot:item.is_active="{ item }">
        <v-icon :color="item.is_active ? 'success' : 'error'" size="small">
          {{ item.is_active ? 'mdi-check-circle' : 'mdi-close-circle' }}
        </v-icon>
      </template>

      <template v-slot:item.created_at="{ item }">
        <span class="text-caption">{{ formatDate(item.created_at) }}</span>
      </template>

      <template v-slot:item.actions="{ item }">
        <div style="white-space: nowrap">
          <v-btn icon size="x-small" variant="text" @click="openEdit(item)" title="Bearbeiten">
            <v-icon>mdi-pencil</v-icon>
          </v-btn>
          <v-btn icon size="x-small" variant="text" @click="openResetPassword(item)" title="Passwort">
            <v-icon>mdi-lock-reset</v-icon>
          </v-btn>
          <v-btn
            icon
            size="x-small"
            variant="text"
            color="error"
            :disabled="item.id === currentUserId"
            @click="confirmDelete(item)"
            title="Loeschen"
          >
            <v-icon>mdi-delete</v-icon>
          </v-btn>
        </div>
      </template>
    </v-data-table>

    <!-- Edit Dialog mit Tabs -->
    <v-dialog v-model="dialog" max-width="700" persistent>
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon start>mdi-account</v-icon>
          {{ editMode ? 'Benutzer bearbeiten' : 'Neuer Benutzer' }}
          <v-spacer />
          <v-chip v-if="editMode && form.is_super_admin" size="small" color="warning" variant="tonal">
            <v-icon start size="x-small">mdi-shield-crown</v-icon>
            Super-Admin
          </v-chip>
        </v-card-title>

        <v-tabs v-model="dialogTab" density="compact" class="px-4">
          <v-tab value="details">Stammdaten</v-tab>
          <v-tab value="roles" :disabled="!editMode">Rollen</v-tab>
          <v-tab value="groups" :disabled="!editMode">Gruppen</v-tab>
          <v-tab value="hosts" :disabled="!editMode">Hosts</v-tab>
          <v-tab value="playbooks" :disabled="!editMode">Playbooks</v-tab>
        </v-tabs>

        <v-alert
          v-if="!editMode"
          type="info"
          variant="tonal"
          density="compact"
          class="mx-4 mt-2"
        >
          Zuweisungen (Rollen, Gruppen, Hosts, Playbooks) nach dem Erstellen bearbeitbar.
        </v-alert>

        <v-card-text style="min-height: 280px;">
          <v-tabs-window v-model="dialogTab">
            <!-- Tab: Stammdaten -->
            <v-tabs-window-item value="details">
              <v-text-field
                v-model="form.username"
                label="Benutzername"
                :disabled="editMode"
                variant="outlined"
                density="compact"
                class="mb-2"
              />
              <v-text-field
                v-if="!editMode"
                v-model="form.password"
                label="Passwort"
                type="password"
                variant="outlined"
                density="compact"
                class="mb-2"
              />
              <v-text-field
                v-model="form.email"
                label="E-Mail"
                type="email"
                variant="outlined"
                density="compact"
                class="mb-2"
              />
              <v-switch
                v-model="form.is_super_admin"
                label="Super-Admin (Vollzugriff)"
                color="warning"
                density="compact"
                hide-details
                class="mb-2"
              />
              <v-switch
                v-if="editMode"
                v-model="form.is_active"
                label="Aktiv"
                color="success"
                density="compact"
                hide-details
              />
            </v-tabs-window-item>

            <!-- Tab: Rollen -->
            <v-tabs-window-item value="roles">
              <v-alert v-if="form.is_super_admin" type="warning" variant="tonal" density="compact" class="mb-3">
                Super-Admins haben automatisch alle Berechtigungen.
              </v-alert>
              <v-autocomplete
                v-model="selectedRoles"
                :items="availableRoles"
                item-title="display_name"
                item-value="id"
                label="Rollen zuweisen"
                multiple
                chips
                closable-chips
                :disabled="form.is_super_admin"
                variant="outlined"
                density="compact"
              >
                <template #chip="{ props, item }">
                  <v-chip v-bind="props" size="small" :color="item.raw.is_system_role ? 'grey' : 'primary'" variant="outlined">
                    {{ item.raw.display_name }}
                  </v-chip>
                </template>
              </v-autocomplete>
            </v-tabs-window-item>

            <!-- Tab: Gruppen -->
            <v-tabs-window-item value="groups">
              <v-alert v-if="form.is_super_admin" type="warning" variant="tonal" density="compact" class="mb-3">
                Super-Admins haben Zugriff auf alle Gruppen.
              </v-alert>
              <v-autocomplete
                v-model="selectedGroups"
                :items="availableGroups"
                label="Inventory-Gruppen zuweisen"
                multiple
                chips
                closable-chips
                :disabled="form.is_super_admin"
                variant="outlined"
                density="compact"
              />
            </v-tabs-window-item>

            <!-- Tab: Hosts -->
            <v-tabs-window-item value="hosts">
              <v-alert v-if="form.is_super_admin" type="warning" variant="tonal" density="compact" class="mb-3">
                Super-Admins haben Zugriff auf alle Hosts.
              </v-alert>
              <v-autocomplete
                v-model="selectedHosts"
                :items="availableHosts"
                label="Einzelne Hosts zuweisen"
                multiple
                chips
                closable-chips
                :disabled="form.is_super_admin"
                variant="outlined"
                density="compact"
              />
              <v-alert type="info" variant="tonal" density="compact" class="mt-2">
                Hosts aus zugewiesenen Gruppen sind automatisch zugaenglich.
              </v-alert>
            </v-tabs-window-item>

            <!-- Tab: Playbooks -->
            <v-tabs-window-item value="playbooks">
              <v-alert v-if="form.is_super_admin" type="warning" variant="tonal" density="compact" class="mb-3">
                Super-Admins haben Zugriff auf alle Playbooks.
              </v-alert>
              <v-autocomplete
                v-model="selectedPlaybooks"
                :items="availablePlaybooks"
                label="Playbooks zuweisen"
                multiple
                chips
                closable-chips
                :disabled="form.is_super_admin"
                variant="outlined"
                density="compact"
              />
            </v-tabs-window-item>
          </v-tabs-window>
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="dialog = false">Abbrechen</v-btn>
          <v-btn color="primary" :loading="saving" @click="save">
            {{ editMode ? 'Speichern' : 'Erstellen' }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Reset Password Dialog -->
    <v-dialog v-model="resetPasswordDialog" max-width="400">
      <v-card>
        <v-card-title>Passwort zuruecksetzen</v-card-title>
        <v-card-text>
          <p class="mb-3">Neues Passwort fuer <strong>{{ selectedUser?.username }}</strong>:</p>
          <v-text-field
            v-model="newPassword"
            label="Neues Passwort"
            type="password"
            variant="outlined"
            density="compact"
            hint="Mindestens 8 Zeichen"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="resetPasswordDialog = false">Abbrechen</v-btn>
          <v-btn color="warning" :loading="saving" @click="resetPassword">Zuruecksetzen</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Dialog -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-card-title>Benutzer loeschen</v-card-title>
        <v-card-text>
          <v-alert type="warning" variant="tonal" density="compact" class="mb-2">
            Diese Aktion kann nicht rueckgaengig gemacht werden!
          </v-alert>
          Benutzer <strong>{{ selectedUser?.username }}</strong> wirklich loeschen?
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">Abbrechen</v-btn>
          <v-btn color="error" :loading="deleting" @click="deleteUser">Loeschen</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { ref, onMounted, inject } from 'vue'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useUsersStore } from '@/stores/users'
import { useRolesStore } from '@/stores/roles'

const authStore = useAuthStore()
const usersStore = useUsersStore()
const rolesStore = useRolesStore()
const showSnackbar = inject('showSnackbar')

const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const users = ref([])
const search = ref('')
const dialog = ref(false)
const dialogTab = ref('details')
const deleteDialog = ref(false)
const resetPasswordDialog = ref(false)
const editMode = ref(false)
const selectedUser = ref(null)
const newPassword = ref('')
const currentUserId = authStore.user?.id

// Zuweisungen
const selectedRoles = ref([])
const selectedGroups = ref([])
const selectedHosts = ref([])
const selectedPlaybooks = ref([])
const availableRoles = ref([])
const availableGroups = ref([])
const availableHosts = ref([])
const availablePlaybooks = ref([])

const form = ref({
  username: '',
  password: '',
  email: '',
  is_super_admin: false,
  is_active: true,
})

const headers = [
  { title: 'Benutzer', key: 'username' },
  { title: 'E-Mail', key: 'email' },
  { title: 'Aktiv', key: 'is_active', width: '70px' },
  { title: 'Erstellt', key: 'created_at', width: '100px' },
  { title: '', key: 'actions', width: '100px', sortable: false },
]

function formatDate(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('de-DE')
}

async function loadUsers() {
  loading.value = true
  try {
    const response = await api.get('/api/users')
    users.value = response.data.items || response.data
  } catch (e) {
    console.error('Laden fehlgeschlagen:', e)
  } finally {
    loading.value = false
  }
}

async function loadAvailableData() {
  try {
    const [rolesRes, groupsRes, hostsRes, playbooksRes] = await Promise.all([
      rolesStore.fetchRoles(),
      api.get('/api/inventory/groups'),
      api.get('/api/inventory/hosts'),
      api.get('/api/playbooks'),
    ])
    availableRoles.value = rolesRes || rolesStore.roles
    availableGroups.value = groupsRes.data.map(g => g.name)
    availableHosts.value = hostsRes.data.map(h => h.name || h.hostname)
    availablePlaybooks.value = playbooksRes.data.map(p => p.name)
  } catch (e) {
    console.error('Laden der verfuegbaren Daten fehlgeschlagen:', e)
  }
}

function openCreate() {
  editMode.value = false
  dialogTab.value = 'details'
  form.value = { username: '', password: '', email: '', is_super_admin: false, is_active: true }
  selectedRoles.value = []
  selectedGroups.value = []
  selectedHosts.value = []
  selectedPlaybooks.value = []
  dialog.value = true
}

async function openEdit(user) {
  editMode.value = true
  dialogTab.value = 'details'
  selectedUser.value = user

  form.value = {
    username: user.username,
    password: '',
    email: user.email || '',
    is_super_admin: user.is_super_admin,
    is_active: user.is_active,
  }

  // Vollstaendige User-Daten laden
  try {
    const [fullUser, userRoles] = await Promise.all([
      usersStore.fetchUser(user.id),
      api.get(`/api/users/${user.id}/roles`).catch(() => ({ data: { roles: [] } })),
    ])

    selectedRoles.value = userRoles.data.roles?.map(r => r.role_id) || []
    selectedGroups.value = fullUser.accessible_groups || []
    selectedHosts.value = fullUser.accessible_hosts || []
    selectedPlaybooks.value = fullUser.accessible_playbooks || []
  } catch (e) {
    console.error('Laden der Benutzerdaten fehlgeschlagen:', e)
  }

  dialog.value = true
}

async function save() {
  saving.value = true
  try {
    let userId

    if (editMode.value) {
      await api.put(`/api/users/${selectedUser.value.id}`, {
        email: form.value.email,
        is_super_admin: form.value.is_super_admin,
        is_active: form.value.is_active,
      })
      userId = selectedUser.value.id

      // Zuweisungen speichern (nur wenn nicht Super-Admin)
      if (!form.value.is_super_admin) {
        await syncUserRoles(userId, selectedRoles.value)
        await usersStore.setUserGroups(userId, selectedGroups.value)
        await usersStore.setUserHosts(userId, selectedHosts.value)
        await usersStore.setUserPlaybooks(userId, selectedPlaybooks.value)
      }

      showSnackbar?.('Benutzer aktualisiert', 'success')
    } else {
      const newUser = await usersStore.createUser(form.value)
      userId = newUser.id

      // Zuweisungen fuer neuen Benutzer (nur wenn nicht Super-Admin)
      if (!form.value.is_super_admin) {
        for (const roleId of selectedRoles.value) {
          await rolesStore.assignRoleToUser(userId, roleId)
        }
        if (selectedGroups.value.length) {
          await usersStore.setUserGroups(userId, selectedGroups.value)
        }
        if (selectedHosts.value.length) {
          await usersStore.setUserHosts(userId, selectedHosts.value)
        }
        if (selectedPlaybooks.value.length) {
          await usersStore.setUserPlaybooks(userId, selectedPlaybooks.value)
        }
      }

      showSnackbar?.('Benutzer erstellt', 'success')
    }

    dialog.value = false
    loadUsers()
  } catch (e) {
    showSnackbar?.('Fehler: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    saving.value = false
  }
}

async function syncUserRoles(userId, newRoleIds) {
  const currentRolesRes = await api.get(`/api/users/${userId}/roles`).catch(() => ({ data: { roles: [] } }))
  const currentRoleIds = currentRolesRes.data.roles?.map(r => r.role_id) || []

  const toRemove = currentRoleIds.filter(id => !newRoleIds.includes(id))
  const toAdd = newRoleIds.filter(id => !currentRoleIds.includes(id))

  for (const roleId of toRemove) {
    await rolesStore.removeRoleFromUser(userId, roleId)
  }
  for (const roleId of toAdd) {
    await rolesStore.assignRoleToUser(userId, roleId)
  }
}

function openResetPassword(user) {
  selectedUser.value = user
  newPassword.value = ''
  resetPasswordDialog.value = true
}

async function resetPassword() {
  if (!newPassword.value || newPassword.value.length < 8) {
    showSnackbar?.('Passwort muss mindestens 8 Zeichen haben', 'error')
    return
  }

  saving.value = true
  try {
    await usersStore.resetPassword(selectedUser.value.id, newPassword.value)
    showSnackbar?.('Passwort zurueckgesetzt', 'success')
    resetPasswordDialog.value = false
  } catch (e) {
    showSnackbar?.('Fehler: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    saving.value = false
  }
}

function confirmDelete(user) {
  selectedUser.value = user
  deleteDialog.value = true
}

async function deleteUser() {
  deleting.value = true
  try {
    await api.delete(`/api/users/${selectedUser.value.id}`)
    showSnackbar?.('Benutzer geloescht', 'success')
    deleteDialog.value = false
    loadUsers()
  } catch (e) {
    showSnackbar?.('Fehler: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    deleting.value = false
  }
}

onMounted(async () => {
  await Promise.all([
    loadUsers(),
    loadAvailableData(),
  ])
})
</script>
