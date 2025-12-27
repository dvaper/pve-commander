<template>
  <v-dialog v-model="dialogVisible" max-width="600" persistent>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2">mdi-tag-multiple</v-icon>
        Playbook-Metadaten
      </v-card-title>

      <v-divider />

      <v-card-text v-if="loading" class="text-center py-8">
        <v-progress-circular indeterminate color="primary" />
        <div class="mt-3">Lade Metadaten...</div>
      </v-card-text>

      <v-card-text v-else>
        <v-form ref="form">
          <div class="text-subtitle-2 mb-2">Playbook</div>
          <v-chip color="primary" class="mb-4">{{ playbook }}</v-chip>

          <v-text-field
            v-model="formData.display_name"
            label="Anzeigename"
            hint="Optionaler Name fuer die Anzeige"
            persistent-hint
            class="mb-3"
          />

          <v-textarea
            v-model="formData.description"
            label="Beschreibung"
            rows="2"
            class="mb-3"
          />

          <v-combobox
            v-model="selectedOsType"
            :items="osTypes"
            item-title="title"
            item-value="value"
            label="OS-Typ"
            hint="Waehle oder gib einen neuen OS-Typ ein"
            persistent-hint
            class="mb-3"
            :return-object="false"
          />

          <v-combobox
            v-model="selectedCategory"
            :items="categories"
            item-title="title"
            item-value="value"
            label="Kategorie"
            hint="Waehle oder gib eine neue Kategorie ein"
            persistent-hint
            class="mb-3"
            :return-object="false"
          />

          <v-combobox
            v-model="formData.tags"
            label="Tags"
            multiple
            chips
            closable-chips
            hint="Druecke Enter um Tags hinzuzufuegen"
            persistent-hint
            class="mb-3"
          />

          <v-select
            v-model="formData.risk_level"
            :items="riskLevels"
            item-title="title"
            item-value="value"
            label="Risiko-Level"
            class="mb-3"
          >
            <template #item="{ item, props }">
              <v-list-item v-bind="props">
                <template #prepend>
                  <v-icon :color="item.raw.color">mdi-alert-circle</v-icon>
                </template>
              </v-list-item>
            </template>
          </v-select>

          <v-checkbox
            v-model="formData.requires_confirmation"
            label="Bestaetigung vor Ausfuehrung erforderlich"
            hint="Zeigt einen Warnhinweis vor der Ausfuehrung"
            persistent-hint
            color="warning"
          />
        </v-form>
      </v-card-text>

      <v-divider />

      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="close">Abbrechen</v-btn>
        <v-btn
          color="primary"
          :loading="saving"
          :disabled="loading"
          @click="save"
        >
          Speichern
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch, inject, onMounted } from 'vue'
import api from '@/api/client'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  playbook: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['update:modelValue', 'saved'])

const showSnackbar = inject('showSnackbar')

// State
const loading = ref(false)
const saving = ref(false)
const osTypes = ref([])
const categories = ref([])
const selectedOsType = ref('all')
const selectedCategory = ref('custom')

const formData = ref({
  display_name: '',
  description: '',
  os_type: 'all',
  category: 'custom',
  tags: [],
  requires_confirmation: false,
  risk_level: 'info',
})

const riskLevels = [
  { title: 'Info', value: 'info', color: 'info' },
  { title: 'Warnung', value: 'warning', color: 'warning' },
  { title: 'Gefaehrlich', value: 'danger', color: 'error' },
]

// Computed
const dialogVisible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

// Methods
async function loadOsTypesAndCategories() {
  try {
    const [osRes, catRes] = await Promise.all([
      api.get('/api/settings/os-types'),
      api.get('/api/settings/categories'),
    ])
    osTypes.value = osRes.data
    categories.value = catRes.data
  } catch (e) {
    console.error('Fehler beim Laden der OS-Types/Kategorien:', e)
    // Fallback
    osTypes.value = [
      { title: 'Alle', value: 'all' },
      { title: 'Linux', value: 'linux' },
      { title: 'Windows', value: 'windows' },
    ]
    categories.value = [
      { title: 'System', value: 'system' },
      { title: 'Wartung', value: 'maintenance' },
      { title: 'Deployment', value: 'deployment' },
      { title: 'Sicherheit', value: 'security' },
      { title: 'Monitoring', value: 'monitoring' },
      { title: 'Custom', value: 'custom' },
    ]
  }
}

async function loadMetadata() {
  if (!props.playbook) return

  loading.value = true
  try {
    const response = await api.get(`/api/playbooks/${props.playbook}/metadata`)
    formData.value = {
      display_name: response.data.display_name || '',
      description: response.data.description || '',
      os_type: response.data.os_type || 'all',
      category: response.data.category || 'custom',
      tags: response.data.tags || [],
      requires_confirmation: response.data.requires_confirmation || false,
      risk_level: response.data.risk_level || 'info',
    }
    selectedOsType.value = formData.value.os_type
    selectedCategory.value = formData.value.category
  } catch (e) {
    console.error('Fehler beim Laden der Metadaten:', e)
    showSnackbar?.('Fehler beim Laden der Metadaten', 'error')
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    // Wert aus Combobox extrahieren (kann String oder Object sein)
    const osTypeValue = typeof selectedOsType.value === 'object'
      ? selectedOsType.value?.value || selectedOsType.value
      : selectedOsType.value
    const categoryValue = typeof selectedCategory.value === 'object'
      ? selectedCategory.value?.value || selectedCategory.value
      : selectedCategory.value

    // Normalisieren (lowercase, keine Leerzeichen)
    const normalizedOsType = String(osTypeValue).toLowerCase().replace(/\s+/g, '-')
    const normalizedCategory = String(categoryValue).toLowerCase().replace(/\s+/g, '-')

    // Pruefen ob neue Custom-Werte angelegt werden muessen
    const existingOsTypes = osTypes.value.map(t => t.value)
    const existingCategories = categories.value.map(c => c.value)

    // Neue OS-Type speichern falls noetig
    if (normalizedOsType && !existingOsTypes.includes(normalizedOsType)) {
      const customOsTypes = osTypes.value
        .filter(t => t.isCustom)
        .map(t => t.value)
      customOsTypes.push(normalizedOsType)
      await api.put('/api/settings/os-types', { values: customOsTypes })
    }

    // Neue Kategorie speichern falls noetig
    if (normalizedCategory && !existingCategories.includes(normalizedCategory)) {
      const customCategories = categories.value
        .filter(c => c.isCustom)
        .map(c => c.value)
      customCategories.push(normalizedCategory)
      await api.put('/api/settings/categories', { values: customCategories })
    }

    // Metadaten speichern
    formData.value.os_type = normalizedOsType
    formData.value.category = normalizedCategory
    await api.put(`/api/playbooks/${props.playbook}/metadata`, formData.value)

    showSnackbar?.('Metadaten gespeichert')
    emit('saved')
    close()
  } catch (e) {
    console.error('Fehler beim Speichern:', e)
    showSnackbar?.(e.response?.data?.detail || 'Fehler beim Speichern', 'error')
  } finally {
    saving.value = false
  }
}

function close() {
  dialogVisible.value = false
}

// Watchers
watch(
  () => props.modelValue,
  async (newVal) => {
    if (newVal && props.playbook) {
      await loadMetadata()
    }
  }
)

// Lifecycle
onMounted(() => {
  loadOsTypesAndCategories()
})
</script>
