<template>
  <v-app>
    <!-- Navigation (nur wenn eingeloggt und nicht im Setup) -->
    <v-navigation-drawer
      v-if="authStore.isAuthenticated && !isSetupRoute"
      v-model="drawer"
      :rail="rail"
      @update:rail="rail = $event"
      permanent
      app
    >
      <!-- Sidebar Header - Banner Logo (ausgeklappt, Hoehe = App-Bar 64px) -->
      <v-menu v-if="!rail" open-on-hover :close-on-content-click="false" location="right">
        <template v-slot:activator="{ props }">
          <div v-bind="props" class="sidebar-header" @click="router.push('/')">
            <AppLogo variant="banner" size="xs" class="sidebar-banner" />
          </div>
        </template>
        <v-card class="logo-tooltip-card pa-4">
          <AppLogo variant="banner" size="md" />
        </v-card>
      </v-menu>

      <!-- Mini-Logo wenn rail aktiv (Hoehe = App-Bar 64px) -->
      <v-menu v-else open-on-hover :close-on-content-click="false" location="right">
        <template v-slot:activator="{ props }">
          <div v-bind="props" class="sidebar-rail-header" @click="router.push('/')">
            <AppLogo variant="icon" size="md" />
          </div>
        </template>
        <v-card class="logo-tooltip-card pa-4">
          <AppLogo variant="banner" size="md" />
        </v-card>
      </v-menu>

      <v-divider></v-divider>

      <v-list nav :class="{ 'rail-list': rail, 'sidebar-list': !rail }">
        <!-- Dashboard -->
        <v-list-item
          to="/"
          :title="rail ? '' : 'Dashboard'"
          :class="{ 'rail-item': rail, 'sidebar-item': !rail }"
        >
          <template v-slot:prepend>
            <v-icon size="24">mdi-view-dashboard</v-icon>
          </template>
          <v-tooltip v-if="rail" activator="parent" location="right">Dashboard</v-tooltip>
        </v-list-item>

        <!-- VMs (Terraform) -->
        <v-list-item
          to="/terraform"
          :title="rail ? '' : 'VMs'"
          :class="{ 'rail-item': rail, 'sidebar-item': !rail }"
        >
          <template v-slot:prepend>
            <v-badge
              v-if="terraformStore.orphanedCount > 0"
              :content="terraformStore.orphanedCount"
              color="warning"
              offset-x="-2"
              offset-y="-2"
            >
              <v-icon size="24">mdi-server-network</v-icon>
            </v-badge>
            <v-icon v-else :size="rail ? 24 : 28">mdi-server-network</v-icon>
          </template>
          <v-tooltip v-if="rail" activator="parent" location="right">VMs</v-tooltip>
        </v-list-item>

        <!-- Netzwerk -->
        <v-list-item
          to="/netbox"
          :title="rail ? '' : 'Netzwerk'"
          :class="{ 'rail-item': rail, 'sidebar-item': !rail }"
        >
          <template v-slot:prepend>
            <v-icon size="24">mdi-ip-network</v-icon>
          </template>
          <v-tooltip v-if="rail" activator="parent" location="right">Netzwerk</v-tooltip>
        </v-list-item>

        <!-- Playbooks -->
        <v-list-item
          to="/playbooks"
          :title="rail ? '' : 'Playbooks'"
          :class="{ 'rail-item': rail, 'sidebar-item': !rail }"
        >
          <template v-slot:prepend>
            <v-icon size="24">mdi-script-text</v-icon>
          </template>
          <v-tooltip v-if="rail" activator="parent" location="right">Playbooks</v-tooltip>
        </v-list-item>

        <!-- Inventory -->
        <v-list-item
          to="/inventory"
          :title="rail ? '' : 'Inventory'"
          :class="{ 'rail-item': rail, 'sidebar-item': !rail }"
        >
          <template v-slot:prepend>
            <v-icon size="24">mdi-format-list-bulleted</v-icon>
          </template>
          <v-tooltip v-if="rail" activator="parent" location="right">Inventory</v-tooltip>
        </v-list-item>

        <!-- History (Executions) -->
        <v-list-item
          to="/executions"
          :title="rail ? '' : 'History'"
          :class="{ 'rail-item': rail, 'sidebar-item': !rail }"
        >
          <template v-slot:prepend>
            <v-icon size="24">mdi-history</v-icon>
          </template>
          <v-tooltip v-if="rail" activator="parent" location="right">History</v-tooltip>
        </v-list-item>

        <!-- Kapazitaet -->
        <v-list-item
          to="/capacity"
          :title="rail ? '' : 'Kapazitaet'"
          :class="{ 'rail-item': rail, 'sidebar-item': !rail }"
        >
          <template v-slot:prepend>
            <v-icon size="24">mdi-chart-bar</v-icon>
          </template>
          <v-tooltip v-if="rail" activator="parent" location="right">Kapazitaet</v-tooltip>
        </v-list-item>

        <v-divider class="my-2" v-if="authStore.isSuperAdmin" />

        <!-- Audit-Log (nur Super-Admin) -->
        <v-list-item
          v-if="authStore.isSuperAdmin"
          to="/audit-log"
          :title="rail ? '' : 'Audit-Log'"
          :class="{ 'rail-item': rail, 'sidebar-item': !rail }"
        >
          <template v-slot:prepend>
            <v-icon size="24">mdi-clipboard-text-clock</v-icon>
          </template>
          <v-tooltip v-if="rail" activator="parent" location="right">Audit-Log</v-tooltip>
        </v-list-item>

        <!-- Einstellungen (nur Super-Admin) - vereinfacht -->
        <v-list-item
          v-if="authStore.isSuperAdmin"
          to="/settings"
          :title="rail ? '' : 'Einstellungen'"
          :class="{ 'rail-item': rail, 'sidebar-item': !rail }"
        >
          <template v-slot:prepend>
            <v-icon size="24">mdi-cog</v-icon>
          </template>
          <v-tooltip v-if="rail" activator="parent" location="right">Einstellungen</v-tooltip>
        </v-list-item>
      </v-list>

      <!-- Spacer -->
      <v-spacer></v-spacer>

      <!-- Version Footer -->
      <div class="sidebar-footer">
        <v-divider></v-divider>
        <div
          :class="['sidebar-footer-content', { 'sidebar-footer-rail': rail }]"
          @click="showChangelog = true"
        >
          <v-icon size="14" class="mr-1">mdi-tag-outline</v-icon>
          <span v-if="!rail">v{{ appVersion }}</span>
          <v-tooltip activator="parent" :location="rail ? 'right' : 'top'">
            Changelog anzeigen
          </v-tooltip>
        </div>
      </div>

    </v-navigation-drawer>

    <!-- App Bar (nur wenn eingeloggt und nicht im Setup) -->
    <v-app-bar v-if="authStore.isAuthenticated && !isSetupRoute" app elevation="1">
      <v-app-bar-nav-icon @click="rail = !rail"></v-app-bar-nav-icon>
      <v-toolbar-title>{{ currentPageTitle }}</v-toolbar-title>
      <v-spacer></v-spacer>

      <!-- Datum und Uhrzeit -->
      <span class="text-body-2 text-medium-emphasis mr-4">
        {{ currentDateTime }}
      </span>

      <!-- Service Status Badge -->
      <v-chip
        :color="healthStatus.color"
        size="small"
        variant="tonal"
        class="mr-2"
        @click="showHealthDetails = true"
      >
        <v-icon start size="small">{{ healthStatus.icon }}</v-icon>
        {{ healthStatus.label }}
      </v-chip>

      <!-- User Menu -->
      <v-menu>
        <template v-slot:activator="{ props }">
          <v-btn icon v-bind="props">
            <v-avatar size="32" :color="authStore.isSuperAdmin ? 'warning' : 'primary'">
              <v-icon size="20">{{ authStore.isSuperAdmin ? 'mdi-shield-crown' : 'mdi-account' }}</v-icon>
            </v-avatar>
          </v-btn>
        </template>
        <v-list>
          <v-list-item>
            <template v-slot:prepend>
              <v-avatar size="40" :color="authStore.isSuperAdmin ? 'warning' : 'primary'" class="mr-3">
                <v-icon size="24">{{ authStore.isSuperAdmin ? 'mdi-shield-crown' : 'mdi-account' }}</v-icon>
              </v-avatar>
            </template>
            <v-list-item-title>{{ authStore.user?.username }}</v-list-item-title>
            <v-list-item-subtitle>{{ authStore.isSuperAdmin ? 'Super-Admin' : 'Benutzer' }}</v-list-item-subtitle>
          </v-list-item>
          <v-divider></v-divider>
          <v-list-item @click="openProfile">
            <template v-slot:prepend>
              <v-icon>mdi-account-cog</v-icon>
            </template>
            <v-list-item-title>Mein Profil</v-list-item-title>
          </v-list-item>
          <v-list-item @click="logout">
            <template v-slot:prepend>
              <v-icon>mdi-logout</v-icon>
            </template>
            <v-list-item-title>Abmelden</v-list-item-title>
          </v-list-item>
        </v-list>
      </v-menu>
    </v-app-bar>

    <!-- Main Content -->
    <v-main>
      <router-view />
    </v-main>

    <!-- Profile Dialog -->
    <ProfileDialog ref="profileDialog" />

    <!-- Beta UI: Globaler Bestaetigungsdialog -->
    <ConfirmDialogProvider v-if="authStore.currentUiBeta" />

    <!-- Beta UI: NotificationStack -->
    <NotificationStack v-if="authStore.currentUiBeta" />

    <!-- Beta UI: Command Palette (Cmd+K) -->
    <CommandPalette v-if="authStore.currentUiBeta" ref="commandPalette" />

    <!-- Snackbar für Benachrichtigungen (Legacy, wird durch NotificationStack ersetzt) -->
    <v-snackbar
      v-model="snackbar.show"
      :color="snackbar.color"
      :timeout="3000"
    >
      {{ snackbar.text }}
    </v-snackbar>

    <!-- Health Status Dialog -->
    <v-dialog v-model="showHealthDetails" max-width="400">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2" :color="healthStatus.color">{{ healthStatus.icon }}</v-icon>
          Service Status
        </v-card-title>
        <v-card-text>
          <v-list density="compact">
            <v-list-item v-for="(service, name) in healthData.services" :key="name">
              <template v-slot:prepend>
                <v-icon :color="getServiceColor(service.status)" size="small">
                  {{ getServiceIcon(service.status) }}
                </v-icon>
              </template>
              <v-list-item-title>{{ name.toUpperCase() }}</v-list-item-title>
              <v-list-item-subtitle>{{ service.message }}</v-list-item-subtitle>
            </v-list-item>
          </v-list>
          <v-alert v-if="healthData.status === 'starting'" type="info" variant="tonal" density="compact" class="mt-2">
            Services werden gestartet. Dies kann einige Minuten dauern...
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="fetchHealth">Aktualisieren</v-btn>
          <v-btn color="primary" @click="showHealthDetails = false">Schließen</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Changelog Dialog -->
    <v-dialog v-model="showChangelog" max-width="600">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2">mdi-history</v-icon>
          Changelog
        </v-card-title>
        <v-card-text>
          <div v-for="release in changelog" :key="release.version" class="mb-4">
            <div class="text-h6 mb-2">{{ release.version }} <span v-if="release.title" class="text-primary ml-2">{{ release.title }}</span> <span class="text-caption text-grey">({{ release.date }})</span></div>
            <div v-for="(items, category) in release.changes" :key="category" class="mb-2">
              <div class="font-weight-medium text-primary">{{ category }}</div>
              <ul class="pl-4">
                <li v-for="item in items" :key="item" class="text-body-2">{{ item }}</li>
              </ul>
            </div>
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="primary" @click="showChangelog = false">Schließen</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-app>
</template>

