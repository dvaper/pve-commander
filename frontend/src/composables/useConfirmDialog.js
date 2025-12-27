/**
 * Composable fuer programmatische Verwendung von ConfirmDialog
 *
 * Ermoeglicht es, Bestaetigungsdialoge per Promise zu verwenden,
 * ohne sie manuell in jeder Komponente einzubinden.
 */
import { ref, reactive, markRaw } from 'vue'

// Globaler State fuer den Dialog
const isOpen = ref(false)
const dialogProps = reactive({
  title: '',
  message: '',
  icon: 'mdi-alert',
  iconColor: 'warning',
  confirmLabel: 'Bestaetigen',
  confirmColor: 'primary',
  confirmVariant: 'elevated',
  confirmIcon: null,
  cancelLabel: 'Abbrechen',
  requireConfirmation: false,
  confirmationLabel: 'Ich verstehe die Konsequenzen',
  requireTextConfirmation: null, // z.B. 'DESTROY' eintippen
  loading: false,
  details: null // Slot-Content als Component
})

let resolvePromise = null

/**
 * Zeigt einen Bestaetigungsdialog und gibt ein Promise zurueck
 *
 * @param {Object} options - Dialog-Optionen
 * @returns {Promise<boolean>} - true wenn bestaetigt, false wenn abgebrochen
 *
 * @example
 * const { confirm } = useConfirmDialog()
 *
 * // Einfache Bestaetigung
 * const confirmed = await confirm({
 *   title: 'VM loeschen?',
 *   message: 'Diese Aktion kann nicht rueckgaengig gemacht werden.',
 *   icon: 'mdi-delete',
 *   iconColor: 'error',
 *   confirmLabel: 'Loeschen',
 *   confirmColor: 'error'
 * })
 *
 * if (confirmed) {
 *   await deleteVM()
 * }
 */
export function useConfirmDialog() {
  function confirm(options = {}) {
    // Props zuruecksetzen und mit neuen Werten fuellen
    Object.assign(dialogProps, {
      title: options.title || 'Bestaetigung',
      message: options.message || 'Moechten Sie fortfahren?',
      icon: options.icon || 'mdi-alert',
      iconColor: options.iconColor || 'warning',
      confirmLabel: options.confirmLabel || 'Bestaetigen',
      confirmColor: options.confirmColor || 'primary',
      confirmVariant: options.confirmVariant || 'elevated',
      confirmIcon: options.confirmIcon || null,
      cancelLabel: options.cancelLabel || 'Abbrechen',
      requireConfirmation: options.requireConfirmation || false,
      confirmationLabel: options.confirmationLabel || 'Ich verstehe die Konsequenzen',
      requireTextConfirmation: options.requireTextConfirmation || null,
      loading: false,
      details: options.details ? markRaw(options.details) : null
    })

    isOpen.value = true

    return new Promise((resolve) => {
      resolvePromise = resolve
    })
  }

  function onConfirm() {
    if (resolvePromise) {
      resolvePromise(true)
      resolvePromise = null
    }
    isOpen.value = false
  }

  function onCancel() {
    if (resolvePromise) {
      resolvePromise(false)
      resolvePromise = null
    }
    isOpen.value = false
  }

  function setLoading(loading) {
    dialogProps.loading = loading
  }

  return {
    // State (fuer ConfirmDialogProvider)
    isOpen,
    dialogProps,

    // Actions
    confirm,
    onConfirm,
    onCancel,
    setLoading
  }
}

// Vordefinierte Dialog-Presets fuer haeufige Aktionen
export const confirmPresets = {
  delete: (itemName) => ({
    title: `${itemName} loeschen?`,
    message: 'Diese Aktion kann nicht rueckgaengig gemacht werden.',
    icon: 'mdi-delete',
    iconColor: 'error',
    confirmLabel: 'Loeschen',
    confirmColor: 'error',
    confirmIcon: 'mdi-delete'
  }),

  deleteVM: (vmName) => ({
    title: 'VM loeschen?',
    message: `Die VM "${vmName}" wird unwiderruflich geloescht. Alle Daten gehen verloren.`,
    icon: 'mdi-server-off',
    iconColor: 'error',
    confirmLabel: 'VM loeschen',
    confirmColor: 'error',
    confirmIcon: 'mdi-delete'
  }),

  destroyVM: (vmName) => ({
    title: 'VM zerstoeren',
    message: `Die VM "${vmName}" wird unwiderruflich aus Proxmox geloescht!`,
    icon: 'mdi-delete-alert',
    iconColor: 'error',
    confirmLabel: 'Destroy',
    confirmColor: 'error',
    confirmIcon: 'mdi-delete-alert',
    requireTextConfirmation: 'DESTROY'
  }),

  releaseIP: (vmName, ip) => ({
    title: 'IP freigeben',
    message: `Die IP-Adresse ${ip} fuer VM "${vmName}" wird in NetBox als frei markiert.`,
    icon: 'mdi-ip-network-outline',
    iconColor: 'warning',
    confirmLabel: 'Freigeben',
    confirmColor: 'warning'
  }),

  batchDestroy: (vmCount) => ({
    title: `${vmCount} VMs zerstoeren`,
    message: `ACHTUNG: Alle ${vmCount} ausgewaehlten VMs werden unwiderruflich aus Proxmox geloescht!`,
    icon: 'mdi-alert-octagon',
    iconColor: 'error',
    confirmLabel: 'Alle zerstoeren',
    confirmColor: 'error',
    requireTextConfirmation: 'DESTROY ALL'
  }),

  stopVM: (vmName) => ({
    title: 'VM stoppen?',
    message: `Die VM "${vmName}" wird heruntergefahren.`,
    icon: 'mdi-stop-circle',
    iconColor: 'warning',
    confirmLabel: 'Stoppen',
    confirmColor: 'warning'
  }),

  destroyTerraform: (vmCount) => ({
    title: 'Terraform State zerstoeren?',
    message: `ACHTUNG: ${vmCount} VM(s) werden aus dem Terraform State entfernt und sind danach unverwaltet!`,
    icon: 'mdi-alert-octagon',
    iconColor: 'error',
    confirmLabel: 'Zerstoeren',
    confirmColor: 'error',
    requireConfirmation: true,
    confirmationLabel: 'Ich verstehe, dass alle VMs unverwaltet werden'
  }),

  unsavedChanges: () => ({
    title: 'Ungespeicherte Aenderungen',
    message: 'Sie haben ungespeicherte Aenderungen. Moechten Sie die Seite wirklich verlassen?',
    icon: 'mdi-content-save-alert',
    iconColor: 'warning',
    confirmLabel: 'Verwerfen',
    confirmColor: 'error',
    cancelLabel: 'Zurueck'
  })
}
