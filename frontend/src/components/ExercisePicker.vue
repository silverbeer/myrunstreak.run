<template>
  <div class="space-y-4">
    <!-- Search -->
    <div class="relative">
      <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
      <input
        ref="searchEl"
        v-model="query"
        type="text"
        placeholder="Search exercises… (name or alias)"
        class="form-input w-full pl-9"
        data-testid="exercise-search"
      />
    </div>

    <!-- Balance nudge (programming assistant) -->
    <div
      v-for="msg in nudges"
      :key="msg"
      class="flex items-start gap-2 text-xs bg-amber-50 border border-amber-200 text-amber-800 rounded-lg px-3 py-2"
      data-testid="balance-nudge"
    >
      <Scale class="w-3.5 h-3.5 mt-0.5 shrink-0" /> {{ msg }}
    </div>

    <!-- Facets -->
    <div class="flex flex-wrap gap-1.5">
      <button
        v-for="opt in ownershipFacets"
        :key="opt.value"
        type="button"
        class="chip"
        :class="ownership === opt.value ? 'chip-on' : 'chip-off'"
        @click="ownership = opt.value"
      >
        {{ opt.label }}
      </button>
      <span class="w-px bg-gray-200 mx-1" />
      <button
        v-for="p in patternFacets"
        :key="p"
        type="button"
        class="chip"
        :class="patternFilter === p ? 'chip-on' : 'chip-off'"
        @click="patternFilter = patternFilter === p ? null : p"
      >
        {{ p }}
      </button>
    </div>

    <!-- Results -->
    <div v-if="filtered.length" class="grid grid-cols-1 sm:grid-cols-2 gap-2" data-testid="results">
      <button
        v-for="ex in filtered"
        :key="ex.key"
        type="button"
        class="text-left rounded-xl border p-3 transition hover:border-brand-400"
        :class="isSelected(ex) ? 'border-brand-500 bg-brand-50' : 'border-gray-200 bg-white'"
        :data-testid="`ex-${ex.key}`"
        @click="onCard(ex)"
      >
        <div class="flex items-start justify-between gap-2">
          <span class="text-sm font-medium text-gray-900">{{ ex.display_name }}</span>
          <Check v-if="isSelected(ex)" class="w-4 h-4 text-brand-600 shrink-0" />
        </div>
        <div class="mt-1 flex flex-wrap items-center gap-1 text-[10px]">
          <span class="tag">{{ ex.category }}</span>
          <span v-if="ex.movement_pattern" class="tag">{{ ex.movement_pattern }}</span>
          <span v-for="eq in ex.equipment" :key="eq" class="tag-muted">{{ eq }}</span>
          <span v-if="ex.owner_id" class="tag-mine">Mine</span>
          <span v-if="ex.visibility === 'private'" class="tag-private">Private</span>
        </div>
        <p v-if="ex.cues.length" class="mt-1 text-[11px] text-gray-500 line-clamp-1">
          {{ ex.cues.join(' · ') }}
        </p>
        <button
          v-if="mode === 'manage' && ex.owner_id && ex.visibility === 'private'"
          type="button"
          class="mt-2 btn-secondary text-[11px]"
          :data-testid="`publish-${ex.key}`"
          @click.stop="$emit('publish', ex.key)"
        >
          Publish to library
        </button>
      </button>
    </div>

    <!-- Empty → create -->
    <div
      v-else
      class="text-sm text-gray-500 bg-gray-50 border border-gray-200 rounded-xl p-4"
      data-testid="empty"
    >
      No match<span v-if="query"> for "{{ query }}"</span>.
      <button type="button" class="text-brand-600 font-medium" @click="openCreate">
        Create a new exercise
      </button>
    </div>

    <!-- Inline create -->
    <form
      v-if="showCreate"
      class="bg-white border border-gray-200 rounded-xl p-4 space-y-3"
      data-testid="create-form"
      @submit.prevent="submitCreate"
    >
      <p class="text-xs font-semibold uppercase tracking-wide text-gray-400">New exercise</p>
      <input
        v-model="form.display_name"
        required
        placeholder="Name"
        class="form-input w-full"
        data-testid="create-name"
      />
      <div class="grid grid-cols-2 gap-2">
        <select v-model="form.category" class="form-input" data-testid="create-category">
          <option v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</option>
        </select>
        <select v-model="form.movement_pattern" class="form-input" data-testid="create-pattern">
          <option :value="null">— movement —</option>
          <option v-for="p in PATTERNS" :key="p" :value="p">{{ p }}</option>
        </select>
      </div>
      <label class="flex items-center gap-2 text-xs text-gray-600">
        <input v-model="publishNow" type="checkbox" data-testid="create-public" />
        Add to the shared public library (otherwise private to you)
      </label>
      <button type="submit" class="btn-primary text-sm" data-testid="create-submit">
        Create exercise
      </button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { Check, Scale, Search } from 'lucide-vue-next'
