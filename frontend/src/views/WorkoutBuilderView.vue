<template>
  <div class="container-app py-8">
    <RouterLink :to="`/coach/${athleteId}`" class="text-sm text-brand-600 hover:text-brand-700">
      ← Back
    </RouterLink>

    <h1 class="text-2xl font-bold text-gray-900 mt-4">{{ editingId ? 'Edit workout' : 'Build workout' }}</h1>

    <!-- Template meta -->
    <div class="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 mt-4 space-y-3">
      <input
        v-model="name"
        placeholder="Workout name (e.g. Saturday Circuit)"
        class="form-input w-full"
        data-testid="tpl-name"
      />
      <div class="grid grid-cols-2 gap-3">
        <select v-model="type" class="form-input" data-testid="tpl-type">
          <option value="circuit">Circuit</option>
          <option value="intervals">Intervals</option>
          <option value="test">Test</option>
          <option value="session">Session</option>
        </select>
        <label class="flex items-center gap-2 text-sm text-gray-600">
          Rounds
          <input v-model.number="rounds" type="number" min="1" class="form-input w-20" data-testid="tpl-rounds" />
        </label>
      </div>
    </div>

    <!-- Sections -->
    <div v-for="sec in SECTIONS" :key="sec.key" class="mt-5">
      <div class="flex items-center justify-between mb-2">
        <h2 class="text-sm font-semibold uppercase tracking-wide text-gray-400">{{ sec.label }}</h2>
        <button
          type="button"
          class="btn-secondary text-xs"
          :data-testid="`add-${sec.key}`"
          @click="openSection = openSection === sec.key ? null : sec.key"
        >
          {{ openSection === sec.key ? 'Done adding' : '+ Add exercise' }}
        </button>
      </div>

      <!-- Items in this section -->
      <div
        v-for="item in itemsIn(sec.key)"
        :key="item.uid"
        class="bg-white rounded-xl border border-gray-200 p-3 mb-2"
        :data-testid="`item-${item.exercise.key}`"
      >
        <div class="flex items-start justify-between gap-2">
          <span class="text-sm font-medium text-gray-900">{{ item.exercise.display_name }}</span>
          <div class="flex items-center gap-1 shrink-0">
            <button type="button" class="icon-btn" title="Up" @click="move(item, -1)">↑</button>
            <button type="button" class="icon-btn" title="Down" @click="move(item, 1)">↓</button>
            <button
              type="button"
              class="icon-btn text-red-500"
              :data-testid="`remove-${item.exercise.key}`"
              title="Remove"
              @click="remove(item)"
            >
              ✕
            </button>
          </div>
        </div>
        <div class="mt-2 flex flex-wrap gap-2 text-xs">
          <label v-if="uses(item, 'reps')" class="field">
            Reps <input v-model.number="item.reps" type="number" min="0" class="w-14 num" />
          </label>
          <label v-if="uses(item, 'duration_s')" class="field">
            Secs <input v-model.number="item.duration_s" type="number" min="0" class="w-16 num" />
          </label>
          <label v-if="uses(item, 'load_kg')" class="field">
            Load(lb) <input v-model.number="item.load_lb" type="number" min="0" class="w-16 num" data-testid="load-lb" />
          </label>
          <label v-if="uses(item, 'distance_m')" class="field">
            Dist(m) <input v-model.number="item.distance_m" type="number" min="0" class="w-16 num" />
          </label>
          <label class="field">
            Rest(s) <input v-model.number="item.rest_s" type="number" min="0" class="w-16 num" />
          </label>
          <label class="field">
            Variant <input v-model="item.variant" placeholder="e.g. left" class="w-20 num" />
          </label>
        </div>
      </div>

      <!-- Picker for this section -->
      <ExercisePicker
        v-if="openSection === sec.key"
        :exercises="exercises"
        :selected-keys="keysIn(sec.key)"
        mode="select"
        class="bg-gray-50 rounded-xl p-3"
        @toggle="(ex) => onPick(sec.key, ex)"
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
        {{ saving ? 'Saving…' : 'Save workout' }}
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
import { createTemplate, getTemplate, updateTemplate } from '@/composables/useWorkoutTemplates'
import { SECTIONS, buildTemplatePayload, kgToLb } from '@/utils/workoutPayload'
import type { BuilderItem, Exercise, WorkoutSectionKey, WorkoutType } from '@/types/workout'

