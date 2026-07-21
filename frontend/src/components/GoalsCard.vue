<template>
  <div class="bg-white rounded-2xl shadow-md p-6 h-full border border-gray-100">
    <div class="flex items-center gap-2 mb-4">
      <Target class="w-4 h-4 text-gray-700" />
      <h3 class="text-sm font-semibold uppercase tracking-wide text-gray-700">
        Goals
      </h3>
    </div>

    <!-- Empty state: no goals stored at all -->
    <div
      v-if="!yearly && !monthly"
      class="text-sm text-gray-500"
    >
      No goals set on SmashRun for this period.
    </div>

    <!-- Monthly goal -->
    <div v-if="monthly" class="mb-4">
      <div class="flex items-start justify-between gap-2 mb-1">
        <span class="inline-flex items-center gap-1 text-xs font-medium text-gray-700">
          <Calendar class="w-3.5 h-3.5" /> {{ currentMonthName }}
          <PartyPopper v-if="monthlyPercent >= 100" class="w-3.5 h-3.5 text-brand-600" />
        </span>
        <span class="text-xs font-semibold text-gray-900 whitespace-nowrap">
          {{ monthly.progress_mi.toFixed(1) }} / {{ monthly.goal_mi.toFixed(0) }} mi
        </span>
      </div>
      <p
        v-if="monthly.text"
        class="text-xs text-gray-500 italic mb-1.5 line-clamp-2"
        :title="monthly.text ?? undefined"
      >
        {{ monthly.text }}
      </p>
      <div class="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
        <div
          class="h-2 rounded-full transition-all duration-500"
          :class="progressBarColor(monthlyPercent, monthlyPaceDelta)"
          :style="{ width: Math.min(monthlyPercent, 100) + '%' }"
        ></div>
      </div>
      <div class="flex justify-between items-center mt-1 text-xs">
        <span class="text-gray-500">
          {{ monthlyPercent.toFixed(1) }}%
        </span>
        <span v-if="monthlyPercent >= 100" class="inline-flex items-center gap-1 text-green-600 font-medium">
          <PartyPopper class="w-3.5 h-3.5" /> Goal achieved!
        </span>
        <span v-else :class="paceColor(monthlyPaceDelta)">
          {{ formatMilesDelta(monthlyMilesDelta) }}
        </span>
      </div>
      <p
        v-if="monthlyCatchUp"
        class="mt-1 text-xs font-medium text-amber-600 inline-flex items-center gap-1"
      >
        <Zap class="w-3.5 h-3.5 inline" /> {{ monthlyCatchUp }}
      </p>
    </div>

    <!-- Yearly goal -->
    <div v-if="yearly">
      <div class="flex items-start justify-between gap-2 mb-1">
        <span class="inline-flex items-center gap-1 text-xs font-medium text-gray-700">
          <Target class="w-3.5 h-3.5" /> {{ currentYear }}
          <PartyPopper v-if="yearlyPercent >= 100" class="w-3.5 h-3.5 text-brand-600" />
        </span>
        <span class="text-xs font-semibold text-gray-900 whitespace-nowrap">
          {{ yearly.progress_mi.toFixed(1) }} / {{ yearly.goal_mi.toFixed(0) }} mi
        </span>
      </div>
      <p
        v-if="yearly.text"
        class="text-xs text-gray-500 italic mb-1.5 line-clamp-2"
        :title="yearly.text ?? undefined"
      >
        {{ yearly.text }}
      </p>
      <div class="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
        <div
          class="h-2 rounded-full transition-all duration-500"
          :class="progressBarColor(yearlyPercent, yearlyPaceDelta)"
          :style="{ width: Math.min(yearlyPercent, 100) + '%' }"
        ></div>
      </div>
      <div class="flex justify-between items-center mt-1 text-xs">
        <span class="text-gray-500">
          {{ yearlyPercent.toFixed(1) }}%
        </span>
        <span v-if="yearlyPercent >= 100" class="inline-flex items-center gap-1 text-green-600 font-medium">
          <PartyPopper class="w-3.5 h-3.5" /> Goal achieved!
        </span>
        <span v-else :class="paceColor(yearlyPaceDelta)">
          {{ formatMilesDelta(yearlyMilesDelta) }}
        </span>
      </div>
      <p
        v-if="yearlyCatchUp"
        class="mt-1 text-xs font-medium text-amber-600 inline-flex items-center gap-1"
      >
        <Zap class="w-3.5 h-3.5 inline" /> {{ yearlyCatchUp }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Calendar, PartyPopper, Target, Zap } from 'lucide-vue-next'
import type { GoalProgress } from '@/types/runs'

const props = defineProps<{
  yearly: GoalProgress | null
  monthly: GoalProgress | null
}>()

