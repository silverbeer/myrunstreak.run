import { ref } from 'vue'
import { apiCall } from '@/config/api'
import type { GoalHistoryItem } from '@/types/runs'

/**
 * Full goal history (past monthly + yearly goals, target vs achieved).
 *
 * Lazy: `load` no-ops after the first successful fetch so re-opening the
 * collapsible section doesn't refetch. Data rarely changes within a session.
 */
export function useGoalHistory() {
  const items = ref<GoalHistoryItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const loaded = ref(false)

  const load = async (): Promise<void> => {
    if (loaded.value || loading.value) return
    loading.value = true
    error.value = null
    try {
      items.value = await apiCall<GoalHistoryItem[]>('/stats/goals/history')
      loaded.value = true
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load goal history'
    } finally {
      loading.value = false
    }
  }

  return { items, loading, error, loaded, load }
}
