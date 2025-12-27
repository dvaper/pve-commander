<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-shield-account</v-icon>
      Rollen ({{ rolesStore.roles.length }})
      <v-spacer />
      <v-btn color="primary" size="small" @click="openCreateDialog">
        <v-icon start>mdi-plus</v-icon>
        Neue Rolle
      </v-btn>
    </v-card-title>

    <v-data-table
      :headers="headers"
      :items="rolesStore.roles"
      :loading="rolesStore.loading"
      density="compact"
      :items-per-page="10"
    >
      <template #item.name="{ item }">
        <div class="d-flex align-center" style="white-space: nowrap">
          <v-icon
            v-if="item.is_super_admin"
            color="warning"
            size="x-small"
            class="mr-1"
          >mdi-crown</v-icon>
          <v-icon
            v-else-if="item.is_system_role"
            color="grey"
            size="x-small"
            class="mr-1"
          >mdi-lock</v-icon>
          <span>{{ item.display_name }}</span>
        </div>
      </template>

      <template #item.users_count="{ item }">
        <v-chip size="x-small" variant="tonal">{{ item.users_count || 0 }}</v-chip>
      </template>

      <template #item.actions="{ item }">
        <div style="white-space: nowrap">
          <v-btn icon size="x-small" variant="text" @click="openEditDialog(item)" title="Bearbeiten">
            <v-icon size="small">mdi-pencil</v-icon>
          </v-btn>
          <v-btn icon size="x-small" variant="text" color="error" :disabled="item.is_system_role" @click="confirmDelete(item)" title="Loeschen">
            <v-icon size="small">mdi-delete</v-icon>
          </v-btn>
        </div>
      </template>
    </v-data-table>

    <!-- Create/Edit Dialog mit Tabs -->
    <v-dialog v-model="roleDialog" max-width="700" persistent>
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon start>mdi-shield-account</v-icon>
          {{ editingRole ? 'Rolle bearbeiten' : 'Neue Rolle' }}
          <v-spacer />
          <v-chip v-if="editingRole?.is_super_admin" size="small" color="warning" variant="tonal">
            <v-icon start size="x-small">mdi-crown</v-icon>
            Super-Admin
          </v-chip>
          <v-chip v-else-if="editingRole?.is_system_role" size="small" color="grey" variant="tonal">
            <v-icon start size="x-small">mdi-lock</v-icon>
            System
          </v-chip>
        </v-card-title>

        <v-tabs v-model="dialogTab" density="compact" class="px-4">
          <v-tab value="details">Stammdaten</v-tab>
          <v-tab value="permissions">Berechtigungen</v-tab>
        </v-tabs>

        <v-card-text style="min-height: 300px;">
          <v-tabs-window v-model="dialogTab">
            <!-- Tab: Stammdaten -->
            <v-tabs-window-item value="details">
              <v-text-field
                v-model="roleFormData.name"
                label="Technischer Name"
                :disabled="!!editingRole"
                variant="outlined"
                density="compact"
                class="mb-2"
                hint="Eindeutiger Bezeichner (z.B. vm_operator)"
              />
              <v-text-field
                v-model="roleFormData.display_name"
                label="Anzeigename"
                variant="outlined"
                density="compact"
                class="mb-2"
                :disabled="editingRole?.is_system_role"
              />
              <v-textarea
                v-model="roleFormData.description"
                label="Beschreibung"
                variant="outlined"
                density="compact"
                rows="2"
                class="mb-2"
                :disabled="editingRole?.is_system_role"
              />
              <v-text-field
                v-model.number="roleFormData.priority"
                label="Prioritaet"
                type="number"
                variant="outlined"
                density="compact"
                hint="Hoehere Prioritaet = mehr Gewicht bei Konflikten"
                :disabled="editingRole?.is_system_role"
              />
            </v-tabs-window-item>

            <!-- Tab: Berechtigungen -->
            <v-tabs-window-item value="permissions">
              <v-alert
                v-if="editingRole?.is_super_admin"
                type="warning"
                variant="tonal"
                density="compact"
                class="mb-3"
              >
                <v-icon start size="small">mdi-crown</v-icon>
                Super-Admins haben automatisch ALLE Berechtigungen.
              </v-alert>

              <v-alert
                v-else-if="editingRole?.is_system_role"
                type="info"
                variant="tonal"
                density="compact"
                class="mb-3"
              >
                <v-icon start size="small">mdi-lock</v-icon>
                Systemrollen koennen nicht geaendert werden.
              </v-alert>

              <div class="d-flex gap-2 mb-3">
                <v-btn
                  size="x-small"
                  variant="outlined"
                  @click="selectAllPermissions"
                  :disabled="editingRole?.is_system_role"
                >
                  Alle
                </v-btn>
                <v-btn
                  size="x-small"
                  variant="outlined"
                  @click="selectedPermissions = []"
                  :disabled="editingRole?.is_system_role"
                >
                  Keine
                </v-btn>
              </div>

              <div style="max-height: 280px; overflow-y: auto;">
                <div v-for="(perms, resource) in rolesStore.permissionsByResource" :key="resource" class="mb-3">
                  <div class="text-subtitle-2 font-weight-bold mb-1 text-capitalize d-flex align-center">
                    <v-icon size="small" class="mr-1">{{ getResourceIcon(resource) }}</v-icon>
                    {{ resource }}
                    <v-btn
                      size="x-small"
                      variant="text"
                      class="ml-2"
                      @click="toggleResourcePermissions(resource, perms)"
                      :disabled="editingRole?.is_system_role"
                    >
                      {{ isResourceFullySelected(perms) ? 'Keine' : 'Alle' }}
                    </v-btn>
                  </div>
                  <div class="d-flex flex-wrap">
                    <v-checkbox
                      v-for="perm in perms"
                      :key="perm.id"
                      v-model="selectedPermissions"
                      :value="perm.id"
                      :label="formatPermissionName(perm.name)"
                      :disabled="editingRole?.is_system_role"
                      :color="editingRole?.is_super_admin ? 'warning' : 'primary'"
                      density="compact"
                      hide-details
                      class="mr-3"
                    />
                  </div>
                </div>
              </div>
            </v-tabs-window-item>
          </v-tabs-window>
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="roleDialog = false">
            {{ editingRole?.is_system_role ? 'Schliessen' : 'Abbrechen' }}
          </v-btn>
          <v-btn
            v-if="!editingRole?.is_system_role"
            color="primary"
            :loading="saving"
            @click="saveRole"
          >
            Speichern
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Dialog -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-card-title>Rolle loeschen</v-card-title>
        <v-card-text>
          <strong>{{ roleToDelete?.display_name }}</strong> wirklich loeschen?
          <v-alert v-if="roleToDelete?.users_count > 0" type="warning" variant="tonal" density="compact" class="mt-2">
            Diese Rolle ist {{ roleToDelete.users_count }} Benutzer(n) zugewiesen!
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">Abbrechen</v-btn>
          <v-btn color="error" :loading="deleting" @click="deleteRole">Loeschen</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { ref, onMounted, inject, watch } from 'vue'
