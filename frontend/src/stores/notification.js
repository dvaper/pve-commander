/**
 * Notification Store - Pinia Store fuer globale Benachrichtigungen
 *
 * Unterstuetzte Typen:
 * - success: Erfolgreiche Aktionen
 * - error: Fehlermeldungen
 * - warning: Warnungen
 * - info: Informationen
 * - loading: Ladevorgang (persistent bis update)
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

let notificationId = 0

export const useNotificationStore = defineStore('notification', () => {
  // State
  const notifications = ref([])

  // Getters
  const activeNotifications = computed(() =>
    notifications.value.filter(n => !n.dismissed)
  )

  const hasNotifications = computed(() => activeNotifications.value.length > 0)

  // Actions

  /**
   * Zeigt eine neue Benachrichtigung
   * @param {Object} options - Notification options
   * @param {string} options.title - Titel der Benachrichtigung
   * @param {string} options.message - Optionale Nachricht
   * @param {string} options.type - success | error | warning | info | loading
   * @param {boolean} options.persistent - Bleibt bis manuell geschlossen
   * @param {number} options.timeout - Timeout in ms (default: 5000, 0 = kein auto-close)
   * @param {string} options.icon - Optionales Icon (default basierend auf type)
   * @returns {number} Notification ID
   */
  function show(options) {
    const id = ++notificationId

    const notification = {
      id,
      title: options.title || '',
      message: options.message || '',
      type: options.type || 'info',
      icon: options.icon || getDefaultIcon(options.type),
      persistent: options.persistent || options.type === 'loading',
      timeout: options.timeout ?? (options.type === 'loading' ? 0 : 5000),
      dismissed: false,
      createdAt: Date.now(),
    }

    notifications.value.push(notification)

    // Auto-dismiss nach timeout (wenn nicht persistent)
    if (notification.timeout > 0 && !notification.persistent) {
      setTimeout(() => {
        dismiss(id)
      }, notification.timeout)
    }

    return id
  }

  /**
   * Aktualisiert eine bestehende Benachrichtigung
   * Nuetzlich fuer loading -> success/error Uebergaenge
   */
  function update(id, updates) {
    const index = notifications.value.findIndex(n => n.id === id)
    if (index === -1) return

    const notification = notifications.value[index]

    // Updates anwenden
    if (updates.title !== undefined) notification.title = updates.title
    if (updates.message !== undefined) notification.message = updates.message
    if (updates.type !== undefined) {
      notification.type = updates.type
      notification.icon = updates.icon || getDefaultIcon(updates.type)
    }
    if (updates.icon !== undefined) notification.icon = updates.icon

    // Persistent auf false setzen wenn type sich aendert
    if (updates.type && updates.type !== 'loading') {
      notification.persistent = false
      // Auto-dismiss starten
      const timeout = updates.timeout ?? 5000
      if (timeout > 0) {
        setTimeout(() => {
          dismiss(id)
        }, timeout)
      }
    }
  }

  /**
   * Schliesst eine Benachrichtigung
   */
  function dismiss(id) {
    const notification = notifications.value.find(n => n.id === id)
    if (notification) {
      notification.dismissed = true
      // Nach Animation entfernen
      setTimeout(() => {
        const index = notifications.value.findIndex(n => n.id === id)
        if (index !== -1) {
          notifications.value.splice(index, 1)
        }
      }, 300)
    }
  }

  /**
   * Schliesst alle Benachrichtigungen
   */
  function dismissAll() {
    notifications.value.forEach(n => {
      n.dismissed = true
    })
    setTimeout(() => {
      notifications.value = []
    }, 300)
  }

  // Helper
  function getDefaultIcon(type) {
    const icons = {
      success: 'mdi-check-circle',
      error: 'mdi-alert-circle',
      warning: 'mdi-alert',
      info: 'mdi-information',
      loading: 'mdi-loading',
    }
    return icons[type] || 'mdi-information'
  }

  return {
    // State
    notifications,

    // Getters
    activeNotifications,
    hasNotifications,

    // Actions
    show,
    update,
    dismiss,
    dismissAll,
  }
})
