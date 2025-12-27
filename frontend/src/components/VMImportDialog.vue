<template>
  <v-dialog v-model="dialog" max-width="900" persistent>
    <v-card>
      <v-toolbar flat density="compact" color="primary">
        <v-icon class="ml-2 mr-2">mdi-import</v-icon>
        <v-toolbar-title>VM importieren</v-toolbar-title>
        <v-spacer></v-spacer>
        <v-btn icon @click="close" :disabled="importing || bulkImporting">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-toolbar>

      <v-card-text class="pa-4">
        <!-- Schritt 1: VM auswählen -->
        <template v-if="!selectedVM && !bulkImportMode">
          <v-alert type="info" variant="tonal" class="mb-4">
            Wähle VMs aus Proxmox zum Importieren in Terraform.
            <strong>Klick auf Zeile</strong> für Einzel-Import oder <strong>Checkboxen</strong> für Bulk-Import.
          </v-alert>

          <!-- Filter und Suche -->
          <v-row class="mb-4" dense>
            <v-col cols="12" md="4">
              <v-text-field
                v-model="searchQuery"
                prepend-inner-icon="mdi-magnify"
                label="Suchen..."
                hide-details
                density="compact"
                variant="outlined"
                clearable
              />
            </v-col>
            <v-col cols="12" md="3">
              <v-select
                v-model="filterNode"
                :items="nodeOptions"
                label="Node"
                hide-details
                density="compact"
                variant="outlined"
                clearable
              />
            </v-col>
            <v-col cols="12" md="2">
              <v-btn
                block
                variant="outlined"
                @click="loadUnmanagedVMs"
                :loading="loading"
              >
                <v-icon start>mdi-refresh</v-icon>
                Scan
              </v-btn>
            </v-col>
            <v-col cols="12" md="3">
              <v-btn
                v-if="selectedVMs.length > 0"
                block
                color="primary"
                @click="openBulkImport"
              >
                <v-icon start>mdi-import</v-icon>
                {{ selectedVMs.length }} VMs importieren
              </v-btn>
            </v-col>
          </v-row>

          <!-- VM-Liste mit Checkboxen -->
          <v-data-table
            v-model="selectedVMs"
            :headers="headers"
            :items="filteredVMs"
            :loading="loading"
            density="compact"
            :items-per-page="10"
            class="elevation-1"
            @click:row="selectVM"
            hover
            show-select
            item-value="vmid"
          >
            <template v-slot:item.status="{ item }">
              <v-chip
                :color="item.status === 'running' ? 'success' : 'grey'"
                size="small"
              >
                {{ item.status }}
              </v-chip>
            </template>

            <template v-slot:item.ip_address="{ item }">
              <code v-if="item.ip_address">{{ item.ip_address }}</code>
              <v-chip v-else size="x-small" color="warning" variant="flat">
                <v-icon start size="x-small">mdi-alert</v-icon>
                Keine IP
              </v-chip>
            </template>

            <template v-slot:item.maxmem="{ item }">
              {{ formatMemory(item.maxmem) }}
            </template>

            <template v-slot:item.maxdisk="{ item }">
              {{ formatDisk(item.maxdisk) }}
            </template>

            <template v-slot:item.actions="{ item }">
              <v-btn
                icon
                size="small"
                variant="text"
                color="primary"
                @click.stop="selectVM(null, { item })"
                title="Einzeln importieren"
              >
                <v-icon>mdi-chevron-right</v-icon>
              </v-btn>
            </template>

            <template v-slot:no-data>
              <div class="text-center pa-4">
                <v-icon size="48" color="grey">mdi-check-circle-outline</v-icon>
                <p class="mt-2">Alle VMs werden bereits von Terraform verwaltet.</p>
              </div>
            </template>
          </v-data-table>
        </template>

        <!-- Bulk Import Konfiguration -->
        <template v-if="bulkImportMode">
          <v-btn
            variant="text"
            size="small"
            class="mb-4"
            @click="closeBulkImport"
            :disabled="bulkImporting"
          >
            <v-icon start>mdi-arrow-left</v-icon>
            Zurück zur Auswahl
          </v-btn>

          <v-alert type="info" variant="tonal" class="mb-4">
            <strong>{{ selectedVMs.length }} VMs</strong> werden importiert.
            Die VMs werden mit ihrem aktuellen Namen importiert.
          </v-alert>

          <!-- VMs ohne IP Warnung -->
          <v-alert v-if="vmsWithoutIP.length > 0" type="warning" variant="tonal" class="mb-4">
            <strong>{{ vmsWithoutIP.length }} VMs ohne erkennbare IP:</strong>
            {{ vmsWithoutIP.map(vm => vm.name).join(', ') }}
            <br><small>Diese VMs können importiert werden, aber die IP muss manuell konfiguriert werden.</small>
          </v-alert>

          <!-- Bulk Import Einstellungen -->
          <v-card variant="outlined" class="mb-4">
            <v-card-title class="text-body-1">
              <v-icon start size="small">mdi-cog</v-icon>
              Import-Einstellungen (für alle VMs)
            </v-card-title>
            <v-card-text>
              <v-row>
                <v-col cols="12" md="6">
                  <v-select
                    v-model="bulkConfig.ansible_group"
                    :items="ansibleGroups"
                    label="Ansible-Gruppe"
                    hint="Optional: Alle VMs in diese Gruppe aufnehmen"
                    persistent-hint
                    variant="outlined"
                    density="compact"
                    clearable
                  />
                </v-col>
                <v-col cols="12" md="6">
                  <v-checkbox
                    v-model="bulkConfig.register_netbox"
                    label="IPs in NetBox registrieren (falls noch nicht vorhanden)"
                    hide-details
                    density="compact"
                  />
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <!-- Zu importierende VMs Liste -->
          <v-card variant="outlined">
            <v-card-title class="text-body-1">
              <v-icon start size="small">mdi-server-network</v-icon>
              Zu importierende VMs
            </v-card-title>
            <v-card-text class="pa-0">
              <v-table density="compact">
                <thead>
                  <tr>
                    <th>VMID</th>
                    <th>Name</th>
                    <th>Node</th>
                    <th>IP</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="vmid in selectedVMs" :key="vmid">
                    <td>{{ getVMByVmid(vmid)?.vmid }}</td>
                    <td>{{ getVMByVmid(vmid)?.name }}</td>
                    <td>{{ getVMByVmid(vmid)?.node }}</td>
                    <td>
                      <code v-if="getVMByVmid(vmid)?.ip_address">{{ getVMByVmid(vmid)?.ip_address }}</code>
                      <v-chip v-else size="x-small" color="warning">Keine IP</v-chip>
                    </td>
                    <td>
                      <v-chip v-if="bulkImportResults[vmid]"
                        :color="bulkImportResults[vmid].success ? 'success' : 'error'"
                        size="x-small"
                      >
                        {{ bulkImportResults[vmid].success ? 'OK' : 'Fehler' }}
                      </v-chip>
                      <span v-else-if="bulkImporting">
                        <v-progress-circular size="16" width="2" indeterminate />
                      </span>
                      <span v-else class="text-grey">Ausstehend</span>
                    </td>
                  </tr>
                </tbody>
              </v-table>
            </v-card-text>
          </v-card>

          <!-- Bulk Import Ergebnis -->
          <v-alert v-if="bulkImportComplete"
            :type="bulkImportFailed > 0 ? 'warning' : 'success'"
            variant="tonal"
            class="mt-4"
          >
            <strong>Import abgeschlossen:</strong>
            {{ bulkImportSuccessful }} erfolgreich, {{ bulkImportFailed }} fehlgeschlagen
          </v-alert>
        </template>

        <!-- Schritt 2: Einzel-Import Konfiguration -->
        <template v-if="selectedVM && !bulkImportMode">
          <v-btn
            variant="text"
            size="small"
            class="mb-4"
            @click="selectedVM = null"
            :disabled="importing"
          >
            <v-icon start>mdi-arrow-left</v-icon>
            Zurück zur Auswahl
          </v-btn>

          <v-row>
            <v-col cols="12" md="6">
              <v-card variant="outlined">
                <v-card-title class="text-body-1">
                  <v-icon start size="small">mdi-server</v-icon>
                  Ausgewählte VM
                </v-card-title>
                <v-card-text>
                  <v-table density="compact">
                    <tbody>
                      <tr>
                        <td class="text-grey">VMID</td>
                        <td>{{ selectedVM.vmid }}</td>
                      </tr>
                      <tr>
                        <td class="text-grey">Name</td>
                        <td>{{ selectedVM.name }}</td>
                      </tr>
                      <tr>
                        <td class="text-grey">Node</td>
                        <td>{{ selectedVM.node }}</td>
                      </tr>
                      <tr>
                        <td class="text-grey">Status</td>
                        <td>
                          <v-chip
                            :color="selectedVM.status === 'running' ? 'success' : 'grey'"
                            size="small"
                          >
                            {{ selectedVM.status }}
                          </v-chip>
                        </td>
                      </tr>
                      <tr>
                        <td class="text-grey">CPU</td>
                        <td>{{ selectedVM.maxcpu }} Kerne</td>
                      </tr>
                      <tr>
                        <td class="text-grey">RAM</td>
                        <td>{{ formatMemory(selectedVM.maxmem) }}</td>
                      </tr>
                      <tr>
                        <td class="text-grey">Disk</td>
                        <td>{{ formatDisk(selectedVM.maxdisk) }}</td>
                      </tr>
                    </tbody>
                  </v-table>
                </v-card-text>
              </v-card>
            </v-col>

            <v-col cols="12" md="6">
              <v-card variant="outlined">
                <v-card-title class="text-body-1">
                  <v-icon start size="small">mdi-cog</v-icon>
                  Import-Einstellungen
                </v-card-title>
                <v-card-text>
                  <v-text-field
                    v-model="importConfig.vm_name"
                    label="VM-Name (Terraform)"
                    hint="Name für die Terraform-Verwaltung"
                    persistent-hint
                    :rules="nameRules"
                    variant="outlined"
                    density="compact"
                    class="mb-3"
                  />

                  <v-select
                    v-model="importConfig.ansible_group"
                    :items="ansibleGroups"
                    label="Ansible-Gruppe"
                    hint="Optional: In Ansible-Inventory aufnehmen"
                    persistent-hint
                    variant="outlined"
                    density="compact"
                    clearable
                    class="mb-3"
                  />

                  <v-checkbox
                    v-model="importConfig.register_netbox"
                    label="IP in NetBox registrieren"
                    hide-details
                    density="compact"
                  />
                </v-card-text>
              </v-card>
            </v-col>
          </v-row>

          <v-alert v-if="importError" type="error" variant="tonal" class="mt-4">
            {{ importError }}
          </v-alert>

          <v-alert v-if="importSuccess" type="success" variant="tonal" class="mt-4">
            <strong>Import erfolgreich!</strong><br>
            VM {{ importSuccess.vm_name }} ({{ importSuccess.ip_address }}) wurde importiert.
          </v-alert>
        </template>
      </v-card-text>

      <v-divider></v-divider>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn @click="close" :disabled="importing || bulkImporting">
          {{ (importSuccess || bulkImportComplete) ? 'Schließen' : 'Abbrechen' }}
        </v-btn>
        <!-- Einzel-Import Button -->
        <v-btn
          v-if="selectedVM && !importSuccess && !bulkImportMode"
          color="primary"
          variant="flat"
          @click="executeImport"
          :loading="importing"
          :disabled="!isValidConfig"
        >
          <v-icon start>mdi-import</v-icon>
          Importieren
        </v-btn>
        <!-- Bulk-Import Button -->
        <v-btn
          v-if="bulkImportMode && !bulkImportComplete"
          color="primary"
          variant="flat"
          @click="executeBulkImport"
          :loading="bulkImporting"
        >
          <v-icon start>mdi-import</v-icon>
          {{ selectedVMs.length }} VMs importieren
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, inject, watch } from 'vue'
import api from '@/api/client'