import type { Exercise, ExerciseCategory, ExerciseCreate, MovementPattern } from '@/types/workout'
import { balanceNudges } from '@/utils/exerciseBalance'

const props = withDefaults(
  defineProps<{
    exercises: Exercise[]
    selectedKeys?: string[]
    mode?: 'select' | 'manage'
  }>(),
  { selectedKeys: () => [], mode: 'select' },
)

const emit = defineEmits<{
  (e: 'toggle', exercise: Exercise): void
  (e: 'create', payload: ExerciseCreate): void
  (e: 'publish', key: string): void
}>()

const CATEGORIES: ExerciseCategory[] = ['strength', 'speed', 'power', 'mobility', 'cardio', 'test']
const PATTERNS: MovementPattern[] = [
  'squat', 'hinge', 'lunge', 'push', 'pull', 'carry',
  'rotation', 'anti_rotation', 'jump', 'sprint', 'isometric', 'mobility', 'other',
]

const searchEl = ref<HTMLInputElement | null>(null)
const query = ref('')
const ownership = ref<'all' | 'mine' | 'public'>('all')
const patternFilter = ref<MovementPattern | null>(null)

const ownershipFacets = [
  { value: 'all' as const, label: 'All' },
  { value: 'mine' as const, label: 'Mine' },
  { value: 'public' as const, label: 'Public' },
]

// Only offer pattern chips actually present in the catalog.
const patternFacets = computed(() => {
  const present = new Set<MovementPattern>()
  for (const ex of props.exercises) if (ex.movement_pattern) present.add(ex.movement_pattern)
  return PATTERNS.filter((p) => present.has(p))
})

const isSelected = (ex: Exercise): boolean => props.selectedKeys.includes(ex.key)

const filtered = computed<Exercise[]>(() => {
  const q = query.value.trim().toLowerCase()
  return props.exercises.filter((ex) => {
    if (ownership.value === 'mine' && !ex.owner_id) return false
    if (ownership.value === 'public' && ex.visibility !== 'public') return false
    if (patternFilter.value && ex.movement_pattern !== patternFilter.value) return false
    if (!q) return true
    const hay = [ex.display_name, ...(ex.aliases ?? [])].map((s) => s.toLowerCase())
    return hay.some((h) => h.includes(q))
  })
})

const nudges = computed<string[]>(() => {
  if (!props.selectedKeys.length) return []
  const selected = props.exercises.filter((ex) => props.selectedKeys.includes(ex.key))
  return balanceNudges(selected)
})

const onCard = (ex: Exercise): void => {
  if (props.mode === 'select') emit('toggle', ex)
}

// --- inline create ---
const showCreate = ref(false)
const publishNow = ref(false)
const form = ref<{
  display_name: string
  category: ExerciseCategory
  movement_pattern: MovementPattern | null
}>({ display_name: '', category: 'strength', movement_pattern: null })

const openCreate = (): void => {
  form.value.display_name = query.value
  showCreate.value = true
}

const submitCreate = (): void => {
  const payload: ExerciseCreate = {
    display_name: form.value.display_name.trim(),
    category: form.value.category,
    movement_pattern: form.value.movement_pattern,
    visibility: publishNow.value ? 'public' : 'private',
  }
  if (!payload.display_name) return
  emit('create', payload)
  showCreate.value = false
  form.value = { display_name: '', category: 'strength', movement_pattern: null }
  publishNow.value = false
}

onMounted(async () => {
  await nextTick()
  searchEl.value?.focus()
})
</script>

<style scoped>
.chip {
  @apply px-2 py-0.5 rounded-full text-xs font-medium border transition;
}
.chip-on {
  @apply bg-brand-600 text-white border-brand-600;
}
.chip-off {
  @apply bg-white text-gray-600 border-gray-200 hover:border-gray-300;
}
.tag {
  @apply px-1.5 py-0.5 rounded bg-gray-100 text-gray-600;
}
.tag-muted {
  @apply px-1.5 py-0.5 rounded bg-gray-50 text-gray-400;
}
.tag-mine {
  @apply px-1.5 py-0.5 rounded bg-blue-100 text-blue-700;
}
.tag-private {
  @apply px-1.5 py-0.5 rounded bg-amber-100 text-amber-700;
}
</style>
