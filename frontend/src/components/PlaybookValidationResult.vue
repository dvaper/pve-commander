<template>
  <div class="validation-result">
    <!-- Loading State -->
    <v-progress-linear
      v-if="loading"
      indeterminate
      color="primary"
      class="mb-2"
    />

    <!-- Kein Ergebnis -->
    <v-alert
      v-if="!loading && !result"
      type="info"
      variant="tonal"
      density="compact"
    >
      <v-icon start>mdi-information-outline</v-icon>
      Noch keine Validierung durchgeführt
    </v-alert>

    <!-- Erfolgreich -->
    <v-alert
      v-else-if="result?.valid"
      type="success"
      variant="tonal"
      density="compact"
    >
      <div class="d-flex align-center">
        <v-icon start>mdi-check-circle</v-icon>
        <span>Playbook ist valide</span>
      </div>

      <!-- Parsed Info anzeigen -->
      <div v-if="result.parsed_info" class="mt-2">
        <v-chip size="x-small" class="mr-1" color="primary" variant="outlined">
          {{ result.parsed_info.plays_count }} Play(s)
        </v-chip>
        <v-chip size="x-small" class="mr-1" color="secondary" variant="outlined">
          Hosts: {{ result.parsed_info.hosts?.join(', ') || 'all' }}
        </v-chip>
        <v-chip
          v-if="result.parsed_info.tasks?.length"
          size="x-small"
          class="mr-1"
          variant="outlined"
        >
          {{ result.parsed_info.tasks.length }} Task(s)
        </v-chip>
        <v-chip
          v-if="result.parsed_info.roles?.length"
          size="x-small"
          class="mr-1"
          variant="outlined"
        >
          {{ result.parsed_info.roles.length }} Role(s)
        </v-chip>
      </div>

      <!-- Warnungen -->
      <div v-if="result.warnings?.length" class="mt-2">
        <v-chip
          v-for="(warning, idx) in result.warnings"
          :key="idx"
          size="x-small"
          color="warning"
          variant="tonal"
          class="mr-1 mb-1"
        >
          <v-icon start size="x-small">mdi-alert</v-icon>
          {{ warning }}
        </v-chip>
      </div>
    </v-alert>

    <!-- YAML-Fehler -->
    <v-alert
      v-else-if="result && !result.yaml_valid"
      type="error"
      variant="tonal"
      density="compact"
    >
      <div class="d-flex align-center">
        <v-icon start>mdi-alert-circle</v-icon>
        <span class="font-weight-bold">YAML-Fehler</span>
      </div>
      <pre class="error-message mt-2">{{ result.yaml_error }}</pre>
    </v-alert>

    <!-- Ansible-Fehler -->
    <v-alert
      v-else-if="result && result.yaml_valid && !result.ansible_valid"
      type="warning"
      variant="tonal"
      density="compact"
    >
      <div class="d-flex align-center">
        <v-icon start>mdi-alert</v-icon>
        <span class="font-weight-bold">Ansible-Fehler</span>
      </div>
      <div class="d-flex align-center mt-1">
        <v-chip size="x-small" color="success" variant="tonal" class="mr-2">
          <v-icon start size="x-small">mdi-check</v-icon>
          YAML OK
        </v-chip>
      </div>
      <pre class="error-message mt-2">{{ result.ansible_error }}</pre>
    </v-alert>
  </div>
</template>

<script setup>
defineProps({
  result: {
    type: Object,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  }
})
</script>

<style scoped>
.validation-result {
  margin-top: 8px;
}

.error-message {
  font-family: monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  background: rgba(0, 0, 0, 0.1);
  padding: 8px;
  border-radius: 4px;
  max-height: 150px;
  overflow: auto;
}
</style>
