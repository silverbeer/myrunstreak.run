import { apiCall } from '@/config/api'
import type { WorkoutSessionInput } from '@/types/workout'

/**
 * Log a completed workout session on an athlete's account. The coach acts on
 * the athlete's behalf via X-Act-As-Athlete (the backend verifies the coach
 * actually coaches that athlete). Mirrors useWorkoutTemplates.createTemplate.
 */
export async function createSession(
  payload: WorkoutSessionInput,
  athleteId: string,
): Promise<{ id: string }> {
  return apiCall<{ id: string }>('/workouts/sessions', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: { 'X-Act-As-Athlete': athleteId },
  })
}
