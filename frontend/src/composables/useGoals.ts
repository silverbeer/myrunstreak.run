import { ref } from 'vue'
import { apiCall } from '@/config/api'
import type { GoalsData } from '@/types/runs'

export function useGoals() {
  const goals = ref<GoalsData | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const load = async (): Promise<void> => {
    loading.value = true
    error.value = null
    try {
      goals.value = await apiCall<GoalsData>('/stats/goals')
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load goals'
    } finally {
      loading.value = false
    }
  }

  return { goals, loading, error, load }
}
