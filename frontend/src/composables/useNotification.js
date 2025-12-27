/**
 * Composable fuer einfache Benachrichtigungen
 *
 * Bietet eine vereinfachte API fuer haeufige Benachrichtigungs-Szenarien.
 *
 * @example
 * const { success, error, loading } = useNotification()
 *
 * // Einfache Benachrichtigungen
 * success('Gespeichert', 'Einstellungen wurden gespeichert')
 * error('Fehler', 'Speichern fehlgeschlagen')
 *
 * // Loading mit anschliessendem Success/Error
 * const notify = loading('Speichere...')
 * try {
 *   await saveData()
 *   notify.success('Gespeichert!')
 * } catch (e) {
 *   notify.error('Speichern fehlgeschlagen')
 * }
 */
import { useNotificationStore } from '@/stores/notification'

export function useNotification() {
  const store = useNotificationStore()

  /**
   * Zeigt eine Erfolgs-Benachrichtigung
   */
  function success(title, message = '') {
    return store.show({
      type: 'success',
      title,
      message,
    })
  }

  /**
   * Zeigt eine Fehler-Benachrichtigung
   */
  function error(title, message = '') {
    return store.show({
      type: 'error',
      title,
      message,
      timeout: 8000, // Fehler laenger anzeigen
    })
  }

  /**
   * Zeigt eine Warn-Benachrichtigung
   */
  function warning(title, message = '') {
    return store.show({
      type: 'warning',
      title,
      message,
    })
  }

  /**
   * Zeigt eine Info-Benachrichtigung
   */
  function info(title, message = '') {
    return store.show({
      type: 'info',
      title,
      message,
    })
  }

  /**
   * Zeigt eine Loading-Benachrichtigung mit Chainable API
   *
   * @example
   * const notify = loading('Lade Daten...')
   * try {
   *   const data = await fetchData()
   *   notify.success('Daten geladen', `${data.length} Eintraege`)
   * } catch (e) {
   *   notify.error('Laden fehlgeschlagen', e.message)
   * }
   */
  function loading(title, message = '') {
    const id = store.show({
      type: 'loading',
      title,
      message,
      persistent: true,
    })

    return {
      /** Aktualisiert zu Erfolg */
      success: (newTitle, newMessage = '') => {
        store.update(id, {
          type: 'success',
          title: newTitle || title,
          message: newMessage,
        })
      },

      /** Aktualisiert zu Fehler */
      error: (newTitle, newMessage = '') => {
        store.update(id, {
          type: 'error',
          title: newTitle || 'Fehler',
          message: newMessage,
          timeout: 8000,
        })
      },

      /** Aktualisiert die Nachricht */
      update: (newMessage) => {
        store.update(id, { message: newMessage })
      },

      /** Schliesst die Benachrichtigung */
      dismiss: () => {
        store.dismiss(id)
      },

      /** Die Notification ID */
      id,
    }
  }

  /**
   * Wrapper fuer async Operationen mit automatischer Benachrichtigung
   *
   * @example
   * await notify.promise(
   *   saveData(),
   *   'Speichere...',
   *   'Gespeichert!',
   *   'Speichern fehlgeschlagen'
   * )
   */
  async function promise(asyncFn, loadingTitle, successTitle, errorTitle) {
    const notify = loading(loadingTitle)
    try {
      const result = await asyncFn
      notify.success(successTitle)
      return result
    } catch (e) {
      notify.error(errorTitle, e.message || String(e))
      throw e
    }
  }

  return {
    success,
    error,
    warning,
    info,
    loading,
    promise,

    // Direkter Store-Zugriff fuer fortgeschrittene Nutzung
    store,
  }
}
