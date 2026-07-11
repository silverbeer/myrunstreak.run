import { ref } from 'vue'
import { apiCall } from '@/config/api'
import type { RunDetail } from '@/types/runs'

/** One run's full story — weather, vitals, splits, elevation (SB-263). */
export function useRunDetail(activityId: string) {
  const run = ref<RunDetail | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const load = async (): Promise<void> => {
    loading.value = true
    error.value = null
    try {
      run.value = await apiCall<RunDetail>(`/runs/${encodeURIComponent(activityId)}`)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load run'
    } finally {
      loading.value = false
    }
  }

  return { run, loading, error, load }
}
