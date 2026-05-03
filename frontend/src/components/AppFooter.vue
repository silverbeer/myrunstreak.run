<template>
  <footer class="bg-gray-50 border-t border-gray-200 mt-8">
    <div class="container-app py-4">
      <div class="flex flex-wrap items-center justify-between gap-3 text-sm text-gray-500">
        <span class="font-mono text-xs">{{ version }}</span>
        <span>© {{ currentYear }} MyRunStreak</span>
        <span :class="statusClass" class="flex items-center gap-1 text-xs">
          <span class="w-2 h-2 rounded-full" :class="dotClass"></span>
          {{ statusText }}
        </span>
      </div>
    </div>
  </footer>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

const version = ref<string | null>(null)
const apiStatus = ref<'healthy' | 'error' | 'unknown'>('unknown')
const currentYear = computed(() => new Date().getFullYear())

const statusText = computed(() => {
  if (apiStatus.value === 'healthy') return 'API healthy'
  if (apiStatus.value === 'error') return 'API unreachable'
  return ''
})

const statusClass = computed(() => ({
  'text-green-600': apiStatus.value === 'healthy',
  'text-red-500': apiStatus.value === 'error',
  'invisible': apiStatus.value === 'unknown',
}))

const dotClass = computed(() => ({
  'bg-green-500': apiStatus.value === 'healthy',
  'bg-red-400': apiStatus.value === 'error',
}))

onMounted(async () => {
  try {
    const base = window.location.hostname === 'localhost' ? '/api' : ''
    const res = await fetch(`${base}/version`)
    if (res.ok) {
      const data = await res.json()
      version.value = data.version ?? null
      apiStatus.value = 'healthy'
    } else {
      apiStatus.value = 'error'
    }
  } catch {
    apiStatus.value = 'error'
  }
})
</script>
