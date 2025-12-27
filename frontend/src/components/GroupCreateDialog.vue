<template>
  <v-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" max-width="500" persistent>
    <v-card>
      <v-toolbar color="primary" density="compact">
        <v-toolbar-title>
          <v-icon start>mdi-folder-plus</v-icon>
          {{ editMode ? 'Gruppe umbenennen' : 'Neue Gruppe erstellen' }}
        </v-toolbar-title>
        <v-spacer></v-spacer>
        <v-btn icon size="small" @click="close">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-toolbar>

      <v-card-text class="pa-4">
        <v-form ref="formRef" @submit.prevent="submit">
          <v-text-field
            v-model="groupName"
            :label="editMode ? 'Neuer Gruppenname' : 'Gruppenname'"
            prepend-inner-icon="mdi-folder"
            variant="outlined"
            density="comfortable"
            :rules="nameRules"
            :disabled="loading"
            autofocus
            hint="Nur Buchstaben, Zahlen, _ und - erlaubt"
          ></v-text-field>

          <v-select
            v-if="!editMode"
            v-model="parentGroup"
            :items="parentOptions"
            label="Parent-Gruppe"
            prepend-inner-icon="mdi-folder-multiple"
            variant="outlined"
            density="comfortable"
            :disabled="loading"
            class="mt-4"
            hint="Die neue Gruppe wird unter dieser Gruppe erstellt"
          ></v-select>

          <v-alert
            v-if="editMode"
            type="info"
            variant="tonal"
            density="compact"
            class="mt-4"
          >
            Gruppe <strong>{{ originalName }}</strong> wird umbenannt
          </v-alert>
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
          <v-icon start>{{ editMode ? 'mdi-pencil' : 'mdi-plus' }}</v-icon>
          {{ editMode ? 'Umbenennen' : 'Erstellen' }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import api from '@/api/client'

const props = defineProps({
  modelValue: Boolean,
  editMode: {
    type: Boolean,
    default: false
  },
  originalName: {
    type: String,
    default: ''
  },
  groups: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:modelValue', 'created', 'renamed'])

const formRef = ref(null)
const groupName = ref('')
const parentGroup = ref('all')
const loading = ref(false)

// Name-Validierung
const nameRules = [
  v => !!v || 'Name ist erforderlich',
  v => v.length >= 2 || 'Mindestens 2 Zeichen',
  v => v.length <= 64 || 'Maximal 64 Zeichen',
  v => /^[a-zA-Z0-9_-]+$/.test(v) || 'Nur Buchstaben, Zahlen, _ und - erlaubt',
  v => !props.groups.some(g => g.name === v) || 'Gruppe existiert bereits',
]

// Parent-Optionen
const parentOptions = computed(() => {
  return [
    { title: 'all (Wurzel)', value: 'all' },
    ...props.groups.map(g => ({ title: g.name, value: g.name }))
  ]
})

// Validierung
const isValid = computed(() => {
  if (!groupName.value || groupName.value.length < 2) return false
  if (!/^[a-zA-Z0-9_-]+$/.test(groupName.value)) return false
  if (!props.editMode && props.groups.some(g => g.name === groupName.value)) return false
  if (props.editMode && groupName.value === props.originalName) return false
  return true
})

// Bei Edit-Mode den aktuellen Namen setzen
watch(() => props.modelValue, (open) => {
  if (open && props.editMode) {
    groupName.value = props.originalName
  } else if (open) {
    groupName.value = ''
    parentGroup.value = 'all'
  }
})

async function submit() {
  if (!isValid.value) return

  loading.value = true
  try {
    if (props.editMode) {
      // Gruppe umbenennen
      await api.put(`/api/inventory/groups/${props.originalName}`, {
        new_name: groupName.value
      })
      emit('renamed', { oldName: props.originalName, newName: groupName.value })
    } else {
      // Neue Gruppe erstellen
      await api.post('/api/inventory/groups', {
        name: groupName.value,
        parent: parentGroup.value
      })
      emit('created', groupName.value)
    }
    close()
  } catch (e) {
    console.error('Fehler:', e)
    // Error wird durch globalen Handler angezeigt
  } finally {
    loading.value = false
  }
}

function close() {
  emit('update:modelValue', false)
}
</script>
