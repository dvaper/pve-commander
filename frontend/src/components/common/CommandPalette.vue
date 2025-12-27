<template>
  <v-dialog
    v-model="isOpen"
    max-width="600"
    :scrim="true"
    scrim-class="command-palette-scrim"
    transition="dialog-top-transition"
    @keydown.esc="close"
  >
    <v-card class="command-palette-card">
      <!-- Search Input -->
      <div class="command-palette-header">
        <v-icon class="mr-2" size="20" color="primary">mdi-magnify</v-icon>
        <input
          ref="searchInput"
          v-model="searchQuery"
          type="text"
          class="command-palette-input"
          placeholder="Suche nach Aktionen, VMs oder Navigation..."
          @keydown.down.prevent="navigateDown"
          @keydown.up.prevent="navigateUp"
          @keydown.enter.prevent="executeSelected"
        />
        <div class="command-palette-shortcut">
          <kbd>ESC</kbd>
        </div>
      </div>

      <v-divider />

      <!-- Results -->
      <div class="command-palette-results" ref="resultsContainer">
        <!-- No Results -->
        <div v-if="filteredActions.length === 0" class="command-palette-empty">
          <v-icon size="48" color="grey-lighten-1">mdi-magnify-close</v-icon>
          <p class="text-body-2 text-grey mt-2">Keine Ergebnisse gefunden</p>
        </div>

        <!-- Grouped Results -->
        <template v-else>
          <template v-for="(group, groupName) in groupedActions" :key="groupName">
            <div class="command-palette-group-header">{{ groupName }}</div>
            <div
              v-for="(action, index) in group"
              :key="action.id"
              class="command-palette-item"
              :class="{ 'command-palette-item--selected': isSelected(action) }"
              @click="executeAction(action)"
              @mouseenter="selectedIndex = getGlobalIndex(groupName, index)"
            >
              <v-icon :color="action.iconColor || 'grey'" size="20" class="mr-3">
                {{ action.icon }}
              </v-icon>
              <div class="command-palette-item-content">
                <div class="command-palette-item-label">{{ action.label }}</div>
                <div v-if="action.description" class="command-palette-item-description">
                  {{ action.description }}
                </div>
              </div>
              <div v-if="action.shortcut" class="command-palette-item-shortcut">
                <kbd v-for="(key, keyIndex) in action.shortcut.split('+')" :key="keyIndex">
                  {{ key }}
                </kbd>
              </div>
            </div>
          </template>
        </template>
      </div>

      <!-- Footer -->
      <v-divider />
      <div class="command-palette-footer">
        <span><kbd>&uarr;</kbd><kbd>&darr;</kbd> Navigation</span>
        <span><kbd>Enter</kbd> Ausfuehren</span>
        <span><kbd>ESC</kbd> Schliessen</span>
      </div>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useTerraformStore } from '@/stores/terraform'
import { registerGlobalShortcut, unregisterGlobalShortcut } from '@/composables/useKeyboardShortcuts'

const router = useRouter()
const authStore = useAuthStore()
const terraformStore = useTerraformStore()

const isOpen = ref(false)
const searchQuery = ref('')
const selectedIndex = ref(0)
const searchInput = ref(null)
const resultsContainer = ref(null)

