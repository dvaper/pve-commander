<template>
  <v-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" max-width="600" persistent>
    <v-card>
      <v-toolbar color="primary" density="compact">
        <v-toolbar-title>
          <v-icon start>mdi-file-document-plus</v-icon>
          Neue VM-Vorlage erstellen
        </v-toolbar-title>
        <v-spacer></v-spacer>
        <v-btn icon size="small" @click="close">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-toolbar>

      <v-card-text class="pa-4">
        <v-form ref="formRef" @submit.prevent="submit">
          <v-text-field
            v-model="form.name"
            label="Name"
            prepend-inner-icon="mdi-tag"
            variant="outlined"
            density="compact"
            :rules="[v => !!v || 'Pflichtfeld']"
            :disabled="loading"
            autofocus
          ></v-text-field>

          <v-textarea
            v-model="form.description"
            label="Beschreibung"
            prepend-inner-icon="mdi-text"
            variant="outlined"
            density="compact"
            rows="2"
            class="mt-3"
            :disabled="loading"
          ></v-textarea>

          <v-row class="mt-3">
            <v-col cols="4">
              <v-text-field
                v-model.number="form.cores"
                label="CPU-Kerne"
                type="number"
                variant="outlined"
                density="compact"
                :min="1"
                :max="32"
                :disabled="loading"
              ></v-text-field>
            </v-col>
            <v-col cols="4">
              <v-text-field
                v-model.number="form.memory_gb"
                label="RAM (GB)"
                type="number"
                variant="outlined"
                density="compact"
                :min="1"
                :max="128"
                :disabled="loading"
              ></v-text-field>
            </v-col>
            <v-col cols="4">
              <v-text-field
                v-model.number="form.disk_size_gb"
                label="Disk (GB)"
                type="number"
                variant="outlined"
                density="compact"
                :min="10"
                :max="1000"
                :disabled="loading"
              ></v-text-field>
            </v-col>
          </v-row>

          <v-select
            v-model="form.target_node"
            :items="nodes"
            item-title="label"
            item-value="name"
            label="Proxmox-Node (optional)"
            prepend-inner-icon="mdi-server-network"
            variant="outlined"
            density="compact"
            clearable
            class="mt-3"
            :disabled="loading"
          ></v-select>

          <v-select
            v-model="form.vlan"
            :items="vlans"
            item-title="label"
            item-value="id"
            label="VLAN"
            prepend-inner-icon="mdi-lan"
            variant="outlined"
            density="compact"
            class="mt-3"
            :disabled="loading"
          ></v-select>

          <v-select
            v-model="form.ansible_group"
            :items="ansibleGroups"
            item-title="label"
            item-value="value"
            label="Ansible-Gruppe"
            prepend-inner-icon="mdi-ansible"
            variant="outlined"
            density="compact"
            clearable
            class="mt-3"
            :disabled="loading"
          ></v-select>

          <v-select
            v-model="form.cloud_init_profile"
            :items="cloudInitProfiles"
            item-title="label"
            item-value="value"
            label="Cloud-Init Profil"
            prepend-inner-icon="mdi-cloud-sync"
            variant="outlined"
            density="compact"
            clearable
            class="mt-3"
            :disabled="loading"
          ></v-select>

          <v-checkbox
            v-model="form.is_default"
            label="Als Standard-Vorlage setzen"
            density="compact"
            class="mt-3"
            :disabled="loading"
          ></v-checkbox>
        </v-form>
      </v-card-text>

      <v-divider></v-divider>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn variant="text" @click="close" :disabled="loading">
          Abbrechen
        </v-btn>
        <v-btn
          color="primary"
          variant="flat"
          @click="submit"
          :loading="loading"
          :disabled="!isValid"
        >
          <v-icon start>mdi-plus</v-icon>
          Erstellen
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import api from '@/api/client'

const props = defineProps({
  modelValue: Boolean,
})

const emit = defineEmits(['update:modelValue', 'created'])

const formRef = ref(null)
const loading = ref(false)

const form = ref({
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
})

// Options fuer Selects
const nodes = ref([])
const vlans = ref([])
const ansibleGroups = ref([])
const cloudInitProfiles = ref([])

// Validierung
const isValid = computed(() => {
  return form.value.name && form.value.name.length >= 2
})

// Optionen laden wenn Dialog geoeffnet wird
watch(() => props.modelValue, async (open) => {
  if (open) {
    // Form zuruecksetzen
    form.value = {
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
    await loadOptions()
  }
})

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

async function submit() {
  if (!isValid.value) return

  loading.value = true
  try {
    const response = await api.post('/api/terraform/templates/presets', form.value)
    emit('created', response.data)
    close()
  } catch (e) {
    console.error('Vorlage erstellen fehlgeschlagen:', e)
  } finally {
    loading.value = false
  }
}

function close() {
  emit('update:modelValue', false)
}
</script>
