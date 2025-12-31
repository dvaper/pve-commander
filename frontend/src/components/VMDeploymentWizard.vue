<template>
  <v-dialog v-model="dialog" max-width="800" persistent>
    <v-card>
      <v-toolbar color="primary" density="compact">
        <v-toolbar-title>Neue VM erstellen</v-toolbar-title>
        <v-spacer></v-spacer>
        <v-btn icon size="small" @click="close">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-toolbar>

      <v-stepper v-model="step" :items="steps" flat>
        <!-- Schritt 1: Basis -->
        <template v-slot:item.1>
          <v-card flat>
            <v-card-text>
              <!-- Vorlagen-Auswahl -->
              <div class="d-flex align-center">
                <v-select
                  v-model="selectedPreset"
                  :items="presets"
                  item-title="name"
                  item-value="id"
                  label="Vorlage verwenden (optional)"
                  prepend-inner-icon="mdi-file-document-multiple"
                  variant="outlined"
                  density="compact"
                  clearable
                  :loading="loadingPresets"
                  hint="Wähle eine Vorlage, um Felder automatisch zu befüllen"
                  persistent-hint
                  class="flex-grow-1"
                  @update:model-value="applyPreset"
                >
                  <template v-slot:item="{ item, props }">
                    <v-list-item v-bind="props">
                      <template v-slot:prepend>
                        <v-icon :color="item.raw.is_default ? 'primary' : 'grey'" size="small">
                          {{ item.raw.is_default ? 'mdi-star' : 'mdi-file-document-outline' }}
                        </v-icon>
                      </template>
                      <template v-slot:subtitle>
                        {{ item.raw.cores }} CPUs, {{ item.raw.memory_gb }} GB RAM, {{ item.raw.disk_size_gb }} GB Disk
                      </template>
                    </v-list-item>
                  </template>
                </v-select>
                <v-btn
                  icon
                  variant="text"
                  color="primary"
                  size="small"
                  class="ml-2"
                  @click="showTemplateCreateDialog = true"
                  title="Neue Vorlage erstellen"
                >
                  <v-icon>mdi-plus</v-icon>
                </v-btn>
              </div>

              <!-- Dialog fuer neue VM-Vorlage -->
              <TemplateCreateDialog
                v-model="showTemplateCreateDialog"
                @created="onTemplateCreated"
              />

              <v-divider class="my-4"></v-divider>

              <v-text-field
                v-model="config.name"
                label="VM-Name (Hostname)"
                prepend-inner-icon="mdi-server"
                hint="Nur Kleinbuchstaben, Zahlen und Bindestriche"
                :rules="[rules.required, rules.vmName]"
                variant="outlined"
                density="compact"
              ></v-text-field>

              <v-textarea
                v-model="config.description"
                label="Beschreibung"
                prepend-inner-icon="mdi-text"
                rows="2"
                variant="outlined"
                density="compact"
                class="mt-4"
              ></v-textarea>

              <v-select
                v-model="config.target_node"
                :items="nodes"
                item-title="label"
                item-value="name"
                label="Proxmox-Node"
                prepend-inner-icon="mdi-server-network"
                variant="outlined"
                density="compact"
                class="mt-4"
                @update:model-value="loadStoragePools"
              >
                <template v-slot:item="{ item, props }">
                  <v-list-item v-bind="props">
                    <template v-slot:subtitle>
                      {{ item.raw.cpus }} CPUs, {{ item.raw.ram_gb }} GB RAM
                    </template>
                  </v-list-item>
                </template>
              </v-select>

              <v-select
                v-model="config.template_id"
                :items="templates"
                item-title="label"
                item-value="vmid"
                label="VM-Template"
                prepend-inner-icon="mdi-content-copy"
                variant="outlined"
                density="compact"
                class="mt-4"
                :loading="loadingTemplates"
                hint="Cloud-Init Template für die VM"
                persistent-hint
              >
                <template v-slot:item="{ item, props }">
                  <v-list-item v-bind="props">
                    <template v-slot:subtitle>
                      VMID: {{ item.raw.vmid }} | Node: {{ item.raw.node }}
                    </template>
                  </v-list-item>
                </template>
              </v-select>

              <div class="d-flex align-center mt-4">
                <v-select
                  v-model="config.ansible_group"
                  :items="ansibleGroups"
                  item-title="label"
                  item-value="value"
                  label="Ansible-Inventar-Gruppe"
                  prepend-inner-icon="mdi-ansible"
                  variant="outlined"
                  density="compact"
                  hint="Nach erfolgreichem Deploy wird die VM automatisch ins Ansible-Inventar eingetragen"
                  persistent-hint
                  class="flex-grow-1"
                ></v-select>
                <v-btn
                  icon
                  variant="text"
                  color="primary"
                  size="small"
                  class="ml-2"
                  @click="showGroupCreateDialog = true"
                  title="Neue Gruppe erstellen"
                >
                  <v-icon>mdi-plus</v-icon>
                </v-btn>
              </div>

              <!-- Dialog für neue Ansible-Gruppe -->
              <GroupCreateDialog
                v-model="showGroupCreateDialog"
                :groups="inventoryGroups"
                @created="onGroupCreated"
              />

              <v-select
                v-model="config.cloud_init_profile"
                :items="cloudInitProfiles"
                item-title="label"
                item-value="value"
                label="Cloud-Init Profil"
                prepend-inner-icon="mdi-cloud-sync"
                variant="outlined"
                density="compact"
                class="mt-4"
                :loading="loadingCloudInit"
                hint="Vorkonfiguriertes Profil für automatische VM-Einrichtung"
                persistent-hint
              >
                <template v-slot:item="{ item, props }">
                  <v-list-item v-bind="props">
                    <template v-slot:subtitle>
                      {{ item.raw.description }}
                    </template>
                  </v-list-item>
                </template>
              </v-select>
            </v-card-text>
          </v-card>
        </template>

        <!-- Schritt 2: Ressourcen -->
        <template v-slot:item.2>
          <v-card flat>
            <v-card-text>
              <div class="text-subtitle-2 mb-2">
                <v-icon size="small" class="mr-1">mdi-chip</v-icon>
                CPU-Kerne: {{ config.cores }}
              </div>
              <v-slider
                v-model="config.cores"
                :min="1"
                :max="16"
                :step="1"
                thumb-label
                color="primary"
              ></v-slider>

              <div class="text-subtitle-2 mb-2 mt-4">
                <v-icon size="small" class="mr-1">mdi-memory</v-icon>
                RAM: {{ config.memory_gb }} GB
              </div>
              <v-slider
                v-model="config.memory_gb"
                :min="1"
                :max="64"
                :step="1"
                thumb-label
                color="primary"
              ></v-slider>

              <div class="text-subtitle-2 mb-2 mt-4">
                <v-icon size="small" class="mr-1">mdi-harddisk</v-icon>
                Disk-Größe: {{ config.disk_size_gb }} GB
              </div>
              <v-slider
                v-model="config.disk_size_gb"
                :min="10"
                :max="200"
                :step="10"
                thumb-label
                color="primary"
              ></v-slider>

              <v-select
                v-model="config.storage"
                :items="storagePools"
                item-title="label"
                item-value="id"
                label="Storage-Pool"
                prepend-inner-icon="mdi-database"
                variant="outlined"
                density="compact"
                class="mt-4"
                :loading="loadingStorage"
                hint="Speicherort für die VM-Disk"
                persistent-hint
              >
                <template v-slot:item="{ item, props }">
                  <v-list-item v-bind="props">
                    <template v-slot:subtitle>
                      {{ formatBytes(item.raw.available) }} frei von {{ formatBytes(item.raw.total) }}
                    </template>
                  </v-list-item>
                </template>
              </v-select>

              <!-- Ressourcen-Zusammenfassung -->
              <v-alert type="info" variant="tonal" density="compact" class="mt-4">
                <strong>{{ config.cores }}</strong> CPU-Kerne,
                <strong>{{ config.memory_gb }}</strong> GB RAM,
                <strong>{{ config.disk_size_gb }}</strong> GB Disk
                <span v-if="config.storage"> auf <strong>{{ config.storage }}</strong></span>
              </v-alert>
            </v-card-text>
          </v-card>
        </template>

        <!-- Schritt 3: Netzwerk -->
        <template v-slot:item.3>
          <v-card flat>
            <v-card-text>
              <v-select
                v-model="config.vlan"
                :items="vlans"
                item-title="label"
                item-value="id"
                label="VLAN"
                prepend-inner-icon="mdi-lan"
                variant="outlined"
                density="compact"
                @update:model-value="loadAvailableIPs"
              ></v-select>

              <v-radio-group v-model="ipMode" class="mt-4">
                <v-radio label="Automatisch (nächste freie IP)" value="auto"></v-radio>
                <v-radio label="Manuell eingeben" value="manual"></v-radio>
              </v-radio-group>

              <!-- IPAM nicht konfiguriert Warnung -->
              <v-alert
                v-if="ipamError"
                type="warning"
                variant="tonal"
                class="mt-2 mb-2"
              >
                <div>
                  <strong>NetBox IPAM nicht konfiguriert</strong><br>
                  <span class="text-caption">
                    Für dieses VLAN wurde noch kein Prefix in NetBox angelegt.
                    Bitte konfigurieren Sie die IP-Bereiche (Prefixes) direkt in NetBox.
                  </span>
                </div>
                <div class="mt-2">
                  <v-btn
                    v-if="netboxUrl"
                    color="warning"
                    variant="elevated"
                    size="small"
                    :href="netboxUrl + '/ipam/prefixes/add/'"
                    target="_blank"
                  >
                    <v-icon start>mdi-open-in-new</v-icon>
                    NetBox IPAM öffnen
                  </v-btn>
                </div>
              </v-alert>

              <v-select
                v-if="ipMode === 'auto'"
                v-model="selectedIP"
                :items="availableIPs"
                :item-title="ip => `${ip.address} (VMID: ${ip.vmid})`"
                item-value="address"
                label="Verfügbare IP-Adressen"
                prepend-inner-icon="mdi-ip-network"
                variant="outlined"
                density="compact"
                :loading="loadingIPs"
                :disabled="ipamError"
                class="mt-2"
                :hint="availableIPs.length === 0 && !loadingIPs && !ipamError ? 'Keine freien IPs im ausgewählten VLAN' : ''"
                persistent-hint
              ></v-select>

              <v-text-field
                v-if="ipMode === 'manual'"
                v-model="config.ip_address"
                label="IP-Adresse"
                prepend-inner-icon="mdi-ip-network"
                placeholder="10.0.0.xxx"
                :rules="[rules.ipAddress]"
                variant="outlined"
                density="compact"
                class="mt-2"
              ></v-text-field>

              <v-checkbox
                v-model="config.auto_reserve_ip"
                label="IP in NetBox reservieren"
                density="compact"
                class="mt-2"
              ></v-checkbox>
            </v-card-text>
          </v-card>
        </template>

        <!-- Schritt 4: Review -->
        <template v-slot:item.4>
          <v-card flat>
            <v-card-text>
              <!-- Zusammenfassung -->
              <v-table density="compact">
                <tbody>
                  <tr>
                    <td class="text-grey">Name</td>
                    <td><strong>{{ config.name }}</strong></td>
                  </tr>
                  <tr>
                    <td class="text-grey">Node</td>
                    <td>{{ config.target_node }}</td>
                  </tr>
                  <tr>
                    <td class="text-grey">IP-Adresse</td>
                    <td>{{ finalIP }}</td>
                  </tr>
                  <tr>
                    <td class="text-grey">VMID</td>
                    <td>{{ calculatedVMID }}</td>
                  </tr>
                  <tr>
                    <td class="text-grey">Template</td>
                    <td>{{ selectedTemplateName }}</td>
                  </tr>
                  <tr>
                    <td class="text-grey">Ressourcen</td>
                    <td>{{ config.cores }} CPUs, {{ config.memory_gb }} GB RAM, {{ config.disk_size_gb }} GB Disk</td>
                  </tr>
                  <tr>
                    <td class="text-grey">Storage</td>
                    <td>{{ config.storage || 'Nicht ausgewaehlt' }}</td>
                  </tr>
                  <tr>
                    <td class="text-grey">Ansible-Gruppe</td>
                    <td>
                      <v-chip v-if="config.ansible_group" size="small" color="primary" variant="outlined">
                        <v-icon start size="x-small">mdi-ansible</v-icon>
                        {{ config.ansible_group }}
                      </v-chip>
                      <span v-else class="text-grey-darken-1">Nicht ins Inventory aufnehmen</span>
                    </td>
                  </tr>
                  <tr>
                    <td class="text-grey">Cloud-Init Profil</td>
                    <td>
                      <v-chip v-if="config.cloud_init_profile" size="small" color="info" variant="outlined">
                        <v-icon start size="x-small">mdi-cloud-sync</v-icon>
                        {{ selectedCloudInitName }}
                      </v-chip>
                      <span v-else class="text-grey-darken-1">Keine Cloud-Init Konfiguration</span>
                    </td>
                  </tr>
                </tbody>
              </v-table>

              <!-- Validierung -->
              <v-alert
                v-if="validation && !validation.valid"
                type="error"
                variant="tonal"
                density="compact"
                class="mt-4"
              >
                <div v-for="error in validation.errors" :key="error">{{ error }}</div>
              </v-alert>

              <v-alert
                v-if="validation && validation.warnings?.length"
                type="warning"
                variant="tonal"
                density="compact"
                class="mt-4"
              >
                <div v-for="warning in validation.warnings" :key="warning">{{ warning }}</div>
              </v-alert>

              <!-- Terraform Preview -->
              <v-expansion-panels class="mt-4">
                <v-expansion-panel title="Terraform-Code Preview">
                  <v-expansion-panel-text>
                    <pre class="tf-preview">{{ preview?.content || 'Lade...' }}</pre>
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>
            </v-card-text>
          </v-card>
        </template>

        <!-- Actions -->
        <template v-slot:actions>
          <v-btn
            v-if="step > 1"
            variant="text"
            @click="step--"
          >
            Zurück
          </v-btn>
          <v-spacer></v-spacer>
          <v-btn
            v-if="step < 4"
            color="primary"
            variant="flat"
            @click="nextStep"
            :disabled="!canProceed"
          >
            Weiter
          </v-btn>
          <v-btn
            v-if="step === 4"
            color="success"
            variant="flat"
            @click="createVM"
            :loading="creating"
            :disabled="!canCreate"
          >
            <v-icon start>mdi-plus</v-icon>
            VM erstellen
          </v-btn>
        </template>
      </v-stepper>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import api from '@/api/client'
