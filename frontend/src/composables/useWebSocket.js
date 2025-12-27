/**
 * WebSocket Composable für Live-Output
 */
import { ref, onUnmounted } from 'vue'

export function useWebSocket(initialExecutionId) {
  const connected = ref(false)
  const logs = ref([])
  const status = ref('connecting')
  const error = ref(null)

  let ws = null
  let reconnectTimer = null
  let currentExecutionId = initialExecutionId

  function connect(newExecutionId = null) {
    if (newExecutionId !== null) {
      currentExecutionId = newExecutionId
    }
    const token = localStorage.getItem('token')
    if (!token) {
      error.value = 'Nicht authentifiziert'
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = import.meta.env.VITE_WS_URL || `${protocol}//${window.location.host}`
    const url = `${host}/ws/execution/${currentExecutionId}`

    ws = new WebSocket(url)

    ws.onopen = () => {
      // Auth senden
      ws.send(JSON.stringify({ type: 'auth', token }))
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)

      switch (data.type) {
        case 'auth_ok':
          connected.value = true
          status.value = 'connected'
          break

        case 'error':
          error.value = data.message
          status.value = 'error'
          break

        case 'stdout':
        case 'stderr':
          logs.value.push({
            type: data.type,
            content: data.content,
            sequence_num: data.sequence_num,
          })
          break

        case 'finished':
          status.value = data.status
          connected.value = false
          break

        case 'pong':
          // Keep-alive response
          break
      }
    }

    ws.onerror = (e) => {
      error.value = 'WebSocket-Fehler'
      status.value = 'error'
    }

    ws.onclose = () => {
      connected.value = false
      if (status.value === 'connected') {
        status.value = 'disconnected'
        // Reconnect nach 3 Sekunden
        reconnectTimer = setTimeout(connect, 3000)
      }
    }
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
    }
    if (ws) {
      ws.close()
      ws = null
    }
  }

  function sendPing() {
    if (ws && connected.value) {
      ws.send(JSON.stringify({ type: 'ping' }))
    }
  }

  // Keep-alive alle 30 Sekunden
  const pingInterval = setInterval(sendPing, 30000)

  onUnmounted(() => {
    clearInterval(pingInterval)
    disconnect()
  })

  return {
    connected,
    logs,
    status,
    error,
    connect,
    disconnect,
  }
}
