<template>
  <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
    <div class="flex items-center justify-between mb-4">
      <h2 class="font-semibold text-gray-900">Last 12 weeks</h2>
      <div class="flex items-center gap-1 text-xs text-gray-500">
        <span>Less</span>
        <span
          v-for="b in [0, 1, 2, 3, 4]"
          :key="b"
          class="w-3 h-3 rounded-sm"
          :class="bucketClass(b)"
        />
        <span>More</span>
      </div>
    </div>

    <div class="overflow-x-auto">
      <div class="flex gap-1 min-w-max">
        <div
          v-for="(week, wi) in grid"
          :key="wi"
          class="grid grid-rows-7 gap-1"
        >
          <div
            v-for="(cell, di) in week"
            :key="di"
            class="w-4 h-4 rounded-sm transition-transform hover:scale-125"
            :class="[
              cell.inFuture ? 'bg-gray-50' : bucketClass(cell.bucket),
            ]"
            :title="cellTitle(cell)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { HeatmapCell, HeatmapGrid } from '@/utils/heatmap'
import { formatDistanceWithUnit, formatDate } from '@/utils/format'
import type { Unit } from '@/types/runs'

const props = defineProps<{
  grid: HeatmapGrid
  unit: Unit
}>()

const bucketClass = (b: number): string => {
  switch (b) {
    case 0:
      return 'bg-gray-100'
    case 1:
      return 'bg-orange-200'
    case 2:
      return 'bg-orange-400'
    case 3:
      return 'bg-orange-500'
    case 4:
      return 'bg-orange-700'
    default:
      return 'bg-gray-100'
  }
}

const cellTitle = (cell: HeatmapCell): string => {
  const dateLabel = formatDate(cell.iso + 'T12:00:00')
  if (cell.inFuture) return dateLabel
  if (cell.distanceKm <= 0) return `${dateLabel}: rest`
  return `${dateLabel}: ${formatDistanceWithUnit(cell.distanceKm, props.unit)}`
}
</script>