// Aktionen-Registry
const actions = computed(() => {
  const allActions = [
    // Navigation
    { id: 'go-dashboard', label: 'Dashboard', description: 'Zur Uebersicht', icon: 'mdi-view-dashboard', group: 'Navigation', action: () => router.push('/') },
    { id: 'go-vms', label: 'VMs', description: 'VM-Verwaltung', icon: 'mdi-server-network', group: 'Navigation', action: () => router.push('/terraform') },
    { id: 'go-netbox', label: 'Netzwerk', description: 'NetBox IPAM', icon: 'mdi-ip-network', group: 'Navigation', action: () => router.push('/netbox') },
    { id: 'go-playbooks', label: 'Playbooks', description: 'Ansible Playbooks', icon: 'mdi-script-text', group: 'Navigation', action: () => router.push('/playbooks') },
    { id: 'go-inventory', label: 'Inventory', description: 'Hosts & Gruppen', icon: 'mdi-format-list-bulleted', group: 'Navigation', action: () => router.push('/inventory') },
    { id: 'go-history', label: 'History', description: 'Ausfuehrungen & Logs', icon: 'mdi-history', group: 'Navigation', action: () => router.push('/executions') },
    { id: 'go-capacity', label: 'Kapazitaet', description: 'Cluster-Ressourcen', icon: 'mdi-chart-bar', group: 'Navigation', action: () => router.push('/capacity') },

    // Aktionen
    { id: 'action-new-vm', label: 'Neue VM erstellen', description: 'Terraform VM provisonieren', icon: 'mdi-plus', iconColor: 'success', group: 'Aktionen', action: () => router.push({ path: '/terraform', query: { action: 'create' } }) },
    { id: 'action-sync-inventory', label: 'Inventory synchronisieren', description: 'NetBox -> Ansible Sync', icon: 'mdi-sync', iconColor: 'primary', group: 'Aktionen', action: syncInventory },
    { id: 'action-refresh-vms', label: 'VMs aktualisieren', description: 'Terraform Status neu laden', icon: 'mdi-refresh', iconColor: 'primary', group: 'Aktionen', action: refreshVMs },

    // Schnellzugriff
    { id: 'quick-theme-toggle', label: 'Theme umschalten', description: 'Dark/Light Mode', icon: 'mdi-theme-light-dark', group: 'Schnellzugriff', action: toggleTheme },
  ]

  // Admin-only Aktionen
  if (authStore.isSuperAdmin) {
    allActions.push(
      { id: 'go-settings', label: 'Einstellungen', description: 'Alle Einstellungen', icon: 'mdi-cog', group: 'Administration', action: () => router.push('/settings') },
      { id: 'go-users', label: 'Benutzer verwalten', description: 'User-Verwaltung', icon: 'mdi-account-multiple', group: 'Administration', action: () => router.push('/settings?tab=users') },
      { id: 'go-audit', label: 'Audit-Log', description: 'Aktivitaetsprotokoll', icon: 'mdi-clipboard-text-clock', group: 'Administration', action: () => router.push('/executions?tab=audit') },
      { id: 'go-backup', label: 'Backup & Restore', description: 'Datensicherung', icon: 'mdi-backup-restore', group: 'Administration', action: () => router.push('/settings?tab=backup') },
    )
  }

  // VM-Schnellsuche (dynamisch aus terraformStore)
  if (terraformStore.vms && terraformStore.vms.length > 0) {
    const vmActions = terraformStore.vms.slice(0, 10).map(vm => ({
      id: `vm-${vm.vmid}`,
      label: vm.name,
      description: `VMID: ${vm.vmid} | ${vm.node} | ${vm.status}`,
      icon: getVMIcon(vm.status),
      iconColor: getVMColor(vm.status),
      group: 'VMs',
      action: () => router.push({ path: '/terraform', query: { vmid: vm.vmid } })
    }))
    allActions.push(...vmActions)
  }

  return allActions
})

// Gefilterte Aktionen basierend auf Suche
const filteredActions = computed(() => {
  if (!searchQuery.value.trim()) {
    return actions.value
  }

  const query = searchQuery.value.toLowerCase()
  return actions.value.filter(action =>
    action.label.toLowerCase().includes(query) ||
    (action.description && action.description.toLowerCase().includes(query)) ||
    action.group.toLowerCase().includes(query)
  )
})

// Gruppierte Aktionen
const groupedActions = computed(() => {
  const groups = {}
  for (const action of filteredActions.value) {
    if (!groups[action.group]) {
      groups[action.group] = []
    }
    groups[action.group].push(action)
  }
  return groups
})

// Flache Liste fuer Navigation
const flatFilteredActions = computed(() => filteredActions.value)

// Index-Berechnung fuer Gruppen
function getGlobalIndex(groupName, localIndex) {
  let globalIndex = 0
  for (const [name, items] of Object.entries(groupedActions.value)) {
    if (name === groupName) {
      return globalIndex + localIndex
    }
    globalIndex += items.length
  }
  return 0
}

// Pruefen ob Aktion selektiert ist
function isSelected(action) {
  return flatFilteredActions.value[selectedIndex.value]?.id === action.id
}

// Navigation
function navigateDown() {
  if (selectedIndex.value < flatFilteredActions.value.length - 1) {
    selectedIndex.value++
    scrollToSelected()
  }
}

