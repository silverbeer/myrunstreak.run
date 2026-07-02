<template>
  <div class="container-app py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p class="text-gray-500 text-sm mt-1">Welcome back, {{ userEmail }}</p>
      </div>
      <SyncButton mode="full" @synced="reload" />
    </div>

    <div v-if="initialLoading" class="space-y-4">
      <div class="h-44 bg-white rounded-2xl border border-gray-100 animate-pulse" />
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div v-for="i in 4" :key="i" class="h-28 bg-white rounded-xl border border-gray-100 animate-pulse" />
      </div>
      <div class="h-44 bg-white rounded-xl border border-gray-100 animate-pulse" />
      <div class="h-72 bg-white rounded-xl border border-gray-100 animate-pulse" />
    </div>

    <div v-else-if="loadError" class="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
      {{ loadError }}
    </div>

    <EmptyState v-else-if="isNewUser" @synced="reload" />

    <template v-else>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <StreakHero
          :current="streak?.current_streak ?? 0"
          :longest="streak?.longest_streak ?? 0"
          :current-distance="formatDistanceWithUnit(streak?.current_streak_km ?? 0, unit, 0)"
        />
        <GoalsCard
          :yearly="goals?.yearly ?? null"
          :monthly="goals?.monthly ?? null"
        />
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <TodayCard :goals="metricGoals" :types="metricTypes" @create="showNewGoal = true" />
        <QuickLog :types="metricTypes" @logged="loadMetricGoals" />
      </div>

      <NewGoalForm
        :show="showNewGoal"
        :types="metricTypes"
        @created="onGoalCreated"
        @cancel="showNewGoal = false"
      />

      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard
          label="Total runs"
          :value="`${stats?.total_runs ?? 0}`"
          sublabel="all time"
          value-class="text-gray-800"
        />
        <StatCard
          label="Total distance"
          :value="formatDistance(stats?.total_km ?? 0, unit, 0)"
          :sublabel="`${distanceLabel(unit)} all time`"
          value-class="text-gray-800"
        />
        <StatCard
          label="Longest run"
          :value="formatDistanceWithUnit(stats?.longest_run_km ?? 0, unit)"
          sublabel="personal best"
        />
        <StatCard
          label="Average pace"
          :value="formatPace(stats?.avg_pace_min_per_km ?? null, unit)"
          sublabel="across all runs"
        />
      </div>

      <div class="mb-6">
        <PersonalBestsCard :records="records" :unit="unit" />
      </div>

      <div class="mb-6">
        <StreakHeatmap :grid="heatmapGrid" :unit="unit" />
      </div>

      <div class="mb-6">
        <MonthlyDistanceChart :months="months" :unit="unit" />
      </div>

      <div class="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        <div class="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 class="font-semibold text-gray-900">Recent runs</h2>
          <RouterLink to="/runs" class="text-sm text-brand-600 hover:text-brand-700">
            View all →
          </RouterLink>
        </div>
        <div v-if="recentRuns.length === 0" class="p-8 text-center text-gray-400 text-sm">
          No recent runs.
        </div>
        <div v-else class="divide-y divide-gray-100">
          <RunRow
            v-for="run in recentRuns.slice(0, 7)"
            :key="run.activity_id"
            :date="run.date"
            :distance-km="run.distance_km"
            :duration-seconds="run.duration_seconds"
            :pace-min-per-km="run.avg_pace_min_per_km"
            :unit="unit"
            :weather="run.weather"
          />
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import StatCard from '@/components/StatCard.vue'
import RunRow from '@/components/RunRow.vue'
import SyncButton from '@/components/SyncButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import StreakHero from '@/components/StreakHero.vue'
import StreakHeatmap from '@/components/StreakHeatmap.vue'
import PersonalBestsCard from '@/components/PersonalBestsCard.vue'
import MonthlyDistanceChart from '@/components/MonthlyDistanceChart.vue'
import GoalsCard from '@/components/GoalsCard.vue'
import TodayCard from '@/components/TodayCard.vue'
import QuickLog from '@/components/QuickLog.vue'
import NewGoalForm from '@/components/NewGoalForm.vue'
import { useStats } from '@/composables/useStats'
import { useMetrics } from '@/composables/useMetrics'
import { useRecentRuns } from '@/composables/useRecentRuns'
import { useMonthlyStats } from '@/composables/useMonthlyStats'
import { useGoals } from '@/composables/useGoals'
import { useUserPreferences } from '@/composables/useUserPreferences'
import { useAuthStore } from '@/stores/auth'
import {
  formatDistance,
  formatDistanceWithUnit,
  formatPace,
  distanceLabel,
} from '@/utils/format'
import { buildHeatmapGrid } from '@/utils/heatmap'

const auth = useAuthStore()
const userEmail = computed(() => auth.user?.email ?? 'runner')

const {
  stats,
  streak,
  records,
  loading: statsLoading,
  error: statsError,
  load: loadStats,
} = useStats()
const {
  runs: recentRuns,
  loading: recentLoading,
  error: recentError,
  load: loadRecent,
} = useRecentRuns(100)
const { months, loading: monthlyLoading, error: monthlyError, load: loadMonthly } = useMonthlyStats(12)
const { goals, error: goalsError, load: loadGoals } = useGoals()
const {
  types: metricTypes,
  goals: metricGoals,
  loadTypes: loadMetricTypes,
  loadGoals: loadMetricGoals,
} = useMetrics()
const { unit } = useUserPreferences()

const showNewGoal = ref(false)
const onGoalCreated = async () => {
  showNewGoal.value = false
  await loadMetricGoals()
}

const initialLoading = computed(
  () =>
    (statsLoading.value || recentLoading.value || monthlyLoading.value) &&
    !stats.value &&
    recentRuns.value.length === 0,
)
const loadError = computed(
  () => statsError.value || recentError.value || monthlyError.value || goalsError.value,
)
const isNewUser = computed(() => stats.value !== null && stats.value.total_runs === 0)

const heatmapGrid = computed(() => buildHeatmapGrid(recentRuns.value, 12))

const reload = async () => {
  await Promise.all([loadStats(), loadRecent(), loadMonthly(), loadGoals(), loadMetricGoals()])
}

onMounted(async () => {
  await Promise.all([reload(), loadMetricTypes()])
})
</script>
