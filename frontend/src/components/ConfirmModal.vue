<template>
  <div v-if="show" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click="$emit('cancel')">
    <div class="bg-white rounded-xl shadow-xl max-w-md w-[90%] max-h-[90vh] overflow-y-auto" @click.stop>
      <div class="p-6">
        <div class="flex items-start mb-4">
          <div class="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center mr-4" :class="iconBgClass">
            <svg class="w-6 h-6" :class="iconClass" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="iconPath" />
            </svg>
          </div>
          <div>
            <h3 class="text-lg font-semibold text-gray-900">{{ title }}</h3>
            <p v-if="message" class="mt-1 text-sm text-gray-500">{{ message }}</p>
          </div>
        </div>

        <div v-if="$slots.default" class="mb-4">
          <slot></slot>
        </div>

        <div class="flex justify-end gap-3">
          <button type="button" @click="$emit('cancel')" class="btn-secondary text-sm">
            {{ cancelText }}
          </button>
          <button type="button" @click="$emit('confirm')" :disabled="loading" :class="confirmClass">
            {{ loading ? loadingText : confirmText }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  show: boolean
  title?: string
  message?: string
  confirmText?: string
  cancelText?: string
  loadingText?: string
  loading?: boolean
  variant?: 'info' | 'warning' | 'danger'
}>(), {
  title: 'Confirm',
  message: '',
  confirmText: 'Confirm',
  cancelText: 'Cancel',
  loadingText: 'Processing...',
  loading: false,
  variant: 'info',
})

defineEmits<{ confirm: []; cancel: [] }>()

const iconBgClass = computed(() => ({
  'bg-blue-100': props.variant === 'info',
  'bg-yellow-100': props.variant === 'warning',
  'bg-red-100': props.variant === 'danger',
}))

const iconClass = computed(() => ({
  'text-blue-600': props.variant === 'info',
  'text-yellow-600': props.variant === 'warning',
  'text-red-600': props.variant === 'danger',
}))

const iconPath = computed(() => {
  if (props.variant === 'danger' || props.variant === 'warning') {
    return 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z'
  }
  return 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z'
})

const confirmClass = computed(() => {
  const base = 'px-4 py-2 text-sm font-semibold text-white rounded-lg disabled:opacity-50 transition'
  if (props.variant === 'danger') return `${base} bg-red-600 hover:bg-red-700`
  if (props.variant === 'warning') return `${base} bg-yellow-600 hover:bg-yellow-700`
  return `${base} bg-brand-600 hover:bg-brand-700`
})
</script>
