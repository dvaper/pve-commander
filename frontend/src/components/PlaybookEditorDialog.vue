<template>
  <v-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    max-width="1200"
    persistent
    scrollable
  >
    <v-card>
      <v-toolbar color="primary" density="compact">
        <v-toolbar-title>
          <v-icon start>{{ isEdit ? 'mdi-pencil' : 'mdi-plus' }}</v-icon>
          {{ isEdit ? `Playbook bearbeiten: ${playbookName}` : 'Neues Playbook erstellen' }}
        </v-toolbar-title>
        <v-spacer></v-spacer>
        <v-btn icon size="small" @click="close" :disabled="saving">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-toolbar>

      <v-card-text class="pa-4">
        <!-- Name-Eingabe (nur bei Neuanlage) -->
        <div v-if="!isEdit" class="mb-4">
          <v-row>
            <v-col cols="12" md="6">
              <v-text-field
                v-model="name"
                label="Playbook-Name"
                prepend-inner-icon="mdi-file-document"
                variant="outlined"
                density="comfortable"
                :rules="nameRules"
                :disabled="saving"
                hint="Muss mit 'custom-' beginnen. Nur Kleinbuchstaben, Zahlen, _ und -"
                persistent-hint
              >
                <template v-slot:prepend-inner>
                  <span class="text-grey">custom-</span>
                </template>
              </v-text-field>
            </v-col>
            <v-col cols="12" md="6">
              <v-select
                v-model="selectedTemplate"
                :items="templates"
                item-title="name"
                item-value="id"
                label="Vorlage verwenden"
                prepend-inner-icon="mdi-file-document-outline"
                variant="outlined"
                density="comfortable"
                :disabled="saving"
                clearable
                @update:model-value="applyTemplate"
              >
                <template v-slot:item="{ item, props }">
                  <v-list-item v-bind="props">
                    <template v-slot:subtitle>
                      {{ item.raw.description }}
                    </template>
                  </v-list-item>
                </template>
              </v-select>
            </v-col>
          </v-row>
        </div>

        <!-- YAML Editor -->
        <div class="editor-wrapper">
          <div class="editor-toolbar d-flex align-center mb-2">
            <span class="text-caption text-grey">YAML Editor</span>
            <v-spacer></v-spacer>
            <v-chip
              v-if="localValidation.checked"
              :color="localValidation.valid ? 'success' : 'error'"
              size="x-small"
              variant="tonal"
            >
              <v-icon start size="x-small">
                {{ localValidation.valid ? 'mdi-check' : 'mdi-alert' }}
              </v-icon>
              {{ localValidation.valid ? 'YAML OK' : 'YAML-Fehler' }}
            </v-chip>
          </div>
          <div class="editor-container">
            <codemirror
              v-model="content"
              :style="{ height: '400px' }"
              :autofocus="true"
              :indent-with-tab="true"
              :tab-size="2"
              :extensions="extensions"
              @change="onContentChange"
            />
          </div>
          <div v-if="localValidation.error" class="local-error mt-1">
            <v-icon size="small" color="error">mdi-alert-circle</v-icon>
            <span class="text-caption text-error ml-1">{{ localValidation.error }}</span>
          </div>
        </div>

        <!-- Server-Validierung -->
        <PlaybookValidationResult
          :result="validationResult"
          :loading="validating"
          class="mt-4"
        />
      </v-card-text>

      <v-divider></v-divider>

      <v-card-actions class="pa-4">
        <v-btn
          variant="outlined"
          @click="validate"
          :loading="validating"
          :disabled="saving || !content.trim()"
        >
          <v-icon start>mdi-check-circle-outline</v-icon>
          Validieren
        </v-btn>

        <v-spacer></v-spacer>

        <v-btn variant="text" @click="close" :disabled="saving">
          Abbrechen
        </v-btn>

        <v-btn
          color="primary"
          variant="flat"
          @click="save"
          :loading="saving"
          :disabled="!canSave"
        >
          <v-icon start>mdi-content-save</v-icon>
          {{ isEdit ? 'Speichern' : 'Erstellen' }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch, shallowRef } from 'vue'
import { Codemirror } from 'vue-codemirror'
import { yaml } from '@codemirror/lang-yaml'
import { oneDark } from '@codemirror/theme-one-dark'
import { EditorView } from 'codemirror'
import api from '@/api/client'
import PlaybookValidationResult from './PlaybookValidationResult.vue'

