<template>
  <v-card>
    <v-toolbar flat density="compact">
      <v-icon class="ml-2 mr-2">mdi-chart-box</v-icon>
      <v-toolbar-title class="text-body-1">Cluster-Kapazität</v-toolbar-title>
      <v-spacer></v-spacer>
      <v-btn
        icon
        size="small"
        variant="text"
        @click="loadStats"
        :loading="loading"
      >
        <v-icon>mdi-refresh</v-icon>
      </v-btn>
    </v-toolbar>

    <v-card-text v-if="loading && !clusterStats">
      <v-skeleton-loader type="card"></v-skeleton-loader>
    </v-card-text>

    <v-card-text v-else-if="error">
      <v-alert type="error" variant="tonal" density="compact">
        {{ error }}
      </v-alert>
    </v-card-text>

    <v-card-text v-else-if="clusterStats">
      <!-- Cluster Overview -->
      <v-row class="mb-4">
        <v-col cols="6" md="3">
          <v-card variant="tonal" color="primary">
            <v-card-text class="text-center py-3">
              <div class="text-h4">{{ clusterStats.nodes_online }}/{{ clusterStats.nodes_total }}</div>
              <div class="text-caption">Nodes Online</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="6" md="3">
          <v-card variant="tonal" color="info">
            <v-card-text class="text-center py-3">
              <div class="text-h4">{{ clusterStats.vms_running }}/{{ clusterStats.vms_total }}</div>
              <div class="text-caption">VMs Running</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="6" md="3">
          <v-card variant="tonal" :color="getCpuColor(clusterStats.cpu_usage_avg)">
            <v-card-text class="text-center py-3">
              <div class="text-h4">{{ clusterStats.cpu_usage_avg.toFixed(1) }}%</div>
              <div class="text-caption">CPU ({{ clusterStats.cpu_total }} Kerne)</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="6" md="3">
          <v-card variant="tonal" :color="getMemoryColor(clusterStats.memory_percent)">
            <v-card-text class="text-center py-3">
              <div class="text-h4">{{ clusterStats.memory_percent.toFixed(1) }}%</div>
              <div class="text-caption">RAM ({{ formatBytes(clusterStats.memory_total) }})</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Divider -->
      <v-divider class="mb-4"></v-divider>

      <!-- Node Details -->
      <div class="text-subtitle-2 mb-3">
        <v-icon size="small" class="mr-1">mdi-server</v-icon>
        Nodes
      </div>

      <v-row>
        <v-col
          v-for="node in clusterStats.nodes"
          :key="node.name"
          cols="12"
          md="6"
          lg="4"
        >
          <v-card variant="outlined" class="node-card">
            <v-card-title class="py-2 px-3 d-flex align-center">
              <v-icon
                :color="node.status === 'online' ? 'success' : 'error'"
                size="small"
                class="mr-2"
              >
                {{ node.status === 'online' ? 'mdi-check-circle' : 'mdi-alert-circle' }}
              </v-icon>
              <span class="text-body-1">{{ node.name }}</span>
              <v-spacer></v-spacer>
              <v-chip
                :color="node.status === 'online' ? 'success' : 'error'"
                size="x-small"
                variant="flat"
              >
                {{ node.status }}
              </v-chip>
            </v-card-title>

            <v-card-text class="pt-0">
              <!-- CPU -->
              <div class="mb-3">
                <div class="d-flex justify-space-between text-caption mb-1">
                  <span>CPU</span>
                  <span>{{ node.cpu_usage.toFixed(1) }}% ({{ node.cpu_total }} Kerne)</span>
                </div>
                <v-progress-linear
                  :model-value="node.cpu_usage"
                  :color="getCpuColor(node.cpu_usage)"
                  height="8"
                  rounded
                ></v-progress-linear>
              </div>

              <!-- Memory -->
              <div class="mb-2">
                <div class="d-flex justify-space-between text-caption mb-1">
                  <span>RAM</span>
                  <span>{{ formatBytes(node.memory_used) }} / {{ formatBytes(node.memory_total) }}</span>
                </div>
                <v-progress-linear
                  :model-value="node.memory_percent"
                  :color="getMemoryColor(node.memory_percent)"
                  height="8"
                  rounded
                ></v-progress-linear>
              </div>

              <!-- Uptime -->
              <div class="text-caption text-medium-emphasis mt-2">
                <v-icon size="x-small" class="mr-1">mdi-clock-outline</v-icon>
                Uptime: {{ formatUptime(node.uptime) }}
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/api/client'

const loading = ref(false)
const error = ref(null)
const clusterStats = ref(null)

async function loadStats() {
  loading.value = true
  error.value = null

  try {
    const response = await api.get('/api/terraform/cluster/stats')
    clusterStats.value = response.data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Fehler beim Laden der Cluster-Statistiken'
    console.error('Fehler beim Laden der Cluster-Stats:', e)
  } finally {
    loading.value = false
  }
}

function getCpuColor(usage) {
  if (usage >= 90) return 'error'
  if (usage >= 70) return 'warning'
  return 'success'
}

function getMemoryColor(percent) {
  if (percent >= 90) return 'error'
  if (percent >= 70) return 'warning'
  return 'success'
}

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const gb = bytes / (1024 * 1024 * 1024)
  if (gb >= 1) {
    return `${gb.toFixed(1)} GB`
  }
  const mb = bytes / (1024 * 1024)
  return `${mb.toFixed(0)} MB`
}

function formatUptime(seconds) {
  if (!seconds) return 'Unbekannt'
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)

  if (days > 0) {
    return `${days}d ${hours}h`
  }
  if (hours > 0) {
    return `${hours}h ${minutes}m`
  }
  return `${minutes}m`
}

onMounted(() => {
  loadStats()
})

// Auto-refresh alle 30 Sekunden
let refreshInterval = null
onMounted(() => {
  refreshInterval = setInterval(() => {
    loadStats()
  }, 30000)
})

import { onUnmounted } from 'vue'
onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<style scoped>
.node-card {
  transition: box-shadow 0.2s;
}
.node-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
</style>
