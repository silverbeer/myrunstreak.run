<template>
  <div class="container-app py-8 max-w-2xl">
    <h1 class="text-2xl font-bold text-gray-900 mb-6">Settings</h1>

    <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
      <h2 class="text-lg font-semibold text-gray-900 mb-1">Units</h2>
      <p class="text-sm text-gray-500 mb-4">
        Choose how distance and pace are displayed across the app.
      </p>

      <div class="inline-flex rounded-lg border border-gray-200 p-1 bg-gray-50">
        <button
          v-for="option in options"
          :key="option.value"
          type="button"
          @click="selectUnit(option.value)"
          :class="[
            'px-4 py-2 text-sm font-semibold rounded-md transition',
            unit === option.value
              ? 'bg-white text-brand-600 shadow-sm'
              : 'text-gray-500 hover:text-gray-800',
          ]"
        >
          {{ option.label }}
        </button>
      </div>

      <p v-if="saved" class="text-xs text-green-600 mt-3">Saved</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useUserPreferences } from '@/composables/useUserPreferences'
import type { Unit } from '@/types/runs'

const { unit, setUnit } = useUserPreferences()
const saved = ref(false)

const options: { value: Unit; label: string }[] = [
  { value: 'mi', label: 'Miles' },
  { value: 'km', label: 'Kilometers' },
]

const selectUnit = async (value: Unit) => {
  if (unit.value === value) return
  await setUnit(value)
  saved.value = true
  setTimeout(() => (saved.value = false), 2000)
}
</script>
