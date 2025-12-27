<template>
  <v-card
    :to="to"
    :hover="!!to"
    class="stat-card"
    :class="{ 'stat-card--clickable': !!to }"
  >
    <v-card-text class="d-flex align-center pa-4">
      <v-avatar :color="color" size="56" class="mr-4">
        <v-icon size="28" color="white">{{ icon }}</v-icon>
      </v-avatar>
      <div class="flex-grow-1">
        <div class="text-h4 font-weight-bold">{{ value }}</div>
        <div class="text-subtitle-1 text-medium-emphasis">{{ label }}</div>
      </div>
      <v-icon v-if="to" color="grey-lighten-1" class="stat-card__arrow">
        mdi-chevron-right
      </v-icon>
    </v-card-text>
  </v-card>
</template>

<script setup>
defineProps({
  /**
   * Anzuzeigender Wert (Zahl oder Text)
   */
  value: {
    type: [String, Number],
    required: true
  },
  /**
   * Beschreibender Text unter dem Wert
   */
  label: {
    type: String,
    required: true
  },
  /**
   * Material Design Icon Name
   */
  icon: {
    type: String,
    required: true
  },
  /**
   * Farbe des Icon-Avatars
   */
  color: {
    type: String,
    default: 'primary'
  },
  /**
   * Router-Link Ziel (macht Card klickbar)
   */
  to: {
    type: String,
    default: null
  }
})
</script>

<style scoped>
.stat-card--clickable {
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.stat-card--clickable:hover {
  transform: translateY(-2px);
}

.stat-card--clickable:hover .stat-card__arrow {
  color: rgba(var(--v-theme-primary), 1) !important;
  transform: translateX(4px);
}

.stat-card__arrow {
  transition: transform 0.15s ease, color 0.15s ease;
}
</style>
