import { ref } from 'vue'
import { apiCall } from '@/config/api'
import type { WorkoutRecurrence, WorkoutRecurrenceInput } from '@/types/workout'

/** Sunday-first, matching `Date.getDay()` and the stored `byweekday` values. */
export const WEEKDAY_CHIPS: { value: number; label: string }[] = [
  { value: 0, label: 'Su' },
  { value: 1, label: 'M' },
  { value: 2, label: 'Tu' },
  { value: 3, label: 'W' },
  { value: 4, label: 'Th' },
  { value: 5, label: 'F' },
  { value: 6, label: 'Sa' },
]

const FULL = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

/** "Every Mon, Thu" — what a pattern reads as on the plan it belongs to. */
export function describeRecurrence(byweekday: number[]): string {
  const days = [...byweekday].sort((a, b) => a - b).map((d) => FULL[d])
  if (days.length === 7) return 'Every day'
  return `Every ${days.join(', ')}`
}

/**
 * Weekly patterns (SB-535). Both sides set them, through the same act-as header
 * as one-off scheduling — repeating is not a coach-only verb any more than
 * scheduling was.
 */
export async function createRecurrence(
  payload: WorkoutRecurrenceInput,
  athleteId: string,
): Promise<WorkoutRecurrence> {
  return apiCall<WorkoutRecurrence>('/workouts/recurrence', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: { 'X-Act-As-Athlete': athleteId },
  })
}

/** Turn a pattern off. Future occasions stop; everything already generated —
 *  and anything logged against it — is left alone. */
export async function stopRecurrence(
  recurrenceId: string,
  athleteId: string,
): Promise<WorkoutRecurrence> {
  return apiCall<WorkoutRecurrence>(`/workouts/recurrence/${recurrenceId}`, {
    method: 'PATCH',
    body: JSON.stringify({ active: false }),
    headers: { 'X-Act-As-Athlete': athleteId },
  })
}

export function useWorkoutRecurrence() {
  const recurrences = ref<WorkoutRecurrence[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const load = async (athleteId: string): Promise<void> => {
    loading.value = true
    error.value = null
    try {
      recurrences.value = await apiCall<WorkoutRecurrence[]>('/workouts/recurrence', {
        headers: { 'X-Act-As-Athlete': athleteId },
      })
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load repeats'
    } finally {
      loading.value = false
    }
  }

  return { recurrences, loading, error, load }
}
