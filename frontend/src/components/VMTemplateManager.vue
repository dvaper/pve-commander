<template>
  <v-card>
    <v-toolbar color="primary" density="compact">
      <v-icon class="mr-2">mdi-file-document-multiple</v-icon>
      <v-toolbar-title>VM-Vorlagen</v-toolbar-title>
      <v-spacer></v-spacer>
      <v-btn icon size="small" @click="loadTemplates">
        <v-icon>mdi-refresh</v-icon>
      </v-btn>
      <v-btn icon size="small" @click="openCreateDialog" v-if="isAdmin">
        <v-icon>mdi-plus</v-icon>
      </v-btn>
    </v-toolbar>

    <v-card-text v-if="loading">
      <v-progress-linear indeterminate color="primary"></v-progress-linear>
    </v-card-text>

    <v-list v-else-if="templates.length > 0" density="compact">
      <v-list-item
        v-for="template in templates"
        :key="template.id"
        @click="selectTemplate(template)"
        :class="{ 'bg-primary-lighten-5': selectedId === template.id }"
      >
        <template v-slot:prepend>
          <v-icon :color="template.is_default ? 'primary' : 'grey'">
            {{ template.is_default ? 'mdi-star' : 'mdi-file-document-outline' }}
          </v-icon>
        </template>

        <v-list-item-title>
          {{ template.name }}
          <v-chip v-if="template.is_default" size="x-small" color="primary" class="ml-2">
            Standard
          </v-chip>
        </v-list-item-title>

        <v-list-item-subtitle>
          {{ template.cores }} CPUs, {{ template.memory_gb }} GB RAM, {{ template.disk_size_gb }} GB Disk
          <span v-if="template.target_node"> | Node: {{ template.target_node }}</span>
        </v-list-item-subtitle>

        <template v-slot:append v-if="isAdmin">
          <v-btn icon size="x-small" variant="text" @click.stop="openEditDialog(template)">
            <v-icon size="small">mdi-pencil</v-icon>
          </v-btn>
          <v-btn icon size="x-small" variant="text" color="error" @click.stop="confirmDelete(template)">
            <v-icon size="small">mdi-delete</v-icon>
          </v-btn>
        </template>
      </v-list-item>
    </v-list>

    <v-card-text v-else class="text-center text-grey">
      Keine Vorlagen vorhanden
    </v-card-text>

    <!-- Create/Edit Dialog -->
    <v-dialog v-model="editDialog" max-width="600" persistent>
      <v-card>
        <v-toolbar color="primary" density="compact">
          <v-toolbar-title>{{ editingId ? 'Vorlage bearbeiten' : 'Neue Vorlage' }}</v-toolbar-title>
          <v-spacer></v-spacer>
          <v-btn icon size="small" @click="editDialog = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-toolbar>

        <v-card-text>
          <v-text-field
            v-model="editForm.name"
            label="Name"
            prepend-inner-icon="mdi-tag"
            variant="outlined"
            density="compact"
            :rules="[v => !!v || 'Pflichtfeld']"
          ></v-text-field>

          <v-textarea
            v-model="editForm.description"
            label="Beschreibung"
            prepend-inner-icon="mdi-text"
            variant="outlined"
            density="compact"
            rows="2"
            class="mt-3"
          ></v-textarea>

          <v-row class="mt-3">
            <v-col cols="4">
              <v-text-field
                v-model.number="editForm.cores"
                label="CPU-Kerne"
                type="number"
                variant="outlined"
                density="compact"
                :min="1"
                :max="32"
              ></v-text-field>
            </v-col>
            <v-col cols="4">
              <v-text-field
                v-model.number="editForm.memory_gb"
                label="RAM (GB)"
                type="number"
                variant="outlined"
                density="compact"
                :min="1"
                :max="128"
              ></v-text-field>
            </v-col>
            <v-col cols="4">
              <v-text-field
                v-model.number="editForm.disk_size_gb"
                label="Disk (GB)"
                type="number"
                variant="outlined"
                density="compact"
                :min="10"
                :max="1000"
              ></v-text-field>
            </v-col>
          </v-row>

          <v-select
            v-model="editForm.target_node"
            :items="nodes"
            item-title="label"
            item-value="name"
            label="Proxmox-Node (optional)"
            prepend-inner-icon="mdi-server-network"
            variant="outlined"
            density="compact"
            clearable
            class="mt-3"
          ></v-select>

          <v-select
            v-model="editForm.vlan"
            :items="vlans"
            item-title="label"
            item-value="id"
            label="VLAN"
            prepend-inner-icon="mdi-lan"
            variant="outlined"
            density="compact"
            class="mt-3"
          ></v-select>

          <v-select
            v-model="editForm.ansible_group"
            :items="ansibleGroups"
            item-title="label"
            item-value="value"
            label="Ansible-Gruppe"
            prepend-inner-icon="mdi-ansible"
            variant="outlined"
            density="compact"
            clearable
            class="mt-3"
          ></v-select>

          <v-select
            v-model="editForm.cloud_init_profile"
            :items="cloudInitProfiles"
            item-title="label"
            item-value="value"
            label="Cloud-Init Profil"
            prepend-inner-icon="mdi-cloud-sync"
            variant="outlined"
            density="compact"
            clearable
            class="mt-3"
          ></v-select>

          <v-checkbox
            v-model="editForm.is_default"
            label="Als Standard-Vorlage setzen"
            density="compact"
            class="mt-3"
          ></v-checkbox>
        </v-card-text>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="editDialog = false">Abbrechen</v-btn>
          <v-btn color="primary" variant="flat" @click="saveTemplate" :loading="saving">
            Speichern
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirmation -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-card-title>Vorlage löschen?</v-card-title>
        <v-card-text>
          Soll die Vorlage "{{ deleteTarget?.name }}" wirklich gelöscht werden?
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="deleteDialog = false">Abbrechen</v-btn>
          <v-btn color="error" variant="flat" @click="deleteTemplate" :loading="deleting">
            Löschen
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const emit = defineEmits(['select'])

