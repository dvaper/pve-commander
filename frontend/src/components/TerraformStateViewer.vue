<template>
  <v-card>
    <v-toolbar flat density="compact">
      <v-icon class="ml-2 mr-2">mdi-database-eye</v-icon>
      <v-toolbar-title class="text-body-1">Terraform State</v-toolbar-title>
      <v-spacer></v-spacer>

      <v-text-field
        v-model="searchQuery"
        prepend-inner-icon="mdi-magnify"
        label="Suchen..."
        single-line
        hide-details
        density="compact"
        variant="outlined"
        style="max-width: 250px"
        class="mr-2"
        clearable
      />

      <v-btn
        icon
        size="small"
        variant="text"
        @click="checkHealth"
        :loading="checkingHealth"
        :disabled="loading"
        title="Auf verwaiste VMs prüfen"
      >
        <v-badge
          v-if="orphanedCount > 0"
          :content="orphanedCount"
          color="error"
          floating
        >
          <v-icon>mdi-alert-circle-check</v-icon>
        </v-badge>
        <v-icon v-else>mdi-shield-check</v-icon>
      </v-btn>

      <v-btn
        icon
        size="small"
        variant="text"
        @click="refreshState"
        :loading="refreshing"
        :disabled="loading"
        title="State aktualisieren"
      >
        <v-icon>mdi-cloud-sync</v-icon>
      </v-btn>

      <v-btn
        icon
        size="small"
        variant="text"
        @click="loadResources"
        :loading="loading"
        title="Neu laden"
      >
        <v-icon>mdi-refresh</v-icon>
      </v-btn>
    </v-toolbar>

    <!-- Warnung bei verwaisten VMs -->
    <v-alert
      v-if="orphanedVMs.length > 0"
      type="warning"
      variant="tonal"
      class="ma-2"
      closable
    >
      <div class="d-flex align-center">
        <div>
          <strong>{{ orphanedVMs.length }} verwaiste VM(s) im State</strong>
          <div class="text-caption">Diese VMs existieren nicht mehr in Proxmox</div>
        </div>
        <v-spacer></v-spacer>
        <v-btn
          size="small"
          variant="outlined"
          @click="showOrphanedDialog = true"
        >
          Details
        </v-btn>
      </div>
    </v-alert>

    <v-row no-gutters>
      <!-- Ressourcen-Liste (links) -->
      <v-col cols="12" md="5" lg="4">
        <v-list
          density="compact"
          class="resource-list"
          :style="{ maxHeight: '600px', overflowY: 'auto' }"
        >
          <v-list-subheader v-if="groupedResources.length > 0">
            {{ filteredResources.length }} Ressourcen
          </v-list-subheader>

          <template v-if="loading">
            <v-skeleton-loader type="list-item" v-for="n in 5" :key="n" />
          </template>

          <template v-else-if="groupedResources.length === 0">
            <v-list-item>
              <v-list-item-title class="text-grey">
                Keine Ressourcen im State
              </v-list-item-title>
            </v-list-item>
          </template>

          <template v-else>
            <v-list-group
              v-for="group in groupedResources"
              :key="group.module || '__root__'"
              :value="group.module || '__root__'"
            >
              <template v-slot:activator="{ props }">
                <v-list-item v-bind="props">
                  <template v-slot:prepend>
                    <v-icon size="small">mdi-puzzle</v-icon>
                  </template>
                  <v-list-item-title>
                    {{ group.module || '(Root)' }}
                    <v-chip size="x-small" class="ml-2">{{ group.resources.length }}</v-chip>
                  </v-list-item-title>
                </v-list-item>
              </template>

              <v-list-item
                v-for="resource in group.resources"
                :key="resource.address"
                :active="selectedResource?.address === resource.address"
                @click="selectResource(resource)"
                density="compact"
              >
                <template v-slot:prepend>
                  <v-icon size="small" :color="getResourceTypeColor(resource.type)">
                    {{ getResourceTypeIcon(resource.type) }}
                  </v-icon>
                </template>
                <v-list-item-title class="text-body-2">
                  {{ resource.name || resource.type }}
                </v-list-item-title>
                <v-list-item-subtitle class="text-caption">
                  {{ resource.type }}
                </v-list-item-subtitle>
              </v-list-item>
            </v-list-group>
          </template>
        </v-list>
      </v-col>

      <!-- Details (rechts) -->
      <v-col cols="12" md="7" lg="8">
        <v-sheet class="pa-4" :style="{ maxHeight: '600px', overflowY: 'auto' }">
          <template v-if="!selectedResource">
            <v-alert type="info" variant="tonal">
              Wähle eine Ressource aus der Liste, um Details anzuzeigen.
            </v-alert>
          </template>

          <template v-else-if="loadingDetails">
            <v-skeleton-loader type="article" />
          </template>

          <template v-else-if="resourceDetails">
            <div class="d-flex align-center mb-4">
              <div>
                <h3 class="text-h6">{{ selectedResource.name || selectedResource.type }}</h3>
                <code class="text-caption text-grey">{{ selectedResource.address }}</code>
              </div>
              <v-spacer></v-spacer>
              <v-btn
                v-if="isAdmin"
                color="error"
                variant="outlined"
                size="small"
                @click="confirmRemove"
                :loading="removing"
              >
                <v-icon start size="small">mdi-database-remove</v-icon>
                Aus State entfernen
              </v-btn>
            </div>

            <v-divider class="mb-4" />

            <!-- Ressourcen-Typ-spezifische Anzeige -->
            <template v-if="resourceDetails.data">
              <!-- VM-spezifische Infos -->
              <v-card v-if="isVMResource" variant="outlined" class="mb-4">
                <v-card-title class="text-body-1">
                  <v-icon start size="small">mdi-server</v-icon>
                  VM-Informationen
                </v-card-title>
                <v-card-text>
                  <v-table density="compact">
                    <tbody>
                      <tr v-if="vmInfo.name">
                        <td class="text-grey" width="150">Name</td>
                        <td>{{ vmInfo.name }}</td>
                      </tr>
                      <tr v-if="vmInfo.vmid">
                        <td class="text-grey">VMID</td>
                        <td>{{ vmInfo.vmid }}</td>
                      </tr>
                      <tr v-if="vmInfo.node">
                        <td class="text-grey">Node</td>
                        <td>{{ vmInfo.node }}</td>
                      </tr>
                      <tr v-if="vmInfo.ip">
                        <td class="text-grey">IP-Adresse</td>
                        <td><code>{{ vmInfo.ip }}</code></td>
                      </tr>
                      <tr v-if="vmInfo.cores">
                        <td class="text-grey">CPUs</td>
                        <td>{{ vmInfo.cores }} Kerne</td>
                      </tr>
                      <tr v-if="vmInfo.memory">
                        <td class="text-grey">RAM</td>
                        <td>{{ formatMemory(vmInfo.memory) }}</td>
                      </tr>
                      <tr v-if="vmInfo.disk">
                        <td class="text-grey">Festplatte</td>
                        <td>{{ vmInfo.disk }} GB</td>
                      </tr>
                    </tbody>
                  </v-table>
                </v-card-text>
              </v-card>

              <!-- Raw JSON -->
              <v-expansion-panels variant="accordion">
                <v-expansion-panel title="Raw State Data">
                  <v-expansion-panel-text>
                    <pre class="state-json text-caption">{{ formatJson(resourceDetails.data) }}</pre>
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>
            </template>

            <!-- Raw output fallback -->
            <template v-else-if="resourceDetails.raw">
              <pre class="state-json text-caption">{{ resourceDetails.raw }}</pre>
            </template>

            <!-- Error -->
            <template v-else-if="resourceDetails.error">
              <v-alert type="error" variant="tonal">
                {{ resourceDetails.error }}
              </v-alert>
            </template>
          </template>
        </v-sheet>
      </v-col>
    </v-row>

    <!-- Entfernen-Dialog -->
    <v-dialog v-model="removeDialog" max-width="500">
      <v-card>
        <v-card-title class="text-error">
          <v-icon start color="error">mdi-database-remove</v-icon>
          Ressource aus State entfernen
        </v-card-title>
        <v-card-text>
          <v-alert type="warning" variant="tonal" class="mb-4">
            Die Ressource wird nur aus dem Terraform State entfernt,
            <strong>nicht</strong> aus der Infrastruktur!
          </v-alert>
          <p class="mb-2">Ressource:</p>
          <code class="d-block pa-2 bg-grey-darken-3 rounded">{{ selectedResource?.address }}</code>
          <p class="mt-4 text-body-2 text-grey">
            Nach dem Entfernen wird Terraform diese Ressource nicht mehr verwalten.
            Bei einem erneuten Apply wird sie als "neu" erkannt.
          </p>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn @click="removeDialog = false">Abbrechen</v-btn>
          <v-btn
            color="error"
            variant="flat"
            @click="removeResource"
            :loading="removing"
          >
            Entfernen
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Verwaiste VMs Dialog -->
    <v-dialog v-model="showOrphanedDialog" max-width="700">
      <v-card>
        <v-card-title class="text-warning">
          <v-icon start color="warning">mdi-alert-circle</v-icon>
          Verwaiste VMs im Terraform State
        </v-card-title>
        <v-card-text>
          <v-alert type="info" variant="tonal" class="mb-4">
            Diese VMs sind im Terraform State, existieren aber nicht mehr in Proxmox.
            Sie sollten aus dem State entfernt werden.
          </v-alert>
          <v-table density="compact">
            <thead>
              <tr>
                <th>VM-Name</th>
                <th>VMID</th>
                <th>Node</th>
                <th>Aktion</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="vm in orphanedVMs" :key="vm.address">
                <td>{{ vm.vm_name || vm.module || '-' }}</td>
                <td>{{ vm.vmid || '-' }}</td>
                <td>{{ vm.node || '-' }}</td>
                <td>
                  <v-btn
                    size="small"
                    color="error"
                    variant="text"
                    :loading="removingOrphaned === vm.address"
                    @click="removeOrphanedVM(vm)"
                  >
                    <v-icon start size="small">mdi-delete</v-icon>
                    Entfernen
                  </v-btn>
                </td>
              </tr>
            </tbody>
          </v-table>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn @click="showOrphanedDialog = false">Schließen</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted, inject } from 'vue'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const showSnackbar = inject('showSnackbar')
