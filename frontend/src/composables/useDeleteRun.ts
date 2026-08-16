import { ref } from 'vue'
import { apiCall } from '@/config/api'

/**
 * Delete an imported run (SB-621).
 *
 * Only imported runs qualify — the API refuses a synced one with a 409, since
 * deleting it would only last until the next sync recreated it. The view hides
 * the control for those, so a 409 here means the run's source changed under us
 * and the server's own wording is the honest thing to show.
 */
export function useDeleteRun() {
  const deleting = ref(false)
  const error = ref<string | null>(null)

  const remove = async (activityId: string): Promise<boolean> => {
    deleting.value = true
    error.value = null
    try {
      await apiCall<null>(`/runs/${encodeURIComponent(activityId)}`, { method: 'DELETE' })
      return true
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Could not delete this run'
      return false
    } finally {
      deleting.value = false
    }
  }

  return { remove, deleting, error }
}
