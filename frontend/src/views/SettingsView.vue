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

    <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-6 mt-6">
      <h2 class="text-lg font-semibold text-gray-900 mb-1">Default view</h2>
      <p class="text-sm text-gray-500 mb-4">
        Where the app opens after you sign in. Auto picks based on your role.
      </p>

      <div class="inline-flex rounded-lg border border-gray-200 p-1 bg-gray-50">
        <button
          v-for="option in viewOptions"
          :key="option.value"
          type="button"
          @click="selectView(option.value)"
          :class="[
            'px-4 py-2 text-sm font-semibold rounded-md transition',
            defaultView === option.value
              ? 'bg-white text-brand-600 shadow-sm'
              : 'text-gray-500 hover:text-gray-800',
          ]"
        >
          {{ option.label }}
        </button>
      </div>

      <p v-if="viewSaved" class="text-xs text-green-600 mt-3">Saved</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useUserPreferences, type DefaultView } from '@/composables/useUserPreferences'
import { useRoles } from '@/composables/useCoach'
import { resetLanding } from '@/composables/useLanding'
import type { Unit } from '@/types/runs'

const { unit, setUnit, defaultView, setDefaultView } = useUserPreferences()
const { isCoach, loadRoles } = useRoles()
const saved = ref(false)
const viewSaved = ref(false)

const options: { value: Unit; label: string }[] = [
  { value: 'mi', label: 'Miles' },
  { value: 'km', label: 'Kilometers' },
]

// Coach is only a meaningful destination for coaches/admins.
const viewOptions = computed(() => {
  const base: { value: DefaultView; label: string }[] = [
    { value: 'auto', label: 'Auto' },
    { value: 'dashboard', label: 'Dashboard' },
    { value: 'runs', label: 'Runs' },
  ]
  if (isCoach.value) base.push({ value: 'coach', label: 'Coach' })
  return base
})

const selectUnit = async (value: Unit) => {
  if (unit.value === value) return
  await setUnit(value)
  saved.value = true
  setTimeout(() => (saved.value = false), 2000)
}

const selectView = async (value: DefaultView) => {
  if (defaultView.value === value) return
  await setDefaultView(value)
  resetLanding() // the next implicit navigation re-resolves with the new pick
  viewSaved.value = true
  setTimeout(() => (viewSaved.value = false), 2000)
}

onMounted(loadRoles)
</script>
