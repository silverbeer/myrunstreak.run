import { ref } from 'vue'
import { apiCall } from '@/config/api'
import type { GoalProgress, MetricEntry, MetricType } from '@/types/metrics'

export function useMetrics() {
  const types = ref<MetricType[]>([])
  const goals = ref<GoalProgress[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const loadTypes = async (): Promise<void> => {
    try {
      types.value = await apiCall<MetricType[]>('/metrics/types')
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load metric types'
    }
  }

  const loadGoals = async (): Promise<void> => {
    loading.value = true
    error.value = null
    try {
      goals.value = await apiCall<GoalProgress[]>('/metrics/goals')
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load goals'
    } finally {
      loading.value = false
    }
  }

  const logEntry = async (metricKey: string, value: number): Promise<MetricEntry> => {
    return apiCall<MetricEntry>('/metrics/entries', {
      method: 'POST',
      body: JSON.stringify({ metric_key: metricKey, value }),
    })
  }

  return { types, goals, loading, error, loadTypes, loadGoals, logEntry }
}