const route = useRoute()
const router = useRouter()
const athleteId = route.params.athleteId as string
const editingId = (route.params.templateId as string | undefined) || null

const { isCoach, loadRoles } = useRoles()
const { exercises, load } = useExercises()

const name = ref('')
const type = ref<WorkoutType>('circuit')
const rounds = ref(2)
const items = ref<BuilderItem[]>([])
const openSection = ref<WorkoutSectionKey | null>(null)
const saving = ref(false)
const error = ref<string | null>(null)

let nextUid = 1

const itemsIn = (section: WorkoutSectionKey) => items.value.filter((i) => i.section === section)
const keysIn = (section: WorkoutSectionKey) => itemsIn(section).map((i) => i.exercise.key)
const uses = (item: BuilderItem, measure: string) => item.exercise.measures.includes(measure)

const onPick = (section: WorkoutSectionKey, ex: Exercise): void => {
  const existing = items.value.find((i) => i.section === section && i.exercise.key === ex.key)
  if (existing) {
    remove(existing) // toggle off
    return
  }
  items.value.push({
    uid: nextUid++,
    exercise: ex,
    section,
    reps: null,
    duration_s: null,
    load_lb: null,
    distance_m: null,
    rest_s: null,
    variant: null,
    notes: null,
  })
}

const remove = (item: BuilderItem): void => {
  items.value = items.value.filter((i) => i.uid !== item.uid)
}

/** Reorder within the item's own section by swapping with the same-section neighbor. */
const move = (item: BuilderItem, dir: -1 | 1): void => {
  const idx = items.value.findIndex((i) => i.uid === item.uid)
  for (let j = idx + dir; j >= 0 && j < items.value.length; j += dir) {
    if (items.value[j].section === item.section) {
      const next = [...items.value]
      ;[next[idx], next[j]] = [next[j], next[idx]]
      items.value = next
      return
    }
  }
}

const canSave = computed(() => name.value.trim().length > 0 && items.value.length > 0)

const save = async (): Promise<void> => {
  if (!canSave.value) return
  saving.value = true
  error.value = null
  try {
    const payload = buildTemplatePayload(name.value, type.value, rounds.value, items.value)
    if (editingId) await updateTemplate(editingId, payload, athleteId)
    else await createTemplate(payload, athleteId)
    router.push(`/coach/${athleteId}`)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to save workout'
  } finally {
    saving.value = false
  }
}

// Load an existing template into the builder state (kg → lb, key → Exercise).
const prefillFrom = (templateId: string): Promise<void> =>
  getTemplate(templateId, athleteId).then((tpl) => {
    name.value = tpl.name
    type.value = tpl.type
    rounds.value = tpl.rounds
    const byKey = new Map(exercises.value.map((e) => [e.key, e]))
    items.value = tpl.items
      .slice()
      .sort((a, b) => a.position - b.position)
      .map((it) => ({
        uid: nextUid++,
        exercise: byKey.get(it.exercise_key) ?? ({ key: it.exercise_key, display_name: it.exercise_key, measures: [] } as unknown as Exercise),
        section: it.section as WorkoutSectionKey,
        reps: it.target_reps,
        duration_s: it.target_duration_seconds,
        load_lb: kgToLb(it.target_load_kg),
        distance_m: it.target_distance_m,
        rest_s: it.rest_seconds,
        variant: it.variant,
        notes: it.notes,
      }))
  })

onMounted(async () => {
  await loadRoles()
  if (!isCoach.value) {
    router.replace('/dashboard')
    return
  }
  await load()
  if (editingId) await prefillFrom(editingId)
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
</style>
