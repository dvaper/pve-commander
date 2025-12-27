<template>
  <v-card>
    <v-toolbar flat density="compact">
      <v-icon class="ml-2 mr-2">mdi-history</v-icon>
      <v-toolbar-title class="text-body-1">
        {{ vmName ? `History: ${vmName}` : 'VM-History' }}
      </v-toolbar-title>
      <v-spacer></v-spacer>

      <v-select
        v-if="!vmName"
        v-model="filterAction"
        :items="actionOptions"
        label="Aktion"
        hide-details
        density="compact"
        variant="outlined"
        style="max-width: 150px"
        class="mr-2"
        clearable
      />

      <v-btn
        icon
        size="small"
        variant="text"
        @click="loadHistory"
        :loading="loading"
      >
        <v-icon>mdi-refresh</v-icon>
      </v-btn>
    </v-toolbar>

    <v-data-table
      :headers="headers"
      :items="history"
      :loading="loading"
      density="compact"
      :items-per-page="10"
      @click:row="openDetail"
      hover
    >
      <template v-slot:item.action="{ item }">
        <v-chip
          :color="getActionColor(item.action)"
          size="small"
          variant="flat"
        >
          <v-icon start size="small">{{ getActionIcon(item.action) }}</v-icon>
          {{ getActionLabel(item.action) }}
        </v-chip>
      </template>

      <template v-slot:item.created_at="{ item }">
        {{ formatDate(item.created_at) }}
      </template>

      <template v-slot:item.metadata="{ item }">
        <span v-if="item.metadata?.ip_address" class="text-caption">
          {{ item.metadata.ip_address }}
        </span>
        <span v-else class="text-grey">-</span>
      </template>

      <template v-slot:item.has_config_diff="{ item }">
        <v-icon v-if="item.has_config_diff" size="small" color="info">
          mdi-file-compare
        </v-icon>
      </template>

      <template v-slot:item.actions="{ item }">
        <v-btn
          icon
          size="small"
          variant="text"
          @click.stop="openDetail(null, { item })"
          title="Details anzeigen"
        >
          <v-icon size="18">mdi-eye</v-icon>
        </v-btn>
        <v-btn
          v-if="item.has_config_diff && isAdmin"
          icon
          size="small"
          variant="text"
          color="warning"
          @click.stop="confirmRollback(item)"
          title="Auf diesen Stand zurücksetzen"
        >
          <v-icon size="18">mdi-restore</v-icon>
        </v-btn>
      </template>

      <template v-slot:no-data>
        <div class="text-center pa-4">
          <v-icon size="48" color="grey">mdi-history</v-icon>
          <p class="mt-2">Keine History-Einträge vorhanden.</p>
        </div>
      </template>
    </v-data-table>

    <!-- Detail-Dialog -->
    <v-dialog v-model="detailDialog" max-width="800">
      <v-card v-if="selectedEntry">
        <v-toolbar flat density="compact" color="primary">
          <v-icon class="ml-2 mr-2">mdi-file-document</v-icon>
          <v-toolbar-title>History-Details</v-toolbar-title>
          <v-spacer></v-spacer>
          <v-btn icon @click="detailDialog = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-toolbar>

        <v-card-text class="pa-4">
          <v-row>
            <v-col cols="12" md="6">
              <v-list density="compact">
                <v-list-item>
                  <v-list-item-title class="text-caption text-grey">VM</v-list-item-title>
                  <v-list-item-subtitle>{{ selectedEntry.vm_name }}</v-list-item-subtitle>
                </v-list-item>
                <v-list-item>
                  <v-list-item-title class="text-caption text-grey">Aktion</v-list-item-title>
                  <v-list-item-subtitle>
                    <v-chip :color="getActionColor(selectedEntry.action)" size="small">
                      {{ getActionLabel(selectedEntry.action) }}
                    </v-chip>
                  </v-list-item-subtitle>
                </v-list-item>
                <v-list-item>
                  <v-list-item-title class="text-caption text-grey">Zeitpunkt</v-list-item-title>
                  <v-list-item-subtitle>{{ formatDate(selectedEntry.created_at) }}</v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </v-col>
            <v-col cols="12" md="6">
              <v-list density="compact">
                <v-list-item v-if="selectedEntry.metadata?.ip_address">
                  <v-list-item-title class="text-caption text-grey">IP-Adresse</v-list-item-title>
                  <v-list-item-subtitle>{{ selectedEntry.metadata.ip_address }}</v-list-item-subtitle>
                </v-list-item>
                <v-list-item v-if="selectedEntry.metadata?.vmid">
                  <v-list-item-title class="text-caption text-grey">VMID</v-list-item-title>
                  <v-list-item-subtitle>{{ selectedEntry.metadata.vmid }}</v-list-item-subtitle>
                </v-list-item>
                <v-list-item v-if="selectedEntry.metadata?.target_node || selectedEntry.metadata?.node">
                  <v-list-item-title class="text-caption text-grey">Node</v-list-item-title>
                  <v-list-item-subtitle>{{ selectedEntry.metadata.target_node || selectedEntry.metadata.node }}</v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </v-col>
          </v-row>

          <v-divider class="my-4"></v-divider>

          <!-- Konfigurations-Diff -->
          <template v-if="entryDetail?.tf_config_before || entryDetail?.tf_config_after">
            <h4 class="mb-2">Terraform-Konfiguration</h4>

            <v-tabs v-model="configTab" density="compact">
              <v-tab value="before" v-if="entryDetail?.tf_config_before">
                <v-icon start size="small">mdi-file-undo</v-icon>
                Vorher
              </v-tab>
              <v-tab value="after" v-if="entryDetail?.tf_config_after">
                <v-icon start size="small">mdi-file-check</v-icon>
                Nachher
              </v-tab>
            </v-tabs>

            <v-tabs-window v-model="configTab" class="mt-2">
              <v-tabs-window-item value="before" v-if="entryDetail?.tf_config_before">
                <pre class="config-view">{{ entryDetail.tf_config_before }}</pre>
              </v-tabs-window-item>
              <v-tabs-window-item value="after" v-if="entryDetail?.tf_config_after">
                <pre class="config-view">{{ entryDetail.tf_config_after }}</pre>
              </v-tabs-window-item>
            </v-tabs-window>
          </template>

          <v-alert v-else type="info" variant="tonal">
            Keine Konfigurationsänderungen für diesen Eintrag verfügbar.
          </v-alert>
        </v-card-text>

        <v-card-actions v-if="entryDetail?.tf_config_before && isAdmin">
          <v-spacer></v-spacer>
          <v-btn @click="detailDialog = false">Schließen</v-btn>
          <v-btn
            color="warning"
            variant="flat"
            @click="confirmRollback(selectedEntry)"
          >
            <v-icon start>mdi-restore</v-icon>
            Auf diesen Stand zurücksetzen
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Rollback-Dialog -->
    <v-dialog v-model="rollbackDialog" max-width="500">
      <v-card>
        <v-card-title class="text-warning">
          <v-icon start color="warning">mdi-restore</v-icon>
          Konfiguration zurücksetzen
        </v-card-title>
        <v-card-text>
          <v-alert type="warning" variant="tonal" class="mb-4">
            Die Terraform-Konfiguration wird auf den Stand vor dieser Änderung zurückgesetzt.
          </v-alert>
          <p v-if="rollbackEntry">
            VM: <strong>{{ rollbackEntry.vm_name }}</strong><br>
            Stand von: <strong>{{ formatDate(rollbackEntry.created_at) }}</strong>
          </p>
          <p class="mt-4 text-body-2 text-grey">
            Nach dem Rollback muss <strong>terraform apply</strong> ausgeführt werden,
            um die Änderungen in Proxmox anzuwenden.
          </p>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn @click="rollbackDialog = false">Abbrechen</v-btn>
          <v-btn
            color="warning"
            variant="flat"
            @click="executeRollback"
            :loading="rollingBack"
          >
            Zurücksetzen
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted, watch, inject } from 'vue'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { formatDate } from '@/utils/formatting'

