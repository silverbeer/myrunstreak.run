import { ref } from 'vue'
import { apiCall } from '@/config/api'
import type { GoalProgress, MetricEntry, MetricGoal, MetricType } from '@/types/metrics'

export interface NewGoalPayload {
  metric_key: string
  kind: string
  period: string
  target: number
  comparator: string
  rest_budget?: number
  period_start?: string
  period_end?: string
}

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

  const createGoal = async (payload: NewGoalPayload): Promise<MetricGoal> => {
    return apiCall<MetricGoal>('/metrics/goals', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  }

  return { types, goals, loading, error, loadTypes, loadGoals, logEntry, createGoal }
}