const authStore = useAuthStore()

const loading = ref(false)
const loadingDetails = ref(false)
const refreshing = ref(false)
const removing = ref(false)
const resources = ref([])
const selectedResource = ref(null)
const resourceDetails = ref(null)
const searchQuery = ref('')
const removeDialog = ref(false)

// Orphaned VMs
const checkingHealth = ref(false)
const orphanedVMs = ref([])
const showOrphanedDialog = ref(false)
const removingOrphaned = ref(null)

const isAdmin = computed(() => authStore.isSuperAdmin)
const orphanedCount = computed(() => orphanedVMs.value.length)

// Ressourcen nach Modulen gruppieren
const groupedResources = computed(() => {
  const groups = {}

  for (const resource of filteredResources.value) {
    const key = resource.module || '__root__'
    if (!groups[key]) {
      groups[key] = {
        module: resource.module,
        resources: []
      }
    }
    groups[key].resources.push(resource)
  }

  // Nach Modul-Name sortieren
  return Object.values(groups).sort((a, b) => {
    if (!a.module) return -1
    if (!b.module) return 1
    return a.module.localeCompare(b.module)
  })
})

// Gefilterte Ressourcen
const filteredResources = computed(() => {
  if (!searchQuery.value) return resources.value

  const query = searchQuery.value.toLowerCase()
  return resources.value.filter(r =>
    r.address.toLowerCase().includes(query) ||
    r.module?.toLowerCase().includes(query) ||
    r.type?.toLowerCase().includes(query) ||
    r.name?.toLowerCase().includes(query)
  )
})

