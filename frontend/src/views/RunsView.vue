<template>
  <div class="container-app py-8">
    <div class="flex items-center justify-between mb-4">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Run history</h1>
        <p class="text-sm text-gray-500 mt-1">
          {{ total > 0 ? `${total} runs` : 'No runs yet' }}
        </p>
      </div>
      <SyncButton mode="full" @synced="reload" />
    </div>

    <form class="mb-3" @submit.prevent="submitSearch">
      <div class="relative">
        <input
          v-model="searchText"
          type="search"
          placeholder='Try "rainy 5 milers last summer" or "hot runs under 9:30"…'
          class="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-200"
        />
        <button
          type="submit"
          class="absolute right-2 top-1/2 -translate-y-1/2 text-xs font-medium text-brand-600 px-2 py-1"
        >
          Search
        </button>
      </div>
      <div v-if="nlChips.length || nlIgnored.length" class="flex flex-wrap items-center gap-1.5 mt-2">
        <span
          v-for="chip in nlChips"
          :key="chip"
          class="px-2.5 py-0.5 rounded-full bg-brand-50 border border-brand-200 text-brand-700 text-xs font-medium"
        >
          {{ chip }}
        </span>
        <span v-if="nlIgnored.length" class="text-xs text-gray-400">
          (ignored: {{ nlIgnored.join(', ') }})
        </span>
        <button type="button" class="text-xs text-gray-500 underline ml-1" @click="clearSearch">
          clear
        </button>
      </div>
    </form>

    <div class="flex flex-wrap items-center gap-2 mb-3">
      <button
        v-for="c in collections"
        :key="c.key"
        type="button"
        @click="selectCollection(c.key)"
        :class="chipClass(collection === c.key)"
      >
        {{ c.label }}
      </button>
    </div>

    <div class="flex flex-wrap items-center gap-2 mb-5">
      <button
        v-for="p in periodChips"
        :key="p.key"
        type="button"
        @click="selectPeriod(p.key)"
        :class="chipClass(period === p.key)"
      >
        {{ p.label }}
      </button>
      <span class="w-px h-5 bg-gray-200 mx-1 hidden sm:block" />
      <button
        v-for="d in distanceChips"
        :key="d.key"
        type="button"
        @click="selectDistance(d.key)"
        :class="chipClass(distance === d.key)"
      >
        {{ d.label }}
      </button>
    </div>

    <p v-if="impact" class="text-sm mb-4 px-1" :class="impact.slower ? 'text-amber-700' : 'text-green-700'">
      {{ impact.text }}
    </p>

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
      <p v-if="isFiltered">No runs match these filters.</p>
      <p v-else>No runs to show yet. Click <span class="font-semibold">Sync now</span> to import.</p>
    </div>

    <template v-else>
      <div v-for="group in monthGroups" :key="group.key" class="mb-5">
        <div class="flex items-baseline justify-between px-1 mb-2">
          <h2 class="text-sm font-semibold text-gray-900">{{ group.label }}</h2>
          <p class="text-xs text-gray-500 tabular-nums">
            {{ group.count }} run{{ group.count === 1 ? '' : 's' }} · {{ formatDistanceWithUnit(group.totalKm, unit) }} · avg
            {{ formatPace(group.avgPace, unit) }}
          </p>
        </div>
        <div class="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden divide-y divide-gray-100">
          <RunRow
            v-for="run in group.runs"
            :key="run.activity_id"
            :date="run.date"
            :distance-km="run.distance_km"
            :duration-minutes="run.duration_minutes"
            :pace-min-per-km="run.avg_pace_min_per_km"
            :unit="unit"
            :weather="weatherText(run)"
            :activity-id="run.activity_id"
            :bar-fraction="run.distance_km / maxKm"
          />
        </div>
      </div>
    </template>

    <div v-if="runs.length > 0" class="flex items-center justify-between mt-4 text-sm">
      <button @click="prev" :disabled="!hasPrev || loading" class="btn-secondary disabled:opacity-50">
        ← Prev
      </button>
      <span class="text-gray-500">Page {{ page }} of {{ totalPages }}</span>
      <button @click="next" :disabled="!hasNext || loading" class="btn-secondary disabled:opacity-50">
        Next →
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import RunRow from '@/components/RunRow.vue'
import SyncButton from '@/components/SyncButton.vue'
import { useRuns } from '@/composables/useRuns'
import { useUserPreferences } from '@/composables/useUserPreferences'
import { apiCall } from '@/config/api'
import { formatDistanceWithUnit, formatPace } from '@/utils/format'
import { parseRunQuery } from '@/utils/runQuery'
import type { PaginatedRun, RunFilters } from '@/types/runs'

