<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12" class="d-flex align-center">
        <h1 class="text-h4">Rollen-Verwaltung</h1>
        <v-spacer />
        <v-btn color="primary" @click="openCreateDialog">
          <v-icon start>mdi-plus</v-icon>
          Neue Rolle
        </v-btn>
      </v-col>
    </v-row>

    <!-- Roles Table -->
    <v-row>
      <v-col cols="12">
        <v-card>
          <v-data-table
            :headers="headers"
            :items="rolesStore.roles"
            :loading="rolesStore.loading"
            density="compact"
            item-value="id"
          >
            <template #item.name="{ item }">
              <div class="d-flex align-center">
                <v-icon
                  v-if="item.is_super_admin"
                  color="warning"
                  size="small"
                  class="mr-2"
                >
                  mdi-crown
                </v-icon>
                <v-icon
                  v-else-if="item.is_system_role"
                  color="grey"
                  size="small"
                  class="mr-2"
                >
                  mdi-lock
                </v-icon>
                <div>
                  <div class="font-weight-medium">{{ item.display_name }}</div>
                  <div class="text-caption text-grey">{{ item.name }}</div>
                </div>
              </div>
            </template>

            <template #item.priority="{ item }">
              <v-chip size="small" :color="getPriorityColor(item.priority)">
                {{ item.priority }}
              </v-chip>
            </template>

            <template #item.restrictions="{ item }">
              <div class="d-flex gap-1 flex-wrap">
                <v-chip
                  v-for="os in parseJson(item.allowed_os_types)"
                  :key="os"
                  size="x-small"
                  color="info"
                  variant="outlined"
                >
                  {{ os }}
                </v-chip>
                <v-chip
                  v-for="cat in parseJson(item.allowed_categories)"
                  :key="cat"
                  size="x-small"
                  color="secondary"
                  variant="outlined"
                >
                  {{ cat }}
                </v-chip>
              </div>
            </template>

            <template #item.users_count="{ item }">
              <v-chip size="small" variant="tonal">
                {{ item.users_count || 0 }}
              </v-chip>
            </template>

            <template #item.actions="{ item }">
              <div style="white-space: nowrap">
                <v-btn
                  icon
                  variant="text"
                  size="small"
                  @click="openPermissionsDialog(item)"
                  title="Berechtigungen"
                >
                  <v-icon>mdi-shield-key</v-icon>
                </v-btn>
                <v-btn
                  icon
                  variant="text"
                  size="small"
                  :disabled="item.is_system_role"
                  @click="openEditDialog(item)"
                  title="Bearbeiten"
                >
                  <v-icon>mdi-pencil</v-icon>
                </v-btn>
                <v-btn
                  icon
                  variant="text"
                  size="small"
                  color="error"
                  :disabled="item.is_system_role"
                  @click="confirmDelete(item)"
                  title="Loeschen"
                >
                  <v-icon>mdi-delete</v-icon>
                </v-btn>
              </div>
            </template>
          </v-data-table>
        </v-card>
      </v-col>
    </v-row>

    <!-- Create/Edit Dialog -->
    <v-dialog v-model="roleDialog" max-width="600" persistent>
      <v-card>
        <v-card-title>
          {{ editingRole ? 'Rolle bearbeiten' : 'Neue Rolle erstellen' }}
        </v-card-title>
        <v-divider />
        <v-card-text>
          <v-form ref="roleForm" v-model="formValid">
            <v-text-field
              v-model="roleFormData.name"
              label="Technischer Name"
              :rules="[rules.required, rules.identifier]"
              :disabled="!!editingRole"
              hint="Kleinbuchstaben, Zahlen, Bindestriche"
              persistent-hint
              class="mb-3"
            />
            <v-text-field
              v-model="roleFormData.display_name"
              label="Anzeigename"
              :rules="[rules.required]"
              class="mb-3"
            />
            <v-textarea
              v-model="roleFormData.description"
              label="Beschreibung"
              rows="2"
              class="mb-3"
            />
            <v-select
              v-model="roleFormData.parent_role_id"
              :items="parentRoleItems"
              label="Uebergeordnete Rolle"
              clearable
              hint="Erbt Berechtigungen von dieser Rolle"
              persistent-hint
              class="mb-3"
            />
            <v-text-field
              v-model.number="roleFormData.priority"
              label="Prioritaet"
              type="number"
              :rules="[rules.requiredNumber]"
              hint="Hoehere Prioritaet = mehr Rechte bei Konflikten"
              persistent-hint
              class="mb-3"
            />
            <v-select
              v-model="roleFormData.allowed_os_types"
              :items="osTypeItems"
              label="Erlaubte OS-Typen"
              multiple
              chips
              closable-chips
              class="mb-3"
            />
            <v-select
              v-model="roleFormData.allowed_categories"
              :items="categoryItems"
              label="Erlaubte Kategorien"
              multiple
              chips
              closable-chips
            />
          </v-form>
        </v-card-text>
        <v-divider />
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="closeRoleDialog">Abbrechen</v-btn>
          <v-btn
            color="primary"
            :loading="saving"
            :disabled="!formValid"
            @click="saveRole"
          >
            Speichern
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Permissions Dialog -->
    <v-dialog v-model="permissionsDialog" max-width="800" persistent>
      <v-card v-if="selectedRole">
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2">mdi-shield-key</v-icon>
          Berechtigungen: {{ selectedRole.display_name }}
          <v-spacer />
          <v-chip
            v-if="selectedRole.is_system_role"
            color="grey"
            size="small"
          >
            System-Rolle (schreibgeschuetzt)
          </v-chip>
        </v-card-title>
        <v-divider />
        <v-card-text style="max-height: 500px; overflow-y: auto;">
          <div
            v-for="(perms, resource) in rolesStore.permissionsByResource"
            :key="resource"
            class="mb-4"
          >
            <div class="text-subtitle-1 font-weight-bold mb-2 text-capitalize">
              {{ resource }}
            </div>
            <v-row>
              <v-col
                v-for="perm in perms"
                :key="perm.id"
                cols="12"
                md="6"
              >
                <v-checkbox
                  v-model="selectedPermissions"
                  :value="perm.id"
                  :label="perm.name"
                  :hint="perm.description"
                  :disabled="selectedRole.is_system_role"
                  persistent-hint
                  density="compact"
                  hide-details="auto"
                />
              </v-col>
            </v-row>
            <v-divider class="mt-3" />
          </div>
        </v-card-text>
        <v-divider />
        <v-card-actions>
          <v-btn variant="text" @click="selectAllPermissions">Alle auswaehlen</v-btn>
          <v-btn variant="text" @click="deselectAllPermissions">Alle abwaehlen</v-btn>
          <v-spacer />
          <v-btn variant="text" @click="permissionsDialog = false">
            {{ selectedRole.is_system_role ? 'Schliessen' : 'Abbrechen' }}
          </v-btn>
          <v-btn
            v-if="!selectedRole.is_system_role"
            color="primary"
            :loading="savingPermissions"
            @click="savePermissions"
          >
            Speichern
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirmation Dialog -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-card-title class="bg-error text-white">
          <v-icon class="mr-2">mdi-alert</v-icon>
          Rolle loeschen
        </v-card-title>
        <v-card-text class="pt-4">
          <p>Moechten Sie die Rolle <strong>{{ roleToDelete?.display_name }}</strong> wirklich loeschen?</p>
          <v-alert type="warning" density="compact" class="mt-3">
            Benutzer mit dieser Rolle verlieren die zugehoerigen Berechtigungen.
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">Abbrechen</v-btn>
          <v-btn color="error" :loading="deleting" @click="deleteRole">
            Loeschen
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRolesStore } from '@/stores/roles'

