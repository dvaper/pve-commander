/**
 * Zentrale Formatierungs-Utilities für Ansible Commander
 */

/**
 * Formatiert ein Datum im deutschen Format
 * @param {string|Date} dateStr - ISO-Datum oder Date-Objekt
 * @returns {string} Formatiertes Datum oder '-' wenn leer
 */
export function formatDate(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('de-DE')
}

/**
 * Formatiert ein Datum nur als Datumsteil (ohne Uhrzeit)
 * @param {string|Date} dateStr - ISO-Datum oder Date-Objekt
 * @returns {string} Formatiertes Datum oder '-' wenn leer
 */
export function formatDateOnly(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('de-DE')
}

/**
 * Formatiert eine Dauer in Sekunden als lesbaren String
 * @param {number} seconds - Dauer in Sekunden
 * @returns {string} Formatierte Dauer oder '-' wenn leer
 */
export function formatDuration(seconds) {
  if (!seconds) return '-'
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const mins = Math.floor(seconds / 60)
  const secs = Math.round(seconds % 60)
  return `${mins}m ${secs}s`
}

/**
 * Gibt die Farbe für einen Status zurück
 * @param {string} status - Status (success, failed, running, pending, cancelled, completed)
 * @returns {string} Vuetify-Farbe
 */
export function getStatusColor(status) {
  const colors = {
    success: 'success',
    completed: 'success',
    failed: 'error',
    running: 'info',
    pending: 'warning',
    cancelled: 'grey',
  }
  return colors[status] || 'grey'
}

/**
 * Gibt das Icon für einen Status zurück
 * @param {string} status - Status (success, failed, running, pending, cancelled, completed)
 * @returns {string} MDI-Icon-Name
 */
export function getStatusIcon(status) {
  const icons = {
    success: 'mdi-check-circle',
    completed: 'mdi-check-circle',
    failed: 'mdi-alert-circle',
    running: 'mdi-loading',
    pending: 'mdi-clock-outline',
    cancelled: 'mdi-cancel',
  }
  return icons[status] || 'mdi-help-circle'
}