// Prüfen ob VM-Ressource
const isVMResource = computed(() => {
  if (!selectedResource.value) return false
  return selectedResource.value.type?.includes('vm') ||
         selectedResource.value.type?.includes('virtual_environment')
})

// VM-Informationen extrahieren
const vmInfo = computed(() => {
  if (!resourceDetails.value?.data) return {}

  const data = resourceDetails.value.data
  const values = data.values || data

  return {
    name: values.name || values.vm_name,
    vmid: values.vm_id || values.vmid,
    node: values.node_name || values.target_node,
    ip: extractIP(values),
    cores: extractCores(values),
    memory: extractMemory(values.memory),
    disk: extractDisk(values),
  }
})

function extractCores(values) {
  // CPU cores aus verschiedenen Strukturen
  // bpg/proxmox Provider: cpu ist ein Array mit Objekten
  if (Array.isArray(values.cpu) && values.cpu.length > 0) {
    return values.cpu[0].cores || null
  }
  if (values.cpu?.cores) return values.cpu.cores
  if (values.cores) return values.cores
  if (values.cpu && typeof values.cpu === 'number') return values.cpu
  return null
}

function extractIP(values) {
  // IP aus verschiedenen möglichen Stellen extrahieren

  // 1. BESTE QUELLE: ipv4_addresses vom QEMU Guest Agent (tatsächliche erreichbare IP)
  // Format: [[lo IPs], [eth0 IPs], [docker0 IPs], ...]
  // Wir nehmen die erste nicht-localhost, nicht-Docker IP
  if (Array.isArray(values.ipv4_addresses)) {
    for (const ifaceIps of values.ipv4_addresses) {
      if (Array.isArray(ifaceIps)) {
        for (const ip of ifaceIps) {
          // Überspringe localhost und Docker-Netzwerke
          if (ip &&
              !ip.startsWith('127.') &&
              !ip.startsWith('172.17.') &&
              !ip.startsWith('172.18.') &&
              !ip.startsWith('172.19.') &&
              !ip.startsWith('172.20.') &&
              !ip.startsWith('172.21.')) {
            return ip
          }
        }
      }
    }
  }

  // 2. Proxmox Provider (bpg/proxmoxve): initialization ist ein Array
  if (Array.isArray(values.initialization) && values.initialization.length > 0) {
    const init = values.initialization[0]
    if (Array.isArray(init?.ip_config) && init.ip_config.length > 0) {
      const ipConfig = init.ip_config[0]
      // ipv4 ist auch ein Array
      if (Array.isArray(ipConfig?.ipv4) && ipConfig.ipv4.length > 0) {
        const ipv4 = ipConfig.ipv4[0]
        if (ipv4?.address) {
          return ipv4.address.split('/')[0]
        }
      }
    }
  }

  // 3. Legacy/Cloud-Init: ipconfig0 String
  if (values.ipconfig0) {
    const match = values.ipconfig0.match(/ip=([^/,]+)/)
    return match ? match[1] : null
  }

  // 4. Direkte IP-Felder
  if (values.default_ipv4_address) {
    return values.default_ipv4_address
  }
  if (values.ip_address) {
    return values.ip_address.split('/')[0]
  }

  return null
}

