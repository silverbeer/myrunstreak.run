<template>
  <div class="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
    <div class="flex items-center justify-between gap-2">
      <h3 class="text-base font-semibold text-gray-900">{{ template.name }}</h3>
      <span class="text-xs text-gray-500 whitespace-nowrap">
        {{ template.type }} · {{ template.rounds }}× rounds
      </span>
    </div>
    <p v-if="template.source" class="text-xs text-gray-400 mt-0.5">Coach: {{ template.source }}</p>

    <div v-for="sec in sections" :key="sec.key" class="mt-3">
      <h4 class="text-[11px] font-semibold uppercase tracking-wide text-gray-400 mb-1">
        {{ sec.label }}
      </h4>
      <ol class="space-y-1">
        <li
          v-for="item in sec.items"
          :key="item.id"
          class="flex items-baseline justify-between gap-3 text-sm"
        >
          <span class="text-gray-800">
            {{ nameFor(item.exercise_key) }}
            <span v-if="item.variant" class="text-gray-400">({{ item.variant }})</span>
          </span>
          <span class="text-xs text-gray-500 text-right whitespace-nowrap">{{ target(item) }}</span>
        </li>
      </ol>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Exercise, TemplateItem, WorkoutSectionKey, WorkoutTemplate } from '@/types/workout'
import { SECTIONS, kgToLb, prettifyKey } from '@/utils/workoutPayload'

const props = defineProps<{
  template: WorkoutTemplate
  exercises?: Exercise[]
}>()

const byKey = computed<Record<string, Exercise>>(() => {
  const map: Record<string, Exercise> = {}
  for (const ex of props.exercises ?? []) map[ex.key] = ex
  return map
})

const nameFor = (key: string): string => byKey.value[key]?.display_name ?? prettifyKey(key)

// Only render sections that have items, in canonical order.
const sections = computed(() =>
  SECTIONS.map((s) => ({
    ...s,
    items: props.template.items
      .filter((it) => it.section === (s.key as WorkoutSectionKey))
      .sort((a, b) => a.position - b.position),
  })).filter((s) => s.items.length > 0),
)

/** Compact target summary, e.g. "60s · 10 lb · rest 30s". */
const target = (it: TemplateItem): string => {
  const parts: string[] = []
  if (it.target_reps != null) parts.push(`${it.target_reps} reps`)
  if (it.target_duration_seconds != null) parts.push(`${it.target_duration_seconds}s`)
  if (it.target_load_kg != null) parts.push(`${kgToLb(it.target_load_kg)} lb`)
  if (it.target_distance_m != null) parts.push(`${it.target_distance_m} m`)
  if (it.rest_seconds != null) parts.push(`rest ${it.rest_seconds}s`)
  return parts.join(' · ')
}
</script>
