/**
 * API Client - Axios mit JWT, Retry-Logic und verbesserter Fehlerbehandlung
 */
import axios from 'axios'

// Retry-Konfiguration
const RETRY_CONFIG = {
  retries: 3,
  retryDelay: 1000, // Start-Delay in ms
  retryCondition: (error) => {
    // Retry bei Netzwerkfehlern oder 5xx Server-Fehlern
    return (
      !error.response || // Netzwerkfehler
      (error.response.status >= 500 && error.response.status < 600)
    )
  },
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 30000,
})

/**
 * Exponential Backoff Delay
 */
function getRetryDelay(retryCount) {
  return RETRY_CONFIG.retryDelay * Math.pow(2, retryCount)
}

/**
 * Sleep Helper
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

// Request Interceptor - JWT Token hinzufuegen
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    // Retry-Counter initialisieren
    config.__retryCount = config.__retryCount || 0
    return config
  },
  (error) => Promise.reject(error)
)

// Response Interceptor - Fehlerbehandlung mit Retry
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config

    // Kein Retry wenn kein Config oder bereits max Retries erreicht
    if (!config || config.__retryCount >= RETRY_CONFIG.retries) {
      return handleFinalError(error)
    }

    // Pruefen ob Retry-Bedingung erfuellt
    if (RETRY_CONFIG.retryCondition(error)) {
      config.__retryCount += 1

      // Exponential Backoff
      const delay = getRetryDelay(config.__retryCount - 1)

      if (import.meta.env.DEV) {
        console.warn(`API Retry ${config.__retryCount}/${RETRY_CONFIG.retries} nach ${delay}ms:`, config.url)
      }

      await sleep(delay)
      return api(config)
    }

    return handleFinalError(error)
  }
)

/**
 * Finale Fehlerbehandlung nach allen Retries
 */
function handleFinalError(error) {
  // 401 - Token ungueltig/abgelaufen
  if (error.response?.status === 401) {
    const currentPath = window.location.pathname

    // Nicht auf Login-Seite redirecten wenn schon dort
    if (currentPath !== '/login' && currentPath !== '/setup') {
      localStorage.removeItem('token')

      // Sanfter Redirect ueber Router statt hartem window.location
      // Falls Router nicht verfuegbar, Fallback auf window.location
      const event = new CustomEvent('auth:logout', { detail: { reason: 'token_expired' } })
      window.dispatchEvent(event)

      // Fallback nach kurzem Delay falls Event nicht behandelt wird
      setTimeout(() => {
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
      }, 100)
    }
  }

  // Error-Details normalisieren
  if (error.response?.data?.error) {
    // Einheitliches Error-Format vom Backend
    error.errorCode = error.response.data.error.error_code
    error.errorMessage = error.response.data.error.message
    error.errorDetails = error.response.data.error.details
  } else if (error.response?.data?.detail) {
    // Legacy-Format
    error.errorMessage = error.response.data.detail
  } else if (!error.response) {
    // Netzwerkfehler
    error.errorCode = 'NETWORK_ERROR'
    error.errorMessage = 'Netzwerkfehler - Server nicht erreichbar'
  }

  return Promise.reject(error)
}

/**
 * Helper fuer einfache Error-Message Extraktion
 */
export function getErrorMessage(error) {
  return (
    error.errorMessage ||
    error.response?.data?.error?.message ||
    error.response?.data?.detail ||
    error.message ||
    'Ein unbekannter Fehler ist aufgetreten'
  )
}

/**
 * Helper fuer Error-Code Extraktion
 */
export function getErrorCode(error) {
  return (
    error.errorCode ||
    error.response?.data?.error?.error_code ||
    `HTTP_${error.response?.status || 'UNKNOWN'}`
  )
}

export default api
