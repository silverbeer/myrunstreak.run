<template>
  <form
    class="bg-white border border-brand-200 rounded-xl p-4 space-y-3 shadow-sm"
    data-testid="edit-form"
    @submit.prevent="submit"
  >
    <div class="flex items-center justify-between">
      <p class="text-xs font-semibold uppercase tracking-wide text-brand-500">
        Edit · {{ exercise.display_name }}
      </p>
      <span v-if="exercise.owner_id == null" class="tag-canonical" data-testid="canonical-badge">
        Canonical
      </span>
    </div>

    <input
      v-model="form.display_name"
      required
      placeholder="Name"
      class="form-input w-full"
      data-testid="edit-name"
    />

    <div class="grid grid-cols-2 gap-2">
      <select v-model="form.category" class="form-input" data-testid="edit-category">
        <option v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</option>
      </select>
      <select v-model="form.movement_pattern" class="form-input" data-testid="edit-pattern">
        <option :value="null">— movement —</option>
        <option v-for="p in PATTERNS" :key="p" :value="p">{{ p }}</option>
      </select>
    </div>

    <div class="grid grid-cols-2 gap-2">
      <select v-model="form.difficulty" class="form-input" data-testid="edit-difficulty">
        <option :value="null">— difficulty —</option>
        <option v-for="d in DIFFICULTIES" :key="d" :value="d">{{ d }}</option>
      </select>
      <select v-model="form.visibility" class="form-input" data-testid="edit-visibility">
        <option value="private">private</option>
        <option value="public">public</option>
      </select>
    </div>

    <div>
      <p class="text-xs text-gray-500 mb-1">Measures</p>
      <div class="flex flex-wrap gap-1.5">
        <label
          v-for="m in MEASURE_OPTIONS"
          :key="m.token"
          class="chip-check"
          :class="form.measures.includes(m.token) ? 'chip-on' : 'chip-off'"
          :data-testid="`edit-measure-${m.token}`"
        >
          <input v-model="form.measures" type="checkbox" :value="m.token" class="sr-only" />
          {{ m.label }}
        </label>
      </div>
    </div>

    <label class="flex items-center gap-2 text-xs text-gray-600">
      <input v-model="form.is_benchmark" type="checkbox" data-testid="edit-benchmark" />
      Tracked benchmark (trend over the season)
    </label>

    <input
      v-model="form.aliases"
      placeholder="Aliases (comma-separated)"
      class="form-input w-full"
      data-testid="edit-aliases"
    />
    <input
      v-model="form.equipment"
      placeholder="Equipment (comma-separated)"
      class="form-input w-full"
      data-testid="edit-equipment"
    />
    <textarea
      v-model="form.cues"
      rows="2"
      placeholder="Coaching cues (comma-separated)"
      class="form-input w-full"
      data-testid="edit-cues"
    />

    <div class="flex items-center gap-2">
      <button type="submit" class="btn-primary text-sm" data-testid="edit-save">Save changes</button>
      <button type="button" class="btn-secondary text-sm" data-testid="edit-cancel" @click="$emit('cancel')">
        Cancel
      </button>
    </div>
  </form>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { Exercise, ExerciseCategory, ExerciseUpdate, MovementPattern } from '@/types/workout'
import {
  DIFFICULTIES,
  MEASURE_OPTIONS,
  buildExercisePatch,
  exerciseToForm,
} from '@/utils/exerciseEditForm'

const props = defineProps<{ exercise: Exercise }>()
const emit = defineEmits<{ (e: 'save', patch: ExerciseUpdate): void; (e: 'cancel'): void }>()

const CATEGORIES: ExerciseCategory[] = ['strength', 'speed', 'power', 'mobility', 'cardio', 'test']
const PATTERNS: MovementPattern[] = [
  'squat', 'hinge', 'lunge', 'push', 'pull', 'carry',
  'rotation', 'anti_rotation', 'jump', 'sprint', 'isometric', 'mobility', 'other',
]

const form = ref(exerciseToForm(props.exercise))

const submit = (): void => {
  if (!form.value.display_name.trim()) return
  emit('save', buildExercisePatch(form.value))
}
</script>

<style scoped>
.chip-check {
  @apply px-2 py-0.5 rounded-full text-xs font-medium border cursor-pointer transition select-none;
}
.chip-on {
  @apply bg-brand-600 text-white border-brand-600;
}
.chip-off {
  @apply bg-white text-gray-600 border-gray-200 hover:border-gray-300;
}
.tag-canonical {
  @apply px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 text-[10px] font-medium;
}
</style>
