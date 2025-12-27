<template>
  <v-container fluid>
    <!-- Zone 1: Alert Banner (nur wenn Alerts vorhanden) -->
    <AlertBanner :alerts="dashboardAlerts" @dismiss="handleAlertDismiss" />

    <!-- Zone 2: Statistik-Karten (klickbar mit Navigation) -->
    <v-row>
      <v-col cols="6" sm="3">
        <StatCard
          :value="stats.vms"
          label="VMs"
          icon="mdi-server-network"
          color="primary"
          to="/terraform"
        />
      </v-col>
      <v-col cols="6" sm="3">
        <StatCard
          :value="stats.hosts"
          label="Hosts"
          icon="mdi-server"
          color="secondary"
          to="/inventory"
        />
      </v-col>
      <v-col cols="6" sm="3">
        <StatCard
          :value="stats.playbooks"
          label="Playbooks"
          icon="mdi-script-text"
          color="info"
          to="/playbooks"
        />
      </v-col>
      <v-col cols="6" sm="3">
        <StatCard
          :value="stats.executions"
          label="Ausführungen"
          icon="mdi-play-circle"
          color="success"
          to="/executions"
        />
      </v-col>
    </v-row>

    <!-- Zone 3: Cluster Kapazität -->
    <v-row class="mt-2">
      <v-col cols="12">
        <v-card>
          <v-card-title class="pb-0 d-flex align-center">
            <v-icon start>mdi-gauge</v-icon>
            Cluster Auslastung
            <v-chip
              v-if="proxmoxNodes.length > 0"
              size="x-small"
              color="success"
              variant="tonal"
              class="ml-2"
            >
              {{ proxmoxNodes.filter(n => n.status === 'online').length }}/{{ proxmoxNodes.length }} online
            </v-chip>
            <v-spacer />
            <v-btn
              variant="text"
              size="small"
              to="/capacity"
            >
              Details
              <v-icon end size="small">mdi-arrow-right</v-icon>
            </v-btn>
          </v-card-title>
          <v-card-text>
            <template v-if="proxmoxNodes.length > 0">
              <v-row>
                <v-col cols="12" md="4">
                  <CapacityGauge
                    :value="clusterCapacity.cpu"
                    label="CPU"
                    icon="mdi-chip"
                    :subtitle="clusterCapacity.cpuInfo || 'Keine Daten'"
                  />
                </v-col>
                <v-col cols="12" md="4">
                  <CapacityGauge
                    :value="clusterCapacity.memory"
                    label="Arbeitsspeicher"
                    icon="mdi-memory"
                    :subtitle="clusterCapacity.memoryInfo || 'Keine Daten'"
                  />
                </v-col>
                <v-col cols="12" md="4">
                  <CapacityGauge
                    :value="clusterCapacity.storage"
                    label="Speicher"
                    icon="mdi-harddisk"
                    :subtitle="clusterCapacity.storageInfo || 'Nicht verfuegbar'"
                  />
                </v-col>
              </v-row>
            </template>
            <div v-else class="text-center text-grey py-4">
              <v-icon size="48" color="grey-lighten-2">mdi-server-network-off</v-icon>
              <p class="mt-2">Keine Proxmox-Nodes konfiguriert</p>
              <v-btn
                variant="text"
                size="small"
                color="primary"
                to="/settings"
              >
                Proxmox einrichten
              </v-btn>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Zone 4: Quick Actions + Recent Executions -->
    <v-row class="mt-2">
      <!-- Quick Actions (kompakt) -->
      <v-col cols="12" md="4">
        <v-card>
          <v-card-title class="py-2">
            <v-icon start size="small">mdi-lightning-bolt</v-icon>
            Schnellzugriff
          </v-card-title>
          <v-list density="compact" class="py-0">
            <v-list-item
              prepend-icon="mdi-server-plus"
              title="Neue VM"
              @click="$router.push('/terraform?action=create')"
            />
            <v-list-item
              prepend-icon="mdi-play"
              title="Playbook ausführen"
              @click="$router.push('/executions?new=1')"
            />
            <v-list-item
              prepend-icon="mdi-sync"
              title="Proxmox Sync"
              @click="$router.push('/netbox?tab=prefixes')"
            />
            <v-list-item
              prepend-icon="mdi-broom"
              title="Aufräumen"
              @click="showCleanupDialog = true"
            />
          </v-list>
        </v-card>
      </v-col>

      <!-- Recent Executions -->
      <v-col cols="12" md="8">
        <v-card>
          <v-card-title class="py-2 d-flex align-center">
            <v-icon start size="small">mdi-history</v-icon>
            Letzte Ausführungen
            <v-spacer />
            <v-btn variant="text" size="small" to="/executions">
              Alle anzeigen
            </v-btn>
          </v-card-title>
          <v-data-table
            v-if="recentExecutions.length"
            :headers="executionHeaders"
            :items="recentExecutions"
            density="compact"
            :items-per-page="-1"
            hide-default-footer
            @click:row="(_, { item }) => $router.push(`/executions/${item.id}`)"
            class="cursor-pointer"
          >
            <template v-slot:item.status="{ item }">
              <v-icon :color="getStatusColor(item.status)" size="small">
                {{ getStatusIcon(item.status) }}
              </v-icon>
            </template>
            <template v-slot:item.name="{ item }">
              {{ item.playbook_name || item.tf_action || '-' }}
            </template>
            <template v-slot:item.created_at="{ item }">
              <span class="text-caption text-no-wrap">{{ formatDate(item.created_at) }}</span>
            </template>
          </v-data-table>
          <v-card-text v-else class="text-center text-grey py-4">
            Keine Ausführungen vorhanden
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Cleanup Dialog -->
    <CleanupDialog
      v-model="showCleanupDialog"
      @cleaned="loadStats(); loadOrphanedVMs()"
    />
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/api/client'
import { formatDate, getStatusColor, getStatusIcon } from '@/utils/formatting'
import StatCard from '@/components/dashboard/StatCard.vue'
import CapacityGauge from '@/components/dashboard/CapacityGauge.vue'
import AlertBanner from '@/components/dashboard/AlertBanner.vue'
import CleanupDialog from '@/components/dashboard/CleanupDialog.vue'

