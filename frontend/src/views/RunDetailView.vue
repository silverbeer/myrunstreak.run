<template>
  <div class="container-app py-8 max-w-3xl">
    <RouterLink to="/runs" class="text-sm text-gray-500 hover:text-brand-600">← Runs</RouterLink>

    <div v-if="loading" class="space-y-3 mt-4">
      <div v-for="i in 3" :key="i" class="bg-white rounded-xl border border-gray-100 h-28 animate-pulse" />
    </div>

    <div v-else-if="error" class="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700 mt-4">
      {{ error }}
    </div>

    <template v-else-if="run">
      <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-6 mt-4">
        <div class="flex items-start justify-between flex-wrap gap-3">
          <div>
            <h1 class="text-xl font-bold text-gray-900">
              {{ formatDate(run.date) }}
              <span class="text-base font-normal text-gray-500"> · {{ startTime }}</span>
            </h1>
            <div
              v-if="weatherText"
              class="inline-flex items-center gap-1.5 mt-2 px-3 py-1 rounded-full border text-xs"
              :class="isSteamy ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-gray-200 text-gray-500'"
            >
              <component :is="weatherIcon" class="w-3.5 h-3.5" />
              <span>{{ weatherText }}</span>
            </div>
          </div>
          <p class="text-3xl font-bold text-gray-900">
            {{ formatDistance(run.distance_km, unit) }}<span class="text-base font-normal text-gray-400"> {{ distanceLabel(unit) }}</span>
          </p>
        </div>

        <p v-if="isSteamy" class="text-xs text-amber-700 mt-3">
          Hot + humid — expect pace to run slower than the effort feels.<template v-if="heatPenalty">
            Your history runs about <strong>{{ heatPenalty }}s/mi</strong> slower in these
            conditions.</template>
        </p>

        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-5">
          <div class="bg-gray-50 rounded-lg px-4 py-3">
            <p class="text-xs text-gray-500">Time</p>
            <p class="text-lg font-semibold text-gray-900">{{ formatDuration(run.duration_seconds) }}</p>
          </div>
          <div class="bg-gray-50 rounded-lg px-4 py-3">
            <p class="text-xs text-gray-500">Avg pace</p>
            <p class="text-lg font-semibold text-gray-900">{{ formatPace(run.avg_pace_min_per_km, unit) }}</p>
          </div>
          <div class="bg-gray-50 rounded-lg px-4 py-3">
            <p class="text-xs text-gray-500">Elev gain</p>
            <p class="text-lg font-semibold text-gray-900">{{ elevGainText }}</p>
          </div>
          <div class="bg-gray-50 rounded-lg px-4 py-3">
            <p class="text-xs text-gray-500">Avg HR</p>
            <p class="text-lg font-semibold text-gray-900">
              {{ run.vitals.heart_rate_avg ? `${Math.round(run.vitals.heart_rate_avg)}` : '—' }}
              <span v-if="run.vitals.heart_rate_avg" class="text-xs font-normal text-gray-400">bpm</span>
            </p>
          </div>
        </div>
      </div>

      <RouteMap v-if="track && track.has_track" :track="track" :unit="unit" />

      <div v-if="run.splits.length > 0" class="bg-white rounded-xl border border-gray-100 shadow-sm p-6 mt-4">
        <h2 class="font-semibold text-gray-900 mb-1">{{ splitNoun }} splits</h2>
        <p class="text-xs text-gray-400 mb-3">fastest split highlighted</p>
        <ApexChart type="bar" height="220" :options="splitOptions" :series="splitSeries" />
      </div>

      <div v-if="hasElevation" class="bg-white rounded-xl border border-gray-100 shadow-sm p-6 mt-4">
        <div class="flex items-baseline justify-between">
          <h2 class="font-semibold text-gray-900">Elevation</h2>
          <p class="text-xs text-gray-500">↑ {{ elevGainText }} · ↓ {{ elevLossText }}</p>
        </div>
        <ApexChart type="area" height="160" :options="elevOptions" :series="elevSeries" />
      </div>

      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
        <div class="bg-white rounded-xl border border-gray-100 shadow-sm px-4 py-3">
          <p class="text-xs text-gray-500">HR max</p>
          <p class="font-semibold text-gray-900">{{ run.vitals.heart_rate_max ? `${Math.round(run.vitals.heart_rate_max)} bpm` : '—' }}</p>
        </div>
        <div class="bg-white rounded-xl border border-gray-100 shadow-sm px-4 py-3">
          <p class="text-xs text-gray-500">HR min</p>
          <p class="font-semibold text-gray-900">{{ run.vitals.heart_rate_min ? `${Math.round(run.vitals.heart_rate_min)} bpm` : '—' }}</p>
        </div>
        <div class="bg-white rounded-xl border border-gray-100 shadow-sm px-4 py-3">
          <p class="text-xs text-gray-500">Cadence</p>
          <p class="font-semibold text-gray-900">{{ run.vitals.cadence_avg ? `${Math.round(run.vitals.cadence_avg)} spm` : '—' }}</p>
        </div>
        <div class="bg-white rounded-xl border border-gray-100 shadow-sm px-4 py-3">
          <p class="text-xs text-gray-500">Wind</p>
          <p class="font-semibold text-gray-900">{{ windText }}</p>
        </div>
      </div>

      <p v-if="run.notes" class="text-sm text-gray-500 mt-4">{{ run.notes }}</p>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { RouterLink } from 'vue-router'