const KM_PER_MI = 1.609344

const { runs, total, loading, error, page, totalPages, hasPrev, hasNext, load, setFilters, next, prev } =
  useRuns(25)
const { unit } = useUserPreferences()

// ---- filter chips (backed by GET /runs query params) ----
type PeriodKey = 'all' | 'month' | '30d'
type DistanceKey = 'all' | 'short' | 'mid' | 'long'

const period = ref<PeriodKey>('all')
const distance = ref<DistanceKey>('all')

const periodChips: { key: PeriodKey; label: string }[] = [
  { key: 'all', label: 'All time' },
  { key: 'month', label: 'This month' },
  { key: '30d', label: 'Last 30 days' },
]

const distanceChips = computed<{ key: DistanceKey; label: string }[]>(() => {
  const u = unit.value
  return [
    { key: 'all', label: 'Any distance' },
    { key: 'short', label: `< 3 ${u}` },
    { key: 'mid', label: `3–5 ${u}` },
    { key: 'long', label: `5+ ${u}` },
  ]
})

// ---- collections: curated filter+sort presets (SB-269) ----
type CollectionKey = 'today' | 'hottest' | 'coldest' | 'rainy' | 'fastest' | 'longest'

const collection = ref<CollectionKey | null>(null)

const todayMmDd = () => {
  const d = new Date()
  return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const COLLECTION_PRESETS: Record<CollectionKey, RunFilters> = {
  today: { on_this_day: todayMmDd(), sort: 'date', order: 'desc' },
  hottest: { sort: 'temperature', order: 'desc' },
  coldest: { sort: 'temperature', order: 'asc' },
  rainy: { weather_type: 'rainy' },
  // Ignore sub-mile stub runs when hunting PRs.
  fastest: { sort: 'pace', order: 'asc', distance_min: 1.61 },
  longest: { sort: 'distance', order: 'desc' },
}

const collections: { key: CollectionKey; label: string }[] = [
  { key: 'today', label: '📅 On this day' },
  { key: 'fastest', label: '⚡ Fastest' },
  { key: 'longest', label: '🏔 Longest' },
  { key: 'hottest', label: '🔥 Hottest' },
  { key: 'coldest', label: '❄️ Coldest' },
  { key: 'rainy', label: '🌧 Rainy' },
]

const selectCollection = (key: CollectionKey) => {
  collection.value = collection.value === key ? null : key
  void applyFilters()
}

// ---- natural-language search (SB-269 PR2) ----
const searchText = ref('')
const nlFilters = ref<RunFilters>({})
const nlChips = ref<string[]>([])
const nlIgnored = ref<string[]>([])

const submitSearch = () => {
  const parsed = parseRunQuery(searchText.value, unit.value)
  nlFilters.value = parsed.filters
  nlChips.value = parsed.chips
  nlIgnored.value = parsed.ignored
  void applyFilters()
}

const clearSearch = () => {
  searchText.value = ''
  nlFilters.value = {}
  nlChips.value = []
  nlIgnored.value = []
  void applyFilters()
}

const isFiltered = computed(
  () =>
    period.value !== 'all' ||
    distance.value !== 'all' ||
    collection.value !== null ||
    nlChips.value.length > 0,
)

// ---- conditions impact: filtered set vs overall (SB-269 PR2) ----
interface RunsSummary {
  count: number
  total_km: number
  avg_pace_min_per_km: number | null
  overall_avg_pace_min_per_km: number | null
}

const summary = ref<RunsSummary | null>(null)

const loadSummary = async (f: RunFilters) => {
  if (!isFiltered.value) {
    summary.value = null
    return
  }
  try {
    const params = new URLSearchParams()
    for (const [k, v] of Object.entries(f)) {
      if (v !== undefined && v !== null && k !== 'sort' && k !== 'order') params.set(k, String(v))
    }
    summary.value = await apiCall<RunsSummary>(`/runs/summary?${params.toString()}`)
  } catch {
    summary.value = null
  }
}

const impact = computed(() => {
  const s = summary.value
  if (!s || !isFiltered.value || s.avg_pace_min_per_km == null || s.overall_avg_pace_min_per_km == null)
    return null
  const deltaMinPerKm = s.avg_pace_min_per_km - s.overall_avg_pace_min_per_km
  const perUnit = unit.value === 'mi' ? deltaMinPerKm * KM_PER_MI : deltaMinPerKm
  const secs = Math.round(Math.abs(perUnit) * 60)
  const slower = deltaMinPerKm > 0
  if (secs < 2) {
    return { slower: false, text: `${s.count} runs · avg ${formatPace(s.avg_pace_min_per_km, unit.value)} — right at your overall pace` }
  }
  return {
    slower,
    text: `${s.count} runs · avg ${formatPace(s.avg_pace_min_per_km, unit.value)} — ${secs}s/${unit.value} ${slower ? 'slower' : 'faster'} than your overall ${formatPace(s.overall_avg_pace_min_per_km, unit.value)}`,
  }
})

const chipClass = (active: boolean) =>
  [
    'px-3 py-1.5 rounded-full text-xs font-medium border transition',
    active
      ? 'bg-brand-600 border-brand-600 text-white'
      : 'bg-white border-gray-200 text-gray-600 hover:border-gray-300',
  ].join(' ')

const iso = (d: Date) => d.toISOString().slice(0, 10)

const buildFilters = (): RunFilters => {
  const f: RunFilters = {}
  const today = new Date()
  if (period.value === 'month') {
    f.date_from = iso(new Date(today.getFullYear(), today.getMonth(), 1))
  } else if (period.value === '30d') {
    f.date_from = iso(new Date(today.getTime() - 30 * 86_400_000))
  }
  const toKm = (v: number) => (unit.value === 'mi' ? v * KM_PER_MI : v)
  if (distance.value === 'short') f.distance_max = toKm(3)
  if (distance.value === 'mid') {
    f.distance_min = toKm(3)
    f.distance_max = toKm(5)
  }
  if (distance.value === 'long') f.distance_min = toKm(5)
  if (collection.value) Object.assign(f, COLLECTION_PRESETS[collection.value])
  Object.assign(f, nlFilters.value) // typed search wins
  return f
}

const applyFilters = async () => {
  const f = buildFilters()
  await Promise.all([setFilters(f), loadSummary(f)])
}
const selectPeriod = (key: PeriodKey) => {
  period.value = key
  void applyFilters()
}
const selectDistance = (key: DistanceKey) => {
  distance.value = key
  void applyFilters()
}

// ---- month grouping with per-group summary ----
interface MonthGroup {
  key: string
  label: string
  runs: PaginatedRun[]
  count: number
  totalKm: number
  avgPace: number | null
}

const monthGroups = computed<MonthGroup[]>(() => {
  const groups: MonthGroup[] = []
  let current: MonthGroup | null = null
  for (const run of runs.value) {
    const d = new Date(run.date)
    const key = `${d.getFullYear()}-${d.getMonth()}`
    if (!current || current.key !== key) {
      current = {
        key,
        label: d.toLocaleDateString(undefined, { month: 'long', year: 'numeric' }),
        runs: [],
        count: 0,
        totalKm: 0,
        avgPace: null,
      }
      groups.push(current)
    }
    current.runs.push(run)
    current.count += 1
    current.totalKm += run.distance_km
  }
  for (const g of groups) {
    const paced = g.runs.filter((r) => r.avg_pace_min_per_km != null)
    // Distance-weighted average pace: total time over total distance.
    const km = paced.reduce((s, r) => s + r.distance_km, 0)
    const mins = paced.reduce((s, r) => s + (r.avg_pace_min_per_km as number) * r.distance_km, 0)
    g.avgPace = km > 0 ? mins / km : null
  }
  return groups
})

const maxKm = computed(() => Math.max(...runs.value.map((r) => r.distance_km), 0.001))

const weatherText = (run: PaginatedRun): string | null => {
  const parts: string[] = []
  if (run.weather) parts.push(run.weather)
  if (run.temperature_celsius != null) {
    parts.push(
      unit.value === 'mi'
        ? `${Math.round((run.temperature_celsius * 9) / 5 + 32)}°F`
        : `${Math.round(run.temperature_celsius)}°C`,
    )
  }
  return parts.length ? parts.join(' · ') : null
}

const reload = async () => {
  await load()
}

onMounted(reload)
</script>