import GroupCreateDialog from './GroupCreateDialog.vue'
import TemplateCreateDialog from './TemplateCreateDialog.vue'

const emit = defineEmits(['created', 'close'])

const dialog = ref(false)
const step = ref(1)
const creating = ref(false)
const loadingIPs = ref(false)

const steps = [
  { title: 'Basis', value: 1 },
  { title: 'Ressourcen', value: 2 },
  { title: 'Netzwerk', value: 3 },
  { title: 'Review', value: 4 },
]

// Konfiguration
const config = ref({
  name: '',
  description: '',
  target_node: '',  // Wird dynamisch aus Cluster geladen
  template_id: null,  // Wird dynamisch aus Proxmox geladen
  storage: '',  // Wird dynamisch aus Proxmox geladen
  cores: 2,
  memory_gb: 2,
  disk_size_gb: 20,
  vlan: null,  // Wird dynamisch aus NetBox geladen
  ip_address: null,
  auto_reserve_ip: true,
  ansible_group: '',
  cloud_init_profile: '',
})

// Nodes, VLANs und Ansible-Gruppen
const nodes = ref([])
const vlans = ref([])
const ansibleGroups = ref([])
const templates = ref([])
const storagePools = ref([])
const cloudInitProfiles = ref([])
const availableIPs = ref([])
const selectedIP = ref(null)
const ipMode = ref('auto')
const ipamError = ref(false)
// NetBox URL: wird aus Settings geladen
const netboxUrl = ref(null)
const validation = ref(null)
const preview = ref(null)
const loadingTemplates = ref(false)
const loadingStorage = ref(false)
const loadingCloudInit = ref(false)

