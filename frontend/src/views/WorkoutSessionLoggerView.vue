<template>
  <div class="container-app py-8">
    <RouterLink :to="`/coach/${athleteId}`" class="text-sm text-brand-600 hover:text-brand-700">
      ← Back
    </RouterLink>

    <h1 class="text-2xl font-bold text-gray-900 mt-4">Log workout</h1>
    <p v-if="templateName" class="text-sm text-gray-500 mt-1" data-testid="from-template">
      From <span class="font-medium text-gray-700">{{ templateName }}</span>
    </p>

    <!-- Session meta -->
    <div class="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 mt-4 space-y-3">
      <div class="grid grid-cols-2 gap-3">
        <label class="flex flex-col gap-1 text-sm text-gray-600">
          Date
          <input v-model="sessionDate" type="date" class="form-input" data-testid="session-date" />
        </label>
        <label class="flex flex-col gap-1 text-sm text-gray-600">
          Total minutes
          <input
            v-model.number="totalMinutes"
            type="number"
            min="0"
            class="form-input"
            data-testid="total-minutes"
          />
        </label>
      </div>

      <div class="flex items-center gap-2">
        <span class="text-sm text-gray-600">Felt</span>
        <button
          v-for="f in FELT_OPTIONS"
          :key="f.value"
          type="button"
          class="felt"
          :class="howFelt === f.value ? 'felt-on' : 'felt-off'"
          :data-testid="`felt-${f.value}`"
          :aria-label="f.label"
          @click="howFelt = howFelt === f.value ? null : f.value"
        >
          {{ f.emoji }}
        </button>
      </div>

      <textarea
        v-model="notes"
        placeholder="Session notes (optional)"
        rows="2"
        class="form-input w-full"
        data-testid="session-notes"
      />
    </div>

    <!-- Logged exercises -->
    <div
      v-for="row in rows"
      :key="row.uid"
      class="bg-white rounded-xl border border-gray-200 p-3 mt-3"
      :data-testid="`row-${row.exercise.key}`"
    >
      <div class="flex items-start justify-between gap-2">
        <span class="text-sm font-medium text-gray-900">{{ row.exercise.display_name }}</span>
        <button
          type="button"
          class="icon-btn text-red-500"
          :data-testid="`remove-${row.exercise.key}`"
          title="Remove"
          @click="removeRow(row)"
        >
          ✕
        </button>
      </div>

      <div class="mt-2 flex flex-wrap gap-2 text-xs">
        <label class="field">
          Round
          <input v-model.number="row.round_number" type="number" min="1" class="w-14 num"
            :data-testid="`round-${row.exercise.key}`" />
        </label>
        <label class="field">
          Variant
          <input v-model="row.variant" placeholder="e.g. left" class="w-20 num"
            :data-testid="`variant-${row.exercise.key}`" />
        </label>
      </div>

      <!-- Attempts (sets) -->
      <div
        v-for="(a, i) in row.attempts"
        :key="i"
        class="mt-2 flex flex-wrap items-center gap-2 text-xs"
        :data-testid="`attempt-${row.exercise.key}-${i}`"
      >
        <span v-if="row.attempts.length > 1" class="w-8 text-gray-400 tabular-nums">#{{ i + 1 }}</span>
        <label v-for="f in fieldsFor(row)" :key="f.model" class="field">
          {{ f.label }}
          <input
            v-model.number="a[f.model]"
            type="number"
            min="0"
            step="any"
            class="w-16 num"
            :data-testid="`${f.model}-${row.exercise.key}-${i}`"
          />
        </label>
        <label class="field">
          RPE
          <input v-model.number="a.rpe" type="number" min="1" max="10" class="w-12 num"
            :data-testid="`rpe-${row.exercise.key}-${i}`" />
        </label>
        <button
          v-if="row.attempts.length > 1"
          type="button"
          class="icon-btn text-gray-400"
          :data-testid="`remove-set-${row.exercise.key}-${i}`"
          title="Remove set"
          @click="removeAttempt(row, i)"
        >
          ✕
        </button>
      </div>

      <button
        type="button"
        class="btn-secondary text-xs mt-2"
        :data-testid="`add-set-${row.exercise.key}`"
        @click="row.attempts.push(blankAttempt())"
      >
        + Add set
      </button>
    </div>

    <!-- Add exercise -->
    <div class="mt-4">
      <button
        type="button"
        class="btn-secondary text-xs"
        data-testid="add-exercise"
        @click="picking = !picking"
      >
        {{ picking ? 'Done adding' : '+ Add exercise' }}
      </button>
      <ExercisePicker
        v-if="picking"
        :exercises="exercises"
        :selected-keys="rowKeys"
        mode="select"
        class="bg-gray-50 rounded-xl p-3 mt-2"
        @toggle="onPick"
      />
    </div>

    <!-- Save -->
    <div class="mt-6 flex items-center gap-3">
      <button
        type="button"
        class="btn-primary"
        :disabled="!canSave || saving"
        data-testid="save"
        @click="save"
      >
        {{ saving ? 'Saving…' : 'Save session' }}
      </button>
      <span v-if="error" class="text-sm text-red-600">{{ error }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ExercisePicker from '@/components/ExercisePicker.vue'
import { useExercises } from '@/composables/useExercises'
import { useRoles } from '@/composables/useCoach'
import { getTemplate } from '@/composables/useWorkoutTemplates'
import { createSession } from '@/composables/useWorkoutSessions'
import {
  FELT_OPTIONS,
  blankAttempt,
  buildSessionPayload,
  templateToRows,
  todayISO,
} from '@/utils/sessionPayload'
import type { Exercise, LoggerRow, WorkoutType } from '@/types/workout'

const route = useRoute()
const router = useRouter()
const athleteId = route.params.athleteId as string
const templateId = (route.params.templateId as string | undefined) || null

const { isCoach, loadRoles } = useRoles()
const { exercises, load } = useExercises()

const sessionDate = ref(todayISO())
const totalMinutes = ref<number | null>(null)
const howFelt = ref<string | null>(null)
const notes = ref<string | null>(null)
const rows = ref<LoggerRow[]>([])
const templateName = ref<string | null>(null)
const sessionType = ref<WorkoutType>('circuit')
const picking = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)