const props = defineProps({
  modelValue: Boolean,
  isEdit: {
    type: Boolean,
    default: false
  },
  playbookName: {
    type: String,
    default: ''
  },
  initialContent: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue', 'saved'])

// State
const name = ref('')
const content = ref('')
const selectedTemplate = ref(null)
const templates = ref([])
const validationResult = ref(null)
const validating = ref(false)
const saving = ref(false)
const localValidation = ref({
  checked: false,
  valid: true,
  error: null
})

// Debounce Timer
let debounceTimer = null

// CodeMirror Extensions
const extensions = [
  yaml(),
  oneDark,
  EditorView.lineWrapping,
  EditorView.theme({
    '&': { fontSize: '13px' },
    '.cm-content': { fontFamily: 'monospace' },
    '.cm-gutters': { backgroundColor: '#1e1e1e' }
  })
]

// Name-Validierung
const nameRules = [
  v => !!v || 'Name ist erforderlich',
  v => v.length >= 2 || 'Mindestens 2 Zeichen',
  v => v.length <= 60 || 'Maximal 60 Zeichen',
  v => /^[a-z0-9_-]+$/.test(v) || 'Nur Kleinbuchstaben, Zahlen, _ und - erlaubt',
]

// Computed: Vollständiger Name mit Prefix
const fullName = computed(() => {
  if (props.isEdit) return props.playbookName
  const cleanName = name.value.toLowerCase().replace(/^custom-/, '')
  return `custom-${cleanName}`
})

// Computed: Kann speichern?
const canSave = computed(() => {
  // Bei Edit: Content muss vorhanden sein
  if (props.isEdit) {
    return content.value.trim().length > 10 && localValidation.value.valid
  }
  // Bei Create: Name und Content müssen vorhanden sein
  return (
    name.value.length >= 2 &&
    /^[a-z0-9_-]+$/.test(name.value) &&
    content.value.trim().length > 10 &&
    localValidation.value.valid
  )
})

// Watch: Dialog öffnen
watch(() => props.modelValue, async (open) => {
  if (open) {
    // Reset
    validationResult.value = null
    localValidation.value = { checked: false, valid: true, error: null }

    if (props.isEdit) {
      // Edit-Mode: Content vom Server laden
      content.value = props.initialContent || ''
      name.value = ''
    } else {
      // Create-Mode: Leerer Content, Templates laden
      content.value = ''
      name.value = ''
      selectedTemplate.value = null
      await loadTemplates()
    }
  }
})

// Templates laden
async function loadTemplates() {
  try {
    const response = await api.get('/api/playbooks/templates')
    templates.value = response.data
  } catch (e) {
    console.error('Templates laden fehlgeschlagen:', e)
    templates.value = []
  }
}

// Template anwenden
function applyTemplate(templateId) {
  if (!templateId) {
    content.value = ''
    return
  }
  const template = templates.value.find(t => t.id === templateId)
  if (template) {
    content.value = template.content
    // Local validation triggern
    validateLocal()
  }
}

// Content-Änderung mit Debounce
function onContentChange() {
  // Debounced lokale Validierung
  if (debounceTimer) {
    clearTimeout(debounceTimer)
  }
  debounceTimer = setTimeout(() => {
    validateLocal()
  }, 500)
}

// Lokale YAML-Validierung (schnell, ohne Server)
function validateLocal() {
  localValidation.value.checked = true

  if (!content.value.trim()) {
    localValidation.value.valid = false
    localValidation.value.error = 'Inhalt ist leer'
    return
  }

  try {
    // Einfache YAML-Struktur-Prüfung
    // Prüft ob es mit --- oder - beginnt (Playbook-Format)
    const trimmed = content.value.trim()

    // Muss mit --- oder - name: beginnen
    if (!trimmed.startsWith('---') && !trimmed.startsWith('- ')) {
      localValidation.value.valid = false
      localValidation.value.error = "Playbook muss mit '---' oder '- name:' beginnen"
      return
    }

    // Basis-Einrückungsprüfung
    const lines = content.value.split('\n')
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i]
      // Tabs sind in YAML problematisch
      if (line.includes('\t')) {
        localValidation.value.valid = false
        localValidation.value.error = `Zeile ${i + 1}: Tabs sind nicht erlaubt, nur Leerzeichen`
        return
      }
    }

    localValidation.value.valid = true
    localValidation.value.error = null
  } catch (e) {
    localValidation.value.valid = false
    localValidation.value.error = e.message
  }
}

// Server-Validierung
async function validate() {
  validating.value = true
  validationResult.value = null

  try {
    const response = await api.post('/api/playbooks/validate', {
      content: content.value
    })
    validationResult.value = response.data
  } catch (e) {
    console.error('Validierung fehlgeschlagen:', e)
    validationResult.value = {
      valid: false,
      yaml_valid: false,
      yaml_error: e.response?.data?.detail || 'Validierung fehlgeschlagen',
      ansible_valid: false,
      ansible_error: null,
      warnings: [],
      parsed_info: null
    }
  } finally {
    validating.value = false
  }
}

// Speichern
async function save() {
  // Zuerst validieren
  await validate()

  if (!validationResult.value?.valid) {
    return
  }

  saving.value = true

  try {
    if (props.isEdit) {
      // Update
      await api.put(`/api/playbooks/${props.playbookName}`, {
        content: content.value
      })
    } else {
      // Create
      await api.post('/api/playbooks', {
        name: fullName.value,
        content: content.value
      })
    }

    emit('saved')
    close()
  } catch (e) {
    console.error('Speichern fehlgeschlagen:', e)
    // Fehler wird durch globalen Error-Handler angezeigt
  } finally {
    saving.value = false
  }
}

// Dialog schließen
function close() {
  emit('update:modelValue', false)
}
</script>

<style scoped>
.editor-wrapper {
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 4px;
  overflow: hidden;
}

.editor-toolbar {
  background: #1e1e1e;
  padding: 8px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.12);
}

.editor-container {
  background: #1e1e1e;
}

.editor-container :deep(.cm-editor) {
  height: 400px;
}

.editor-container :deep(.cm-scroller) {
  overflow: auto;
}

.local-error {
  background: rgba(244, 67, 54, 0.1);
  padding: 4px 8px;
  border-radius: 0 0 4px 4px;
}

/* Name-Input Prefix Styling */
:deep(.v-field__prepend-inner) {
  padding-right: 0;
}
</style>
