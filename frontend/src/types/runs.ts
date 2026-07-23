export type Unit = 'mi' | 'km'

export interface OverallStats {
  total_runs: number
  total_km: number
  avg_km: number
  longest_run_km: number
  avg_pace_min_per_km: number
}

export interface RecordsInfo {
  longest_run?: { date: string; distance_km: number; activity_id: string }
  fastest_pace?: {
    date: string
    pace_min_per_km: number
    distance_km: number
    activity_id: string
  }
  most_km_month?: { month: string; run_count: number; total_km: number }
}

export interface StreakInfo {
  current_streak: number
  current_streak_km: number
  longest_streak: number
  longest_streak_km: number
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
  weather: string | null
  temperature_celsius: number | null
}

/** GET /runs filter params (SB-268 history filters; SB-269 explorer). */
export interface RunFilters {
  date_from?: string
  date_to?: string
  distance_min?: number
  distance_max?: number
  weather_type?: string
  temp_min?: number
  temp_max?: number
  pace_min?: number
  pace_max?: number
  on_this_day?: string
  hour_min?: number
  hour_max?: number
  sort?: 'date' | 'distance' | 'pace' | 'temperature'
  order?: 'asc' | 'desc'
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

export interface GoalHistoryItem extends GoalProgress {
  year: number
  month: number | null
  period: 'year' | 'month'
  hit: boolean
}

// ---- Run detail (SB-263) ----

export interface RunSplit {
  split_number: number
  split_unit: string | null
  cumulative_distance_km: number | null
  cumulative_seconds: number | null
  pace_min_per_km: number | null
  heart_rate: number | null
  elevation_gain_m: number | null
  elevation_loss_m: number | null
}

export interface RunWeather {
  temperature_celsius: number | null
  weather_type: string | null
  humidity_percent: number | null
  wind_speed_kph: number | null
}

export interface RunVitals {
  heart_rate_avg: number | null
  heart_rate_min: number | null
  heart_rate_max: number | null
  cadence_avg: number | null
}

export interface RunDetail {
  activity_id: string
  date: string
  distance_km: number
  duration_seconds: number
  avg_pace_min_per_km: number | null
  weather: RunWeather
  vitals: RunVitals
  how_felt: string | null
  notes: string | null
  splits: RunSplit[]
}

/** Per-point GPS track + aligned metric series for the route map (SB-298). */
export interface RunTrack {
  activity_id: string
  has_track: boolean
  lat: number[]
  lon: number[]
  elevation_m: number[]
  heart_rate: number[]
  pace_min_per_km: number[]
  dist_km: number[]
  city: string | null
  state: string | null
  date: string
  distance_km: number | null
  duration_seconds: number | null
  avg_pace_min_per_km: number | null
  weather_type: string | null
  temperature_celsius: number | null
}
