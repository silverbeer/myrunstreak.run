// Shapes returned by the backend /metrics/* endpoints (see backend/routes/metrics.py).

export type MetricAggregation = 'sum' | 'count' | 'latest' | 'max'
export type GoalKind = 'volume' | 'frequency' | 'streak'
export type GoalPeriod = 'year' | 'month' | 'week' | 'custom'
export type GoalComparator = 'gte' | 'lte'
export type GoalStatus = 'active' | 'achieved' | 'archived'

export interface MetricType {
  key: string
  display_name: string
  unit: string
  aggregation: MetricAggregation
  higher_is_better: boolean
}

export interface MetricGoal {
  id: string
  user_id: string
  metric_key: string
  kind: GoalKind
  period: GoalPeriod
  period_start: string | null
  period_end: string | null
  target: number
  comparator: GoalComparator
  rest_budget: number
  status: GoalStatus
  created_at?: string | null
}

export interface GoalProgress {
  goal: MetricGoal
  window_start: string
  window_end: string
  progress: number
  target: number
  percent: number | null
  met: boolean
  projected: number | null
  on_pace: boolean | null
  per_day_needed: number | null
}

export interface MetricEntry {
  id: string
  user_id: string
  metric_key: string
  occurred_on: string
  occurred_at: string | null
  value: number
  note: string | null
  source: string
  external_id: string | null
  created_at?: string | null
}
