<template>
  <v-dialog v-model="dialog" max-width="500" persistent>
    <v-card>
      <v-toolbar color="primary" density="compact">
        <v-icon class="ml-2 mr-2">mdi-content-copy</v-icon>
        <v-toolbar-title>VM Klonen</v-toolbar-title>
        <v-spacer></v-spacer>
        <v-btn icon size="small" @click="close" :disabled="loading">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-toolbar>

      <v-card-text class="pt-4">
        <v-alert type="info" variant="tonal" density="compact" class="mb-4">
          <strong>{{ sourceVm?.name }}</strong> wird geklont.
          <br>
          <span class="text-caption">
            {{ sourceVm?.cores }} CPUs, {{ sourceVm?.memory_gb }} GB RAM, {{ sourceVm?.disk_size_gb }} GB Disk
          </span>
        </v-alert>

        <v-text-field
          v-model="targetName"
          label="Name des Klons"
          prepend-inner-icon="mdi-server"
          hint="Nur Kleinbuchstaben, Zahlen und Bindestriche"
          :rules="[rules.required, rules.vmName]"
          variant="outlined"
          density="compact"
          autofocus
        ></v-text-field>

        <v-switch
          v-model="fullClone"
          label="Full Clone"
          color="primary"
          hide-details
          class="mt-4"
        >
          <template v-slot:label>
            <div>
              <div>{{ fullClone ? 'Full Clone' : 'Linked Clone' }}</div>
              <div class="text-caption text-grey">
                {{ fullClone
                  ? 'Eigenständige Kopie, benötigt mehr Speicherplatz'
                  : 'Nutzt Basis-Image, benötigt weniger Speicherplatz'
                }}
              </div>
            </div>
          </template>
        </v-switch>

        <v-alert
          v-if="error"
          type="error"
          variant="tonal"
          density="compact"
          class="mt-4"
        >
          {{ error }}
        </v-alert>

        <v-alert
          v-if="result"
          type="success"
          variant="tonal"
          density="compact"
          class="mt-4"
        >
          <div><strong>{{ result.target_name }}</strong> wird erstellt</div>
          <div class="text-caption">
            VMID: {{ result.target_vmid }} | IP: {{ result.target_ip }}
          </div>
        </v-alert>
      </v-card-text>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn @click="close" :disabled="loading">
          {{ result ? 'Schließen' : 'Abbrechen' }}
        </v-btn>
        <v-btn
          v-if="!result"
          color="primary"
          variant="flat"
          @click="cloneVM"
          :loading="loading"
          :disabled="!isValid"
        >
          <v-icon start>mdi-content-copy</v-icon>
          Klonen
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import api from '@/api/client'

const emit = defineEmits(['cloned', 'close'])

const dialog = ref(false)
const sourceVm = ref(null)
const targetName = ref('')
const fullClone = ref(true)
const loading = ref(false)
const error = ref(null)
const result = ref(null)

const rules = {
  required: v => !!v || 'Pflichtfeld',
  vmName: v => /^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$/.test(v) || 'Nur Kleinbuchstaben, Zahlen und Bindestriche',
}

const isValid = computed(() => {
  return targetName.value &&
         rules.vmName(targetName.value) === true &&
         targetName.value !== sourceVm.value?.name
})

function open(vm) {
  sourceVm.value = vm
  targetName.value = `${vm.name}-clone`
  fullClone.value = true
  error.value = null
  result.value = null
  dialog.value = true
}

function close() {
  dialog.value = false
  if (result.value) {
    emit('cloned', result.value)
  }
  emit('close')
}

async function cloneVM() {
  if (!isValid.value) return

  loading.value = true
  error.value = null

  try {
    const response = await api.post(`/api/terraform/vms/${sourceVm.value.name}/clone`, {
      target_name: targetName.value,
      full_clone: fullClone.value,
    })

    result.value = response.data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Klonen fehlgeschlagen'
    console.error('Clone-Fehler:', e)
  } finally {
    loading.value = false
  }
}

defineExpose({ open })
</script>