// VM-Vorlagen (Presets)
const presets = ref([])
const selectedPreset = ref(null)
const loadingPresets = ref(false)

// Gruppen-Dialog
const showGroupCreateDialog = ref(false)
const inventoryGroups = ref([])

// Template-Dialog
const showTemplateCreateDialog = ref(false)

// Validierungsregeln
const rules = {
  required: v => !!v || 'Pflichtfeld',
  vmName: v => /^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$/.test(v) || 'Nur Kleinbuchstaben, Zahlen und Bindestriche',
  ipAddress: v => !v || /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(v) || 'Ungültige IP-Adresse',
}

// Computed
const finalIP = computed(() => {
  if (ipMode.value === 'manual' && config.value.ip_address) {
    return config.value.ip_address
  }
  return selectedIP.value || '(wird automatisch gewählt)'
})

const calculatedVMID = computed(() => {
  const ip = ipMode.value === 'manual' ? config.value.ip_address : selectedIP.value
  if (!ip) return '-'
  const octets = ip.split('.')
  return parseInt(octets[2]) * 1000 + parseInt(octets[3])
})

const canProceed = computed(() => {
  switch (step.value) {
    case 1:
      return config.value.name && config.value.target_node && rules.vmName(config.value.name) === true
    case 2:
      return config.value.cores > 0 && config.value.memory_gb > 0 && config.value.disk_size_gb >= 10
    case 3:
      return ipMode.value === 'auto' ? !!selectedIP.value : !!config.value.ip_address
    default:
      return true
  }
})

