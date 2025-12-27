<template>
  <v-container fluid class="pa-4">
    <div class="d-flex align-center mb-4">
      <v-icon size="large" class="mr-3">mdi-clipboard-text-clock</v-icon>
      <div>
        <h1 class="text-h5">Audit-Log</h1>
        <p class="text-caption text-grey">Protokoll aller Benutzeraktionen und Systemereignisse</p>
      </div>
    </div>

    <AuditLogViewer />
  </v-container>
</template>

<script setup>
import AuditLogViewer from '@/components/AuditLogViewer.vue'
</script>
