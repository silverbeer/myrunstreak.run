import { apiCall } from '@/config/api'
import type { WorkoutTemplateInput } from '@/types/workout'

/**
 * Create a workout template on an athlete's account. The coach acts on the
 * athlete's behalf via the X-Act-As-Athlete header (the backend verifies the
 * coach actually coaches that athlete).
 */
export async function createTemplate(
  payload: WorkoutTemplateInput,
  athleteId: string,
): Promise<{ id: string }> {
  return apiCall<{ id: string }>('/workouts/templates', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: { 'X-Act-As-Athlete': athleteId },
  })
}
