import { ref } from 'vue'
import { apiCall } from '@/config/api'
import type { OverallStats, StreakInfo } from '@/types/runs'

export function useStats() {
  const stats = ref<OverallStats | null>(null)
  const streak = ref<StreakInfo | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const load = async (): Promise<void> => {
    loading.value = true
    error.value = null
    try {
      const [overall, streaks] = await Promise.all([
        apiCall<OverallStats>('/stats/overall'),
        apiCall<StreakInfo>('/stats/streaks'),
      ])
      stats.value = overall
      streak.value = streaks
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load stats'
    } finally {
      loading.value = false
    }
  }

  return { stats, streak, loading, error, load }
}