let nextUid = 1

const rowKeys = computed(() => rows.value.map((r) => r.exercise.key))

// Which numeric fields to show per attempt — the exercise's own measures, or a
// reps + time fallback when the catalog carries none. RPE is always shown.
interface FieldDef {
  measure: string
  label: string
  model: 'reps' | 'duration_s' | 'load_lb' | 'distance_m' | 'time_seconds'
}
const FIELD_DEFS: FieldDef[] = [
  { measure: 'reps', label: 'Reps', model: 'reps' },
  { measure: 'duration_s', label: 'Secs', model: 'duration_s' },
  { measure: 'load_kg', label: 'Load(lb)', model: 'load_lb' },
  { measure: 'distance_m', label: 'Dist(m)', model: 'distance_m' },
  { measure: 'time_seconds', label: 'Time(s)', model: 'time_seconds' },
]
const FALLBACK: FieldDef[] = [FIELD_DEFS[0], FIELD_DEFS[4]] // reps + time

const fieldsFor = (row: LoggerRow): FieldDef[] => {
  const shown = FIELD_DEFS.filter((f) => row.exercise.measures.includes(f.measure))
  return shown.length ? shown : FALLBACK
}

const onPick = (ex: Exercise): void => {
  const existing = rows.value.find((r) => r.exercise.key === ex.key)
  if (existing) {
    removeRow(existing) // toggle off
    return
  }
  rows.value.push({
    uid: nextUid++,
    exercise: ex,
    round_number: null,
    variant: null,
    notes: null,
    attempts: [blankAttempt()],
  })
}

const removeRow = (row: LoggerRow): void => {
  rows.value = rows.value.filter((r) => r.uid !== row.uid)
}

const removeAttempt = (row: LoggerRow, i: number): void => {
  row.attempts.splice(i, 1)
}

const payload = computed(() =>
  buildSessionPayload(
    {
      session_date: sessionDate.value,
      type: sessionType.value,
      total_minutes: totalMinutes.value,
      how_felt: howFelt.value,
      notes: notes.value,
      template_id: templateId,
    },
    rows.value,
  ),
)

const canSave = computed(() => sessionDate.value.length > 0 && payload.value.sets.length > 0)

const save = async (): Promise<void> => {
  if (!canSave.value) return
  saving.value = true
  error.value = null
  try {
    await createSession(payload.value, athleteId)
    router.push(`/coach/${athleteId}`)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to save session'
  } finally {
    saving.value = false
  }
}

const prefillFrom = (id: string): Promise<void> =>
  getTemplate(id, athleteId).then((tpl) => {
    templateName.value = tpl.name
    sessionType.value = tpl.type
    const byKey = new Map(exercises.value.map((e) => [e.key, e]))
    rows.value = templateToRows(tpl, byKey, nextUid)
    nextUid += rows.value.length
  })

onMounted(async () => {
  await loadRoles()
  if (!isCoach.value) {
    router.replace('/dashboard')
    return
  }
  await load()
  if (templateId) await prefillFrom(templateId)
})
</script>

<style scoped>
.field {
  @apply inline-flex items-center gap-1 text-gray-600;
}
.num {
  @apply border border-gray-200 rounded px-1.5 py-0.5 text-xs;
}
.icon-btn {
  @apply px-1.5 py-0.5 rounded hover:bg-gray-100 text-gray-500 text-sm;
}
.felt {
  @apply w-9 h-9 rounded-full text-lg grid place-items-center border transition-colors;
}
.felt-on {
  @apply border-brand-400 bg-brand-50;
}
.felt-off {
  @apply border-gray-200 hover:bg-gray-50;
}
</style>
