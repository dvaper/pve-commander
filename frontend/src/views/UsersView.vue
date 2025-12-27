<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon start>mdi-account-group</v-icon>
            Benutzerverwaltung ({{ usersStore.totalUsers }})
            <v-spacer></v-spacer>
            <v-btn
              color="primary"
              prepend-icon="mdi-plus"
              @click="openCreateDialog"
            >
              Neuer Benutzer
            </v-btn>
          </v-card-title>

          <v-text-field
            v-model="search"
            label="Benutzer suchen"
            prepend-inner-icon="mdi-magnify"
            variant="outlined"
            density="compact"
            hide-details
            class="mx-4 mb-2"
            @input="debouncedSearch"
          ></v-text-field>

          <v-data-table
            :headers="headers"
            :items="usersStore.users"
            :loading="usersStore.loading"
            :search="search"
            density="compact"
            class="elevation-0"
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

            <template v-slot:item.is_super_admin="{ item }">
              <v-chip
                size="small"
                :color="item.is_super_admin ? 'warning' : 'grey'"
              >
                {{ item.is_super_admin ? 'Super-Admin' : 'Benutzer' }}
              </v-chip>
            </template>

            <template v-slot:item.is_active="{ item }">
              <v-icon :color="item.is_active ? 'success' : 'error'">
                {{ item.is_active ? 'mdi-check-circle' : 'mdi-close-circle' }}
              </v-icon>
            </template>

            <template v-slot:item.created_at="{ item }">
              {{ formatDate(item.created_at) }}
            </template>

            <template v-slot:item.last_login="{ item }">
              {{ item.last_login ? formatDate(item.last_login) : '-' }}
            </template>

            <template v-slot:item.actions="{ item }">
              <div class="d-flex flex-nowrap">
                <v-btn
                  icon
                  size="small"
                  variant="text"
                  @click="openEditDialog(item)"
                >
                  <v-icon>mdi-pencil</v-icon>
                  <v-tooltip activator="parent">Bearbeiten</v-tooltip>
                </v-btn>
                <v-btn
                  icon
                  size="small"
                  variant="text"
                  @click="openResetPasswordDialog(item)"
                >
                  <v-icon>mdi-lock-reset</v-icon>
                  <v-tooltip activator="parent">Passwort zurücksetzen</v-tooltip>
                </v-btn>
                <v-btn
                  icon
                  size="small"
                  variant="text"
                  color="error"
                  :disabled="item.id === authStore.user?.id"
                  @click="confirmDelete(item)"
                >
                  <v-icon>mdi-delete</v-icon>
                  <v-tooltip activator="parent">Löschen</v-tooltip>
                </v-btn>
              </div>
            </template>
          </v-data-table>
        </v-card>
      </v-col>
    </v-row>

    <!-- Create/Edit Dialog -->
    <v-dialog v-model="editDialog" max-width="700" persistent>
      <v-card>
        <v-toolbar color="primary" dark flat>
          <v-toolbar-title>
            {{ editMode ? 'Benutzer bearbeiten' : 'Neuer Benutzer' }}
          </v-toolbar-title>
          <v-spacer></v-spacer>
          <v-btn icon @click="editDialog = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-toolbar>

        <v-card-text>
          <v-tabs v-model="editTab" bg-color="transparent">
            <v-tab value="details">Stammdaten</v-tab>
            <v-tab value="roles">Rollen</v-tab>
            <v-tab value="groups">Gruppen</v-tab>
            <v-tab value="playbooks">Playbooks</v-tab>
          </v-tabs>

          <v-window v-model="editTab" class="mt-4">
            <!-- Tab: Stammdaten -->
            <v-window-item value="details">
              <v-form ref="editForm" @submit.prevent="saveUser">
                <v-text-field
                  v-model="editData.username"
                  label="Benutzername"
                  :rules="[v => !!v || 'Pflichtfeld', v => v.length >= 3 || 'Min. 3 Zeichen']"
                  :disabled="editMode"
                  prepend-icon="mdi-account"
                ></v-text-field>

                <v-text-field
                  v-if="!editMode"
                  v-model="editData.password"
                  label="Passwort"
                  type="password"
                  :rules="[v => !!v || 'Pflichtfeld', v => v.length >= 8 || 'Min. 8 Zeichen']"
                  prepend-icon="mdi-lock"
                ></v-text-field>

                <v-text-field
                  v-model="editData.email"
                  label="E-Mail"
                  type="email"
                  prepend-icon="mdi-email"
                ></v-text-field>

                <v-switch
                  v-model="editData.is_super_admin"
                  label="Super-Admin"
                  color="warning"
                  hint="Super-Admins haben Vollzugriff auf alle Ressourcen"
                  persistent-hint
                ></v-switch>

                <v-switch
                  v-if="editMode"
                  v-model="editData.is_active"
                  label="Aktiv"
                  color="success"
                  hint="Deaktivierte Benutzer können sich nicht anmelden"
                  persistent-hint
                ></v-switch>
              </v-form>
            </v-window-item>

            <!-- Tab: Rollen -->
            <v-window-item value="roles">
              <v-alert v-if="editData.is_super_admin" type="info" variant="tonal" class="mb-4">
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
                :disabled="editData.is_super_admin"
                prepend-icon="mdi-shield-account"
              >
                <template #chip="{ props, item }">
                  <v-chip
                    v-bind="props"
                    :color="item.raw.is_system_role ? 'grey' : 'primary'"
                    variant="outlined"
                  >
                    <v-icon v-if="item.raw.is_super_admin" start size="x-small">mdi-crown</v-icon>
                    {{ item.raw.display_name }}
                  </v-chip>
                </template>
                <template #item="{ props, item }">
                  <v-list-item v-bind="props">
                    <template #prepend>
                      <v-icon v-if="item.raw.is_super_admin" color="warning">mdi-crown</v-icon>
                      <v-icon v-else-if="item.raw.is_system_role" color="grey">mdi-lock</v-icon>
                      <v-icon v-else color="primary">mdi-shield-account</v-icon>
                    </template>
                    <template #subtitle>
                      {{ item.raw.description || 'Keine Beschreibung' }}
                    </template>
                  </v-list-item>
                </template>
              </v-autocomplete>
            </v-window-item>

            <!-- Tab: Gruppen -->
            <v-window-item value="groups">
              <v-alert v-if="editData.is_super_admin" type="info" variant="tonal" class="mb-4">
                Super-Admins haben automatisch Zugriff auf alle Gruppen.
              </v-alert>

              <v-autocomplete
                v-model="selectedGroups"
                :items="availableGroups"
                label="Gruppen zuweisen"
                multiple
                chips
                closable-chips
                :disabled="editData.is_super_admin"
                prepend-icon="mdi-folder-multiple"
              ></v-autocomplete>
            </v-window-item>

            <!-- Tab: Playbooks -->
            <v-window-item value="playbooks">
              <v-alert v-if="editData.is_super_admin" type="info" variant="tonal" class="mb-4">
                Super-Admins haben automatisch Zugriff auf alle Playbooks.
              </v-alert>

              <v-autocomplete
                v-model="selectedPlaybooks"
                :items="availablePlaybooks"
                label="Playbooks zuweisen"
                multiple
                chips
                closable-chips
                :disabled="editData.is_super_admin"
                prepend-icon="mdi-script-text"
              ></v-autocomplete>
            </v-window-item>
          </v-window>
        </v-card-text>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn @click="editDialog = false">Abbrechen</v-btn>
          <v-btn color="primary" :loading="saving" @click="saveUser">
            Speichern
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Reset Password Dialog -->
    <v-dialog v-model="resetPasswordDialog" max-width="400">
      <v-card>
        <v-toolbar color="warning" dark flat>
          <v-toolbar-title>Passwort zurücksetzen</v-toolbar-title>
          <v-spacer></v-spacer>
          <v-btn icon @click="resetPasswordDialog = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-toolbar>

        <v-card-text>
          <p class="mb-4">
            Neues Passwort für <strong>{{ selectedUser?.username }}</strong> setzen:
          </p>
          <v-text-field
            v-model="newPassword"
            label="Neues Passwort"
            type="password"
            :rules="[v => !!v || 'Pflichtfeld', v => v.length >= 8 || 'Min. 8 Zeichen']"
            prepend-icon="mdi-lock"
          ></v-text-field>
        </v-card-text>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn @click="resetPasswordDialog = false">Abbrechen</v-btn>
          <v-btn color="warning" :loading="saving" @click="resetPassword">
            Zurücksetzen
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirm Dialog -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-toolbar color="error" dark flat>
          <v-toolbar-title>Benutzer löschen</v-toolbar-title>
        </v-toolbar>

        <v-card-text class="pt-4">
          <v-alert type="warning" variant="tonal" class="mb-4">
            Diese Aktion kann nicht rückgängig gemacht werden!
          </v-alert>
          <p>
            Möchten Sie den Benutzer <strong>{{ selectedUser?.username }}</strong> wirklich löschen?
          </p>
        </v-card-text>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn @click="deleteDialog = false">Abbrechen</v-btn>
          <v-btn color="error" :loading="saving" @click="deleteUser">
            Löschen
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, onMounted, inject } from 'vue'
import { useUsersStore } from '@/stores/users'
import { useAuthStore } from '@/stores/auth'
import { useRolesStore } from '@/stores/roles'
import api from '@/api/client'
import { formatDate } from '@/utils/formatting'