import ApexChart from 'vue3-apexcharts'
import {
  Cloud, CloudDrizzle, CloudRain, CloudSnow, Snowflake, Sun, SunDim, Wind, Zap, Home, Thermometer,
} from 'lucide-vue-next'
import { useRunDetail } from '@/composables/useRunDetail'
import { useRunTrack } from '@/composables/useRunTrack'
import { useConditionsPenalty } from '@/composables/useConditionsPenalty'
import { useUserPreferences } from '@/composables/useUserPreferences'
import { formatDate, formatDistance, formatDuration, formatPace, distanceLabel } from '@/utils/format'
import RouteMap from '@/components/RouteMap.vue'

const KM_PER_MI = 1.609344

const route = useRoute()
const { unit } = useUserPreferences()
const { run, loading, error, load } = useRunDetail(String(route.params.activityId))
const { track, load: loadTrack } = useRunTrack(String(route.params.activityId))
const { penalty, load: loadPenalty } = useConditionsPenalty()

// Quantified steamy penalty (SB-304): the user's own hot+humid pace hit, shown
// only when meaningful (positive) — otherwise the flag keeps its generic line.
const heatPenalty = computed(() => {
  const p = penalty.value
  return p?.available && (p.penalty_sec_per_mi ?? 0) > 0 ? p.penalty_sec_per_mi : null
})

// Start time (browser-local, matching formatDate) + early-bird nod (SB-270).
const startTime = computed(() => {
  if (!run.value) return ''
  const d = new Date(run.value.date)
  if (Number.isNaN(d.getTime())) return ''
  const label = d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
  return d.getHours() < 7 ? `🌅 ${label}` : label
})

// ---- weather (the "hot + humid" story) ----
const WEATHER_ICONS: Record<string, unknown> = {
  clear: Sun, sunny: Sun, hot: Thermometer, partlycloudy: SunDim, cloudy: Cloud,
  rain: CloudRain, rainy: CloudRain, drizzle: CloudDrizzle, extremerain: CloudRain,
  storm: Zap, snow: CloudSnow, snowy: CloudSnow, blizzard: CloudSnow,
  extremecold: Snowflake, cold: Snowflake, windy: Wind, extremewind: Wind, indoor: Home,
}
const weatherIcon = computed(() => WEATHER_ICONS[run.value?.weather.weather_type ?? ''] ?? Cloud)

const tempText = computed(() => {
  const c = run.value?.weather.temperature_celsius
  if (c == null) return null
  return unit.value === 'mi' ? `${Math.round((c * 9) / 5 + 32)}°F` : `${Math.round(c)}°C`
})

const weatherText = computed(() => {
  if (!run.value) return null
  const w = run.value.weather
  const parts = [w.weather_type, tempText.value, w.humidity_percent != null ? `${w.humidity_percent}% humidity` : null]
  const text = parts.filter(Boolean).join(' · ')
  return text || null
})

// Heat stress flag: warm AND humid — the conditions that quietly slow a run.
const isSteamy = computed(() => {
  const w = run.value?.weather
  return !!w && w.temperature_celsius != null && w.humidity_percent != null &&
    w.temperature_celsius >= 24 && w.humidity_percent >= 70
})

const windText = computed(() => {
  const kph = run.value?.weather.wind_speed_kph
  if (kph == null) return '—'
  return unit.value === 'mi' ? `${Math.round(kph / KM_PER_MI)} mph` : `${kph} kph`
})