<script setup>
import { ref, computed, provide, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTheme } from 'vuetify'
import { useAuthStore } from '@/stores/auth'
import { useTerraformStore } from '@/stores/terraform'
import ProfileDialog from '@/components/ProfileDialog.vue'
import ConfirmDialogProvider from '@/components/common/ConfirmDialogProvider.vue'
import NotificationStack from '@/components/common/NotificationStack.vue'
import CommandPalette from '@/components/common/CommandPalette.vue'
import AppLogo from '@/components/AppLogo.vue'
import changelog from '@/data/changelog.json'
import axios from 'axios'

const appVersion = __APP_VERSION__

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const terraformStore = useTerraformStore()
const theme = useTheme()

const drawer = ref(true)
const rail = ref(false)

// Datum und Uhrzeit
const currentDateTime = ref('')
let clockInterval = null

function updateDateTime() {
  const now = new Date()
  const options = {
    weekday: 'short',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }
  currentDateTime.value = now.toLocaleString('de-DE', options)
}

// Theme bei Aenderung anwenden (kombiniert Farbschema + Dark Mode)
watch([() => authStore.currentTheme, () => authStore.currentDarkMode], ([newTheme, newDarkMode]) => {
  if (!newTheme) return

  // Dark Mode bestimmen
  let isDark = true
  if (newDarkMode === 'light') {
    isDark = false
  } else if (newDarkMode === 'system') {
    isDark = authStore.systemPrefersDark
  }

  // Vuetify Theme-Name zusammensetzen
  const vuetifyThemeName = newTheme + (isDark ? 'Dark' : 'Light')

  if (theme.global.name.value !== vuetifyThemeName) {
    theme.global.name.value = vuetifyThemeName
  }
}, { immediate: true })
const profileDialog = ref(null)
const commandPalette = ref(null)
const showChangelog = ref(false)
const showHealthDetails = ref(false)