const canCreate = computed(() => {
  return validation.value?.valid && preview.value
})

const selectedTemplateName = computed(() => {
  if (!config.value.template_id) return 'Standard (940001)'
  const template = templates.value.find(t => t.vmid === config.value.template_id)
  return template ? template.name : `VMID ${config.value.template_id}`
})

const selectedCloudInitName = computed(() => {
  if (!config.value.cloud_init_profile) return 'Keine'
  const profile = cloudInitProfiles.value.find(p => p.value === config.value.cloud_init_profile)
  return profile ? profile.name : config.value.cloud_init_profile
})

// Hilfsfunktion für Bytes-Formatierung
function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

// Methoden
async function open() {
  // Reset
  step.value = 1
  config.value = {
    name: '',
    description: '',
    target_node: '',  // Wird dynamisch geladen
    template_id: null,  // Wird dynamisch geladen
    storage: '',  // Wird dynamisch geladen
    cores: 2,
    memory_gb: 2,
    disk_size_gb: 20,
    vlan: null,  // Wird dynamisch geladen
    ip_address: null,
    auto_reserve_ip: true,
    ansible_group: '',
    cloud_init_profile: '',
  }
  selectedIP.value = null
  ipMode.value = 'auto'
  ipamError.value = false
  validation.value = null
  preview.value = null
  selectedPreset.value = null

  // Daten parallel laden fuer schnelleren Dialog-Aufbau
  await Promise.all([
    loadNodes(),
    loadVLANs(),
    loadAnsibleGroups(),
    loadCloudInitProfiles(),
    loadTemplates(),
    loadPresets(),  // ruft applyPreset() auf, das loadStoragePools() und loadAvailableIPs() triggert
    loadNetboxUrl(),
  ])

  // Fallback: IPs laden falls kein Default-Preset existiert
  // (loadAvailableIPs wird sonst nur durch applyPreset oder VLAN-Wechsel getriggert)
  if (availableIPs.value.length === 0 && config.value.vlan) {
    await loadAvailableIPs()
  }

  dialog.value = true
}