const emit = defineEmits(['imported'])
const showSnackbar = inject('showSnackbar')

const dialog = ref(false)
const loading = ref(false)
const importing = ref(false)
const unmanagedVMs = ref([])
const selectedVM = ref(null)
const selectedVMs = ref([])
const searchQuery = ref('')
const filterNode = ref(null)
const importError = ref(null)
const importSuccess = ref(null)
const ansibleGroups = ref([])

// Bulk Import State
const bulkImportMode = ref(false)
const bulkImporting = ref(false)
const bulkImportResults = ref({})
const bulkImportComplete = ref(false)
const bulkImportSuccessful = ref(0)
const bulkImportFailed = ref(0)

const bulkConfig = ref({
  ansible_group: '',
  register_netbox: true,
})

const importConfig = ref({
  vm_name: '',
  ansible_group: '',
  register_netbox: true,
})

const headers = [
  { title: 'VMID', key: 'vmid', width: '80px' },
  { title: 'Name', key: 'name' },
  { title: 'Node', key: 'node', width: '100px' },
  { title: 'IP', key: 'ip_address', width: '130px' },
  { title: 'Status', key: 'status', width: '90px' },
  { title: 'CPU', key: 'maxcpu', width: '60px' },
  { title: 'RAM', key: 'maxmem', width: '80px' },
  { title: 'Disk', key: 'maxdisk', width: '80px' },
  { title: '', key: 'actions', sortable: false, width: '50px' },
]

