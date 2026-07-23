<template>
  <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-6 mt-4">
    <div class="flex items-start justify-between flex-wrap gap-3 mb-3">
      <div>
        <h2 class="font-semibold text-gray-900">Route</h2>
        <p v-if="place" class="text-xs text-gray-400 mt-0.5">📍 {{ place }}</p>
      </div>
      <div class="flex items-center gap-1.5 flex-wrap">
        <button
          v-for="m in availableModes"
          :key="m.key"
          type="button"
          class="text-xs px-2.5 py-1 rounded-full border transition-colors"
          :class="mode === m.key
            ? 'border-brand-500 bg-brand-50 text-brand-700 font-medium'
            : 'border-gray-200 text-gray-500 hover:border-gray-300'"
          @click="mode = m.key"
        >
          {{ m.label }}
        </button>
        <button
          type="button"
          class="text-xs px-2.5 py-1 rounded-full border border-gray-200 text-gray-500 hover:border-gray-300"
          @click="replay"
        >
          ↻ Replay
        </button>
      </div>
    </div>

    <div
      class="relative w-full rounded-lg overflow-hidden"
      :style="{ aspectRatio: `${vb.W} / ${vb.H}`, background: 'radial-gradient(120% 90% at 50% 0%, #fff7ec, #fdfbf7)' }"
      @pointermove="onHover"
      @pointerleave="hoverIdx = null"
    >
      <svg :viewBox="`0 0 ${vb.W} ${vb.H}`" preserveAspectRatio="xMidYMid meet" class="block w-full h-full">
        <defs>
          <filter id="rm-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="0.5" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        <!-- ghost full route -->
        <path :d="pathD" fill="none" stroke="#f1930f" stroke-opacity="0.12"
              stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round" />

        <!-- colored segments, revealed progressively -->
        <g filter="url(#rm-glow)">
          <line
            v-for="(s, i) in segments"
            :key="i"
            :x1="s.x1" :y1="s.y1" :x2="s.x2" :y2="s.y2"
            :stroke="s.color"
            stroke-width="1.2"
            stroke-linecap="round"
            :style="{ opacity: i < shown ? 1 : 0 }"
          />
        </g>

        <!-- start marker -->
        <circle :cx="pts[0].x" :cy="pts[0].y" r="1.4" fill="#ffffff"
                stroke="#16a34a" stroke-width="0.8" />

        <!-- runner dot while drawing -->
        <circle v-if="running" :cx="runnerPt.x" :cy="runnerPt.y" r="1.4"
                fill="#fff" filter="url(#rm-glow)" />

        <!-- hover marker -->
        <circle v-if="hoverIdx !== null" :cx="pts[hoverIdx].x" :cy="pts[hoverIdx].y"
                r="1.6" fill="#f1930f" stroke="#fff" stroke-width="0.7" />
      </svg>

      <!-- hover tooltip -->
      <div
        v-if="hoverIdx !== null"
        class="absolute pointer-events-none bg-gray-900/90 text-white text-[11px] rounded-md px-2 py-1.5 shadow-lg whitespace-nowrap -translate-x-1/2"
        :style="{
          left: `${(pts[hoverIdx].x / vb.W) * 100}%`,
          top: `calc(${(pts[hoverIdx].y / vb.H) * 100}% - 8px)`,
          transform: 'translate(-50%, -100%)',
        }"
      >
        <div class="font-semibold">{{ hoverDistance }}</div>
        <div v-if="hoverPace" class="text-gray-300">{{ hoverPace }}</div>
        <div v-if="hoverHr" class="text-gray-300">{{ hoverHr }} bpm</div>
        <div v-if="hoverElev" class="text-gray-300">↑ {{ hoverElev }}</div>
      </div>
    </div>

    <!-- legend for the active metric -->
    <div class="flex items-center justify-between mt-3 text-xs text-gray-400">
      <span>{{ activeMode.legendLow }}</span>
      <div class="h-1.5 flex-1 mx-3 rounded-full" :style="{ background: legendGradient }" />
      <span>{{ activeMode.legendHigh }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { RunTrack, Unit } from '@/types/runs'
import { formatPace, distanceLabel } from '@/utils/format'

const props = defineProps<{ track: RunTrack; unit: Unit }>()

const KM_PER_MI = 1.609344
const toMi = (km: number) => km / KM_PER_MI
const toFt = (m: number) => m * 3.28084

type ModeKey = 'pace' | 'elevation' | 'hr'
type Stop = [number, number, number]

// Each metric: how to read its series, the colour ramp (low→high value), and
// how to phrase the legend ends. Pace ramps gold(fast)→red(slow); elevation
// low→high blue; HR easy→max green→red.
const MODE_DEFS: Record<
  ModeKey,
  { key: ModeKey; label: string; series: () => number[]; stops: Stop[]; legend: (lo: number, hi: number) => [string, string] }
> = {
  pace: {
    key: 'pace',
    label: 'Pace',
    series: () => props.track.pace_min_per_km,
    stops: [[255, 210, 74], [241, 147, 15], [224, 87, 31]],
    legend: (lo, hi) => [`${formatPace(lo, props.unit)}/${distanceLabel(props.unit)}`, `${formatPace(hi, props.unit)}/${distanceLabel(props.unit)}`],
  },
  elevation: {
    key: 'elevation',
    label: 'Elevation',
    series: () => props.track.elevation_m,
    stops: [[147, 197, 253], [59, 130, 246], [30, 58, 138]],
    legend: (lo, hi) => [elevLabel(lo), elevLabel(hi)],
  },
  hr: {
    key: 'hr',
    label: 'Heart rate',
    series: () => props.track.heart_rate,
    stops: [[52, 211, 153], [245, 158, 11], [239, 68, 68]],
    legend: (lo, hi) => [`${Math.round(lo)} bpm`, `${Math.round(hi)} bpm`],
  },
}

const elevLabel = (m: number) =>
  props.unit === 'mi' ? `${Math.round(toFt(m))} ft` : `${Math.round(m)} m`

const n = computed(() => props.track.lat.length)

const availableModes = computed(() =>
  (Object.values(MODE_DEFS) as (typeof MODE_DEFS)[ModeKey][]).filter((m) => {
    const s = m.series()
    return s.length === n.value && Math.max(...s) > Math.min(...s)
  }),
)

const mode = ref<ModeKey>('pace')
watch(availableModes, (modes) => {
  if (!modes.some((m) => m.key === mode.value) && modes.length) mode.value = modes[0].key
}, { immediate: true })

const activeDef = computed(() => MODE_DEFS[mode.value])

// --- projection (equirectangular, cos(lat)-corrected, north up) ---
const vb = computed(() => {
  const { lat, lon } = props.track
  const meanLat = lat.reduce((a, b) => a + b, 0) / lat.length
  const k = Math.cos((meanLat * Math.PI) / 180)
  const xs = lon.map((v) => v * k)
  const minx = Math.min(...xs)
  const maxx = Math.max(...xs)
  const miny = Math.min(...lat)
  const maxy = Math.max(...lat)
  const spanx = maxx - minx || 1e-9
  const spany = maxy - miny || 1e-9
  const W = 100
  const pad = 6
  // Fit both spans to one scale so the shape isn't distorted; height follows.
  const s = Math.max(spanx / (W - 2 * pad), spany / 60)
  const usedW = spanx / s
  const usedH = spany / s
  const H = usedH + 2 * pad
  const offx = (W - usedW) / 2
  const pts = lat.map((la, i) => ({
    x: offx + (xs[i] - minx) / s,
    y: H - (pad + (la - miny) / s),
  }))
  return { W, H, pts, xs, minx, s }
})

const pts = computed(() => vb.value.pts)
const pathD = computed(() => 'M' + pts.value.map((p) => `${p.x.toFixed(2)} ${p.y.toFixed(2)}`).join(' L'))

// --- colour ramp for the active metric ---
function ramp(values: number[], stops: Stop[]) {
  const sorted = [...values].sort((a, b) => a - b)
  const lo = sorted[Math.floor(sorted.length * 0.05)]
  const hi = sorted[Math.floor(sorted.length * 0.95)] || lo + 1
  const color = (v: number) => {
    let t = (v - lo) / (hi - lo || 1)
    t = Math.max(0, Math.min(1, t))
    const seg = t * (stops.length - 1)
    const i = Math.min(stops.length - 2, Math.floor(seg))
    const f = seg - i
    const a = stops[i]
    const b = stops[i + 1]
    return `rgb(${Math.round(a[0] + (b[0] - a[0]) * f)},${Math.round(a[1] + (b[1] - a[1]) * f)},${Math.round(a[2] + (b[2] - a[2]) * f)})`
  }
  return { color, lo, hi }
}

const segments = computed(() => {
  const s = activeDef.value.series()
  const { color } = ramp(s, activeDef.value.stops)
  const p = pts.value
  const out: { x1: number; y1: number; x2: number; y2: number; color: string }[] = []
  for (let i = 1; i < p.length; i++) {
    out.push({ x1: p[i - 1].x, y1: p[i - 1].y, x2: p[i].x, y2: p[i].y, color: color(s[i]) })
  }
  return out
})

const activeMode = computed(() => {
  const s = activeDef.value.series()
  const { lo, hi } = ramp(s, activeDef.value.stops)
  const [legendLow, legendHigh] = activeDef.value.legend(lo, hi)
  return { legendLow, legendHigh }
})

const legendGradient = computed(() => {
  const st = activeDef.value.stops
  const css = st.map((c, i) => `rgb(${c[0]},${c[1]},${c[2]}) ${(i / (st.length - 1)) * 100}%`)
  return `linear-gradient(90deg, ${css.join(', ')})`
})

// --- draw-on animation ---
const shown = ref(0)
const running = ref(false)
const runnerPt = computed(() => pts.value[Math.max(0, Math.min(pts.value.length - 1, shown.value))])
let rafId = 0

function replay() {
  cancelAnimationFrame(rafId)
  const total = segments.value.length
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (prefersReduced) {
    shown.value = total
    running.value = false
    return
  }
  const dur = 3400
  const t0 = performance.now()
  running.value = true
  const step = (now: number) => {
    const p = Math.min(1, (now - t0) / dur)
    const e = 1 - Math.pow(1 - p, 3)
    shown.value = Math.round(total * e)
    if (p < 1) {
      rafId = requestAnimationFrame(step)
    } else {
      running.value = false
    }
  }
  rafId = requestAnimationFrame(step)
}

onMounted(replay)
onBeforeUnmount(() => cancelAnimationFrame(rafId))

// --- hover scrubbing ---
const hoverIdx = ref<number | null>(null)
function onHover(e: PointerEvent) {
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const vx = ((e.clientX - rect.left) / rect.width) * vb.value.W
  const vy = ((e.clientY - rect.top) / rect.height) * vb.value.H
  let best = -1
  let bestD = Infinity
  const p = pts.value
  for (let i = 0; i < p.length; i++) {
    const dx = p[i].x - vx
    const dy = p[i].y - vy
    const d = dx * dx + dy * dy
    if (d < bestD) {
      bestD = d
      best = i
    }
  }
  hoverIdx.value = best
}

const hoverDistance = computed(() => {
  if (hoverIdx.value === null) return ''
  const km = props.track.dist_km[hoverIdx.value] ?? 0
  return props.unit === 'mi' ? `${toMi(km).toFixed(2)} mi` : `${km.toFixed(2)} km`
})
const hoverPace = computed(() => {
  const i = hoverIdx.value
  if (i === null) return ''
  const p = props.track.pace_min_per_km[i]
  return p ? `${formatPace(p, props.unit)}/${distanceLabel(props.unit)}` : ''
})
const hoverHr = computed(() => {
  const i = hoverIdx.value
  if (i === null) return 0
  return props.track.heart_rate[i] ? Math.round(props.track.heart_rate[i]) : 0
})
const hoverElev = computed(() => {
  const i = hoverIdx.value
  if (i === null || !props.track.elevation_m.length) return ''
  return elevLabel(props.track.elevation_m[i])
})

const place = computed(() =>
  [props.track.city, props.track.state].filter(Boolean).join(', '),
)
</script>
