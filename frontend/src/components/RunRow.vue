<template>
  <div class="flex items-center justify-between py-3 px-4 hover:bg-gray-50 transition">
    <div class="flex flex-col">
      <span class="text-sm font-semibold text-gray-900">{{ formatDate(date) }}</span>
      <span v-if="weather" class="text-xs text-gray-400 mt-0.5">{{ weather }}</span>
    </div>
    <div class="flex items-center gap-6 text-sm text-gray-700 tabular-nums">
      <span class="font-medium">{{ formatDistanceWithUnit(distanceKm, unit) }}</span>
      <span>{{ duration }}</span>
      <span class="hidden sm:inline text-gray-500">{{ formatPace(paceMinPerKm, unit) }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatDate, formatDistanceWithUnit, formatPace, formatDuration } from '@/utils/format'
import type { Unit } from '@/types/runs'

const props = defineProps<{
  date: string
  distanceKm: number
  durationSeconds?: number
  durationMinutes?: number
  paceMinPerKm: number | null
  unit: Unit
  weather?: string | null
}>()

const duration = computed(() => {
  if (props.durationSeconds !== undefined) return formatDuration(props.durationSeconds)
  if (props.durationMinutes !== undefined) return formatDuration(props.durationMinutes * 60)
  return '–'
})
</script>
