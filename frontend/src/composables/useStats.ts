import { ref } from 'vue'
import { apiCall } from '@/config/api'
import type { OverallStats, RecordsInfo, StreakInfo } from '@/types/runs'

export function useStats() {
  const stats = ref<OverallStats | null>(null)
  const streak = ref<StreakInfo | null>(null)
  const records = ref<RecordsInfo | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const load = async (): Promise<void> => {
    loading.value = true
    error.value = null
    try {
      const [overall, streaks, recs] = await Promise.all([
        apiCall<OverallStats>('/stats/overall'),
        apiCall<StreakInfo>('/stats/streaks'),
        apiCall<RecordsInfo>('/stats/records'),
      ])
      stats.value = overall
      streak.value = streaks
      records.value = recs
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load stats'
    } finally {
      loading.value = false
    }
  }

  return { stats, streak, records, loading, error, load }
}
