/**
 * Vue Router Konfiguration
 */
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import axios from 'axios'

// Setup-Status Cache (wird beim ersten Aufruf geladen)
let setupStatusCache = null
let setupStatusLoading = null

async function checkSetupStatus() {
  // Cache verwenden wenn vorhanden
  if (setupStatusCache !== null) {
    return setupStatusCache
  }

  // Wenn bereits eine Anfrage laeuft, darauf warten
  if (setupStatusLoading) {
    return setupStatusLoading
  }

  // Status vom Backend abrufen
  setupStatusLoading = axios.get('/api/setup/status')
    .then(response => {
      setupStatusCache = response.data.setup_complete
      return setupStatusCache
    })
    .catch(() => {
      // Bei Fehler annehmen dass Setup abgeschlossen ist
      // (Backend nicht erreichbar = andere Probleme)
      return true
    })
    .finally(() => {
      setupStatusLoading = null
    })

  return setupStatusLoading
}

// Cache invalidieren (z.B. nach Setup)
export function invalidateSetupCache() {
  setupStatusCache = null
}

const routes = [
  // Auth & Setup
  {
    path: '/setup',
    name: 'Setup',
    component: () => import('@/views/SetupWizardView.vue'),
    meta: { requiresAuth: false, isSetupPage: true },
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/forgot-password',
    name: 'ForgotPassword',
    component: () => import('@/views/ForgotPasswordView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/reset-password',
    name: 'ResetPassword',
    component: () => import('@/views/ResetPasswordView.vue'),
    meta: { requiresAuth: false },
  },

  // Haupt-Navigation (flache Struktur)
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/terraform',
    name: 'VMs',
    component: () => import('@/views/TerraformView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/netbox',
    name: 'Netzwerk',
    component: () => import('@/views/NetBoxView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/playbooks',
    name: 'Playbooks',
    component: () => import('@/views/PlaybooksView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/inventory',
    name: 'Inventory',
    component: () => import('@/views/InventoryView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/executions',
    name: 'History',
    component: () => import('@/views/ExecutionsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/executions/:id',
    name: 'ExecutionDetail',
    component: () => import('@/views/ExecutionDetailView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/capacity',
    name: 'Kapazitaet',
    component: () => import('@/views/TerraformCapacityView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/audit-log',
    name: 'AuditLog',
    component: () => import('@/views/AuditLogView.vue'),
    meta: { requiresAuth: true, requiresSuperAdmin: true },
  },

  // Admin-Bereich (vereinfacht)
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { requiresAuth: true, requiresSuperAdmin: true },
  },
  {
    path: '/settings/netbox/users',
    name: 'netbox-users',
    component: () => import('@/views/NetBoxUsersView.vue'),
    meta: { requiresAuth: true, requiresSuperAdmin: true },
  },

  // Benutzer-spezifische Seiten
  {
    path: '/my/notifications',
    name: 'MyNotifications',
    component: () => import('@/views/MyNotificationsView.vue'),
    meta: { requiresAuth: true },
  },

  // Legacy Redirects (fuer Backwards-Kompatibilitaet)
  { path: '/users', redirect: '/settings?tab=users' },
  { path: '/roles', redirect: '/settings?tab=users' },
  { path: '/audit', redirect: '/audit-log' },
  { path: '/settings/proxmox', redirect: '/settings?tab=proxmox' },
  { path: '/settings/netbox', redirect: '/settings?tab=netbox' },
  { path: '/settings/notifications', redirect: '/settings?tab=notifications' },
  { path: '/settings/cloud-init', redirect: '/executions?tab=cloud-init' },
  { path: '/settings/ssh', redirect: '/settings?tab=ansible' },
  { path: '/settings/backup', redirect: '/settings?tab=backup' },
  { path: '/settings/netbox-users', redirect: '/settings/netbox/users' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Navigation Guard
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()

  // Setup-Status pruefen (ausser auf der Setup-Seite selbst)
  if (!to.meta.isSetupPage) {
    const setupComplete = await checkSetupStatus()

    if (!setupComplete) {
      // Setup nicht abgeschlossen -> zur Setup-Seite
      next('/setup')
      return
    }
  }

  // Auf Setup-Seite aber Setup bereits abgeschlossen
  // HINWEIS: Setup-Seite ist immer erreichbar fuer erneutes Setup (Testing)
  // Der Backend-Endpoint verwendet ?force=true um das zu erlauben
  if (to.meta.isSetupPage) {
    // Setup-Seite immer erlauben - Backend regelt den Rest
    // Cache invalidieren damit der neue Status geladen wird
    invalidateSetupCache()
  }

  // Pruefen ob Authentifizierung erforderlich
  if (to.meta.requiresAuth !== false && !authStore.isAuthenticated) {
    next('/login')
    return
  }

  // Pruefen ob Super-Admin erforderlich
  if (to.meta.requiresSuperAdmin && !authStore.isSuperAdmin) {
    next('/')
    return
  }

  // Login-Seite wenn bereits eingeloggt
  if (to.path === '/login' && authStore.isAuthenticated) {
    next('/')
    return
  }

  next()
})

export default router
