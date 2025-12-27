<template>
  <v-dialog v-model="modelValue" max-width="450" persistent>
    <v-card>
      <v-card-title class="d-flex align-center pa-4">
        <v-avatar :color="iconColor" size="40" class="mr-3">
          <v-icon color="white">{{ icon }}</v-icon>
        </v-avatar>
        <span>{{ title }}</span>
      </v-card-title>

      <v-card-text class="pb-2">
        <p class="text-body-1 mb-0">{{ message }}</p>

        <!-- Slot fuer zusaetzliche Details (z.B. betroffene Items) -->
        <slot name="details" />

        <!-- Optionale Text-Bestaetigung (z.B. "DESTROY" eintippen) -->
        <v-text-field
          v-if="requireTextConfirmation"
          v-model="textConfirmInput"
          :label="`Tippe '${requireTextConfirmation}' zur Bestaetigung`"
          variant="outlined"
          density="compact"
          :color="confirmColor"
          class="mt-4"
          hide-details
        />

        <!-- Optionale Checkbox fuer kritische Aktionen -->
        <v-checkbox
          v-else-if="requireConfirmation"
          v-model="confirmed"
          :label="confirmationLabel"
          color="primary"
          hide-details
          density="compact"
          class="mt-4"
        />
      </v-card-text>

      <v-card-actions class="pa-4 pt-2">
        <v-spacer />
        <v-btn
          variant="text"
          :disabled="loading"
          @click="cancel"
        >
          {{ cancelLabel }}
        </v-btn>
        <v-btn
          :color="confirmColor"
          :variant="confirmVariant"
          :disabled="!canConfirm"
          :loading="loading"
          @click="confirm"
        >
          <v-icon v-if="confirmIcon" start>{{ confirmIcon }}</v-icon>
          {{ confirmLabel }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  // Dialog-Inhalt
  title: {
    type: String,
    required: true
  },
  message: {
    type: String,
    required: true
  },

  // Icon-Konfiguration
  icon: {
    type: String,
    default: 'mdi-alert'
  },
  iconColor: {
    type: String,
    default: 'warning'
  },

  // Bestaetigen-Button
  confirmLabel: {
    type: String,
    default: 'Bestaetigen'
  },
  confirmColor: {
    type: String,
    default: 'primary'
  },
  confirmVariant: {
    type: String,
    default: 'elevated'
  },
  confirmIcon: {
    type: String,
    default: null
  },

  // Abbrechen-Button
  cancelLabel: {
    type: String,
    default: 'Abbrechen'
  },

  // Zusaetzliche Bestaetigung (Checkbox)
  requireConfirmation: {
    type: Boolean,
    default: false
  },
  confirmationLabel: {
    type: String,
    default: 'Ich verstehe die Konsequenzen'
  },

  // Text-Bestaetigung (z.B. 'DESTROY' eintippen)
  requireTextConfirmation: {
    type: String,
    default: null
  },

  // Loading-State
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])

const modelValue = defineModel({ type: Boolean, default: false })
const confirmed = ref(false)
const textConfirmInput = ref('')

// Computed: Kann bestaetigt werden?
const canConfirm = computed(() => {
  if (props.requireTextConfirmation) {
    return textConfirmInput.value === props.requireTextConfirmation
  }
  if (props.requireConfirmation) {
    return confirmed.value
  }
  return true
})

// Reset state wenn Dialog geschlossen wird
watch(modelValue, (newVal) => {
  if (!newVal) {
    confirmed.value = false
    textConfirmInput.value = ''
  }
})

function confirm() {
  emit('confirm')
}

function cancel() {
  confirmed.value = false
  textConfirmInput.value = ''
  emit('cancel')
  modelValue.value = false
}
</script>
