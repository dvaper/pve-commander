<template>
  <div v-if="visibleAlerts.length > 0" class="alert-banner mb-4">
    <v-alert
      v-for="alert in visibleAlerts"
      :key="alert.id"
      :type="alert.type"
      variant="tonal"
      prominent
      closable
      class="mb-2"
      @click:close="dismissAlert(alert.id)"
    >
      <template #prepend>
        <v-icon>{{ alert.icon }}</v-icon>
      </template>

      <div class="d-flex align-center justify-space-between flex-wrap">
        <div>
          <div class="font-weight-medium">{{ alert.title }}</div>
          <div v-if="alert.message" class="text-body-2">{{ alert.message }}</div>
        </div>

        <v-btn
          v-if="alert.action"
          :to="alert.action.to"
          :color="alert.type"
          variant="outlined"
          size="small"
          class="ml-4 mt-2 mt-sm-0"
          @click="alert.action.onClick"
        >
          {{ alert.action.label }}
        </v-btn>
      </div>
    </v-alert>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const props = defineProps({
  /**
   * Liste der Alerts
   * Jeder Alert hat: id, type, icon, title, message?, action?
   */
  alerts: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['dismiss'])

// Dismissed alert IDs (gespeichert in localStorage)
const dismissedAlerts = ref([])

// Sichtbare Alerts (nicht dismissed)
const visibleAlerts = computed(() => {
  return props.alerts.filter(alert => !dismissedAlerts.value.includes(alert.id))
})

function dismissAlert(id) {
  dismissedAlerts.value.push(id)
  // In localStorage speichern (mit Ablaufdatum)
  saveDismissed()
  emit('dismiss', id)
}

function saveDismissed() {
  const data = {
    ids: dismissedAlerts.value,
    timestamp: Date.now()
  }
  localStorage.setItem('pvc-dismissed-alerts', JSON.stringify(data))
}

function loadDismissed() {
  try {
    const stored = localStorage.getItem('pvc-dismissed-alerts')
    if (!stored) return

    const data = JSON.parse(stored)
    // Nach 24 Stunden zuruecksetzen
    const maxAge = 24 * 60 * 60 * 1000
    if (Date.now() - data.timestamp < maxAge) {
      dismissedAlerts.value = data.ids || []
    }
  } catch (e) {
    // Ignorieren
  }
}

onMounted(() => {
  loadDismissed()
})
</script>

<style scoped>
.alert-banner :deep(.v-alert__content) {
  width: 100%;
}
</style>
