<template>
  <component
    :is="activityId ? RouterLink : 'div'"
    :to="activityId ? `/runs/${activityId}` : undefined"
    class="relative block py-3 px-4 hover:bg-gray-50 transition"
    :class="activityId ? 'cursor-pointer' : ''"
  >
    <div class="flex items-center justify-between">
      <div class="flex flex-col">
        <span class="text-sm font-semibold text-gray-900">{{ formatDate(date) }}</span>
        <span v-if="weather" class="text-xs text-gray-400 mt-0.5">{{ weather }}</span>
      </div>
      <div class="flex items-center gap-6 text-sm text-gray-700 tabular-nums">
        <span class="font-medium">{{ formatDistanceWithUnit(distanceKm, unit) }}</span>
        <span>{{ duration }}</span>
        <span class="hidden sm:inline text-gray-500">{{ formatPace(paceMinPerKm, unit) }}</span>
        <ChevronRight v-if="activityId" class="w-4 h-4 text-gray-300" />
      </div>
    </div>
    <div
      v-if="barFraction !== undefined"
      class="absolute bottom-0 left-4 h-0.5 rounded-full bg-brand-200"
      :style="{ width: `calc((100% - 2rem) * ${Math.min(1, Math.max(0, barFraction))})` }"
    />
  </component>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { ChevronRight } from 'lucide-vue-next'
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
  /** When set, the row links to the run detail view (SB-263). */
  activityId?: string
  /** 0..1 — draws a subtle distance bar along the row's bottom (SB-268). */
  barFraction?: number
}>()

const duration = computed(() => {
  if (props.durationSeconds !== undefined) return formatDuration(props.durationSeconds)
  if (props.durationMinutes !== undefined) return formatDuration(props.durationMinutes * 60)
  return '–'
})
</script>
