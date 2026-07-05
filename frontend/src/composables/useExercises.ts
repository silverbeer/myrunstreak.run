import { ref } from 'vue'
import { apiCall } from '@/config/api'
import type { Exercise, ExerciseCreate } from '@/types/workout'

/**
 * The exercise catalog: the public library + the caller's own private exercises
 * (backend `GET /workouts/exercises` returns exactly the visible set). Small
 * enough to load once and search/filter client-side.
 */
export function useExercises() {
  const exercises = ref<Exercise[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const load = async (): Promise<void> => {
    loading.value = true
    error.value = null
    try {
      exercises.value = await apiCall<Exercise[]>('/workouts/exercises')
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load exercises'
    } finally {
      loading.value = false
    }
  }

  const create = async (payload: ExerciseCreate): Promise<Exercise | null> => {
    error.value = null
    try {
      const created = await apiCall<Exercise>('/workouts/exercises', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      exercises.value = [...exercises.value, created]
      return created
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to create exercise'
      return null
    }
  }

  const publish = async (key: string): Promise<Exercise | null> => {
    error.value = null
    try {
      const updated = await apiCall<Exercise>(`/workouts/exercises/${key}/publish`, {
        method: 'POST',
      })
      exercises.value = exercises.value.map((e) => (e.key === key ? updated : e))
      return updated
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to publish exercise'
      return null
    }
  }

  return { exercises, loading, error, load, create, publish }
}
