<template>
  <v-dialog :model-value="modelValue" max-width="500" @update:model-value="emit('update:modelValue', $event)">
    <v-card>
      <v-card-title>
        <v-icon start>mdi-broom</v-icon>
        System aufraeumen
      </v-card-title>
      <v-card-text>
        <v-alert type="info" variant="tonal" density="compact" class="mb-4">
          Waehlen Sie die Bereinigungsoptionen aus.
        </v-alert>

        <v-checkbox
          v-model="options.orphanedVMs"
          :disabled="orphanedCount === 0"
          density="compact"
          hide-details
          class="mb-2"
        >
          <template v-slot:label>
            <span>Verwaiste VMs bereinigen</span>
            <v-chip
              v-if="orphanedCount > 0"
              size="x-small"
              color="warning"
              class="ml-2"
            >
              {{ orphanedCount }} gefunden
            </v-chip>
            <span v-else class="text-grey ml-2">(keine)</span>
          </template>
        </v-checkbox>

        <v-checkbox
          v-model="options.oldExecutions"
          density="compact"
          hide-details
          class="mb-2"
        >
          <template v-slot:label>
            <span>Alte Ausfuehrungen loeschen</span>
          </template>
        </v-checkbox>
        <v-slider
          v-if="options.oldExecutions"
          v-model="options.executionDays"
          :min="7"
          :max="90"
          :step="1"
          thumb-label
          density="compact"
          class="ml-8"
          hide-details
        >
          <template v-slot:prepend>
            <span class="text-caption text-grey">Aelter als</span>
          </template>
          <template v-slot:append>
            <span class="text-caption">{{ options.executionDays }} Tage</span>
          </template>
        </v-slider>

        <v-checkbox
          v-model="options.oldBackups"
          density="compact"
          hide-details
          class="mb-2 mt-4"
        >
          <template v-slot:label>
            <span>Alte geplante Backups loeschen</span>
          </template>
        </v-checkbox>
        <v-slider
          v-if="options.oldBackups"
          v-model="options.backupDays"
          :min="7"
          :max="90"
          :step="1"
          thumb-label
          density="compact"
          class="ml-8"
          hide-details
        >
          <template v-slot:prepend>
            <span class="text-caption text-grey">Aelter als</span>
          </template>
          <template v-slot:append>
            <span class="text-caption">{{ options.backupDays }} Tage</span>
          </template>
        </v-slider>

        <v-checkbox
          v-model="options.tfState"
          density="compact"
          hide-details
          class="mt-4"
        >
          <template v-slot:label>
            <span>Terraform State bereinigen</span>
            <span class="text-grey ml-2">(entfernt verwaiste Eintraege)</span>
          </template>
        </v-checkbox>

        <v-alert
          v-if="hasSelection"
          type="warning"
          variant="tonal"
          density="compact"
          class="mt-4"
        >
          Die gewaehlten Daten werden unwiderruflich geloescht.
        </v-alert>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="emit('update:modelValue', false)">Abbrechen</v-btn>
        <v-btn
          color="warning"
          variant="flat"
          :loading="running"
          :disabled="!hasSelection"
          @click="runCleanup"
        >
          <v-icon start>mdi-broom</v-icon>
          Bereinigen
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch, inject } from 'vue'
import api from '@/api/client'

const props = defineProps({
  modelValue: Boolean,
})

const emit = defineEmits(['update:modelValue', 'cleaned'])
const showSnackbar = inject('showSnackbar')

const running = ref(false)
const orphanedCount = ref(0)
const options = ref({
  orphanedVMs: false,
  oldExecutions: false,
  executionDays: 30,
  oldBackups: false,
  backupDays: 30,
  tfState: false,
})

const hasSelection = computed(() => {
  return options.value.orphanedVMs ||
         options.value.oldExecutions ||
         options.value.oldBackups ||
         options.value.tfState
})

watch(() => props.modelValue, async (open) => {
  if (open) {
    // Orphaned VMs zaehlen
    try {
      const res = await api.get('/api/terraform/state/health/status')
      orphanedCount.value = res.data.orphaned_vms?.length || 0
    } catch {
      orphanedCount.value = 0
    }
  }
})

async function runCleanup() {
  running.value = true
  const results = []

  try {
    // Verwaiste VMs
    if (options.value.orphanedVMs && orphanedCount.value > 0) {
      try {
        const res = await api.post('/api/terraform/state/health/cleanup')
        results.push(`${res.data.cleaned || 0} VMs bereinigt`)
      } catch (e) {
        results.push('VMs: Fehler')
      }
    }

    // Alte Ausfuehrungen
    if (options.value.oldExecutions) {
      try {
        const res = await api.delete(`/api/executions/cleanup?days=${options.value.executionDays}`)
        results.push(`${res.data.deleted || 0} Ausfuehrungen geloescht`)
      } catch (e) {
        // Fallback: Endpoint existiert moeglicherweise nicht
        results.push('Ausfuehrungen: nicht verfuegbar')
      }
    }

    // Alte Backups
    if (options.value.oldBackups) {
      try {
        const res = await api.post(`/api/backup/cleanup?retention_days=${options.value.backupDays}`)
        results.push(`${res.data.deleted_count || 0} Backups geloescht`)
      } catch (e) {
        results.push('Backups: Fehler')
      }
    }

    // Terraform State
    if (options.value.tfState) {
      try {
        const res = await api.post('/api/terraform/state/health/cleanup')
        results.push('Terraform State bereinigt')
      } catch (e) {
        results.push('Terraform: Fehler')
      }
    }

    showSnackbar?.(results.join(', '), 'success')
    emit('cleaned')
    emit('update:modelValue', false)
  } catch (e) {
    showSnackbar?.('Bereinigung fehlgeschlagen', 'error')
  } finally {
    running.value = false
  }
}
</script>
