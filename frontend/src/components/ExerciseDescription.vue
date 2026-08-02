<template>
  <div class="rounded-lg bg-gray-50 px-3 py-2 text-xs text-gray-600" data-testid="exercise-description">
    <ul v-if="cues.length" class="space-y-0.5">
      <li v-for="cue in cues" :key="cue" class="flex gap-1.5">
        <span class="text-gray-300" aria-hidden="true">·</span>
        <span>{{ cue }}</span>
      </li>
    </ul>
    <p v-if="exercise?.instructions" :class="cues.length ? 'mt-1.5' : ''">
      {{ exercise.instructions }}
    </p>
    <p v-if="isEmpty" class="text-gray-400">No description added for this exercise yet.</p>
  </div>
</template>

<script setup lang="ts">
/**
 * What an exercise actually is, for an athlete mid-workout (SB-525).
 *
 * Gabe hit "Aquaman" and had no way to find out what it was — while the cues
 * ("Prone: lift opposite arm + leg", "Long through the spine") sat in the
 * database the whole time. 43 of 57 exercises already have cues; they simply
 * were not rendered on any athlete-facing screen, only on the printed sheet.
 *
 * Presentational only. Each surface owns its own trigger and layout, because
 * the workout card and the session logger arrange their rows differently — but
 * the content and, importantly, the empty-state wording live here so they
 * cannot drift apart.
 */
import { computed } from 'vue'
import type { Exercise } from '@/types/workout'

const props = defineProps<{ exercise?: Exercise | null }>()

const cues = computed(() => props.exercise?.cues ?? [])
const isEmpty = computed(() => cues.value.length === 0 && !props.exercise?.instructions)
</script>