function close() {
  dialog.value = false
  emit('close')
}

async function loadNodes() {
  try {
    const response = await api.get('/api/terraform/nodes')
    nodes.value = response.data.map(n => ({
      ...n,
      label: `${n.name} (${n.cpus} CPUs, ${n.ram_gb} GB)`,
    }))
    // Ersten Node als Default setzen falls noch keiner gewählt
    if (nodes.value.length > 0 && !config.value.target_node) {
      config.value.target_node = nodes.value[0].name
      loadStoragePools()
    }
  } catch (e) {
    console.error('Nodes laden fehlgeschlagen:', e)
  }
}

async function loadVLANs() {
  try {
    const response = await api.get('/api/terraform/vlans')
    vlans.value = response.data.map(v => ({
      ...v,
      label: `VLAN ${v.id} - ${v.name} (${v.prefix})`,
    }))
  } catch (e) {
    console.error('VLANs laden fehlgeschlagen:', e)
  }
}

async function loadAnsibleGroups() {
  try {
    const response = await api.get('/api/terraform/ansible-groups')
    ansibleGroups.value = response.data
    // Für GroupCreateDialog: Alle Gruppen ohne "Keine"-Option
    inventoryGroups.value = response.data
      .filter(g => g.value !== '')
      .map(g => ({ name: g.value }))
  } catch (e) {
    console.error('Ansible-Gruppen laden fehlgeschlagen:', e)
    // Fallback mit Standard-Gruppen
    ansibleGroups.value = [
      { value: '', label: 'Nicht ins Inventory aufnehmen' },
    ]
    inventoryGroups.value = []
  }
}

