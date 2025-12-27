<template>
  <img
    :src="logoSrc"
    :alt="alt"
    :class="logoClass"
    :style="customStyle"
  />
</template>

<script setup>
import { computed } from 'vue'
import { useTheme } from 'vuetify'

// Logo Assets
import logoIconWithBg from '@/assets/logo.svg'
import logoIconLight from '@/assets/logo-icon-light.svg'
import logoIconDark from '@/assets/logo-icon-dark.svg'
import logoBannerLight from '@/assets/logo-banner-light.svg'
import logoBannerDark from '@/assets/logo-banner-dark.svg'

const props = defineProps({
  // 'icon' = nur das grafische Logo, 'banner' = komplettes Banner mit Text
  variant: {
    type: String,
    default: 'icon',
    validator: (value) => ['icon', 'banner'].includes(value)
  },
  // Groesse: 'xs', 'sm', 'md', 'lg', 'xl' oder custom via style
  size: {
    type: String,
    default: 'md'
  },
  // Alt-Text
  alt: {
    type: String,
    default: 'PVE Commander Logo'
  },
  // Custom inline styles
  customStyle: {
    type: Object,
    default: () => ({})
  },
  // Bei Icon-Variante: Mit Hexagon-Hintergrund oder transparent?
  withBackground: {
    type: Boolean,
    default: false
  }
})

const theme = useTheme()

// Ist Dark Mode aktiv?
const isDark = computed(() => {
  const themeName = theme.global.name.value
  return themeName.endsWith('Dark')
})

// Logo-Quelle basierend auf Variante, Theme und Background-Option
const logoSrc = computed(() => {
  if (props.variant === 'icon') {
    // Mit Hintergrund: immer das gleiche Logo (hat eigenen blauen Hexagon)
    if (props.withBackground) {
      return logoIconWithBg
    }
    // Ohne Hintergrund: Theme-abhaengig
    return isDark.value ? logoIconDark : logoIconLight
  }
  // Banner: Theme-abhaengig
  return isDark.value ? logoBannerDark : logoBannerLight
})

// CSS-Klassen basierend auf Groesse und Variante
const logoClass = computed(() => {
  const classes = ['app-logo']
  classes.push(`app-logo--${props.variant}`)
  classes.push(`app-logo--${props.size}`)
  return classes
})
</script>

<style scoped>
.app-logo {
  display: block;
  object-fit: contain;
}

/* Icon Variante */
.app-logo--icon.app-logo--xs {
  width: 24px;
  height: 24px;
}

.app-logo--icon.app-logo--sm {
  width: 32px;
  height: 32px;
}

.app-logo--icon.app-logo--md {
  width: 40px;
  height: 40px;
}

.app-logo--icon.app-logo--lg {
  width: 56px;
  height: 56px;
}

.app-logo--icon.app-logo--xl {
  width: 80px;
  height: 80px;
}

/* Banner Variante - kompaktes Layout (480x100 SVG) */
.app-logo--banner.app-logo--xs {
  width: 240px;
  height: auto;
}

.app-logo--banner.app-logo--sm {
  width: 320px;
  height: auto;
}

.app-logo--banner.app-logo--md {
  width: 400px;
  height: auto;
}

.app-logo--banner.app-logo--lg {
  width: 440px;
  height: auto;
}

.app-logo--banner.app-logo--xl {
  width: 480px;
  height: auto;
}
</style>