// Health Status
const healthData = ref({
  status: 'unknown',
  services: {}
})

let healthInterval = null

const fetchHealth = async () => {
  try {
    const response = await axios.get('/api/health')
    healthData.value = response.data
  } catch (e) {
    healthData.value = {
      status: 'error',
      services: { api: { status: 'error', message: 'API not reachable' } }
    }
  }
}

const healthStatus = computed(() => {
  const status = healthData.value.status
  const statusMap = {
    healthy: { color: 'success', icon: 'mdi-check-circle', label: 'Services: Online' },
    starting: { color: 'warning', icon: 'mdi-loading mdi-spin', label: 'Services: Starting...' },
    degraded: { color: 'warning', icon: 'mdi-alert-circle', label: 'Services: Degraded' },
    error: { color: 'error', icon: 'mdi-close-circle', label: 'Services: Error' },
    unknown: { color: 'grey', icon: 'mdi-help-circle', label: 'Services: Unknown' },
  }
  return statusMap[status] || statusMap.unknown
})

const getServiceColor = (status) => {
  const colors = { healthy: 'success', starting: 'warning', degraded: 'warning', error: 'error' }
  return colors[status] || 'grey'
}

const getServiceIcon = (status) => {
  const icons = {
    healthy: 'mdi-check-circle',
    starting: 'mdi-loading mdi-spin',
    degraded: 'mdi-alert-circle',
    error: 'mdi-close-circle'
  }
  return icons[status] || 'mdi-help-circle'
}