const nameRules = [
  v => !!v || 'Name ist erforderlich',
  v => /^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$/.test(v) || 'Nur Kleinbuchstaben, Zahlen und Bindestriche',
]

const nodeOptions = computed(() => {
  const nodes = new Set(unmanagedVMs.value.map(vm => vm.node))
  return Array.from(nodes).sort()
})

const filteredVMs = computed(() => {
  let vms = unmanagedVMs.value

  if (filterNode.value) {
    vms = vms.filter(vm => vm.node === filterNode.value)
  }

  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    vms = vms.filter(vm =>
      vm.name.toLowerCase().includes(query) ||
      String(vm.vmid).includes(query) ||
      vm.node.toLowerCase().includes(query)
    )
  }

  return vms
})

const isValidConfig = computed(() => {
  if (!importConfig.value.vm_name) return false
  return /^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$/.test(importConfig.value.vm_name)
})

async function loadUnmanagedVMs() {
  loading.value = true
  try {
    const response = await api.get('/api/terraform/proxmox/vms/unmanaged')
    unmanagedVMs.value = response.data
  } catch (e) {
    console.error('VMs laden fehlgeschlagen:', e)
    showSnackbar?.('VMs konnten nicht geladen werden', 'error')
  } finally {
    loading.value = false
  }
}

