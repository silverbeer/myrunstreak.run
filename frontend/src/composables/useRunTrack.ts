import { ref } from 'vue'
import { apiCall } from '@/config/api'
import type { RunTrack } from '@/types/runs'

/** One run's GPS track + aligned metric series for the route map (SB-298).
 * Fetched lazily and separately from the run detail (it hits SmashRun). */
export function useRunTrack(activityId: string) {
  const track = ref<RunTrack | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const load = async (): Promise<void> => {
    loading.value = true
    error.value = null
    try {
      track.value = await apiCall<RunTrack>(`/runs/${encodeURIComponent(activityId)}/track`)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load route'
    } finally {
      loading.value = false
    }
  }

  return { track, loading, error, load }
}