onMounted(() => {
  fetchHealth()
  // Alle 30 Sekunden aktualisieren
  healthInterval = setInterval(fetchHealth, 30000)

  // Uhrzeit initialisieren und jede Sekunde aktualisieren
  updateDateTime()
  clockInterval = setInterval(updateDateTime, 1000)

  // Terraform Health-Status Polling starten (wenn eingeloggt)
  if (authStore.isAuthenticated) {
    terraformStore.startPolling(60000) // Alle 60 Sekunden
  }
})

// Polling starten wenn User sich einloggt
watch(() => authStore.isAuthenticated, (isAuth) => {
  if (isAuth) {
    terraformStore.startPolling(60000)
  } else {
    terraformStore.stopPolling()
  }
})

onUnmounted(() => {
  if (healthInterval) clearInterval(healthInterval)
  if (clockInterval) clearInterval(clockInterval)
  terraformStore.stopPolling()
})

// Mapping für Seitentitel (flache Struktur)
const pageTitles = {
  '/': 'Dashboard',
  '/terraform': 'VMs',
  '/netbox': 'Netzwerk',
  '/playbooks': 'Playbooks',
  '/inventory': 'Inventory',
  '/executions': 'History',
  '/capacity': 'Kapazität',
  '/audit-log': 'Audit-Log',
  '/settings': 'Einstellungen',
  '/my/notifications': 'Meine Benachrichtigungen',
}