const authStore = useAuthStore()
const isAdmin = computed(() => authStore.isAdmin || authStore.isSuperAdmin)

const templates = ref([])
const loading = ref(false)
const selectedId = ref(null)

// Edit Dialog
const editDialog = ref(false)
const editingId = ref(null)
const editForm = ref({})
const saving = ref(false)

// Delete Dialog
const deleteDialog = ref(false)
const deleteTarget = ref(null)
const deleting = ref(false)

// Options für Selects
const nodes = ref([])
const vlans = ref([])
const ansibleGroups = ref([])
const cloudInitProfiles = ref([])

async function loadTemplates() {
  loading.value = true
  try {
    const response = await api.get('/api/terraform/templates/presets')
    templates.value = response.data
  } catch (e) {
    console.error('Vorlagen laden fehlgeschlagen:', e)
  } finally {
    loading.value = false
  }
}

async function loadOptions() {
  try {
    const [nodesRes, vlansRes, groupsRes, profilesRes] = await Promise.all([
      api.get('/api/terraform/nodes'),
      api.get('/api/terraform/vlans'),
      api.get('/api/terraform/ansible-groups'),
      api.get('/api/terraform/cloud-init/profiles'),
    ])

    nodes.value = nodesRes.data.map(n => ({
      ...n,
      label: `${n.name} (${n.cpus} CPUs, ${n.ram_gb} GB)`,
    }))

    vlans.value = vlansRes.data.map(v => ({
      ...v,
      label: `VLAN ${v.id} - ${v.name}`,
    }))

    ansibleGroups.value = groupsRes.data

    cloudInitProfiles.value = profilesRes.data.map(p => ({
      ...p,
      label: p.name,
      value: p.id,
    }))
  } catch (e) {
    console.error('Optionen laden fehlgeschlagen:', e)
  }
}

function selectTemplate(template) {
  selectedId.value = template.id
  emit('select', template)
}

function openCreateDialog() {
  editingId.value = null
  editForm.value = {
    name: '',
    description: '',
    cores: 2,
    memory_gb: 2,
    disk_size_gb: 20,
    target_node: null,
    vlan: 60,
    ansible_group: null,
    cloud_init_profile: null,
    is_default: false,
  }
  editDialog.value = true
}

function openEditDialog(template) {
  editingId.value = template.id
  editForm.value = { ...template }
  editDialog.value = true
}

async function saveTemplate() {
  saving.value = true
  try {
    if (editingId.value) {
      await api.put(`/api/terraform/templates/presets/${editingId.value}`, editForm.value)
    } else {
      await api.post('/api/terraform/templates/presets', editForm.value)
    }
    editDialog.value = false
    await loadTemplates()
  } catch (e) {
    console.error('Speichern fehlgeschlagen:', e)
  } finally {
    saving.value = false
  }
}

function confirmDelete(template) {
  deleteTarget.value = template
  deleteDialog.value = true
}

async function deleteTemplate() {
  deleting.value = true
  try {
    await api.delete(`/api/terraform/templates/presets/${deleteTarget.value.id}`)
    deleteDialog.value = false
    await loadTemplates()
  } catch (e) {
    console.error('Löschen fehlgeschlagen:', e)
  } finally {
    deleting.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadTemplates(), loadOptions()])
})

defineExpose({ loadTemplates, selectTemplate })
</script>
