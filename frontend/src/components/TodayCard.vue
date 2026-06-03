<template>
  <div class="bg-white rounded-2xl shadow-md p-6 h-full border border-gray-100">
    <div class="flex items-center gap-2 mb-4">
      <span class="text-lg">📈</span>
      <h3 class="text-sm font-semibold uppercase tracking-wide text-gray-700">
        Today
      </h3>
    </div>

    <div v-if="goals.length === 0" class="text-sm text-gray-500">
      No active goals yet — set one to start tracking.
    </div>

    <div v-for="row in rows" :key="row.id" class="mb-4 last:mb-0">
      <div class="flex items-start justify-between gap-2 mb-1">
        <span class="text-xs font-medium text-gray-700">
          {{ row.label }}
          <span v-if="row.met" class="ml-1">🎉</span>
        </span>
        <span class="text-xs font-semibold text-gray-900 whitespace-nowrap">
          {{ row.progressText }}
        </span>
      </div>
      <div class="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
        <div
          class="h-2 rounded-full transition-all duration-500"
          :class="row.barClass"
          :style="{ width: Math.min(row.percent, 100) + '%' }"
        ></div>
      </div>
      <div class="flex justify-between items-center mt-1 text-xs">
        <span class="text-gray-500">{{ row.percent.toFixed(0) }}%</span>
        <span :class="row.paceClass">{{ row.paceText }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { GoalProgress, MetricType } from '@/types/metrics'
import { displayDecimals, displayUnit, toDisplay } from '@/utils/metrics'

const props = defineProps<{
  goals: GoalProgress[]
  types: MetricType[]
}>()

interface Row {
  id: string
  label: string
  progressText: string
  percent: number
  met: boolean
  barClass: string
  paceText: string
  paceClass: string
}

function metricFor(key: string): MetricType | undefined {
  return props.types.find((t) => t.key === key)
}

function fmt(unit: string, value: number): string {
  return toDisplay(unit, value).toFixed(displayDecimals(unit))
}

const rows = computed<Row[]>(() =>
  props.goals.map((g): Row => {
    const metric = metricFor(g.goal.metric_key)
    const unit = metric?.unit ?? ''
    const label = metric?.display_name ?? g.goal.metric_key
    const percent = g.percent ?? (g.target > 0 ? (g.progress / g.target) * 100 : 0)

    let progressText: string
    let paceText: string
    if (g.goal.kind === 'frequency') {
      progressText = `${g.progress} / ${g.target}`
      paceText = `${g.progress} of ${g.target} days`
    } else if (g.goal.kind === 'streak') {
      progressText = `${g.progress} day${g.progress === 1 ? '' : 's'}`
      paceText = `target ${g.target}-day streak`
    } else {
      const u = displayUnit(unit)
      progressText = `${fmt(unit, g.progress)} / ${fmt(unit, g.target)} ${u}`
      paceText = paceForVolume(g, unit)
    }

    return {
      id: g.goal.id,
      label,
      progressText,
      percent,
      met: g.met,
      barClass: barClass(g, percent),
      paceText: g.met ? 'Achieved 🎉' : paceText,
      paceClass: paceClass(g),
    }
  }),
)

function paceForVolume(g: GoalProgress, unit: string): string {
  if (g.met) return 'Achieved 🎉'
  if (g.projected !== null) {
    const u = displayUnit(unit)
    const proj = `on pace for ${fmt(unit, g.projected)} ${u}`
    if (g.per_day_needed && g.per_day_needed > 0) {
      return `${fmt(unit, g.per_day_needed)} ${u}/day to finish · ${proj}`
    }
    return proj
  }
  return ''
}

function barClass(g: GoalProgress, percent: number): string {
  if (g.met || percent >= 100) return 'bg-green-500'
  if (g.on_pace === true) return 'bg-green-500'
  if (g.on_pace === false) return 'bg-amber-500'
  return 'bg-blue-500'
}

function paceClass(g: GoalProgress): string {
  if (g.met) return 'text-green-600 font-medium'
  if (g.on_pace === true) return 'text-green-600 font-medium'
  if (g.on_pace === false) return 'text-amber-600 font-medium'
  return 'text-gray-500'
}
</script>