async function loadAnsibleGroups() {
  try {
    const response = await api.get('/api/terraform/ansible-groups')
    ansibleGroups.value = response.data
      .filter(g => g.value) // Leere Gruppe ausfiltern
      .map(g => ({ title: g.label, value: g.value }))
  } catch (e) {
    console.error('Ansible-Gruppen laden fehlgeschlagen:', e)
  }
}

function selectVM(event, { item }) {
  selectedVM.value = item
  // Name vorschlagen (bereinigt)
  importConfig.value.vm_name = item.name
    .toLowerCase()
    .replace(/[^a-z0-9-]/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
  importError.value = null
  importSuccess.value = null
}

async function executeImport() {
  if (!selectedVM.value || !isValidConfig.value) return

  importing.value = true
  importError.value = null

  try {
    const response = await api.post('/api/terraform/import', {
      vmid: selectedVM.value.vmid,
      node: selectedVM.value.node,
      vm_name: importConfig.value.vm_name,
      ansible_group: importConfig.value.ansible_group || '',
      register_netbox: importConfig.value.register_netbox,
    })

    importSuccess.value = response.data
    showSnackbar?.(`VM '${response.data.vm_name}' erfolgreich importiert`, 'success')
    emit('imported', response.data)
  } catch (e) {
    console.error('Import fehlgeschlagen:', e)
    importError.value = e.response?.data?.detail || 'Import fehlgeschlagen'
  } finally {
    importing.value = false
  }
}

// Bulk Import Funktionen
function getVMByVmid(vmid) {
  return unmanagedVMs.value.find(vm => vm.vmid === vmid)
}

const vmsWithoutIP = computed(() => {
  return selectedVMs.value
    .map(vmid => getVMByVmid(vmid))
    .filter(vm => vm && !vm.ip_address)
})

function openBulkImport() {
  bulkImportMode.value = true
  bulkImportResults.value = {}
  bulkImportComplete.value = false
  bulkImportSuccessful.value = 0
  bulkImportFailed.value = 0
}

function closeBulkImport() {
  bulkImportMode.value = false
}

function sanitizeName(name) {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9-]/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
}