// ---- splits ----
const splitNoun = computed(() => (run.value?.splits[0]?.split_unit === 'mi' ? 'Mile' : 'Km'))

const paceInUnit = (minPerKm: number) => (unit.value === 'mi' ? minPerKm * KM_PER_MI : minPerKm)

const splitPaces = computed(() =>
  (run.value?.splits ?? [])
    .filter((s) => s.pace_min_per_km != null)
    .map((s) => ({ n: s.split_number, pace: paceInUnit(s.pace_min_per_km as number) })),
)

const fastestIdx = computed(() => {
  let idx = -1
  let best = Infinity
  splitPaces.value.forEach((s, i) => {
    if (s.pace < best) { best = s.pace; idx = i }
  })
  return idx
})

const fmtPaceTick = (v: number) => {
  const m = Math.floor(v)
  return `${m}:${Math.round((v - m) * 60).toString().padStart(2, '0')}`
}

const splitSeries = computed(() => [
  { name: `pace (min/${distanceLabel(unit.value)})`, data: splitPaces.value.map((s) => Number(s.pace.toFixed(2))) },
])

const splitOptions = computed(() => ({
  chart: { toolbar: { show: false }, fontFamily: 'inherit' },
  plotOptions: { bar: { borderRadius: 4, columnWidth: '55%', distributed: true } },
  colors: splitPaces.value.map((_, i) => (i === fastestIdx.value ? '#f1930f' : '#fbd9a2')),
  dataLabels: {
    enabled: true,
    formatter: fmtPaceTick,
    style: { colors: ['#78716c'], fontWeight: 500 },
    offsetY: -18,
  },
  legend: { show: false },
  xaxis: { categories: splitPaces.value.map((s) => String(s.n)), axisBorder: { show: false }, axisTicks: { show: false } },
  yaxis: { labels: { formatter: fmtPaceTick }, reversed: false },
  grid: { borderColor: '#f3f4f6' },
  tooltip: { y: { formatter: (v: number) => `${fmtPaceTick(v)} /${distanceLabel(unit.value)}` } },
}))

// ---- elevation (cumulative gain across splits) ----
const elevPoints = computed(() =>
  (run.value?.splits ?? []).filter((s) => s.elevation_gain_m != null),
)
const hasElevation = computed(() => elevPoints.value.length > 1)

const toElev = (m: number) => (unit.value === 'mi' ? m * 3.28084 : m)
const elevUnit = computed(() => (unit.value === 'mi' ? 'ft' : 'm'))

const lastElev = computed(() => {
  const pts = elevPoints.value
  return pts.length ? pts[pts.length - 1] : null
})
const elevGainText = computed(() =>
  lastElev.value?.elevation_gain_m != null
    ? `${Math.round(toElev(lastElev.value.elevation_gain_m))} ${elevUnit.value}`
    : '—',
)
const elevLossText = computed(() =>
  lastElev.value?.elevation_loss_m != null
    ? `${Math.round(toElev(lastElev.value.elevation_loss_m))} ${elevUnit.value}`
    : '—',
)

const elevSeries = computed(() => [
  {
    name: `climb (${elevUnit.value})`,
    data: [0, ...elevPoints.value.map((s) => Math.round(toElev(s.elevation_gain_m as number)))],
  },
])

const elevOptions = computed(() => ({
  chart: { toolbar: { show: false }, sparkline: { enabled: false }, fontFamily: 'inherit' },
  stroke: { curve: 'smooth' as const, width: 2 },
  colors: ['#f1930f'],
  fill: { type: 'solid', opacity: 0.16 },
  dataLabels: { enabled: false },
  xaxis: {
    categories: ['0', ...elevPoints.value.map((s) => String(s.split_number))],
    axisBorder: { show: false },
    axisTicks: { show: false },
    title: { text: `${splitNoun.value.toLowerCase()} marker`, style: { fontSize: '11px', color: '#9ca3af' } },
  },
  yaxis: { labels: { formatter: (v: number) => `${Math.round(v)}` } },
  grid: { borderColor: '#f3f4f6' },
  tooltip: { y: { formatter: (v: number) => `${Math.round(v)} ${elevUnit.value}` } },
}))

onMounted(() => {
  load()
  // The track hits SmashRun on the backend — load it lazily, never block the
  // page, and let RouteMap render only if a GPS track came back.
  loadTrack()
  // Cached history stat; only surfaced when the run is steamy (SB-304).
  loadPenalty()
})
</script>
