import { ref } from 'vue'
import { apiCall } from '@/config/api'
import { actAs } from '@/utils/actAs'
import type { WorkoutScheduleEntry, WorkoutScheduleInput } from '@/types/workout'

/**
 * Planned occasions — a plan put on a day (SB-534).
 *
 * Both sides schedule: the coach assigning Thursday, and the athlete planning
 * their own week. Both go through the same act-as header, because the API
 * authorises the coach and the linked athlete identically — one code path for
 * two callers is what stops the coach case working while the athlete's breaks.
 */
export async function createSchedule(
  payload: WorkoutScheduleInput,
  athleteId: string | null,
): Promise<WorkoutScheduleEntry> {
  return apiCall<WorkoutScheduleEntry>('/workouts/schedule', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: actAs(athleteId),
  })
}

export async function deleteSchedule(scheduleId: string, athleteId: string | null): Promise<void> {
  await apiCall(`/workouts/schedule/${scheduleId}`, {
    method: 'DELETE',
    headers: actAs(athleteId),
  })
}

export function useWorkoutSchedule() {
  const schedule = ref<WorkoutScheduleEntry[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  /** Occasions from `from` onwards, soonest first. Coming up asks from today. */
  const load = async (athleteId: string | null, from?: string): Promise<void> => {
    loading.value = true
    error.value = null
    try {
      const query = from ? `?date_from=${from}` : ''
      schedule.value = await apiCall<WorkoutScheduleEntry[]>(`/workouts/schedule${query}`, {
        headers: actAs(athleteId),
      })
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load the schedule'
    } finally {
      loading.value = false
    }
  }

  return { schedule, loading, error, load }
}
