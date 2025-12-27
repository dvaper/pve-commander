/**
 * PVE Commander - Vue.js Entry Point
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'

// Vuetify
import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import '@mdi/font/css/materialdesignicons.css'

import App from './App.vue'
import router from './router'

// Vuetify Theme mit benutzerdefinierten Farbthemes (Dark + Light Varianten)
const vuetify = createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: 'blueDark',
    themes: {
      // ========== DARK THEMES ==========
      blueDark: {
        dark: true,
        colors: {
          primary: '#1976D2',
          secondary: '#424242',
          accent: '#82B1FF',
          error: '#FF5252',
          info: '#2196F3',
          success: '#4CAF50',
          warning: '#FFC107',
          background: '#121212',
          surface: '#1E1E1E',
        },
      },
      orangeDark: {
        dark: true,
        colors: {
          primary: '#FF9800',
          secondary: '#5D4037',
          accent: '#FFAB40',
          error: '#FF5252',
          info: '#FF9800',
          success: '#4CAF50',
          warning: '#FFC107',
          background: '#121212',
          surface: '#1E1E1E',
        },
      },
      greenDark: {
        dark: true,
        colors: {
          primary: '#4CAF50',
          secondary: '#2E7D32',
          accent: '#69F0AE',
          error: '#FF5252',
          info: '#2196F3',
          success: '#4CAF50',
          warning: '#FFC107',
          background: '#121212',
          surface: '#1E1E1E',
        },
      },
      purpleDark: {
        dark: true,
        colors: {
          primary: '#9C27B0',
          secondary: '#6A1B9A',
          accent: '#E040FB',
          error: '#FF5252',
          info: '#2196F3',
          success: '#4CAF50',
          warning: '#FFC107',
          background: '#121212',
          surface: '#1E1E1E',
        },
      },
      tealDark: {
        dark: true,
        colors: {
          primary: '#009688',
          secondary: '#00695C',
          accent: '#64FFDA',
          error: '#FF5252',
          info: '#2196F3',
          success: '#4CAF50',
          warning: '#FFC107',
          background: '#121212',
          surface: '#1E1E1E',
        },
      },
      // ========== LIGHT THEMES ==========
      blueLight: {
        dark: false,
        colors: {
          primary: '#1976D2',
          secondary: '#546E7A',
          accent: '#82B1FF',
          error: '#D32F2F',
          info: '#1976D2',
          success: '#388E3C',
          warning: '#F57C00',
          background: '#FAFAFA',
          surface: '#FFFFFF',
        },
      },
      orangeLight: {
        dark: false,
        colors: {
          primary: '#E65100',
          secondary: '#6D4C41',
          accent: '#FF9100',
          error: '#D32F2F',
          info: '#E65100',
          success: '#388E3C',
          warning: '#F57C00',
          background: '#FAFAFA',
          surface: '#FFFFFF',
        },
      },
      greenLight: {
        dark: false,
        colors: {
          primary: '#2E7D32',
          secondary: '#558B2F',
          accent: '#00C853',
          error: '#D32F2F',
          info: '#1976D2',
          success: '#2E7D32',
          warning: '#F57C00',
          background: '#FAFAFA',
          surface: '#FFFFFF',
        },
      },
      purpleLight: {
        dark: false,
        colors: {
          primary: '#7B1FA2',
          secondary: '#512DA8',
          accent: '#D500F9',
          error: '#D32F2F',
          info: '#1976D2',
          success: '#388E3C',
          warning: '#F57C00',
          background: '#FAFAFA',
          surface: '#FFFFFF',
        },
      },
      tealLight: {
        dark: false,
        colors: {
          primary: '#00796B',
          secondary: '#00695C',
          accent: '#1DE9B6',
          error: '#D32F2F',
          info: '#1976D2',
          success: '#388E3C',
          warning: '#F57C00',
          background: '#FAFAFA',
          surface: '#FFFFFF',
        },
      },
    },
  },
})

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(vuetify)

app.mount('#app')