const usersStore = useUsersStore()
const authStore = useAuthStore()
const rolesStore = useRolesStore()
const showSnackbar = inject('showSnackbar')

const search = ref('')
const editDialog = ref(false)
const editMode = ref(false)
const editTab = ref('details')
const editForm = ref(null)
const editData = ref({})
const selectedUser = ref(null)
const selectedRoles = ref([])
const selectedGroups = ref([])
const selectedPlaybooks = ref([])
const availableRoles = ref([])
const availableGroups = ref([])
const availablePlaybooks = ref([])
const saving = ref(false)

const resetPasswordDialog = ref(false)
const newPassword = ref('')

const deleteDialog = ref(false)

const headers = [
  { title: 'Benutzername', key: 'username' },
  { title: 'E-Mail', key: 'email' },
  { title: 'Rolle', key: 'is_super_admin' },
  { title: 'Status', key: 'is_active', align: 'center' },
  { title: 'Erstellt', key: 'created_at' },
  { title: 'Letzter Login', key: 'last_login' },
  { title: 'Aktionen', key: 'actions', sortable: false, width: '140px' },
]

function debouncedSearch() {
  // Implement debounce if needed for server-side search
}

async function loadData() {
  await usersStore.fetchUsers()

  // Verfügbare Rollen, Gruppen und Playbooks laden
  try {
    const [rolesRes, groupsRes, playbooksRes] = await Promise.all([
      rolesStore.fetchRoles(),
      api.get('/api/inventory/groups'),
      api.get('/api/playbooks'),
    ])
    availableRoles.value = rolesRes || rolesStore.roles
    availableGroups.value = groupsRes.data.map(g => g.name)
    availablePlaybooks.value = playbooksRes.data.map(p => p.name)
  } catch (e) {
    console.error('Laden fehlgeschlagen:', e)
  }
}