const rolesStore = useRolesStore()

// State
const roleDialog = ref(false)
const permissionsDialog = ref(false)
const deleteDialog = ref(false)
const formValid = ref(false)
const saving = ref(false)
const savingPermissions = ref(false)
const deleting = ref(false)

const editingRole = ref(null)
const selectedRole = ref(null)
const roleToDelete = ref(null)
const selectedPermissions = ref([])

const roleFormData = ref({
  name: '',
  display_name: '',
  description: '',
  parent_role_id: null,
  priority: 0,
  allowed_os_types: [],
  allowed_categories: [],
})

// Table headers
const headers = [
  { title: 'Rolle', key: 'name', width: '250px' },
  { title: 'Beschreibung', key: 'description' },
  { title: 'Prioritaet', key: 'priority', width: '100px', align: 'center' },
  { title: 'Einschraenkungen', key: 'restrictions', sortable: false },
  { title: 'Benutzer', key: 'users_count', width: '100px', align: 'center' },
  { title: 'Aktionen', key: 'actions', width: '150px', sortable: false },
]

// Dropdown items
const osTypeItems = [
  { title: 'Alle', value: 'all' },
  { title: 'Linux', value: 'linux' },
  { title: 'Windows', value: 'windows' },
]

const categoryItems = [
  { title: 'System', value: 'system' },
  { title: 'Wartung', value: 'maintenance' },
  { title: 'Deployment', value: 'deployment' },
  { title: 'Sicherheit', value: 'security' },
  { title: 'Monitoring', value: 'monitoring' },
  { title: 'Custom', value: 'custom' },
]

