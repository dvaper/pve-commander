/**
 * useDebounce - Composable fuer debounced Werte und Funktionen
 *
 * Verwendung:
 *
 * 1. Debounced ref value:
 *    const searchQuery = ref('')
 *    const debouncedQuery = useDebouncedRef(searchQuery, 300)
 *
 * 2. Debounced function:
 *    const debouncedSearch = useDebounce((query) => api.search(query), 300)
 */

import { ref, watch, onUnmounted } from 'vue'

/**
 * Erstellt eine debounced Version einer Funktion
 *
 * @param {Function} fn - Die zu debouncende Funktion
 * @param {number} delay - Verzoegerung in Millisekunden (Standard: 300)
 * @returns {Function} Debounced Funktion
 */
export function useDebounce(fn, delay = 300) {
  let timeoutId = null

  const debouncedFn = (...args) => {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    timeoutId = setTimeout(() => {
      fn(...args)
      timeoutId = null
    }, delay)
  }

  // Cleanup bei Component unmount
  onUnmounted(() => {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
  })

  // Cancel-Methode fuer manuelles Abbrechen
  debouncedFn.cancel = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
    }
  }

  // Flush-Methode fuer sofortige Ausfuehrung
  debouncedFn.flush = (...args) => {
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
    }
    fn(...args)
  }

  return debouncedFn
}

/**
 * Erstellt einen debounced ref der einen Quell-Ref verzoegert spiegelt
 *
 * @param {Ref} source - Der Quell-Ref
 * @param {number} delay - Verzoegerung in Millisekunden (Standard: 300)
 * @returns {Ref} Debounced Ref
 */
export function useDebouncedRef(source, delay = 300) {
  const debounced = ref(source.value)
  let timeoutId = null

  const stopWatch = watch(source, (newValue) => {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    timeoutId = setTimeout(() => {
      debounced.value = newValue
      timeoutId = null
    }, delay)
  })

  // Cleanup bei Component unmount
  onUnmounted(() => {
    stopWatch()
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
  })

  return debounced
}

/**
 * Einfache Debounce-Funktion (ohne Vue-Integration)
 * Fuer Verwendung ausserhalb von Components
 *
 * @param {Function} fn - Die zu debouncende Funktion
 * @param {number} delay - Verzoegerung in Millisekunden
 * @returns {Function} Debounced Funktion
 */
export function debounce(fn, delay = 300) {
  let timeoutId = null

  const debouncedFn = (...args) => {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    timeoutId = setTimeout(() => {
      fn(...args)
    }, delay)
  }

  debouncedFn.cancel = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
  }

  return debouncedFn
}

export default useDebounce
