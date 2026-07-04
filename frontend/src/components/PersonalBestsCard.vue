<template>
  <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
    <div class="flex items-center gap-2 mb-4">
      <Trophy class="w-4 h-4 text-gray-700" />
      <h3 class="text-sm font-semibold uppercase tracking-wide text-gray-700">Personal bests</h3>
    </div>

    <div v-if="!hasAny" class="text-sm text-gray-500">No records yet — sync some runs.</div>

    <div v-else class="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <div v-if="records?.longest_run" class="rounded-xl bg-gray-50 border border-gray-100 p-4">
        <div class="flex items-center gap-1.5 text-xs font-medium text-gray-500">
          <Route class="w-3.5 h-3.5" /> Longest run
        </div>
        <p class="text-2xl font-bold text-gray-900 mt-1 tabular-nums">
          {{ formatDistanceWithUnit(records.longest_run.distance_km, unit, 1) }}
        </p>
        <p class="text-xs text-gray-400 mt-0.5">{{ fmtDate(records.longest_run.date) }}</p>
      </div>

      <div v-if="records?.fastest_pace" class="rounded-xl bg-gray-50 border border-gray-100 p-4">
        <div class="flex items-center gap-1.5 text-xs font-medium text-gray-500">
          <Timer class="w-3.5 h-3.5" /> Fastest pace
        </div>
        <p class="text-2xl font-bold text-gray-900 mt-1 tabular-nums">
          {{ formatPace(records.fastest_pace.pace_min_per_km, unit) }}
        </p>
        <p class="text-xs text-gray-400 mt-0.5">
          {{ formatDistanceWithUnit(records.fastest_pace.distance_km, unit, 1) }} ·
          {{ fmtDate(records.fastest_pace.date) }}
        </p>
      </div>

      <div v-if="records?.most_km_month" class="rounded-xl bg-gray-50 border border-gray-100 p-4">
        <div class="flex items-center gap-1.5 text-xs font-medium text-gray-500">
          <CalendarDays class="w-3.5 h-3.5" /> Biggest month
        </div>
        <p class="text-2xl font-bold text-gray-900 mt-1 tabular-nums">
          {{ formatDistanceWithUnit(records.most_km_month.total_km, unit, 0) }}
        </p>
        <p class="text-xs text-gray-400 mt-0.5">
          {{ fmtMonth(records.most_km_month.month) }} · {{ records.most_km_month.run_count }} runs
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CalendarDays, Route, Timer, Trophy } from 'lucide-vue-next'
import { formatDistanceWithUnit, formatPace } from '@/utils/format'
import type { RecordsInfo } from '@/types/runs'
import type { Unit } from '@/types/runs'

const props = defineProps<{ records: RecordsInfo | null; unit: Unit }>()

const hasAny = computed(
  () => !!(props.records?.longest_run || props.records?.fastest_pace || props.records?.most_km_month),
)

const fmtDate = (iso: string): string =>
  new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })

const fmtMonth = (iso: string): string =>
  new Date(iso).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
</script>
