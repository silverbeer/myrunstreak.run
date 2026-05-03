import { ref } from 'vue'
import { apiCall } from '@/config/api'
import type { RecentRun, RecentRunsResponse } from '@/types/runs'

export function useRecentRuns(limit = 7) {
  const runs = ref<RecentRun[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const load = async (): Promise<void> => {
    loading.value = true
    error.value = null
    try {
      const res = await apiCall<RecentRunsResponse>(`/runs/recent?limit=${limit}`)
      runs.value = res.runs
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load recent runs'
    } finally {
      loading.value = false
    }
  }

  return { runs, loading, error, load }
}
