import { apiCall } from '@/config/api'
import { actAs } from '@/utils/actAs'
import type { WorkoutTemplate, WorkoutTemplateInput } from '@/types/workout'

/**
 * Create a workout template on an athlete's account. The coach acts on the
 * athlete's behalf via the X-Act-As-Athlete header (the backend verifies the
 * coach actually coaches that athlete).
 */
export async function createTemplate(
  payload: WorkoutTemplateInput,
  athleteId: string | null,
): Promise<{ id: string }> {
  return apiCall<{ id: string }>('/workouts/templates', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: actAs(athleteId),
  })
}

export async function getTemplate(templateId: string, athleteId: string | null): Promise<WorkoutTemplate> {
  return apiCall<WorkoutTemplate>(`/workouts/templates/${templateId}`, {
    headers: actAs(athleteId),
  })
}

export async function updateTemplate(
  templateId: string,
  payload: WorkoutTemplateInput,
  athleteId: string | null,
): Promise<WorkoutTemplate> {
  return apiCall<WorkoutTemplate>(`/workouts/templates/${templateId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
    headers: actAs(athleteId),
  })
}

export async function deleteTemplate(templateId: string, athleteId: string | null): Promise<void> {
  await apiCall(`/workouts/templates/${templateId}`, {
    method: 'DELETE',
    headers: actAs(athleteId),
  })
}
