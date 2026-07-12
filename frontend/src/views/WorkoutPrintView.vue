<template>
  <div class="min-h-screen bg-gray-100 print:bg-white">
    <div class="no-print sticky top-0 z-10 bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
      <RouterLink :to="`/coach/${athleteId}`" class="text-sm text-gray-500 hover:text-brand-600">
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
    <div v-else-if="error" class="max-w-3xl mx-auto p-8 text-sm text-red-700">{{ error }}</div>

    <div
      v-else-if="template"
      class="sheet mx-auto bg-white text-black"
      :class="format === 'card' ? 'sheet-card' : 'sheet-full'"
    >
      <h1 class="sheet-title">{{ athleteName }} — {{ template.name }}</h1>

      <div class="sheet-meta">
        <span>Date: <span class="blank w-32" /></span>
        <span>Start time: <span class="blank w-24" /></span>
        <span class="felt">Felt: <span class="felt-icons">🙂 😐 🙁</span></span>
      </div>

      <div v-for="section in sections" :key="section.key" class="section">
        <div class="section-bar">
          <span class="section-chip">{{ section.label }}</span>
          <span v-if="section.key === 'main' && template.rounds > 1" class="section-note">
            Complete {{ template.rounds }} rounds
          </span>
        </div>

        <table class="sheet-table">
          <thead>
            <tr>
              <th class="col-ex">Exercise</th>
              <th class="col-target">Target / details</th>
              <th class="col-done">Done</th>
              <th class="col-times">Times / reps</th>
              <th class="col-notes">Notes</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in section.items" :key="item.id">
              <td class="col-ex font-bold uppercase">
                {{ exerciseName(item.exercise_key) }}
                <span v-if="item.variant" class="variant">({{ item.variant }})</span>
              </td>
              <td class="col-target">
                <div>{{ targetText(item) }}</div>
                <div v-for="cue in cuesFor(item.exercise_key)" :key="cue" class="cue">· {{ cue }}</div>
                <div v-if="item.notes" class="cue">{{ item.notes }}</div>
              </td>
              <td class="col-done"><span class="checkbox" /></td>
              <td class="col-times">
                <table v-if="timeRows(item).length" class="attempts">
                  <tr>
                    <th>{{ item.segments?.length ? 'Segment' : 'Attempt' }}</th>
                    <th>Time</th>
                  </tr>
                  <tr v-for="row in timeRows(item)" :key="row.label">
                    <td>{{ row.label }}<span v-if="row.goal" class="goal"> ({{ row.goal }})</span></td>
                    <td><span class="blank w-16" /></td>
                  </tr>
                </table>
              </td>
              <td class="col-notes"></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="format === 'full'" class="fold">— — — — — — — — — — <span>fold here</span> — — — — — — — — — —</div>

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
import type { Exercise, TemplateItem, WorkoutTemplate } from '@/types/workout'
import type { Athlete } from '@/types/coach'

const route = useRoute()
const athleteId = String(route.params.athleteId)
const templateId = String(route.params.templateId)

const template = ref<WorkoutTemplate | null>(null)
const athleteName = ref('')
const exercises = ref<Map<string, Exercise>>(new Map())
const loading = ref(true)
const error = ref<string | null>(null)

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
  return order.map((key) => ({
    key,
    label: SECTION_LABELS[key] ?? key.replace(/_/g, ' '),
    items: by[key],
  }))
})

const exerciseName = (key: string) => exercises.value.get(key)?.display_name ?? key

// Print at most two cues — the sheet is a reminder, not a manual.
const cuesFor = (key: string) => (exercises.value.get(key)?.cues ?? []).slice(0, 2)

const fmtSecs = (s: number) => {
  if (s >= 60) return `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`
  return `${s} sec`
}

const targetText = (item: TemplateItem): string => {
  const parts: string[] = []
  if (item.target_reps) parts.push(`${item.target_reps} rep${item.target_reps === 1 ? '' : 's'}`)
  if (item.target_duration_seconds != null) {
    const max = item.target_duration_max_seconds
    parts.push(
      max != null
        ? `${item.target_duration_seconds}-${max} sec`
        : fmtSecs(item.target_duration_seconds),
    )
  }
  if (item.target_load_kg != null) parts.push(`${Math.round(item.target_load_kg * 2.20462)} lb`)
  if (item.target_distance_m != null) {
    const yd = item.target_distance_m / 0.9144
    parts.push(
      Math.abs(yd - Math.round(yd)) < 0.01 && Math.abs(item.target_distance_m - Math.round(item.target_distance_m)) > 0.01
        ? `${Math.round(yd)} yd`
        : `${item.target_distance_m} m`,
    )
  }
  if (item.rest_seconds) parts.push(`rest ${fmtSecs(item.rest_seconds)}`)
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

onMounted(async () => {
  try {
    const actAs = { 'X-Act-As-Athlete': athleteId }
    const [tpl, athlete, catalog] = await Promise.all([
      apiCall<WorkoutTemplate>(`/workouts/templates/${templateId}`, { headers: actAs }),
      apiCall<Athlete>(`/athletes/${athleteId}`),
      apiCall<Exercise[]>('/workouts/exercises'),
    ])
    template.value = tpl
    athleteName.value = athlete.display_name
    exercises.value = new Map(catalog.map((e) => [e.key, e]))
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load workout'
  } finally {
    loading.value = false
  }
})
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
.col-times { width: 22%; }
.col-notes { width: 19%; }
.variant { font-weight: 400; text-transform: none; }
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
.fold {
  text-align: center;
  color: #555;
  font-style: italic;
  margin: 1.5em 0;
  white-space: nowrap;
  overflow: hidden;
}
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
