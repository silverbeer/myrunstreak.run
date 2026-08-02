<template>
  <div class="container-app py-8 max-w-2xl">
    <div class="flex items-start justify-between gap-4 mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 mb-1">My workouts</h1>
        <p class="text-sm text-gray-500">
          Workouts your coach has assigned, plus any you build yourself.
        </p>
      </div>
      <!-- "+ New workout" used to be the loudest control here and it built a
           PLAN, which read as "do a workout" and was the reported confusion
           (SB-530). Building is secondary; doing is the point. -->
      <RouterLink
        to="/my/workouts/build"
        class="shrink-0 rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50"
      >
        + Build a workout
      </RouterLink>
    </div>

    <!-- Nothing is scheduled yet — `scheduled_for` is unset on every template —
         so logging what you just did IS the primary action (SB-531). When
         scheduling lands this becomes the "due today" card and the ad-hoc link
         drops beneath it. -->
    <div class="mb-5 rounded-2xl border border-brand-200 bg-brand-50 p-5 text-center">
      <p class="text-sm font-semibold text-brand-800">Did a workout on your own?</p>
      <p class="mt-1 text-sm text-brand-700">Log it and get the credit — no plan needed.</p>
      <RouterLink
        to="/my/workouts/log"
        class="mt-3 inline-block rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
        data-testid="log-adhoc"
      >
        + Log a workout
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
