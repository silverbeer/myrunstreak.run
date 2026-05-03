<template>
  <div class="container-app py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Run history</h1>
        <p class="text-sm text-gray-500 mt-1">
          {{ total > 0 ? `${total} total runs` : 'No runs yet' }}
        </p>
      </div>
      <SyncButton mode="full" @synced="reload" />
    </div>

    <div v-if="loading && runs.length === 0" class="space-y-2">
      <div v-for="i in 5" :key="i" class="bg-white rounded-lg border border-gray-100 h-14 animate-pulse" />
    </div>

    <div v-else-if="error" class="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
      {{ error }}
    </div>

    <div
      v-else-if="runs.length === 0"
      class="bg-white rounded-xl border border-gray-100 shadow-sm p-10 text-center text-gray-500"
    >
      <p>No runs to show yet. Click <span class="font-semibold">Sync now</span> to import.</p>
    </div>

    <div v-else class="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
      <div class="hidden sm:flex items-center justify-between px-4 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wide border-b border-gray-100">
        <span>Date</span>
        <div class="flex gap-6">
          <span>Distance</span>
          <span>Duration</span>
          <span>Pace</span>
        </div>
      </div>
      <div class="divide-y divide-gray-100">
        <RunRow
          v-for="run in runs"
          :key="run.activity_id"
          :date="run.date"
          :distance-km="run.distance_km"
          :duration-minutes="run.duration_minutes"
          :pace-min-per-km="run.avg_pace_min_per_km"
          :unit="unit"
        />
      </div>
    </div>

    <div v-if="runs.length > 0" class="flex items-center justify-between mt-4 text-sm">
      <button
        @click="prev"
        :disabled="!hasPrev || loading"
        class="btn-secondary disabled:opacity-50"
      >
        ← Prev
      </button>
      <span class="text-gray-500">Page {{ page }} of {{ totalPages }}</span>
      <button
        @click="next"
        :disabled="!hasNext || loading"
        class="btn-secondary disabled:opacity-50"
      >
        Next →
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import RunRow from '@/components/RunRow.vue'
import SyncButton from '@/components/SyncButton.vue'
import { useRuns } from '@/composables/useRuns'
import { useUserPreferences } from '@/composables/useUserPreferences'

const { runs, total, loading, error, page, totalPages, hasPrev, hasNext, load, next, prev } =
  useRuns(25)
const { unit } = useUserPreferences()

const reload = async () => {
  await load()
}

onMounted(reload)
</script>
