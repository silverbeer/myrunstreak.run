import { ref } from 'vue'
import { apiCall } from '@/config/api'
import type { Exercise, WorkoutTemplate } from '@/types/workout'

/**
 * The linked athlete's own coach-assigned workouts (SB-332). Reads
 * GET /me/workouts — the backend resolves the athlete from the caller's
 * linked_user_id, so no coach act-as header is involved. Exercises are fetched
 * alongside so the card can show display names.
 */
export function useMyWorkouts() {
  const templates = ref<WorkoutTemplate[]>([])
  const exercises = ref<Exercise[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const load = async (): Promise<void> => {
    loading.value = true
    error.value = null
    try {
      const [t, ex] = await Promise.all([
        apiCall<WorkoutTemplate[]>('/me/workouts'),
        apiCall<Exercise[]>('/workouts/exercises'),
      ])
      templates.value = t
      exercises.value = ex
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load workouts'
    } finally {
      loading.value = false
    }
  }

  return { templates, exercises, loading, error, load }
}
