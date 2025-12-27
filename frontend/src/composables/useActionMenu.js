/**
 * useActionMenu - Composable fuer VM Action Menus
 *
 * Generiert gruppierte Aktionen basierend auf VM-Status.
 * Wird von VMList und anderen Komponenten verwendet.
 */

import { computed } from 'vue'

/**
 * Erstellt Action-Gruppen fuer eine VM basierend auf ihrem Status
 * @param {Object} vm - Die VM mit name, status, ip_address, etc.
 * @param {Object} options - Optionen wie loadingAction
 * @returns {Array} Array von Action-Gruppen
 */
export function getVMActions(vm, options = {}) {
  if (!vm) return []

  const { loadingAction = null } = options

  const isDeployed = ['deployed', 'running', 'stopped', 'paused'].includes(vm.status)
  const isRunning = vm.status === 'running'
  const isStopped = vm.status === 'stopped'
  const isPlanned = vm.status === 'planned'
  const isInProgress = ['deploying', 'destroying'].includes(vm.status)

  const groups = []

  // Gruppe 1: Verwaltung (nur fuer deployed VMs)
  if (isDeployed) {
    groups.push({
      label: 'Verwaltung',
      items: [
        {
          key: 'edit',
          label: 'Bearbeiten',
          icon: 'mdi-pencil',
          color: 'warning',
        },
        {
          key: 'clone',
          label: 'Klonen',
          icon: 'mdi-content-copy',
          color: 'primary',
        },
        {
          key: 'snapshots',
          label: 'Snapshots',
          icon: 'mdi-camera',
          color: 'secondary',
        },
        {
          key: 'migrate',
          label: 'Migrieren',
          icon: 'mdi-server-network',
          color: 'info',
        },
      ],
    })
  }

  // Gruppe 2: Terraform
  groups.push({
    label: 'Terraform',
    items: [
      {
        key: 'plan',
        label: 'Plan',
        icon: 'mdi-file-search',
        color: 'info',
        disabled: isInProgress,
      },
      {
        key: 'apply',
        label: 'Deploy',
        icon: 'mdi-rocket-launch',
        color: 'success',
        disabled: isDeployed || isInProgress,
        subtitle: isDeployed ? 'Bereits deployed' : null,
      },
      {
        key: 'destroy',
        label: 'Destroy',
        icon: 'mdi-delete-alert',
        color: 'error',
        disabled: isPlanned || isInProgress,
        subtitle: isPlanned ? 'Nicht deployed' : null,
      },
    ],
  })

  // Gruppe 3: Bereinigung
  const cleanupItems = []

  if (isPlanned && vm.ip_address) {
    cleanupItems.push({
      key: 'release-ip',
      label: 'IP freigeben',
      icon: 'mdi-ip-network-outline',
      color: 'warning',
      subtitle: vm.ip_address,
    })
  }

  cleanupItems.push({
    key: 'delete-config',
    label: 'Config loeschen',
    icon: 'mdi-file-remove',
    disabled: isInProgress,
  })

  cleanupItems.push({
    key: 'delete-complete',
    label: 'Vollstaendig loeschen',
    icon: 'mdi-delete-forever',
    color: 'error',
    disabled: isInProgress,
    subtitle: 'Alle Systeme',
  })

  groups.push({
    label: 'Bereinigung',
    items: cleanupItems,
  })

  // Gruppe 4: Links (wenn Frontend-URL vorhanden)
  if (vm.frontend_url) {
    groups.unshift({
      items: [
        {
          key: 'open-frontend',
          label: 'Frontend oeffnen',
          icon: 'mdi-open-in-new',
          color: 'primary',
        },
      ],
    })
  }

  // Frontend-URL bearbeiten immer hinzufuegen (in Verwaltung oder eigene Gruppe)
  const editUrlAction = {
    key: 'edit-frontend-url',
    label: vm.frontend_url ? 'Frontend-URL bearbeiten' : 'Frontend-URL hinzufuegen',
    icon: 'mdi-link-variant',
  }

  // Fuege zu Verwaltung hinzu wenn vorhanden, sonst neue Gruppe
  if (groups[0]?.label === 'Verwaltung') {
    groups[0].items.unshift(editUrlAction)
  } else if (!isDeployed) {
    groups.unshift({
      label: 'Verwaltung',
      items: [
        {
          key: 'edit',
          label: 'Bearbeiten',
          icon: 'mdi-pencil',
          color: 'warning',
        },
        editUrlAction,
      ],
    })
  }

  return groups
}

/**
 * Composable fuer Action-Menu Funktionalitaet
 */
export function useActionMenu() {
  return {
    getVMActions,
  }
}

export default useActionMenu