async function onGroupCreated(groupName) {
  // Gruppen neu laden und die neue Gruppe auswählen
  await loadAnsibleGroups()
  config.value.ansible_group = groupName
}

async function onTemplateCreated(template) {
  // Vorlagen neu laden und die neue Vorlage auswaehlen
  await loadPresets()
  if (template?.id) {
    selectedPreset.value = template.id
    applyPreset(template.id)
  }
}

async function loadCloudInitProfiles() {
  loadingCloudInit.value = true
  try {
    const response = await api.get('/api/terraform/cloud-init/profiles')
    cloudInitProfiles.value = response.data.map(p => ({
      ...p,
      label: p.name,
      value: p.id,
    }))
  } catch (e) {
    console.error('Cloud-Init Profile laden fehlgeschlagen:', e)
    // Fallback mit Basis-Profilen
    cloudInitProfiles.value = [
      { value: '', label: 'Keine', description: 'Keine Cloud-Init Konfiguration' },
      { value: 'basic', label: 'Basic', description: 'SSH-Key, System-Updates, grundlegende Tools' },
    ]
  } finally {
    loadingCloudInit.value = false
  }
}

async function loadPresets() {
  loadingPresets.value = true
  try {
    const response = await api.get('/api/terraform/templates/presets')
    presets.value = response.data
    // Default-Preset automatisch anwenden, falls vorhanden
    const defaultPreset = presets.value.find(p => p.is_default)
    if (defaultPreset) {
      selectedPreset.value = defaultPreset.id
      applyPreset(defaultPreset.id)
    }
  } catch (e) {
    console.error('Vorlagen laden fehlgeschlagen:', e)
    presets.value = []
  } finally {
    loadingPresets.value = false
  }
}

function applyPreset(presetId) {
  if (!presetId) {
    // Wenn Vorlage abgewählt wird, nichts ändern
    return
  }
  const preset = presets.value.find(p => p.id === presetId)
  if (!preset) return

  // Felder aus Vorlage übernehmen
  config.value.cores = preset.cores
  config.value.memory_gb = preset.memory_gb
  config.value.disk_size_gb = preset.disk_size_gb
  config.value.vlan = preset.vlan

  if (preset.target_node) {
    config.value.target_node = preset.target_node
    loadStoragePools()
  }

  if (preset.ansible_group) {
    config.value.ansible_group = preset.ansible_group
  }

  if (preset.cloud_init_profile) {
    config.value.cloud_init_profile = preset.cloud_init_profile
  }

  // IPs für das gewählte VLAN neu laden
  loadAvailableIPs()
}