const parentRoleItems = computed(() => {
  return rolesStore.roles
    .filter(r => !editingRole.value || r.id !== editingRole.value.id)
    .map(r => ({ title: r.display_name, value: r.id }))
})

// Validation rules
const rules = {
  required: v => !!v || 'Pflichtfeld',
  requiredNumber: v => v !== null && v !== undefined && v !== '' || 'Pflichtfeld',
  identifier: v => /^[a-z0-9-]+$/.test(v) || 'Nur Kleinbuchstaben, Zahlen und Bindestriche',
}

// Methods
function parseJson(value) {
  if (!value) return []
  if (Array.isArray(value)) return value
  try {
    return JSON.parse(value)
  } catch {
    return []
  }
}

function getPriorityColor(priority) {
  if (priority >= 100) return 'error'
  if (priority >= 50) return 'warning'
  if (priority >= 20) return 'primary'
  return 'grey'
}

function openCreateDialog() {
  editingRole.value = null
  roleFormData.value = {
    name: '',
    display_name: '',
    description: '',
    parent_role_id: null,
    priority: 0,
    allowed_os_types: [],
    allowed_categories: [],
  }
  roleDialog.value = true
}

function openEditDialog(role) {
  editingRole.value = role
  roleFormData.value = {
    name: role.name,
    display_name: role.display_name,
    description: role.description || '',
    parent_role_id: role.parent_role_id,
    priority: role.priority,
    allowed_os_types: parseJson(role.allowed_os_types),
    allowed_categories: parseJson(role.allowed_categories),
  }
  roleDialog.value = true
}

function closeRoleDialog() {
  roleDialog.value = false
  editingRole.value = null
}

async function saveRole() {
  saving.value = true
  try {
    const data = {
      ...roleFormData.value,
      allowed_os_types: roleFormData.value.allowed_os_types.length
        ? roleFormData.value.allowed_os_types
        : null,
      allowed_categories: roleFormData.value.allowed_categories.length
        ? roleFormData.value.allowed_categories
        : null,
    }

    if (editingRole.value) {
      await rolesStore.updateRole(editingRole.value.id, data)
    } else {
      await rolesStore.createRole(data)
    }
    closeRoleDialog()
  } finally {
    saving.value = false
  }
}

async function openPermissionsDialog(role) {
  selectedRole.value = role
  selectedPermissions.value = []

  // Load current permissions
  const perms = await rolesStore.getRolePermissions(role.id)
  selectedPermissions.value = perms.map(p => p.permission.id)

  permissionsDialog.value = true
}

function selectAllPermissions() {
  selectedPermissions.value = rolesStore.permissions.map(p => p.id)
}

function deselectAllPermissions() {
  selectedPermissions.value = []
}

async function savePermissions() {
  savingPermissions.value = true
  try {
    await rolesStore.setRolePermissions(selectedRole.value.id, selectedPermissions.value)
    permissionsDialog.value = false
  } finally {
    savingPermissions.value = false
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
    deleteDialog.value = false
  } finally {
    deleting.value = false
  }
}

// Lifecycle
onMounted(async () => {
  await Promise.all([
    rolesStore.fetchRoles(),
    rolesStore.fetchPermissions(),
  ])
})
</script>
