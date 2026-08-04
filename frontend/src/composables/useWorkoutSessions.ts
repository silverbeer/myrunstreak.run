import { ref } from 'vue'
import { apiCall } from '@/config/api'
import { actAs } from '@/utils/actAs'
import type { WorkoutSession } from '@/types/coach'
import type { WorkoutSessionInput } from '@/types/workout'

/**
 * Log a completed workout session on an athlete's account. The coach acts on
 * the athlete's behalf via X-Act-As-Athlete (the backend verifies the coach
 * actually coaches that athlete). Mirrors useWorkoutTemplates.createTemplate.
 */
/**
 * Rename a logged session (SB-536). Only the name — the sets are the record,
 * and relabelling one must never disturb what was logged.
 */
export async function renameSession(
  sessionId: string,
  name: string | null,
  athleteId: string | null,
): Promise<WorkoutSession> {
  return apiCall<WorkoutSession>(`/workouts/sessions/${sessionId}`, {
    method: 'PATCH',
    body: JSON.stringify({ name }),
    headers: actAs(athleteId),
  })
}

export async function createSession(
  payload: WorkoutSessionInput,
  athleteId: string | null,
): Promise<{ id: string }> {
  return apiCall<{ id: string }>('/workouts/sessions', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: actAs(athleteId),
  })
}

/**
 * An athlete's logged sessions, newest first (SB-530).
 *
 * `GET /workouts/sessions` has existed since SB-230 and nothing on the athlete's
 * screen ever called it — which is why "zero sessions ever logged" was invisible
 * rather than merely true. Same act-as header as `createSession`: the backend
 * authorises the coach and the linked athlete identically, so this one function
 * serves both callers.
 *
 * Sets are not returned by the list endpoint; `exercise_count` says what was
 * logged instead.
 */
export function useWorkoutSessions() {
  const sessions = ref<WorkoutSession[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const load = async (athleteId: string | null, limit = 100): Promise<void> => {
    loading.value = true
    error.value = null
    try {
      sessions.value = await apiCall<WorkoutSession[]>(`/workouts/sessions?limit=${limit}`, {
        headers: actAs(athleteId),
      })
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load sessions'
    } finally {
      loading.value = false
    }
  }

  return { sessions, loading, error, load }
}
