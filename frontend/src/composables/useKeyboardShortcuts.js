import { ref, onMounted, onUnmounted } from 'vue'

/**
 * Composable fuer globale Keyboard Shortcuts
 *
 * @example
 * const { registerShortcut, unregisterShortcut } = useKeyboardShortcuts()
 * registerShortcut({ key: 'k', ctrl: true }, () => openCommandPalette())
 */
export function useKeyboardShortcuts() {
  const shortcuts = ref(new Map())

  function handleKeyDown(event) {
    // Ignoriere Shortcuts wenn Input/Textarea fokussiert ist
    const target = event.target
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
      // Erlaube nur Escape in Inputs
      if (event.key !== 'Escape') {
        return
      }
    }

    for (const [id, shortcut] of shortcuts.value) {
      const { key, ctrl, meta, shift, callback } = shortcut

      // Pruefe Modifikatoren
      const ctrlOrMeta = (ctrl && (event.ctrlKey || event.metaKey)) || (!ctrl && !event.ctrlKey && !event.metaKey)
      const shiftMatch = shift ? event.shiftKey : !event.shiftKey
      const keyMatch = event.key.toLowerCase() === key.toLowerCase()

      if (keyMatch && ctrlOrMeta && shiftMatch) {
        event.preventDefault()
        callback(event)
        return
      }
    }
  }

  function registerShortcut(config, callback) {
    const id = `${config.ctrl ? 'ctrl+' : ''}${config.meta ? 'meta+' : ''}${config.shift ? 'shift+' : ''}${config.key}`
    shortcuts.value.set(id, {
      ...config,
      callback
    })
    return id
  }

  function unregisterShortcut(id) {
    shortcuts.value.delete(id)
  }

  onMounted(() => {
    window.addEventListener('keydown', handleKeyDown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', handleKeyDown)
    shortcuts.value.clear()
  })

  return {
    registerShortcut,
    unregisterShortcut
  }
}

/**
 * Globale Shortcut-Registry fuer App-weite Shortcuts
 */
const globalShortcuts = new Map()
let globalListenerAttached = false

function handleGlobalKeyDown(event) {
  const target = event.target
  if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
    if (event.key !== 'Escape') {
      return
    }
  }

  for (const [id, shortcut] of globalShortcuts) {
    const { key, ctrl, meta, shift, callback } = shortcut

    // Ctrl oder Meta (Cmd auf Mac)
    const ctrlOrMeta = ctrl ? (event.ctrlKey || event.metaKey) : (!event.ctrlKey && !event.metaKey)
    const shiftMatch = shift ? event.shiftKey : !event.shiftKey
    const keyMatch = event.key.toLowerCase() === key.toLowerCase()

    if (keyMatch && ctrlOrMeta && shiftMatch) {
      event.preventDefault()
      callback(event)
      return
    }
  }
}

export function registerGlobalShortcut(config, callback) {
  if (!globalListenerAttached) {
    window.addEventListener('keydown', handleGlobalKeyDown)
    globalListenerAttached = true
  }

  const id = `${config.ctrl ? 'ctrl+' : ''}${config.meta ? 'meta+' : ''}${config.shift ? 'shift+' : ''}${config.key}`
  globalShortcuts.set(id, {
    ...config,
    callback
  })
  return id
}

export function unregisterGlobalShortcut(id) {
  globalShortcuts.delete(id)
}