function openCreateDialog() {
  editMode.value = false
  editTab.value = 'details'
  editData.value = {
    username: '',
    password: '',
    email: '',
    is_super_admin: false,
    is_active: true,
  }
  selectedRoles.value = []
  selectedGroups.value = []
  selectedPlaybooks.value = []
  editDialog.value = true
}

async function openEditDialog(user) {
  editMode.value = true
  editTab.value = 'details'
  selectedUser.value = user

  // Vollständige User-Daten und Rollen laden
  const [fullUser, userRoles] = await Promise.all([
    usersStore.fetchUser(user.id),
    api.get(`/api/users/${user.id}/roles`).catch(() => ({ data: { roles: [] } })),
  ])
  editData.value = {
    username: fullUser.username,
    email: fullUser.email,
    is_super_admin: fullUser.is_super_admin,
    is_active: fullUser.is_active,
  }
  selectedRoles.value = userRoles.data.roles?.map(r => r.id) || []
  selectedGroups.value = fullUser.accessible_groups || []
  selectedPlaybooks.value = fullUser.accessible_playbooks || []
  editDialog.value = true
}

async function saveUser() {
  saving.value = true
  try {
    if (editMode.value) {
      // Update
      await usersStore.updateUser(selectedUser.value.id, {
        email: editData.value.email,
        is_super_admin: editData.value.is_super_admin,
        is_active: editData.value.is_active,
      })

      // Rollen, Gruppen und Playbooks aktualisieren (nur wenn nicht Super-Admin)
      if (!editData.value.is_super_admin) {
        await syncUserRoles(selectedUser.value.id, selectedRoles.value)
        await usersStore.setUserGroups(selectedUser.value.id, selectedGroups.value)
        await usersStore.setUserPlaybooks(selectedUser.value.id, selectedPlaybooks.value)
      }

      showSnackbar('Benutzer erfolgreich aktualisiert')
    } else {
      // Create
      const newUser = await usersStore.createUser({
        username: editData.value.username,
        password: editData.value.password,
        email: editData.value.email,
        is_super_admin: editData.value.is_super_admin,
      })

      // Rollen, Gruppen und Playbooks setzen (nur wenn nicht Super-Admin)
      if (!editData.value.is_super_admin) {
        // Rollen zuweisen
        for (const roleId of selectedRoles.value) {
          await rolesStore.assignRoleToUser(newUser.id, roleId)
        }
        // Gruppen zuweisen
        if (selectedGroups.value.length) {
          await usersStore.setUserGroups(newUser.id, selectedGroups.value)
        }
        // Playbooks zuweisen
        if (selectedPlaybooks.value.length) {
          await usersStore.setUserPlaybooks(newUser.id, selectedPlaybooks.value)
        }
      }

      showSnackbar('Benutzer erfolgreich erstellt')
    }

    editDialog.value = false
    await loadData()
  } catch (e) {
    showSnackbar(e.response?.data?.detail || 'Fehler beim Speichern', 'error')
  } finally {
    saving.value = false
  }
}