function extractMemory(memory) {
  // Memory kann ein Array, Objekt oder direkt ein Wert sein
  if (memory === null || memory === undefined) {
    return null
  }
  // bpg/proxmox Provider: memory ist ein Array
  if (Array.isArray(memory) && memory.length > 0) {
    return memory[0].dedicated || memory[0].floating || null
  }
  if (typeof memory === 'number') {
    return memory
  }
  if (typeof memory === 'object') {
    return memory.dedicated || memory.floating || null
  }
  return null
}

function extractDisk(values) {
  // Disk-Größe aus verschiedenen Strukturen extrahieren
  // Proxmox Provider: disk ist ein Array mit Objekten die size enthalten
  if (values.disk && Array.isArray(values.disk) && values.disk.length > 0) {
    // Erste Disk nehmen (Hauptdisk)
    const firstDisk = values.disk[0]
    if (firstDisk.size) return firstDisk.size
  }
  // Alternativ: disk als Objekt mit size
  if (values.disk?.size) return values.disk.size
  // Fallback: scsi0 oder virtio0
  if (values.scsi0) {
    const match = values.scsi0.match(/size=(\d+)G?/)
    if (match) return parseInt(match[1])
  }
  if (values.virtio0) {
    const match = values.virtio0.match(/size=(\d+)G?/)
    if (match) return parseInt(match[1])
  }
  return null
}

async function loadResources() {
  loading.value = true
  try {
    const response = await api.get('/api/terraform/state')
    resources.value = response.data
    selectedResource.value = null
    resourceDetails.value = null
  } catch (e) {
    console.error('State laden fehlgeschlagen:', e)
    showSnackbar?.('State konnte nicht geladen werden', 'error')
  } finally {
    loading.value = false
  }
}

