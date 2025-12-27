<template>
  <div class="capacity-gauge">
    <div class="d-flex justify-space-between align-center mb-1">
      <div class="d-flex align-center">
        <v-icon v-if="icon" size="small" class="mr-2" :color="gaugeColor">
          {{ icon }}
        </v-icon>
        <span class="text-body-2">{{ label }}</span>
      </div>
      <span class="text-body-2 font-weight-medium" :class="textColorClass">
        {{ formattedValue }}
      </span>
    </div>
    <v-progress-linear
      :model-value="value"
      :color="gaugeColor"
      height="10"
      rounded
      :bg-color="bgColor"
    />
    <div v-if="subtitle" class="text-caption text-medium-emphasis mt-1">
      {{ subtitle }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  /**
   * Aktueller Wert (0-100)
   */
  value: {
    type: Number,
    required: true,
    validator: (v) => v >= 0 && v <= 100
  },
  /**
   * Label ueber der Fortschrittsleiste
   */
  label: {
    type: String,
    required: true
  },
  /**
   * Optionales Icon
   */
  icon: {
    type: String,
    default: null
  },
  /**
   * Optionaler Untertitel
   */
  subtitle: {
    type: String,
    default: null
  },
  /**
   * Format fuer den Wert
   */
  format: {
    type: String,
    default: 'percent', // 'percent' | 'value'
    validator: (v) => ['percent', 'value'].includes(v)
  },
  /**
   * Einheit bei format='value'
   */
  unit: {
    type: String,
    default: ''
  },
  /**
   * Schwellwerte fuer Farbwechsel
   */
  thresholds: {
    type: Object,
    default: () => ({ warning: 75, critical: 90 })
  },
  /**
   * Invertierte Logik (niedrig = schlecht)
   */
  inverted: {
    type: Boolean,
    default: false
  }
})

const gaugeColor = computed(() => {
  const { warning, critical } = props.thresholds

  if (props.inverted) {
    // Invertiert: niedriger Wert = schlecht (z.B. freier Speicher)
    if (props.value <= 100 - critical) return 'error'
    if (props.value <= 100 - warning) return 'warning'
    return 'success'
  }

  // Normal: hoher Wert = schlecht (z.B. CPU-Auslastung)
  if (props.value >= critical) return 'error'
  if (props.value >= warning) return 'warning'
  return 'success'
})

const textColorClass = computed(() => {
  const color = gaugeColor.value
  if (color === 'error') return 'text-error'
  if (color === 'warning') return 'text-warning'
  return ''
})

const bgColor = computed(() => {
  // Leicht gefaerbter Hintergrund passend zur Farbe
  return `${gaugeColor.value}-lighten-4`
})

const formattedValue = computed(() => {
  if (props.format === 'percent') {
    return `${Math.round(props.value)}%`
  }
  return `${props.value}${props.unit ? ' ' + props.unit : ''}`
})
</script>

<style scoped>
.capacity-gauge {
  padding: 8px 0;
}
</style>
