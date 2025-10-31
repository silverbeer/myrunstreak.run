-- MyRunStreak.com DuckDB Schema
-- Optimized for analytical queries on running data

-- =============================================================================
-- Main Runs Table
-- =============================================================================
-- Stores summary data for each run activity
-- Optimized for:
--   - Streak calculations (date-based queries)
--   - Distance and pace trend analysis
--   - Environmental condition correlations
--   - Time-based aggregations (daily, weekly, monthly, yearly)

CREATE TABLE IF NOT EXISTS runs (
    -- Primary Identifiers
    activity_id VARCHAR PRIMARY KEY,
    external_id VARCHAR,

    -- Temporal Data (indexed for fast date queries)
    start_date_time_local TIMESTAMP WITH TIME ZONE NOT NULL,
    start_date DATE NOT NULL,  -- Denormalized for fast date-based queries
    start_year INTEGER NOT NULL,
    start_month INTEGER NOT NULL,
    start_day_of_week INTEGER NOT NULL,  -- 0=Monday, 6=Sunday

    -- Core Metrics
    distance_km DOUBLE NOT NULL CHECK (distance_km > 0),
    duration_seconds INTEGER NOT NULL CHECK (duration_seconds > 0),

    -- Computed Performance Metrics (stored for fast queries)
    average_pace_min_per_km DOUBLE,  -- Computed: duration_minutes / distance_km
    average_speed_kph DOUBLE,        -- Computed: (distance_km / duration_seconds) * 3600

    -- Cadence Metrics
    cadence_average DOUBLE,
    cadence_min DOUBLE,
    cadence_max DOUBLE,

    -- Heart Rate Metrics
    heart_rate_average DOUBLE,
    heart_rate_min DOUBLE,
    heart_rate_max DOUBLE,

    -- Health & Subjective Data
    body_weight_kg DOUBLE,
    how_felt VARCHAR,  -- Unstoppable, great, soso, tired, injured

    -- Environmental Conditions
    terrain VARCHAR,  -- road, trail, track, treadmill, beach, snowpack
    temperature_celsius INTEGER,
    weather_type VARCHAR,  -- indoor, clear, cloudy, rain, storm, snow
    humidity_percent INTEGER CHECK (humidity_percent BETWEEN 0 AND 100),
    wind_speed_kph INTEGER,

    -- User Content
    notes VARCHAR(800),

    -- Metadata
    activity_type VARCHAR DEFAULT 'running',
    device_type VARCHAR,
    app_version VARCHAR,

    -- Recording Data Flags
    has_gps_data BOOLEAN DEFAULT FALSE,
    has_heart_rate_data BOOLEAN DEFAULT FALSE,
    has_cadence_data BOOLEAN DEFAULT FALSE,
    has_laps BOOLEAN DEFAULT FALSE,

    -- Audit Fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- Indexes for Query Optimization
-- =============================================================================

-- Date-based queries (streak calculations, time-based aggregations)
CREATE INDEX IF NOT EXISTS idx_runs_start_date
    ON runs(start_date DESC);

-- Year/Month aggregations
CREATE INDEX IF NOT EXISTS idx_runs_year_month
    ON runs(start_year, start_month);

-- External ID lookup for deduplication
CREATE INDEX IF NOT EXISTS idx_runs_external_id
    ON runs(external_id)
    WHERE external_id IS NOT NULL;

-- =============================================================================
-- Recording Data Table (Time Series)
-- =============================================================================
-- Stores detailed time series data for runs
-- Optional: Can be populated for detailed analysis, omitted for summary-only runs

CREATE TABLE IF NOT EXISTS recording_data (
    id INTEGER PRIMARY KEY,
    activity_id VARCHAR NOT NULL,

    -- Time series arrays stored as JSON for flexibility
    -- Arrays are parallel (same length, same index = same point in time)
    recording_keys VARCHAR[] NOT NULL,  -- e.g., ['clock', 'distance', 'latitude', 'longitude', 'heartRate']
    recording_values DOUBLE[][],        -- e.g., [[0.0, 100.2, ...], [0.0, 0.5, ...], ...]

    -- Pause information
    pause_indexes INTEGER[],

    FOREIGN KEY (activity_id) REFERENCES runs(activity_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_recording_data_activity_id
    ON recording_data(activity_id);

-- =============================================================================
-- Laps Table
-- =============================================================================
-- Stores lap segments for runs with structured interval training

CREATE TABLE IF NOT EXISTS laps (
    id INTEGER PRIMARY KEY,
    activity_id VARCHAR NOT NULL,
    lap_number INTEGER NOT NULL,  -- Sequential lap number within the run

    lap_type VARCHAR NOT NULL,  -- general, work, recovery, warmup, cooldown
    end_time_seconds DOUBLE,    -- For duration-based laps
    end_distance_meters DOUBLE, -- For distance-based laps

    FOREIGN KEY (activity_id) REFERENCES runs(activity_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_laps_activity_id
    ON laps(activity_id);

-- =============================================================================
-- Analytics Views
-- =============================================================================

-- Daily Summary View
CREATE OR REPLACE VIEW daily_summary AS
SELECT
    start_date,
    COUNT(*) as run_count,
    SUM(distance_km) as total_distance_km,
    SUM(duration_seconds) as total_duration_seconds,
    AVG(average_pace_min_per_km) as avg_pace_min_per_km,
    AVG(heart_rate_average) as avg_heart_rate,
    MIN(start_date_time_local) as first_run_time,
    MAX(start_date_time_local) as last_run_time
FROM runs
GROUP BY start_date
ORDER BY start_date DESC;

-- Monthly Summary View
CREATE OR REPLACE VIEW monthly_summary AS
SELECT
    start_year,
    start_month,
    COUNT(*) as run_count,
    SUM(distance_km) as total_distance_km,
    SUM(duration_seconds) as total_duration_seconds,
    AVG(average_pace_min_per_km) as avg_pace_min_per_km,
    AVG(distance_km) as avg_distance_km,
    MAX(distance_km) as longest_run_km
FROM runs
GROUP BY start_year, start_month
ORDER BY start_year DESC, start_month DESC;

-- Streak Calculation View (identifies consecutive running days)
CREATE OR REPLACE VIEW streak_analysis AS
WITH date_series AS (
    SELECT DISTINCT start_date
    FROM runs
    ORDER BY start_date
),
streak_groups AS (
    SELECT
        start_date,
        start_date - (ROW_NUMBER() OVER (ORDER BY start_date) * INTERVAL '1 day') as streak_group
    FROM date_series
)
SELECT
    MIN(start_date) as streak_start,
    MAX(start_date) as streak_end,
    COUNT(*) as streak_length_days
FROM streak_groups
GROUP BY streak_group
ORDER BY streak_length_days DESC;

-- =============================================================================
-- Imperial Unit Views (Miles, MPH)
-- =============================================================================
-- These views automatically convert all distances to miles for US users
-- The underlying data is stored in kilometers for consistency

-- Daily Summary (Miles)
CREATE OR REPLACE VIEW daily_summary_miles AS
SELECT
    start_date,
    COUNT(*) as run_count,
    SUM(distance_km * 0.621371) as total_distance_miles,
    SUM(duration_seconds) as total_duration_seconds,
    AVG(average_pace_min_per_km / 0.621371) as avg_pace_min_per_mile,
    AVG(average_speed_kph * 0.621371) as avg_speed_mph,
    AVG(heart_rate_average) as avg_heart_rate,
    MIN(start_date_time_local) as first_run_time,
    MAX(start_date_time_local) as last_run_time
FROM runs
GROUP BY start_date
ORDER BY start_date DESC;

-- Monthly Summary (Miles)
CREATE OR REPLACE VIEW monthly_summary_miles AS
SELECT
    start_year,
    start_month,
    COUNT(*) as run_count,
    SUM(distance_km * 0.621371) as total_distance_miles,
    SUM(duration_seconds) as total_duration_seconds,
    AVG(average_pace_min_per_km / 0.621371) as avg_pace_min_per_mile,
    AVG(average_speed_kph * 0.621371) as avg_speed_mph,
    AVG(distance_km * 0.621371) as avg_distance_miles,
    MAX(distance_km * 0.621371) as longest_run_miles
FROM runs
GROUP BY start_year, start_month
ORDER BY start_year DESC, start_month DESC;

-- Runs View (Miles) - All runs with imperial units
CREATE OR REPLACE VIEW runs_miles AS
SELECT
    activity_id,
    external_id,
    start_date_time_local,
    start_date,
    start_year,
    start_month,
    start_day_of_week,
    distance_km * 0.621371 as distance_miles,
    duration_seconds,
    average_pace_min_per_km / 0.621371 as average_pace_min_per_mile,
    average_speed_kph * 0.621371 as average_speed_mph,
    cadence_average,
    cadence_min,
    cadence_max,
    heart_rate_average,
    heart_rate_min,
    heart_rate_max,
    body_weight_kg * 2.20462 as body_weight_lbs,
    how_felt,
    terrain,
    temperature_celsius,
    (temperature_celsius * 9.0 / 5.0) + 32 as temperature_fahrenheit,
    weather_type,
    humidity_percent,
    wind_speed_kph * 0.621371 as wind_speed_mph,
    notes,
    activity_type,
    device_type,
    app_version,
    has_gps_data,
    has_heart_rate_data,
    has_cadence_data,
    has_laps,
    created_at,
    updated_at,
    synced_at
FROM runs;

-- =============================================================================
-- Schema Metadata
-- =============================================================================

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description VARCHAR
);

INSERT INTO schema_version (version, description)
VALUES (1, 'Initial schema with runs, recording_data, and laps tables');
