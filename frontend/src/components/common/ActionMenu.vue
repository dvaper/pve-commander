<template>
  <v-menu
    v-model="menuOpen"
    :close-on-content-click="false"
    location="bottom end"
  >
    <template v-slot:activator="{ props }">
      <v-btn
        v-bind="props"
        icon
        size="small"
        variant="text"
        :disabled="disabled"
      >
        <v-icon>mdi-dots-vertical</v-icon>
      </v-btn>
    </template>

    <v-list density="compact" min-width="200">
      <template v-for="(group, groupIndex) in groupedActions" :key="groupIndex">
        <!-- Group Header (optional) -->
        <v-list-subheader v-if="group.label" class="text-uppercase">
          {{ group.label }}
        </v-list-subheader>

        <!-- Actions in Group -->
        <v-list-item
          v-for="action in group.items"
          :key="action.key"
          :disabled="action.disabled || loadingAction === action.key"
          @click="executeAction(action)"
        >
          <template v-slot:prepend>
            <v-progress-circular
              v-if="loadingAction === action.key"
              indeterminate
              size="20"
              width="2"
              class="mr-2"
            />
            <v-icon
              v-else
              :color="action.color"
              size="small"
            >
              {{ action.icon }}
            </v-icon>
          </template>
          <v-list-item-title :class="action.color ? `text-${action.color}` : ''">
            {{ action.label }}
          </v-list-item-title>
          <v-list-item-subtitle v-if="action.subtitle">
            {{ action.subtitle }}
          </v-list-item-subtitle>
        </v-list-item>

        <!-- Divider between groups -->
        <v-divider v-if="groupIndex < groupedActions.length - 1" class="my-1" />
      </template>

      <!-- Empty State -->
      <v-list-item v-if="groupedActions.length === 0">
        <v-list-item-title class="text-grey">
          Keine Aktionen verfuegbar
        </v-list-item-title>
      </v-list-item>
    </v-list>
  </v-menu>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  /**
   * Array of action groups
   * Each group: { label?: string, items: Action[] }
   * Each action: { key: string, label: string, icon: string, color?: string, disabled?: boolean, subtitle?: string }
   */
  actions: {
    type: Array,
    required: true,
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  loadingAction: {
    type: String,
    default: null,
  },
})

const emit = defineEmits(['action'])

const menuOpen = ref(false)

// Filter out empty groups and disabled-only groups
const groupedActions = computed(() => {
  return props.actions.filter(group => {
    if (!group.items || group.items.length === 0) return false
    // Keep group if at least one item is not disabled
    return group.items.some(item => !item.disabled)
  })
})

function executeAction(action) {
  if (action.disabled || props.loadingAction === action.key) return

  // Close menu for non-destructive actions
  if (!action.keepOpen) {
    menuOpen.value = false
  }

  emit('action', action.key, action)
}
</script>