const stats = ref({
  vms: 0,
  hosts: 0,
  playbooks: 0,
  executions: 0,
})

const showCleanupDialog = ref(false)

const recentExecutions = ref([])
const proxmoxNodes = ref([])
const orphanedVMs = ref([])
const netboxStatus = ref({ online: true })
const storageStats = ref({ total: 0, used: 0 })

const executionHeaders = [
  { title: '', key: 'status', width: '40px', sortable: false },
  { title: 'Name', key: 'name' },
  { title: 'Datum', key: 'created_at', width: '140px' },
]

// Cluster-Kapazitaet berechnet aus Proxmox Nodes
const clusterCapacity = computed(() => {
  if (proxmoxNodes.value.length === 0) {
    return { cpu: 0, memory: 0, storage: 0 }
  }

  const onlineNodes = proxmoxNodes.value.filter(n => n.status === 'online')
  if (onlineNodes.length === 0) {
    return { cpu: 0, memory: 0, storage: 0 }
  }

  const avgCpu = onlineNodes.reduce((sum, n) => sum + (n.cpu_usage || 0), 0) / onlineNodes.length
  const avgMemory = onlineNodes.reduce((sum, n) => sum + (n.memory_percent || 0), 0) / onlineNodes.length
  const totalCpus = onlineNodes.reduce((sum, n) => sum + (n.cpus || 0), 0)
  const totalRam = onlineNodes.reduce((sum, n) => sum + (n.ram_gb || 0), 0)

  // Storage-Berechnung (in TB fuer bessere Lesbarkeit bei Cluster-Groessen)
  const storageTotalTB = (storageStats.value.total / (1024 * 1024 * 1024 * 1024)).toFixed(1)
  const storageUsedTB = (storageStats.value.used / (1024 * 1024 * 1024 * 1024)).toFixed(1)
  const storagePercent = storageStats.value.total > 0
    ? Math.round((storageStats.value.used / storageStats.value.total) * 100)
    : 0

  return {
    cpu: Math.round(avgCpu),
    cpuInfo: `${totalCpus} vCPUs über ${onlineNodes.length} Nodes`,
    memory: Math.round(avgMemory),
    memoryInfo: `${totalRam} GB gesamt`,
    storage: storagePercent,
    storageInfo: storageStats.value.total > 0
      ? `${storageUsedTB} / ${storageTotalTB} TB`
      : 'Nicht verfuegbar',
  }
})