const now = new Date()
const currentYear = now.getFullYear()
const currentMonthName = now.toLocaleDateString('en-US', { month: 'long' })

// Pace math — compare actual % against expected % (day-of-period / days-in-period).
// Backend's percent field can lag the live progress_mi if it was computed against
// stale progress_km; recompute locally so the bar matches what we display above.
const monthlyPercent = computed((): number => {
  if (!props.monthly || props.monthly.goal_mi <= 0) return 0
  return (props.monthly.progress_mi / props.monthly.goal_mi) * 100
})

const yearlyPercent = computed((): number => {
  if (!props.yearly || props.yearly.goal_mi <= 0) return 0
  return (props.yearly.progress_mi / props.yearly.goal_mi) * 100
})

const expectedMonthlyPct = computed((): number => {
  const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate()
  return (now.getDate() / daysInMonth) * 100
})

const expectedYearlyPct = computed((): number => {
  const start = new Date(now.getFullYear(), 0, 0)
  const dayOfYear = Math.floor((now.getTime() - start.getTime()) / 86400000)
  const isLeap =
    (now.getFullYear() % 4 === 0 && now.getFullYear() % 100 !== 0) ||
    now.getFullYear() % 400 === 0
  return (dayOfYear / (isLeap ? 366 : 365)) * 100
})

const monthlyPaceDelta = computed((): number | null =>
  props.monthly ? monthlyPercent.value - expectedMonthlyPct.value : null,
)

const yearlyPaceDelta = computed((): number | null =>
  props.yearly ? yearlyPercent.value - expectedYearlyPct.value : null,
)

const monthlyMilesDelta = computed((): number | null => {
  const delta = monthlyPaceDelta.value
  if (delta === null || !props.monthly) return null
  return (delta / 100) * props.monthly.goal_mi
})

const yearlyMilesDelta = computed((): number | null => {
  const delta = yearlyPaceDelta.value
  if (delta === null || !props.yearly) return null
  return (delta / 100) * props.yearly.goal_mi
})

// Catch-up coaching: when behind, the deficit alone scolds — the actionable
// number is "what to run per day to still finish". Today's run is assumed
// banked into progress_mi, so days left excludes today (guarded against the
// final-day divide-by-zero).
const monthlyDaysLeft = computed((): number => {
  const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate()
  return daysInMonth - now.getDate()
})

const yearlyDaysLeft = computed((): number => {
  const start = new Date(now.getFullYear(), 0, 0)
  const dayOfYear = Math.floor((now.getTime() - start.getTime()) / 86400000)
  const isLeap =
    (now.getFullYear() % 4 === 0 && now.getFullYear() % 100 !== 0) ||
    now.getFullYear() % 400 === 0
  return (isLeap ? 366 : 365) - dayOfYear
})

const catchUpText = (
  goal: GoalProgress | null,
  delta: number | null,
  daysLeft: number,
): string | null => {
  // Only when meaningfully behind (amber/red) and the goal is still reachable-by-running.
  if (!goal || delta === null || delta > -0.5) return null
  const remaining = goal.goal_mi - goal.progress_mi
  if (remaining <= 0 || daysLeft <= 0) return null
  const perDay = remaining / daysLeft
  const dayWord = daysLeft === 1 ? 'day' : 'days'
  return `${daysLeft} ${dayWord} left · ${perDay.toFixed(1)} mi/day to finish`
}

const monthlyCatchUp = computed((): string | null =>
  catchUpText(props.monthly, monthlyPaceDelta.value, monthlyDaysLeft.value),
)

const yearlyCatchUp = computed((): string | null =>
  catchUpText(props.yearly, yearlyPaceDelta.value, yearlyDaysLeft.value),
)

const formatMilesDelta = (milesDelta: number | null): string => {
  if (milesDelta === null) return ''
  const abs = Math.abs(milesDelta).toFixed(1)
  if (milesDelta >= 0.1) return `${abs} mi ahead of pace`
  if (milesDelta <= -0.1) return `${abs} mi behind pace`
  return 'on pace'
}

const paceColor = (delta: number | null): string => {
  if (delta === null) return 'text-gray-500'
  if (delta >= 0.5) return 'text-green-600 font-medium'
  if (delta <= -5) return 'text-red-600 font-medium'
  if (delta <= -0.5) return 'text-amber-600 font-medium'
  return 'text-gray-500'
}

const progressBarColor = (percent: number, delta: number | null): string => {
  if (percent >= 100) return 'bg-green-500'
  if (delta === null) return 'bg-blue-500'
  if (delta >= 0.5) return 'bg-green-500'
  if (delta <= -5) return 'bg-red-500'
  if (delta <= -0.5) return 'bg-amber-500'
  return 'bg-blue-500'
}
</script>
