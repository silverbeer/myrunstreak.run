<template>
  <div class="container-app py-8 max-w-2xl">
    <div class="flex items-start justify-between gap-4 mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 mb-1">My workouts</h1>
        <p class="text-sm text-gray-500">
          Workouts your coach has assigned, plus any you build yourself.
        </p>
      </div>
      <RouterLink
        to="/my/workouts/build"
        class="shrink-0 rounded-lg bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700"
      >
        + New workout
      </RouterLink>
    </div>

    <div v-if="loading" class="space-y-3">
      <div
        v-for="i in 3"
        :key="i"
        class="h-28 bg-white rounded-2xl border border-gray-100 animate-pulse"
      />
    </div>

    <div
      v-else-if="error"
      class="bg-red-50 border border-red-100 rounded-xl p-4 text-sm text-red-600"
    >
      {{ error }}
    </div>

    <div
      v-else-if="templates.length === 0"
      class="bg-white rounded-xl border border-gray-100 shadow-sm p-8 text-center text-gray-500"
    >
      <p>No workouts yet.</p>
    </div>

    <div v-else class="space-y-4">
      <WorkoutTemplateCard
        v-for="t in templates"
        :key="t.id"
        :template="t"
        :exercises="exercises"
        can-log
        can-print
        :can-edit="isMine(t)"
        @log="router.push(`/my/workouts/log/${t.id}`)"
        @print="router.push(`/my/workouts/print/${t.id}`)"
        @edit="router.push(`/my/workouts/build/${t.id}`)"
        @delete="remove(t)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { useMyAthlete } from '@/composables/useCoach'
import { useMyWorkouts } from '@/composables/useMyWorkouts'
import { deleteTemplate } from '@/composables/useWorkoutTemplates'
import WorkoutTemplateCard from '@/components/WorkoutTemplateCard.vue'
import type { WorkoutTemplate } from '@/types/workout'

const router = useRouter()
const { myAthlete, loadMyAthlete } = useMyAthlete()
const { templates, exercises, loading, error, load } = useMyWorkouts()

/**
 * Mine to change (SB-486). A workout the coach prescribed can be logged and
 * printed but not edited — the API enforces that too, this only keeps the
 * buttons honest.
 *
 * Compared against the athlete's own `linked_user_id` rather than the auth
 * store: it is the same user id, already loaded here, and keeps this view free
 * of a Pinia dependency it otherwise would not need.
 */
const isMine = (t: WorkoutTemplate): boolean =>
  !!t.created_by && t.created_by === myAthlete.value?.linked_user_id

const remove = async (t: WorkoutTemplate): Promise<void> => {
  if (!myAthlete.value) return
  if (!window.confirm(`Delete "${t.name}"?`)) return
  await deleteTemplate(t.id, myAthlete.value.id)
  await load()
}

onMounted(async () => {
  await loadMyAthlete(true)
  // Not a linked athlete → no workouts to show here.
  if (!myAthlete.value) {
    router.replace('/dashboard')
    return
  }
  await load()
})
</script>
