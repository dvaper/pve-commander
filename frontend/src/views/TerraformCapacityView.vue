<template>
  <v-container fluid class="pa-4">
    <v-row>
      <v-col cols="12">
        <div class="d-flex align-center mb-4">
          <v-btn
            icon
            variant="text"
            @click="$router.back()"
            class="mr-2"
          >
            <v-icon>mdi-arrow-left</v-icon>
          </v-btn>
          <div>
            <h1 class="text-h5">Cluster Kapazitaet</h1>
            <p class="text-caption text-grey">Ressourcen-Uebersicht des Proxmox Clusters</p>
          </div>
        </div>
      </v-col>
    </v-row>

    <CapacityDashboard />
  </v-container>
</template>

<script setup>
import CapacityDashboard from '@/components/CapacityDashboard.vue'
</script>
