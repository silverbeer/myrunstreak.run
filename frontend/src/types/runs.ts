export type Unit = 'mi' | 'km'

export interface OverallStats {
  total_runs: number
  total_km: number
  avg_km: number
  longest_run_km: number
  avg_pace_min_per_km: number
}

export interface StreakInfo {
  current_streak: number
  longest_streak: number
  top_streaks: TopStreak[]
}

export interface TopStreak {
  start_date: string | null
  end_date: string | null
  length_days: number
  is_current: boolean
}

export interface RecentRun {
  activity_id: string
  date: string
  distance_km: number
  duration_seconds: number
  duration_minutes: number
  avg_pace_min_per_km: number | null
  heart_rate_avg: number | null
  temperature_celsius: number | null
  weather: string | null
}

export interface PaginatedRun {
  activity_id: string
  date: string
  distance_km: number
  duration_minutes: number
  avg_pace_min_per_km: number | null
}

export interface RecentRunsResponse {
  count: number
  runs: RecentRun[]
}

export interface RunsResponse {
  total: number
  offset: number
  limit: number
  count: number
  runs: PaginatedRun[]
}

export interface MonthlyStats {
  month: string
  run_count: number
  total_km: number
  avg_km: number
  avg_pace_min_per_km: number | null
}

export interface MonthlyStatsResponse {
  count: number
  months: MonthlyStats[]
}

export interface SyncResponse {
  message: string
  runs_synced: number
  since: string
  until: string
}

export interface GoalProgress {
  goal_mi: number
  progress_mi: number
  percent: number | null
  text: string | null
  fetched_at: string | null
}

export interface GoalsData {
  yearly: GoalProgress | null
  monthly: GoalProgress | null
}
