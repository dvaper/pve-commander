<template>
  <div class="notification-stack">
    <TransitionGroup name="notification">
      <div
        v-for="notification in activeNotifications"
        :key="notification.id"
        class="notification-item"
        :class="[
          `notification-item--${notification.type}`,
          { 'notification-item--dismissed': notification.dismissed }
        ]"
      >
        <div class="notification-content">
          <div class="notification-icon">
            <v-progress-circular
              v-if="notification.type === 'loading'"
              indeterminate
              size="20"
              width="2"
              color="primary"
            />
            <v-icon
              v-else
              :color="getIconColor(notification.type)"
              size="20"
            >
              {{ notification.icon }}
            </v-icon>
          </div>

          <div class="notification-text">
            <div class="notification-title">{{ notification.title }}</div>
            <div v-if="notification.message" class="notification-message">
              {{ notification.message }}
            </div>
          </div>

          <v-btn
            v-if="!notification.persistent"
            icon
            size="x-small"
            variant="text"
            class="notification-close"
            @click="dismiss(notification.id)"
          >
            <v-icon size="16">mdi-close</v-icon>
          </v-btn>
        </div>

        <!-- Progress bar for auto-dismiss -->
        <div
          v-if="notification.timeout > 0 && !notification.persistent"
          class="notification-progress"
          :style="{ animationDuration: `${notification.timeout}ms` }"
        />
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useNotificationStore } from '@/stores/notification'

const store = useNotificationStore()

const activeNotifications = computed(() => store.activeNotifications)

function dismiss(id) {
  store.dismiss(id)
}

function getIconColor(type) {
  const colors = {
    success: 'success',
    error: 'error',
    warning: 'warning',
    info: 'info',
    loading: 'primary',
  }
  return colors[type] || 'grey'
}
</script>

<style scoped>
.notification-stack {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 9999;
  display: flex;
  flex-direction: column-reverse;
  gap: 8px;
  max-width: 400px;
  pointer-events: none;
}

.notification-item {
  background: rgb(var(--v-theme-surface));
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  overflow: hidden;
  pointer-events: auto;
  border-left: 4px solid transparent;
}

.notification-item--success {
  border-left-color: rgb(var(--v-theme-success));
}

.notification-item--error {
  border-left-color: rgb(var(--v-theme-error));
}

.notification-item--warning {
  border-left-color: rgb(var(--v-theme-warning));
}

.notification-item--info {
  border-left-color: rgb(var(--v-theme-info));
}

.notification-item--loading {
  border-left-color: rgb(var(--v-theme-primary));
}

.notification-content {
  display: flex;
  align-items: flex-start;
  padding: 12px 16px;
  gap: 12px;
}

.notification-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding-top: 2px;
}

.notification-text {
  flex: 1;
  min-width: 0;
}

.notification-title {
  font-weight: 500;
  font-size: 14px;
  line-height: 1.4;
  color: rgb(var(--v-theme-on-surface));
}

.notification-message {
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface));
  opacity: 0.7;
  margin-top: 2px;
  line-height: 1.4;
}

.notification-close {
  flex-shrink: 0;
  margin: -4px -8px -4px 0;
  opacity: 0.6;
}

.notification-close:hover {
  opacity: 1;
}

.notification-progress {
  height: 3px;
  background: rgba(var(--v-theme-on-surface), 0.1);
  position: relative;
  overflow: hidden;
}

.notification-progress::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  width: 100%;
  background: rgba(var(--v-theme-primary), 0.5);
  animation: progress-shrink linear forwards;
}

@keyframes progress-shrink {
  from {
    transform: scaleX(1);
    transform-origin: left;
  }
  to {
    transform: scaleX(0);
    transform-origin: left;
  }
}

/* Transition animations */
.notification-enter-active {
  animation: notification-in 0.3s ease-out;
}

.notification-leave-active {
  animation: notification-out 0.3s ease-in;
}

@keyframes notification-in {
  from {
    opacity: 0;
    transform: translateX(100%);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes notification-out {
  from {
    opacity: 1;
    transform: translateX(0);
  }
  to {
    opacity: 0;
    transform: translateX(100%);
  }
}

/* Mobile responsiveness */
@media (max-width: 480px) {
  .notification-stack {
    left: 16px;
    right: 16px;
    bottom: 16px;
    max-width: none;
  }
}
</style>