import { useRolesStore } from '@/stores/roles'

const rolesStore = useRolesStore()
const showSnackbar = inject('showSnackbar')

const roleDialog = ref(false)
const dialogTab = ref('details')
const deleteDialog = ref(false)
const saving = ref(false)
const deleting = ref(false)
const editingRole = ref(null)
const roleToDelete = ref(null)
const selectedPermissions = ref([])

const roleFormData = ref({
  name: '',
  display_name: '',
  description: '',
  priority: 0,
})

const headers = [
  { title: 'Rolle', key: 'name' },
  { title: 'Beschreibung', key: 'description' },
  { title: 'Benutzer', key: 'users_count', width: '80px', align: 'center' },
  { title: '', key: 'actions', width: '80px', sortable: false },
]

const resourceIcons = {
  vm: 'mdi-server',
  inventory: 'mdi-folder-multiple',
  playbook: 'mdi-script-text',
  user: 'mdi-account-group',
  role: 'mdi-shield-account',
  settings: 'mdi-cog',
  audit: 'mdi-clipboard-text-clock',
  backup: 'mdi-backup-restore',
  template: 'mdi-file-document',
}

function getResourceIcon(resource) {
  return resourceIcons[resource] || 'mdi-folder'
}

function formatPermissionName(name) {
  // z.B. "vm:create" -> "Erstellen"
  const action = name.split(':')[1] || name
  const labels = {
    create: 'Erstellen',
    read: 'Lesen',
    update: 'Bearbeiten',
    delete: 'Loeschen',
    execute: 'Ausfuehren',
    manage: 'Verwalten',
    view: 'Anzeigen',
    export: 'Exportieren',
  }
  return labels[action] || action
}