// Dashboard-Alerts generieren
const dashboardAlerts = computed(() => {
  const alerts = []

  if (orphanedVMs.value.length > 0) {
    alerts.push({
      id: 'orphaned-vms',
      type: 'warning',
      icon: 'mdi-alert',
      title: `${orphanedVMs.value.length} verwaiste VM(s) erkannt`,
      message: 'VMs im Terraform State, die nicht mehr in Proxmox existieren.',
      action: { label: 'Bereinigen', to: '/terraform?tab=orphaned' },
    })
  }

  if (!netboxStatus.value.online) {
    alerts.push({
      id: 'netbox-offline',
      type: 'error',
      icon: 'mdi-server-off',
      title: 'NetBox nicht erreichbar',
      message: 'IP-Adressverwaltung ist derzeit offline.',
      action: { label: 'NetBox pruefen', to: '/netbox' },
    })
  }

  const offlineNodes = proxmoxNodes.value.filter(n => n.status === 'offline')
  if (offlineNodes.length > 0) {
    alerts.push({
      id: 'nodes-offline',
      type: 'error',
      icon: 'mdi-server-off',
      title: `${offlineNodes.length} Proxmox Node(s) offline`,
      message: offlineNodes.map(n => n.name).join(', '),
    })
  }

  return alerts
})

function handleAlertDismiss(id) {
  // Alerts werden im AlertBanner selbst per localStorage dismissed
}

async function loadStats() {
  try {
    const [hosts, playbooks, executions, vms] = await Promise.all([
      api.get('/api/inventory/hosts'),
      api.get('/api/playbooks'),
      api.get('/api/executions?page_size=5'),
      api.get('/api/terraform/vms').catch(() => ({ data: [] })),
    ])

    stats.value = {
      vms: vms.data.length || 0,
      hosts: hosts.data.length,
      playbooks: playbooks.data.length,
      executions: executions.data.total,
    }

    recentExecutions.value = executions.data.items
  } catch (e) {
    console.error('Stats laden fehlgeschlagen:', e)
  }
}

async function loadProxmoxNodes() {
  try {
    const nodesResponse = await api.get('/api/terraform/nodes')
    const nodes = nodesResponse.data

    try {
      const statsResponse = await api.get('/api/terraform/nodes/stats')
      const nodeStats = statsResponse.data

      proxmoxNodes.value = nodes.map(node => {
        const stats = nodeStats.find(s => s.name === node.name)
        return {
          ...node,
          status: stats?.status || 'unknown',
          cpu_usage: stats?.cpu_usage || 0,
          memory_percent: stats?.memory_percent || 0,
        }
      })
    } catch (e) {
      proxmoxNodes.value = nodes.map(node => ({ ...node, status: 'unknown' }))
    }
  } catch (e) {
    console.error('Proxmox Nodes laden fehlgeschlagen:', e)
  }
}

async function loadOrphanedVMs() {
  try {
    const response = await api.get('/api/terraform/state/health/status')
    orphanedVMs.value = response.data.orphaned_vms || []
  } catch (e) {
    console.debug('Orphaned VMs check fehlgeschlagen:', e)
  }
}

async function loadNetboxStatus() {
  try {
    await api.get('/api/netbox/status')
    netboxStatus.value = { online: true }
  } catch (e) {
    netboxStatus.value = { online: false }
  }
}

async function loadStorageStats() {
  try {
    const response = await api.get('/api/terraform/storage')
    const pools = response.data || []

    // Aggregiere alle Storage-Pools
    const total = pools.reduce((sum, pool) => sum + (pool.total || 0), 0)
    const used = pools.reduce((sum, pool) => sum + (pool.used || 0), 0)

    storageStats.value = { total, used }
  } catch (e) {
    console.debug('Storage Stats laden fehlgeschlagen:', e)
  }
}

onMounted(() => {
  loadStats()
  loadProxmoxNodes()
  loadOrphanedVMs()
  loadNetboxStatus()
  loadStorageStats()
})
</script>

<style scoped>
.cursor-pointer :deep(tbody tr) {
  cursor: pointer;
}
</style>