async function syncUserRoles(userId, newRoleIds) {
  // Aktuelle Rollen holen
  const currentRolesRes = await api.get(`/api/users/${userId}/roles`).catch(() => ({ data: { roles: [] } }))
  const currentRoleIds = currentRolesRes.data.roles?.map(r => r.id) || []

  // Zu entfernende Rollen
  const toRemove = currentRoleIds.filter(id => !newRoleIds.includes(id))
  // Hinzuzufuegende Rollen
  const toAdd = newRoleIds.filter(id => !currentRoleIds.includes(id))

  // Rollen entfernen
  for (const roleId of toRemove) {
    await rolesStore.removeRoleFromUser(userId, roleId)
  }
  // Rollen hinzufuegen
  for (const roleId of toAdd) {
    await rolesStore.assignRoleToUser(userId, roleId)
  }
}

function openResetPasswordDialog(user) {
  selectedUser.value = user
  newPassword.value = ''
  resetPasswordDialog.value = true
}

async function resetPassword() {
  if (!newPassword.value || newPassword.value.length < 8) {
    showSnackbar('Passwort muss mindestens 8 Zeichen haben', 'error')
    return
  }

  saving.value = true
  try {
    await usersStore.resetPassword(selectedUser.value.id, newPassword.value)
    showSnackbar('Passwort erfolgreich zurückgesetzt')
    resetPasswordDialog.value = false
  } catch (e) {
    showSnackbar(e.response?.data?.detail || 'Fehler beim Zurücksetzen', 'error')
  } finally {
    saving.value = false
  }
}

function confirmDelete(user) {
  selectedUser.value = user
  deleteDialog.value = true
}

async function deleteUser() {
  saving.value = true
  try {
    await usersStore.deleteUser(selectedUser.value.id)
    showSnackbar('Benutzer erfolgreich gelöscht')
    deleteDialog.value = false
  } catch (e) {
    showSnackbar(e.response?.data?.detail || 'Fehler beim Löschen', 'error')
  } finally {
    saving.value = false
  }
}

onMounted(loadData)
</script>