function isResourceFullySelected(perms) {
  return perms.every(p => selectedPermissions.value.includes(p.id))
}

function toggleResourcePermissions(resource, perms) {
  if (isResourceFullySelected(perms)) {
    // Alle entfernen
    selectedPermissions.value = selectedPermissions.value.filter(
      id => !perms.some(p => p.id === id)
    )
  } else {
    // Alle hinzufuegen
    for (const perm of perms) {
      if (!selectedPermissions.value.includes(perm.id)) {
        selectedPermissions.value.push(perm.id)
      }
    }
  }
}

function selectAllPermissions() {
  selectedPermissions.value = rolesStore.permissions.map(p => p.id)
}

function openCreateDialog() {
  editingRole.value = null
  dialogTab.value = 'details'
  roleFormData.value = { name: '', display_name: '', description: '', priority: 0 }
  selectedPermissions.value = []
  roleDialog.value = true
}

async function openEditDialog(role) {
  editingRole.value = role
  dialogTab.value = 'details'
  roleFormData.value = {
    name: role.name,
    display_name: role.display_name,
    description: role.description || '',
    priority: role.priority,
  }

  // Berechtigungen laden
  if (role.is_super_admin) {
    // SuperAdmin: Alle Berechtigungen als ausgewaehlt anzeigen
    selectedPermissions.value = rolesStore.permissions.map(p => p.id)
  } else {
    const perms = await rolesStore.getRolePermissions(role.id)
    selectedPermissions.value = perms.map(p => p.permission.id)
  }

  roleDialog.value = true
}

async function saveRole() {
  saving.value = true
  try {
    let roleId

    if (editingRole.value) {
      // Update existierende Rolle
      await rolesStore.updateRole(editingRole.value.id, roleFormData.value)
      roleId = editingRole.value.id
    } else {
      // Neue Rolle erstellen
      const newRole = await rolesStore.createRole(roleFormData.value)
      roleId = newRole.id
    }

    // Berechtigungen speichern (nicht fuer Systemrollen)
    if (!editingRole.value?.is_system_role) {
      await rolesStore.setRolePermissions(roleId, selectedPermissions.value)
    }

    showSnackbar?.(editingRole.value ? 'Rolle aktualisiert' : 'Rolle erstellt', 'success')
    roleDialog.value = false
  } catch (e) {
    showSnackbar?.('Fehler: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    saving.value = false
  }
}

function confirmDelete(role) {
  roleToDelete.value = role
  deleteDialog.value = true
}

async function deleteRole() {
  deleting.value = true
  try {
    await rolesStore.deleteRole(roleToDelete.value.id)
    showSnackbar?.('Rolle geloescht', 'success')
    deleteDialog.value = false
  } catch (e) {
    showSnackbar?.('Fehler: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    deleting.value = false
  }
}

onMounted(async () => {
  await Promise.all([
    rolesStore.fetchRoles(),
    rolesStore.fetchPermissions(),
  ])
})
</script>