// Setup-Route erkennen (keine Navigation anzeigen)
const isSetupRoute = computed(() => route.path === '/setup')

const currentPageTitle = computed(() => {
  // Prüfe auf exakte Übereinstimmung
  if (pageTitles[route.path]) {
    return pageTitles[route.path]
  }
  // Prüfe auf Präfix (z.B. /executions/123)
  for (const [path, title] of Object.entries(pageTitles)) {
    if (path !== '/' && route.path.startsWith(path)) {
      return title
    }
  }
  return 'PVE Commander'
})

// Snackbar
const snackbar = ref({
  show: false,
  text: '',
  color: 'success',
})

const showSnackbar = (text, color = 'success') => {
  snackbar.value = { show: true, text, color }
}

provide('showSnackbar', showSnackbar)

// Profile
const openProfile = () => {
  profileDialog.value.open()
}

// Logout
const logout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<style>
html {
  overflow-y: auto !important;
}

/* Sidebar Banner Header Styles */
.sidebar-banner-header {
  padding: 12px 16px;
  text-align: center;
}

.sidebar-banner-logo-wrapper {
  cursor: pointer;
}

.sidebar-banner-logo {
  max-width: 100%;
  height: auto;
}

.sidebar-banner-version {
  margin-top: 4px;
  font-size: 0.75rem;
  color: rgba(var(--v-theme-on-surface), 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Logo Tooltip Styles */
.logo-tooltip {
  background: rgba(var(--v-theme-surface), 0.98) !important;
  padding: 16px !important;
  border-radius: 8px !important;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3) !important;
}

/* Rail Mode Styles - Icons farbig hervorheben */
.rail-list .v-list-item {
  padding-left: 8px !important;
  padding-right: 8px !important;
}

.rail-list .v-list-item .v-list-item__prepend {
  margin-right: 0 !important;
}

.rail-list .v-list-item .v-icon {
  color: rgb(var(--v-theme-primary)) !important;
  opacity: 0.8;
}

.rail-list .v-list-item:hover .v-icon {
  opacity: 1;
}

.rail-list .v-list-item--active .v-icon {
  color: rgb(var(--v-theme-primary)) !important;
  opacity: 1;
}

/* Sidebar Normal Mode - Icons und Text */
.sidebar-list .v-list-item {
  min-height: 48px !important;
  padding: 8px 16px !important;
}

.sidebar-list .v-list-item .v-list-item__prepend {
  margin-right: 16px !important;
}

.sidebar-list .v-list-item .v-icon {
  color: rgb(var(--v-theme-primary)) !important;
  opacity: 0.7;
}

.sidebar-list .v-list-item:hover .v-icon {
  opacity: 1;
}

.sidebar-list .v-list-item--active .v-icon {
  color: rgb(var(--v-theme-primary)) !important;
  opacity: 1;
}

.sidebar-item .v-list-item-title {
  font-size: 1rem !important;
  font-weight: 500 !important;
}

/* Sidebar Header mit Banner - gleiche Hoehe wie App-Bar (64px) */
.sidebar-header {
  height: 64px;
  display: flex;
  align-items: center;
  padding: 0 12px !important;
  cursor: pointer;
}

.sidebar-header:hover {
  background: rgba(var(--v-theme-primary), 0.04);
}

.sidebar-banner {
  height: 32px;
  width: auto;
}

/* Rail Header - exakt gleiche Hoehe wie App-Bar (64px) */
.sidebar-rail-header {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.sidebar-rail-header:hover {
  background: rgba(var(--v-theme-primary), 0.04);
}

/* Logo Tooltip Card */
.logo-tooltip-card {
  background: rgba(var(--v-theme-surface), 0.98) !important;
  border-radius: 8px !important;
}

/* Sidebar Footer */
.sidebar-footer {
  flex-shrink: 0;
}

.sidebar-footer-content {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
  cursor: pointer;
  color: rgba(var(--v-theme-on-surface), 0.5);
  font-size: 0.75rem;
  transition: color 0.2s ease;
}

.sidebar-footer-content:hover {
  color: rgb(var(--v-theme-primary));
}

.sidebar-footer-rail {
  padding: 12px 8px;
}
</style>