const props = defineProps({
  vmName: {
    type: String,
    default: null,
  },
})

const emit = defineEmits(['rollback'])
const showSnackbar = inject('showSnackbar')
const authStore = useAuthStore()

const loading = ref(false)
const history = ref([])
const filterAction = ref(null)
const detailDialog = ref(false)
const selectedEntry = ref(null)
const entryDetail = ref(null)
const configTab = ref('after')
const rollbackDialog = ref(false)
const rollbackEntry = ref(null)
const rollingBack = ref(false)

const isAdmin = computed(() => authStore.isSuperAdmin)

const headers = computed(() => {
  const cols = [
    { title: 'ID', key: 'id', width: '60px' },
  ]

  if (!props.vmName) {
    cols.push({ title: 'VM', key: 'vm_name', width: '150px' })
  }

  cols.push(
    { title: 'Aktion', key: 'action', width: '130px' },
    { title: 'IP', key: 'metadata', width: '120px' },
    { title: 'Zeitpunkt', key: 'created_at', width: '180px' },
    { title: '', key: 'has_config_diff', width: '50px', sortable: false },
    { title: '', key: 'actions', width: '100px', sortable: false },
  )

  return cols
})

const actionOptions = [
  { title: 'Erstellt', value: 'created' },
  { title: 'Deployed', value: 'deployed' },
  { title: 'Destroyed', value: 'destroyed' },
  { title: 'Importiert', value: 'imported' },
  { title: 'Rollback', value: 'rollback' },
]

