<template>
  <div class="container-app py-8">
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-gray-900">Exercise catalog</h1>
      <p class="text-sm text-gray-500 mt-1">
        The shared library plus your own exercises. Search before adding — keep the catalog clean.
      </p>
    </div>

    <div v-if="loading" class="text-sm text-gray-500">Loading catalog…</div>
    <div
      v-else-if="error"
      class="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700"
    >
      {{ error }}
    </div>

    <ExercisePicker
      v-else
      :exercises="exercises"
      mode="manage"
      @create="onCreate"
      @publish="onPublish"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import ExercisePicker from '@/components/ExercisePicker.vue'
import { useExercises } from '@/composables/useExercises'
import { useRoles } from '@/composables/useCoach'
import type { ExerciseCreate } from '@/types/workout'

const router = useRouter()
const { isCoach, loadRoles } = useRoles()
const { exercises, loading, error, load, create, publish } = useExercises()

const onCreate = async (payload: ExerciseCreate) => {
  await create(payload)
}
const onPublish = async (key: string) => {
  await publish(key)
}

onMounted(async () => {
  // Coach/admin only — the nav link is hidden for others, but guard direct URLs.
  await loadRoles()
  if (!isCoach.value) {
    router.replace('/dashboard')
    return
  }
  await load()
})
</script>