async function loadTemplates() {
  loadingTemplates.value = true
  try {
    const response = await api.get('/api/terraform/templates')
    templates.value = response.data.map(t => ({
      ...t,
      label: `${t.name} (VMID: ${t.vmid})`,
    }))
    // Erstes verfuegbares Template vorauswaehlen
    if (templates.value.length > 0) {
      config.value.template_id = templates.value[0].vmid
    }
  } catch (e) {
    console.error('Templates laden fehlgeschlagen:', e)
    templates.value = []
  } finally {
    loadingTemplates.value = false
  }
}

async function loadStoragePools() {
  loadingStorage.value = true
  try {
    const response = await api.get('/api/terraform/storage', {
      params: { node: config.value.target_node }
    })
    storagePools.value = response.data.map(s => ({
      ...s,
      label: `${s.id} (${s.type})`,
    }))
    // Erstes verfuegbares Storage vorauswaehlen
    if (storagePools.value.length > 0) {
      config.value.storage = storagePools.value[0].id
    }
  } catch (e) {
    console.error('Storage laden fehlgeschlagen:', e)
    storagePools.value = []
  } finally {
    loadingStorage.value = false
  }
}

async function loadAvailableIPs() {
  loadingIPs.value = true
  ipamError.value = false
  try {
    const response = await api.get(`/api/terraform/available-ips/${config.value.vlan}?limit=250`)
    availableIPs.value = response.data
    if (availableIPs.value.length > 0) {
      selectedIP.value = availableIPs.value[0].address
    }
  } catch (e) {
    console.error('IPs laden fehlgeschlagen:', e)
    availableIPs.value = []
    // Prüfen ob es ein "Prefix nicht gefunden" Fehler ist
    const errorMsg = e.response?.data?.detail || ''
    if (errorMsg.includes('Prefix') && errorMsg.includes('nicht')) {
      ipamError.value = true
    }
  } finally {
    loadingIPs.value = false
  }
}

async function loadNetboxUrl() {
  try {
    const response = await api.get('/api/settings/netbox-url')
    netboxUrl.value = response.data.url
  } catch (e) {
    console.error('NetBox URL laden fehlgeschlagen:', e)
  }
}

async function nextStep() {
  if (step.value === 3) {
    // Vor Review: Validieren und Preview laden
    await validateAndPreview()
  }
  step.value++
}

async function validateAndPreview() {
  const payload = {
    ...config.value,
    ip_address: ipMode.value === 'manual' ? config.value.ip_address : selectedIP.value,
  }

  try {
    // Validieren
    const valResponse = await api.post('/api/terraform/vms/validate', payload)
    validation.value = valResponse.data

    // Preview
    const prevResponse = await api.post('/api/terraform/vms/preview', payload)
    preview.value = prevResponse.data
  } catch (e) {
    console.error('Validierung fehlgeschlagen:', e)
    validation.value = { valid: false, errors: [e.response?.data?.detail || 'Fehler bei Validierung'] }
  }
}

async function createVM() {
  creating.value = true
  try {
    const payload = {
      ...config.value,
      ip_address: ipMode.value === 'manual' ? config.value.ip_address : selectedIP.value,
    }

    const response = await api.post('/api/terraform/vms', payload)
    emit('created', response.data)
    close()
  } catch (e) {
    console.error('VM erstellen fehlgeschlagen:', e)
    validation.value = { valid: false, errors: [e.response?.data?.detail || 'Fehler beim Erstellen'] }
  } finally {
    creating.value = false
  }
}

// Watch für IP-Modus
watch(ipMode, (newMode) => {
  if (newMode === 'auto' && availableIPs.value.length > 0) {
    selectedIP.value = availableIPs.value[0].address
  }
})

// Expose
defineExpose({ open })
</script>

<style scoped>
.tf-preview {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 4px;
  font-size: 11px;
  max-height: 300px;
  overflow: auto;
  white-space: pre-wrap;
}
</style>
