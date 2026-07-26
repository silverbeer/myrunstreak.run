<template>
  <div class="container-app py-8 max-w-2xl">
    <h1 class="text-2xl font-bold text-gray-900 mb-1">My workouts</h1>
    <p class="text-sm text-gray-500 mb-6">Workouts your coach has assigned to you.</p>

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
      <p>No workouts assigned yet.</p>
    </div>

    <div v-else class="space-y-4">
      <WorkoutTemplateCard
        v-for="t in templates"
        :key="t.id"
        :template="t"
        :exercises="exercises"
        readonly
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMyAthlete } from '@/composables/useCoach'
import { useMyWorkouts } from '@/composables/useMyWorkouts'
import WorkoutTemplateCard from '@/components/WorkoutTemplateCard.vue'

const router = useRouter()
const { myAthlete, loadMyAthlete } = useMyAthlete()
const { templates, exercises, loading, error, load } = useMyWorkouts()

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
