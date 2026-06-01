# MyRunStreak.run — Data Model & Schema

Data lives in **Supabase Postgres**. The schema is multi-user and multi-source
from the ground up, with Row-Level Security (RLS) for isolation and SQL
migrations under `supabase/migrations/`.

> Earlier versions used DuckDB on S3. That was replaced by Supabase Postgres
> during the LKE migration; see `docs/SUPABASE_MIGRATION.md` for the history.

## Pipeline

```
SmashRun API → Pydantic models (src/shared/models) → Supabase repositories
             → Postgres tables → analytics views / RPC functions → API
```

- **Pydantic v2** validates and normalizes source payloads (camelCase →
  snake_case, computed pace/speed, enum coercion).
- **Repositories** (`src/shared/supabase_ops/`) wrap all table access:
  `runs_repository`, `goals_repository`, `users_repository`,
  `token_repository`, plus `mappers`.
- Distances are stored canonically in **kilometers**; the API/UI convert to
  miles at the edge (see `docs/UNITS.md`).

## Core tables

All UUID PKs (`gen_random_uuid()`), `ON DELETE CASCADE` to the owning user, and
`created_at` / `updated_at` audit columns (the latter maintained by the
`update_updated_at_column()` trigger).

### `users`
Runner accounts — `user_id`, `email`, `display_name`. One row per user.

### `user_sources`
OAuth/data-source connections, one per `(user_id, source_type)`.
- `source_type` enum: `smashrun` | `strava` | `garmin` | `other`.
- Per-user tokens stored directly: `access_token`, `refresh_token`,
  `token_expires_at` (added in `add_token_columns`). `source_user_id`,
  `source_username`, `is_active`, `last_sync_at`, `last_sync_status`.

### `runs`
The core activity table — one row per synced run.
- Identity/dedup: `source_activity_id`, `external_id`,
  `UNIQUE(user_id, source_id, source_activity_id)`.
- Temporal: `start_date_time_local`, plus denormalized `start_date`,
  `start_year`, `start_month`, `start_day_of_week` — populated by the
  `compute_run_metrics()` trigger.
- Metrics: `distance_km`, `duration_seconds`, computed
  `average_pace_min_per_km` / `average_speed_kph`; cadence + heart-rate
  min/avg/max.
- Health/context: `body_weight_kg`, `how_felt`, `terrain`,
  `temperature_celsius`, `weather_type`, `humidity_percent`, `wind_speed_kph`,
  `notes`.
- Metadata: `activity_type`, `device_type`, `app_version`, and `has_*` data
  availability flags.
- Indexes: `(user_id, start_date DESC)`, `(user_id, start_year, start_month)`,
  `source_id`.

### `splits`
Per-mile/km splits for a run. `split_unit` (`mi`|`km`), cumulative distance/time,
`pace_min_per_km`, `heart_rate`, cumulative elevation gain/loss.
`UNIQUE(run_id, split_unit, split_number)`.

### `recording_data`
GPS tracks / time series for a run (one row per run).
`recording_keys TEXT[]` + `recording_values NUMERIC[][]` (parallel arrays) +
`pause_indexes`.

### `laps`
Structured-workout intervals. `lap_type` enum
(`general`|`warmup`|`work`|`recovery`|`cooldown`), time- or distance-based.

### `sync_history`
Audit log of sync runs per source: timing, `sync_status`, counts
(`runs_fetched/inserted/updated/failed`), date range, `error_message`.

### `goals`
Yearly/monthly running goals **mirrored from SmashRun** (read-only cache).
`month IS NULL` = yearly, `1–12` = monthly; `goal_km`, `progress_km`,
`goal_text`, `fetched_at` (staleness control). Partial unique indexes enforce
one yearly and one monthly row per period. See `backend/goals.py`.

> Native, app-defined goals across metrics (weight, push-ups, lifting) are a
> separate planned subsystem — see `docs/GOALS_TRACKING.md`. This `goals` table
> stays the SmashRun mirror.

## Views & functions

- **Views:** `daily_summary`, `monthly_summary` — per-user aggregates
  (run count, total/avg km, pace, longest run).
- **RPC functions / stats:** `user_stats_function`, `user_running_stats`
  (later migrations) back the backend's `/stats/*` endpoints; subsequent
  migrations fix the metrics trigger, RPC timezones, and distance precision.
- **Triggers:** `update_updated_at_column` (audit), `compute_run_metrics`
  (denormalized dates + pace/speed on insert/update).

## Row-Level Security

RLS is enabled on user-data tables (`runs`, `splits`, `recording_data`, `laps`,
`user_sources`, `goals`). Current policies use
`USING (user_id = auth.uid() OR auth.uid() IS NULL)` — the `auth.uid() IS NULL`
escape exists so service-role jobs and the public status feed can read.

> **Planned tightening:** sensitive personal-tracking tables (body weight,
> etc. — see `docs/GOALS_TRACKING.md`) will use strict
> `USING (user_id = auth.uid())` with **no** anon escape. The escape stays
> scoped to the public running-streak surface only.

## Migrations

Schema changes are ordered SQL files in `supabase/migrations/`, applied by the
`supabase-migrations` GitHub Actions workflow on merge to `main`. Current set:

```
initial_schema · user_stats_function · add_token_columns · user_running_stats
fix_compute_run_metrics_trigger · fix_timezone_in_rpc_functions
increase_distance_precision · create_goals_table
```

## Reference

- [SmashRun API](https://api.smashrun.com/v1/documentation)
- [Supabase](https://supabase.com/docs) · [Pydantic](https://docs.pydantic.dev/)