async function loadHistory() {
  loading.value = true
  try {
    let url = props.vmName
      ? `/api/terraform/vms/${props.vmName}/history`
      : '/api/terraform/history'

    const params = new URLSearchParams()
    if (filterAction.value) params.append('action', filterAction.value)
    if (params.toString()) url += `?${params.toString()}`

    const response = await api.get(url)
    history.value = response.data
  } catch (e) {
    console.error('History laden fehlgeschlagen:', e)
    showSnackbar?.('History konnte nicht geladen werden', 'error')
  } finally {
    loading.value = false
  }
}

async function openDetail(event, { item }) {
  selectedEntry.value = item
  entryDetail.value = null
  configTab.value = item.action === 'destroyed' ? 'before' : 'after'
  detailDialog.value = true

  // Details laden
  try {
    const response = await api.get(`/api/terraform/history/${item.id}`)
    entryDetail.value = response.data
  } catch (e) {
    console.error('Detail laden fehlgeschlagen:', e)
  }
}

function confirmRollback(entry) {
  rollbackEntry.value = entry
  rollbackDialog.value = true
  detailDialog.value = false
}

async function executeRollback() {
  if (!rollbackEntry.value) return

  rollingBack.value = true
  try {
    const response = await api.post(`/api/terraform/history/${rollbackEntry.value.id}/rollback`)
    showSnackbar?.(response.data.message, 'success')
    rollbackDialog.value = false
    emit('rollback', response.data)
    await loadHistory()
  } catch (e) {
    console.error('Rollback fehlgeschlagen:', e)
    showSnackbar?.('Rollback fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    rollingBack.value = false
  }
}

function getActionColor(action) {
  const colors = {
    created: 'success',
    deployed: 'primary',
    destroyed: 'error',
    imported: 'info',
    config_changed: 'warning',
    rollback: 'orange',
  }
  return colors[action] || 'grey'
}

function getActionIcon(action) {
  const icons = {
    created: 'mdi-plus-circle',
    deployed: 'mdi-rocket-launch',
    destroyed: 'mdi-delete',
    imported: 'mdi-import',
    config_changed: 'mdi-pencil',
    rollback: 'mdi-restore',
  }
  return icons[action] || 'mdi-circle'
}

function getActionLabel(action) {
  const labels = {
    created: 'Erstellt',
    deployed: 'Deployed',
    destroyed: 'Destroyed',
    imported: 'Importiert',
    config_changed: 'Geändert',
    rollback: 'Rollback',
  }
  return labels[action] || action
}

watch(filterAction, () => {
  loadHistory()
})

watch(() => props.vmName, () => {
  loadHistory()
})

onMounted(() => {
  loadHistory()
})

defineExpose({ loadHistory })
</script>

<style scoped>
.config-view {
  background: rgba(0, 0, 0, 0.2);
  padding: 12px;
  border-radius: 4px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  max-height: 300px;
  overflow-y: auto;
}
</style>