async function executeBulkImport() {
  if (selectedVMs.value.length === 0) return

  bulkImporting.value = true
  bulkImportResults.value = {}
  bulkImportSuccessful.value = 0
  bulkImportFailed.value = 0

  // VMs für Bulk-Import vorbereiten
  const vmsToImport = selectedVMs.value.map(vmid => {
    const vm = getVMByVmid(vmid)
    return {
      vmid: vm.vmid,
      node: vm.node,
      vm_name: sanitizeName(vm.name),
    }
  })

  try {
    const response = await api.post('/api/terraform/import/bulk', {
      vms: vmsToImport,
      ansible_group: bulkConfig.value.ansible_group || '',
      register_netbox: bulkConfig.value.register_netbox,
    })

    // Ergebnisse verarbeiten
    for (const result of response.data.results) {
      bulkImportResults.value[result.vmid] = result
    }

    bulkImportSuccessful.value = response.data.successful
    bulkImportFailed.value = response.data.failed
    bulkImportComplete.value = true

    if (response.data.successful > 0) {
      showSnackbar?.(`${response.data.successful} VMs erfolgreich importiert`, 'success')
      emit('imported', { bulk: true, count: response.data.successful })
    }
  } catch (e) {
    console.error('Bulk-Import fehlgeschlagen:', e)
    showSnackbar?.('Bulk-Import fehlgeschlagen', 'error')
  } finally {
    bulkImporting.value = false
  }
}

function formatMemory(bytes) {
  if (!bytes) return '-'
  const gb = bytes / (1024 * 1024 * 1024)
  if (gb >= 1) return `${gb.toFixed(1)} GB`
  const mb = bytes / (1024 * 1024)
  return `${mb.toFixed(0)} MB`
}

function formatDisk(bytes) {
  if (!bytes) return '-'
  const gb = bytes / (1024 * 1024 * 1024)
  return `${gb.toFixed(0)} GB`
}

function open() {
  dialog.value = true
  selectedVM.value = null
  selectedVMs.value = []
  importError.value = null
  importSuccess.value = null
  importConfig.value = {
    vm_name: '',
    ansible_group: '',
    register_netbox: true,
  }
  // Bulk Import State zurücksetzen
  bulkImportMode.value = false
  bulkImporting.value = false
  bulkImportResults.value = {}
  bulkImportComplete.value = false
  bulkImportSuccessful.value = 0
  bulkImportFailed.value = 0
  bulkConfig.value = {
    ansible_group: '',
    register_netbox: true,
  }
  loadUnmanagedVMs()
  loadAnsibleGroups()
}

function close() {
  dialog.value = false
}

defineExpose({ open, close })
</script>