function navigateUp() {
  if (selectedIndex.value > 0) {
    selectedIndex.value--
    scrollToSelected()
  }
}

function scrollToSelected() {
  nextTick(() => {
    const container = resultsContainer.value
    const selected = container?.querySelector('.command-palette-item--selected')
    if (selected && container) {
      selected.scrollIntoView({ block: 'nearest' })
    }
  })
}

// Ausfuehrung
function executeSelected() {
  const action = flatFilteredActions.value[selectedIndex.value]
  if (action) {
    executeAction(action)
  }
}

function executeAction(action) {
  close()
  if (action.action) {
    action.action()
  }
}

// Oeffnen/Schliessen
function open() {
  isOpen.value = true
  searchQuery.value = ''
  selectedIndex.value = 0
  nextTick(() => {
    searchInput.value?.focus()
  })
}

function close() {
  isOpen.value = false
}

// Hilfsfunktionen
function getVMIcon(status) {
  const icons = {
    running: 'mdi-server',
    stopped: 'mdi-server-off',
    paused: 'mdi-pause-circle'
  }
  return icons[status] || 'mdi-server'
}

function getVMColor(status) {
  const colors = {
    running: 'success',
    stopped: 'grey',
    paused: 'warning'
  }
  return colors[status] || 'grey'
}

// Aktions-Handler
async function syncInventory() {
  // Trigger inventory sync via API
  try {
    const { default: axios } = await import('axios')
    await axios.post('/api/netbox/sync-inventory')
  } catch (e) {
    console.error('Inventory sync failed:', e)
  }
}

async function refreshVMs() {
  await terraformStore.fetchVMs()
}

function toggleTheme() {
  const newDarkMode = authStore.currentDarkMode === 'dark' ? 'light' : 'dark'
  authStore.updateSetting('dark_mode', newDarkMode)
}

// Reset Index bei Suche
watch(searchQuery, () => {
  selectedIndex.value = 0
})

// Keyboard Shortcut registrieren
let shortcutId = null

onMounted(() => {
  shortcutId = registerGlobalShortcut({ key: 'k', ctrl: true }, open)
})

onUnmounted(() => {
  if (shortcutId) {
    unregisterGlobalShortcut(shortcutId)
  }
})

// Expose fuer externe Nutzung
defineExpose({ open, close })
</script>

<style scoped>
.command-palette-card {
  border-radius: 12px !important;
  overflow: hidden;
}

.command-palette-header {
  display: flex;
  align-items: center;
  padding: 16px;
  gap: 8px;
}

.command-palette-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 16px;
  background: transparent;
  color: rgb(var(--v-theme-on-surface));
}

.command-palette-input::placeholder {
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.command-palette-shortcut {
  display: flex;
  gap: 4px;
}

.command-palette-shortcut kbd,
.command-palette-item-shortcut kbd,
.command-palette-footer kbd {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 22px;
  padding: 0 6px;
  font-size: 11px;
  font-family: inherit;
  background: rgba(var(--v-theme-on-surface), 0.08);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 4px;
  color: rgba(var(--v-theme-on-surface), 0.7);
}

.command-palette-results {
  max-height: 400px;
  overflow-y: auto;
  padding: 8px 0;
}

.command-palette-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 16px;
}

.command-palette-group-header {
  padding: 8px 16px 4px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.command-palette-item {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.15s;
}

.command-palette-item:hover,
.command-palette-item--selected {
  background: rgba(var(--v-theme-primary), 0.08);
}

.command-palette-item--selected {
  background: rgba(var(--v-theme-primary), 0.12);
}

.command-palette-item-content {
  flex: 1;
  min-width: 0;
}

.command-palette-item-label {
  font-size: 14px;
  font-weight: 500;
  color: rgb(var(--v-theme-on-surface));
}

.command-palette-item-description {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.6);
  margin-top: 1px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.command-palette-item-shortcut {
  display: flex;
  gap: 4px;
  margin-left: 12px;
}

.command-palette-footer {
  display: flex;
  gap: 16px;
  padding: 10px 16px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.command-palette-footer span {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* Scrim Styling */
:deep(.command-palette-scrim) {
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
}
</style>
