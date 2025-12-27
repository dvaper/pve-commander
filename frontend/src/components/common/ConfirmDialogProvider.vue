<template>
  <ConfirmDialog
    v-model="isOpen"
    :title="dialogProps.title"
    :message="dialogProps.message"
    :icon="dialogProps.icon"
    :icon-color="dialogProps.iconColor"
    :confirm-label="dialogProps.confirmLabel"
    :confirm-color="dialogProps.confirmColor"
    :confirm-variant="dialogProps.confirmVariant"
    :confirm-icon="dialogProps.confirmIcon"
    :cancel-label="dialogProps.cancelLabel"
    :require-confirmation="dialogProps.requireConfirmation"
    :confirmation-label="dialogProps.confirmationLabel"
    :require-text-confirmation="dialogProps.requireTextConfirmation"
    :loading="dialogProps.loading"
    @confirm="onConfirm"
    @cancel="onCancel"
  >
    <template v-if="dialogProps.details" #details>
      <component :is="dialogProps.details" />
    </template>
  </ConfirmDialog>
</template>

<script setup>
import { useConfirmDialog } from '@/composables/useConfirmDialog'
import ConfirmDialog from './ConfirmDialog.vue'

const { isOpen, dialogProps, onConfirm, onCancel } = useConfirmDialog()
</script>
