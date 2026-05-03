import { ref } from 'vue'
import { apiCall } from '@/config/api'
import type { MonthlyStats, MonthlyStatsResponse } from '@/types/runs'

export function useMonthlyStats(limit = 12) {
  const months = ref<MonthlyStats[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const load = async (): Promise<void> => {
    loading.value = true
    error.value = null
    try {
      const res = await apiCall<MonthlyStatsResponse>(`/stats/monthly?limit=${limit}`)
      months.value = [...res.months].reverse()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load monthly stats'
    } finally {
      loading.value = false
    }
  }

  return { months, loading, error, load }
}