async function selectResource(resource) {
  selectedResource.value = resource
  loadingDetails.value = true
  resourceDetails.value = null

  try {
    const encodedAddress = encodeURIComponent(resource.address)
    const response = await api.get(`/api/terraform/state/${encodedAddress}`)
    resourceDetails.value = response.data
  } catch (e) {
    console.error('Details laden fehlgeschlagen:', e)
    resourceDetails.value = { error: e.response?.data?.detail || 'Fehler beim Laden' }
  } finally {
    loadingDetails.value = false
  }
}

async function refreshState() {
  refreshing.value = true
  try {
    await api.post('/api/terraform/state/refresh')
    showSnackbar?.('State aktualisiert', 'success')
    await loadResources()
  } catch (e) {
    console.error('Refresh fehlgeschlagen:', e)
    showSnackbar?.('State-Refresh fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    refreshing.value = false
  }
}

function confirmRemove() {
  removeDialog.value = true
}

async function removeResource() {
  if (!selectedResource.value) return

  removing.value = true
  try {
    const encodedAddress = encodeURIComponent(selectedResource.value.address)
    await api.delete(`/api/terraform/state/${encodedAddress}`)
    showSnackbar?.('Ressource aus State entfernt', 'success')
    removeDialog.value = false
    selectedResource.value = null
    resourceDetails.value = null
    await loadResources()
  } catch (e) {
    console.error('Entfernen fehlgeschlagen:', e)
    showSnackbar?.('Entfernen fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    removing.value = false
  }
}

async function checkHealth() {
  checkingHealth.value = true
  try {
    const response = await api.get('/api/terraform/state/health')
    orphanedVMs.value = response.data.orphaned_vms || []
    if (orphanedVMs.value.length > 0) {
      showSnackbar?.(`${orphanedVMs.value.length} verwaiste VM(s) gefunden`, 'warning')
    } else {
      showSnackbar?.('Alle VMs sind gesund', 'success')
    }
  } catch (e) {
    console.error('Health-Check fehlgeschlagen:', e)
    showSnackbar?.('Health-Check fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    checkingHealth.value = false
  }
}

async function removeOrphanedVM(vm) {
  removingOrphaned.value = vm.address
  try {
    const encodedAddress = encodeURIComponent(vm.address)
    await api.delete(`/api/terraform/state/${encodedAddress}`)
    showSnackbar?.(`VM "${vm.vm_name || vm.module}" aus State entfernt`, 'success')
    // VM aus Liste entfernen
    orphanedVMs.value = orphanedVMs.value.filter(v => v.address !== vm.address)
    // Ressourcen-Liste aktualisieren
    await loadResources()
    // Dialog schließen wenn keine verwaisten VMs mehr
    if (orphanedVMs.value.length === 0) {
      showOrphanedDialog.value = false
    }
  } catch (e) {
    console.error('Entfernen fehlgeschlagen:', e)
    showSnackbar?.('Entfernen fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    removingOrphaned.value = null
  }
}

function getResourceTypeIcon(type) {
  if (!type) return 'mdi-cube-outline'

  if (type.includes('vm') || type.includes('virtual')) return 'mdi-server'
  if (type.includes('network') || type.includes('vlan')) return 'mdi-lan'
  if (type.includes('disk') || type.includes('storage')) return 'mdi-harddisk'
  if (type.includes('firewall')) return 'mdi-shield'
  if (type.includes('dns')) return 'mdi-dns'

  return 'mdi-cube-outline'
}

function getResourceTypeColor(type) {
  if (!type) return 'grey'

  if (type.includes('vm') || type.includes('virtual')) return 'primary'
  if (type.includes('network')) return 'orange'
  if (type.includes('disk')) return 'cyan'
  if (type.includes('firewall')) return 'error'

  return 'grey'
}

function formatJson(obj) {
  return JSON.stringify(obj, null, 2)
}

function formatMemory(mb) {
  if (!mb) return '-'
  if (mb >= 1024) {
    return `${(mb / 1024).toFixed(1)} GB`
  }
  return `${mb} MB`
}

onMounted(() => {
  loadResources()
})

// Expose für Parent-Komponente
defineExpose({
  loadResources,
  refreshState
})
</script>

<style scoped>
.resource-list {
  border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.state-json {
  background: rgba(0, 0, 0, 0.2);
  padding: 12px;
  border-radius: 4px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  max-height: 70vh;
  min-height: 300px;
  overflow-y: auto;
}
</style>
