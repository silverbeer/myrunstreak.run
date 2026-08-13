<template>
  <div class="min-h-screen bg-gray-100 print:bg-white">
    <div class="no-print sticky top-0 z-10 bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
      <RouterLink :to="backTo" class="text-sm text-gray-500 hover:text-brand-600">
        ← Back
      </RouterLink>
      <div class="flex items-center gap-3">
        <div class="inline-flex rounded-lg border border-gray-200 p-0.5 bg-gray-50 text-xs font-medium">
          <button
            v-for="f in formats"
            :key="f.key"
            type="button"
            @click="format = f.key"
            :class="[
              'px-3 py-1 rounded-md transition',
              format === f.key ? 'bg-white text-brand-600 shadow-sm' : 'text-gray-500',
            ]"
          >
            {{ f.label }}
          </button>
        </div>
        <button type="button" class="btn-primary text-sm" @click="printSheet">Print</button>
      </div>
    </div>

    <div v-if="loading" class="max-w-3xl mx-auto p-8">
      <div class="bg-white rounded-xl h-96 animate-pulse" />
    </div>
    <div v-else-if="error" class="max-w-xl mx-auto p-8">
      <div class="bg-white rounded-xl p-6 text-center" data-testid="print-error">
        <h2 class="text-lg font-semibold text-gray-900">Couldn't load this workout</h2>
        <p class="mt-2 text-sm text-gray-600">{{ errorHelp }}</p>
        <div class="mt-5 flex items-center justify-center gap-3">
          <button type="button" class="btn-primary text-sm" data-testid="print-retry" @click="load">
            Try again
          </button>
          <RouterLink :to="backTo" class="text-sm text-gray-500 hover:text-brand-600">
            Back to workouts
          </RouterLink>
        </div>
        <p class="mt-4 text-xs text-gray-400">{{ error }}</p>
      </div>
    </div>

    <div
      v-else-if="template"
      class="sheet mx-auto bg-white text-black"
      :class="format === 'card' ? 'sheet-card' : 'sheet-full'"
    >
      <h1 class="sheet-title">{{ athleteName ? `${athleteName} — ${template.name}` : template.name }}</h1>

      <div class="sheet-meta">
        <span>Date: <span class="blank w-32" /></span>
        <span>Start time: <span class="blank w-24" /></span>
        <span class="felt">Felt: <span class="felt-icons">🙂 😐 🙁</span></span>
      </div>

      <div v-for="section in sections" :key="section.key" class="section">
        <div class="section-bar">
          <span class="section-chip">{{ section.label }}</span>
        </div>

        <!-- One table per circuit: Circuit A is two rounds and Circuit B one,
             and a single table cannot carry both sets of columns (SB-528). -->
        <template v-for="(g, gi) in section.groups" :key="g.block?.id ?? `loose-${gi}`">
          <div v-if="g.block" class="block-bar" data-testid="circuit-bar">
            {{ g.block.label.toUpperCase() }}
            <span v-if="g.rounds > 1"> — COMPLETE {{ g.rounds }} ROUNDS</span>
          </div>

          <table class="sheet-table">
            <thead>
              <tr>
                <th class="col-ex">Exercise</th>
                <th class="col-target">Target / details</th>
                <!-- A box per round beats repeating every exercise N times. -->
                <th v-for="r in roundCols(g.rounds)" :key="r" class="col-round">{{ r }}</th>
                <th v-if="!roundCols(g.rounds).length" class="col-done">Done</th>
                <th class="col-times">Times / reps</th>
                <th class="col-notes">Notes</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="row in g.rows" :key="row.kind === 'group' ? row.key : row.item.id">
                <tr v-if="row.kind === 'group'" class="option-head">
                  <td :colspan="4 + Math.max(roundCols(g.rounds).length, 1)">
                    {{ row.label }} — do <strong>one</strong>, circle which
                  </td>
                </tr>
                <tr
                  v-for="item in row.kind === 'group' ? row.items : [row.item]"
                  :key="item.id"
                  :class="{ 'option-item': row.kind === 'group' }"
                >
                  <td class="col-ex font-bold uppercase">
                    <span v-if="row.kind === 'group'" class="option-mark">○</span>
                    {{ exerciseName(item.exercise_key) }}
                    <!-- (L) / (R): these are distinct movements, not repeats. -->
                    <span v-if="item.variant" class="variant">({{ variantLabel(item.variant) }})</span>
                  </td>
                  <td class="col-target">
                    <div>{{ targetText(item) }}</div>
                    <div v-for="cue in cuesFor(item.exercise_key)" :key="cue" class="cue">· {{ cue }}</div>
                    <div v-if="item.notes" class="cue">{{ item.notes }}</div>
                  </td>
                  <td v-for="r in roundCols(g.rounds)" :key="r" class="col-round"></td>
                  <td v-if="!roundCols(g.rounds).length" class="col-done"><span class="checkbox" /></td>
                  <td class="col-times">
                    <table v-if="timeRows(item).length" class="attempts">
                      <tr>
                        <th>{{ item.segments?.length ? 'Segment' : 'Attempt' }}</th>
                        <th>Time</th>
                      </tr>
                      <tr v-for="tr in timeRows(item)" :key="tr.label">
                        <td>{{ tr.label }}<span v-if="tr.goal" class="goal"> ({{ tr.goal }})</span></td>
                        <td><span class="blank w-16" /></td>
                      </tr>
                    </table>
                  </td>
                  <td class="col-notes"></td>
                </tr>
              </template>
              <!-- Rest is a step in the sequence, not a footnote on the last
                   exercise, which is where it used to hide. -->
              <tr v-if="g.restAfter" class="rest-row" data-testid="rest-row">
                <td class="col-ex font-bold uppercase">Rest</td>
                <td class="col-target">{{ fmtSecs(g.restAfter) }} — water</td>
                <td v-for="r in roundCols(g.rounds)" :key="r" class="col-round"></td>
                <td v-if="!roundCols(g.rounds).length" class="col-done"></td>
                <td class="col-times"></td>
                <td class="col-notes"></td>
              </tr>
            </tbody>
          </table>
        </template>
      </div>

      <div class="sheet-footer">
        <span>Total time: <span class="blank w-24" /></span>
        <span class="cheer">Great work!</span>
        <span>Coach notes: <span class="blank w-48" /></span>
      </div>
      <p v-if="template.notes" class="coach-note">{{ template.notes }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { apiCall } from '@/config/api'
import { actAs } from '@/utils/actAs'
import type { Exercise, TemplateItem, WorkoutTemplate } from '@/types/workout'
import type { Athlete } from '@/types/coach'
import { groupOptionItems } from '@/utils/optionGroups'
import { groupByBlock, roundsFor } from '@/utils/circuits'
import { fmtRange, hrZoneText, restText } from '@/utils/targets'
import { useActingAthlete } from '@/composables/useActingAthlete'

const route = useRoute()
const templateId = String(route.params.templateId)

// This view serves two routes:
//   /coach/:athleteId/print/:templateId   — a coach printing for an athlete
//   /my/workouts/print/:templateId        — the athlete printing their own
//
// Only the coach route carries an athleteId, so it must stay nullable:
// String(undefined) yields the string "undefined", which the API rejects as an
// invalid UUID with a bare 422 (SB-522).
// Every workout request is scoped by an athlete id, and a coach-assigned
// template belongs to the ATHLETE row — not to the athlete's user account.
// Omitting the header sends the query down the "my own self-authored rows"
// branch (athlete_id IS NULL), which can never match it, so the athlete got a
// 404 (SB-524).
//
// useActingAthlete already resolves exactly this for both routes — the coach's
// :athleteId param, or the caller's own athlete row — and owns the back-link
// too. SB-524 hand-rolled it here; this is that duplication removed (SB-501).
const { athleteId: scopeAthleteId, isSelf, homePath, resolveAthlete } = useActingAthlete()
const isCoachRoute = !isSelf.value
const backTo = homePath

const template = ref<WorkoutTemplate | null>(null)
const athleteName = ref('')
const exercises = ref<Map<string, Exercise>>(new Map())
const loading = ref(true)
const error = ref<string | null>(null)
const errorStatus = ref<number | null>(null)

type FormatKey = 'full' | 'card'
const format = ref<FormatKey>('full')
const formats: { key: FormatKey; label: string }[] = [
  { key: 'full', label: 'Full page' },
  { key: 'card', label: 'Card' },
]

const SECTION_LABELS: Record<string, string> = {
  warmup: 'Warm-up',
  main: 'Workout',
  cooldown: 'Cool-down',
}

/**
 * The sheet's structure: sections, each split into circuits (SB-528).
 *
 * A circuit gets its own table so it can carry its own round columns — Circuit
 * A is two rounds while Circuit B is one, and a single table cannot have both.
 * Items outside any circuit (the warm-up, the cool-down) form an unlabelled
 * group that renders exactly as before.
 */
const sections = computed(() => {
  const items = [...(template.value?.items ?? [])].sort((a, b) => a.position - b.position)

  const order: string[] = []
  const by: Record<string, TemplateItem[]> = {}
  for (const item of items) {
    const key = item.section || 'main'
    if (!by[key]) {
      by[key] = []
      order.push(key)
    }
    by[key].push(item)
  }

  return order.map((key) => {
    // Partitioned in position order so a circuit stays contiguous on the page.
    // Shared with the card, which has to agree with the paper about what the
    // workout is (SB-543).
    const groups = groupByBlock(by[key], template.value?.blocks ?? [])
    return {
      key,
      label: SECTION_LABELS[key] ?? key.replace(/_/g, ' '),
      items: by[key],
      groups: groups.map((g) => ({
        block: g.block,
        rounds: roundsFor(g, template.value?.rounds),
        restAfter: g.block?.rest_after_seconds ?? null,
        // "Pick one of N" alternatives fold into a single row (SB-448) —
        // printed flat, the aerobic day told Gabe to do all three.
        rows: groupOptionItems(g.items),
      })),
    }
  })
})

/** R1, R2, ... — a box per round. One round needs no columns, just "Done". */
const roundCols = (rounds: number): string[] =>
  rounds > 1 ? Array.from({ length: rounds }, (_, i) => `R${i + 1}`) : []

/** "left" -> "L". The sheet is narrow; the full word costs a line break. */
const SHORT_VARIANT: Record<string, string> = { left: 'L', right: 'R' }
const variantLabel = (v: string): string => SHORT_VARIANT[v.toLowerCase()] ?? v

const exerciseName = (key: string) => exercises.value.get(key)?.display_name ?? key

// Print at most two cues — the sheet is a reminder, not a manual.
const cuesFor = (key: string) => (exercises.value.get(key)?.cues ?? []).slice(0, 2)

const fmtSecs = (s: number) => {
  if (s >= 60) return `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`
  return `${s} sec`
}

const targetText = (item: TemplateItem): string => {
  const parts: string[] = []
  const reps = fmtRange(item.target_reps, item.target_reps_max)
  if (reps) parts.push(`${reps} rep${item.target_reps === 1 && !item.target_reps_max ? '' : 's'}`)
  if (item.target_duration_seconds != null) {
    const max = item.target_duration_max_seconds
    parts.push(
      max != null
        ? `${item.target_duration_seconds}-${max} sec`
        : fmtSecs(item.target_duration_seconds),
    )
  }
  if (item.target_load_kg != null || item.target_load_max_kg != null) {
    const lb = (kg?: number | null) => (kg != null ? Math.round(kg * 2.20462) : null)
    parts.push(`${fmtRange(lb(item.target_load_kg), lb(item.target_load_max_kg))} lb`)
  }
  if (item.target_distance_m != null) {
    const yd = item.target_distance_m / 0.9144
    parts.push(
      Math.abs(yd - Math.round(yd)) < 0.01 && Math.abs(item.target_distance_m - Math.round(item.target_distance_m)) > 0.01
        ? `${Math.round(yd)} yd`
        : `${item.target_distance_m} m`,
    )
  }
  // A prescribed heart-rate zone is the point of the in-season aerobic day.
  const zone = hrZoneText(item)
  if (zone) parts.push(zone)
  if (item.target_cadence != null) parts.push(`${item.target_cadence}/min`)
  if (item.target_speed_kph != null)
    parts.push(`${Math.round(item.target_speed_kph * 0.621371)} mph`)
  const rest = restText(item)
  if (rest) parts.push(rest)
  return parts.join(' · ') || '—'
}

interface TimeRow {
  label: string
  goal: string | null
}

// Attempt rows (timed sprints: "3 attempts, record each") or broken-rep
// segment rows with their goals (SB-264).
const timeRows = (item: TemplateItem): TimeRow[] => {
  if (item.segments?.length) {
    return item.segments.map((seg, i) => ({
      label: seg.label ?? `${i + 1}`,
      goal:
        seg.target_s_min != null && seg.target_s_max != null
          ? `${seg.target_s_min}-${seg.target_s_max}s`
          : seg.target_s_min != null
            ? `${seg.target_s_min}s`
            : null,
    }))
  }
  const measures = exercises.value.get(item.exercise_key)?.measures ?? []
  if (measures.includes('time_s') && (item.target_reps ?? 0) >= 1) {
    return Array.from({ length: item.target_reps as number }, (_, i) => ({
      label: String(i + 1),
      goal: null,
    }))
  }
  return []
}

const printSheet = () => window.print()

// Plain-English cause, chosen by status. The raw message stays on screen too,
// small and grey — useful when debugging, not shouted at the athlete (SB-523).
const errorHelp = computed(() => {
  switch (errorStatus.value) {
    case 401:
    case 403:
      return 'You may not have access to this workout, or your session expired. Try signing in again.'
    case 404:
      return "This workout doesn't exist any more — it may have been deleted."
    case 422:
      return 'Something in the request was wrong, so the server turned it down. This is a bug on our side, not something you did.'
    default:
      return errorStatus.value && errorStatus.value >= 500
        ? 'The server had a problem. Trying again usually works.'
        : 'Check your connection and try again.'
  }
})

const load = async () => {
  loading.value = true
  error.value = null
  errorStatus.value = null
  try {
    // On the athlete route the scope id is not in the URL — resolve it first.
    // Still null afterwards means the caller is printing their own plan and is
    // nobody's athlete (SB-578); actAs omits the header and the API serves
    // their self-owned template.
    if (scopeAthleteId.value === null) await resolveAthlete()
    const headers = actAs(scopeAthleteId.value)
    const [tpl, catalog] = await Promise.all([
      apiCall<WorkoutTemplate>(`/workouts/templates/${templateId}`, { headers }),
      apiCall<Exercise[]>('/workouts/exercises'),
    ])
    template.value = tpl
    exercises.value = new Map(catalog.map((e) => [e.key, e]))
    // Only a coach needs the athlete's name in the heading — printing your own
    // sheet does not, so skip the extra request.
    if (isCoachRoute) {
      const athlete = await apiCall<Athlete>(`/athletes/${scopeAthleteId.value}`)
      athleteName.value = athlete.display_name
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load workout'
    errorStatus.value = (e as { status?: number })?.status ?? null
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.sheet {
  font-family: Helvetica, Arial, sans-serif;
  padding: 2rem 2.5rem;
}
.sheet-full {
  max-width: 8.5in;
  font-size: 12px;
}
.sheet-card {
  max-width: 5in;
  font-size: 9px;
  padding: 1rem 1.25rem;
}
.sheet-title {
  font-size: 2em;
  font-weight: 900;
  text-align: center;
  text-transform: uppercase;
  letter-spacing: 0.01em;
  margin-bottom: 0.75em;
}
.sheet-meta {
  display: flex;
  justify-content: space-between;
  gap: 1em;
  margin-bottom: 1.25em;
  font-weight: 600;
}
.felt-icons {
  font-size: 1.3em;
  letter-spacing: 0.35em;
}
.blank {
  display: inline-block;
  border-bottom: 1px solid #000;
  height: 1em;
  vertical-align: bottom;
}
.w-16 { width: 4rem; }
.w-24 { width: 6rem; }
.w-32 { width: 8rem; }
.w-48 { width: 12rem; }
.section { margin-bottom: 1.25em; }
.section-bar {
  display: flex;
  align-items: center;
  gap: 0.75em;
  margin-bottom: 0.4em;
}
.section-chip {
  background: #000;
  color: #fff;
  font-weight: 800;
  text-transform: uppercase;
  padding: 0.25em 0.9em;
}
.section-note {
  font-weight: 700;
  text-transform: uppercase;
}
.sheet-table {
  width: 100%;
  border-collapse: collapse;
}
.sheet-table th,
.sheet-table td {
  border: 1px solid #000;
  padding: 0.45em 0.55em;
  vertical-align: top;
  text-align: left;
}
.sheet-table thead th {
  background: #e5e5e5;
  text-transform: uppercase;
  font-size: 0.85em;
  text-align: center;
}
.col-ex { width: 18%; }
.col-target { width: 34%; }
.col-done { width: 7%; text-align: center; }
/* Narrow, so the round boxes cost little width and Notes keeps room to
   actually write in (SB-528). */
.col-round { width: 5%; text-align: center; }
.block-bar {
  background: #e9e9e9;
  border: 1px solid #000;
  border-bottom: 0;
  padding: 0.25em 0.5em;
  font-weight: 700;
  font-size: 0.9em;
  letter-spacing: 0.02em;
  margin-top: 0.6em;
}
.rest-row td { background: #f7f7f7; }
.col-times { width: 22%; }
.col-notes { width: 19%; }
.variant { font-weight: 400; text-transform: none; }
/* "Pick one of N" (SB-448): the heading has to survive black-and-white
   photocopying, so it leans on weight and a rule rather than colour. */
.option-head td {
  font-size: 0.92em;
  font-style: italic;
  padding-top: 0.35em;
  border-bottom: 1px solid #000;
}
.option-item td { background: #f4f4f4; }
.option-mark { font-style: normal; margin-right: 0.35em; }
.cue { color: #444; font-size: 0.9em; margin-top: 0.15em; }
.checkbox {
  display: inline-block;
  width: 1.1em;
  height: 1.1em;
  border: 1.5px solid #000;
  margin-top: 0.15em;
}
.attempts {
  width: 100%;
  border-collapse: collapse;
}
.attempts th,
.attempts td {
  border: 1px solid #999;
  padding: 0.15em 0.4em;
  font-size: 0.9em;
  text-align: center;
}
.attempts th {
  background: #f0f0f0;
  text-transform: uppercase;
  font-size: 0.75em;
}
.goal { color: #444; }
.sheet-footer {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 1em;
  font-weight: 700;
  margin-top: 1em;
}
.cheer { font-style: italic; }
.coach-note { margin-top: 0.75em; color: #333; }

@media print {
  .no-print { display: none !important; }
  .sheet {
    max-width: none;
    padding: 0;
  }
  .sheet-card { font-size: 9px; }
}
@page {
  margin: 0.6in;
}
</style>
