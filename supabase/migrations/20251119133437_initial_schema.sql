-- =====================================================
-- MyRunStreak.com - Multi-User, Multi-Source Database Schema
-- =====================================================
-- Migration: Initial schema for Supabase PostgreSQL
-- Replaces: Single-user DuckDB implementation
--
-- Key Features:
-- - Multi-user support with user_id partitioning
-- - Multi-source ready (SmashRun, Strava, etc.)
-- - Row Level Security (RLS) for data isolation
-- - Computed fields via triggers
-- - Indexes for query performance
-- =====================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- USERS & AUTHENTICATION
-- =====================================================

CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE,
    display_name VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);

COMMENT ON TABLE users IS 'Runner accounts - one row per MyRunStreak user';
COMMENT ON COLUMN users.email IS 'Optional for now, will be required when proper auth is added';

-- =====================================================
-- DATA SOURCES & OAUTH
-- =====================================================

CREATE TYPE source_type AS ENUM ('smashrun', 'strava', 'garmin', 'other');

CREATE TABLE user_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    source_type source_type NOT NULL,

    -- OAuth credentials (reference to AWS Secrets Manager)
    access_token_secret VARCHAR(255),

    -- Source-specific user info
    source_user_id VARCHAR(100),
    source_username VARCHAR(100),

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_sync_at TIMESTAMPTZ,
    last_sync_status VARCHAR(50),

    -- Audit
    connected_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, source_type)
);

CREATE INDEX idx_user_sources_user_id ON user_sources(user_id);
CREATE INDEX idx_user_sources_active ON user_sources(user_id, is_active);

COMMENT ON TABLE user_sources IS 'OAuth connections to running data sources';
COMMENT ON COLUMN user_sources.access_token_secret IS 'AWS Secrets Manager path: myrunstreak/users/{user_id}/sources/{source_type}/tokens';

-- =====================================================
-- RUNS/ACTIVITIES (Core Data)
-- =====================================================

CREATE TYPE activity_type AS ENUM ('running', 'walking', 'cycling', 'other');
CREATE TYPE how_felt AS ENUM ('unstoppable', 'great', 'soso', 'tired', 'injured');
CREATE TYPE terrain AS ENUM ('road', 'trail', 'track', 'treadmill', 'beach', 'snowpack');
CREATE TYPE weather_type AS ENUM ('sunny', 'cloudy', 'rainy', 'snowy', 'windy', 'hot', 'cold');
CREATE TYPE device_type AS ENUM ('apple', 'google', 'garmin', 'other');

CREATE TABLE runs (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Foreign Keys
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES user_sources(id) ON DELETE CASCADE,

    -- Source Identity (for deduplication)
    source_activity_id VARCHAR(100) NOT NULL,
    external_id VARCHAR(255),

    -- Temporal Data
    start_date_time_local TIMESTAMPTZ NOT NULL,
    start_date DATE NOT NULL,
    start_year INTEGER NOT NULL,
    start_month INTEGER NOT NULL,
    start_day_of_week INTEGER NOT NULL,
    timezone VARCHAR(50),

    -- Core Metrics (stored in metric units)
    distance_km NUMERIC(10, 3) NOT NULL CHECK (distance_km > 0),
    duration_seconds NUMERIC(10, 2) NOT NULL CHECK (duration_seconds > 0),

    -- Computed Performance (denormalized for query speed)
    average_pace_min_per_km NUMERIC(6, 2),
    average_speed_kph NUMERIC(6, 2),

    -- Cadence Metrics
    cadence_average NUMERIC(6, 2),
    cadence_min NUMERIC(6, 2),
    cadence_max NUMERIC(6, 2),

    -- Heart Rate Metrics
    heart_rate_average INTEGER,
    heart_rate_min INTEGER,
    heart_rate_max INTEGER,

    -- Health & Subjective Data
    body_weight_kg NUMERIC(5, 2),
    how_felt how_felt,

    -- Environmental Conditions
    terrain terrain,
    temperature_celsius NUMERIC(5, 2),
    weather_type weather_type,
    humidity_percent INTEGER CHECK (humidity_percent BETWEEN 0 AND 100),
    wind_speed_kph INTEGER,

    -- User Content
    notes TEXT CHECK (LENGTH(notes) <= 800),

    -- Metadata
    activity_type activity_type DEFAULT 'running',
    device_type device_type,
    app_version VARCHAR(50),

    -- Data Availability Flags
    has_gps_data BOOLEAN DEFAULT FALSE,
    has_heart_rate_data BOOLEAN DEFAULT FALSE,
    has_cadence_data BOOLEAN DEFAULT FALSE,
    has_splits BOOLEAN DEFAULT FALSE,
    has_laps BOOLEAN DEFAULT FALSE,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    synced_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    UNIQUE(user_id, source_id, source_activity_id)
);

-- Indexes for common queries
CREATE INDEX idx_runs_user_id ON runs(user_id);
CREATE INDEX idx_runs_user_date ON runs(user_id, start_date DESC);
CREATE INDEX idx_runs_user_year_month ON runs(user_id, start_year, start_month);
CREATE INDEX idx_runs_source ON runs(source_id);

COMMENT ON TABLE runs IS 'Running activities from all sources';
COMMENT ON COLUMN runs.source_activity_id IS 'Unique ID from source API (SmashRun activityId, Strava id, etc.)';

-- =====================================================
-- SPLITS (Per-Mile/KM Performance)
-- =====================================================

CREATE TABLE splits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,

    -- Split Identification
    split_number INTEGER NOT NULL,
    split_unit VARCHAR(2) NOT NULL CHECK (split_unit IN ('mi', 'km')),

    -- Cumulative Metrics (from API)
    cumulative_distance_km NUMERIC(10, 3) NOT NULL,
    cumulative_seconds NUMERIC(10, 2) NOT NULL,

    -- Performance Metrics
    speed_kph NUMERIC(6, 2),
    pace_min_per_km NUMERIC(6, 2),
    heart_rate INTEGER,

    -- Elevation
    cumulative_elevation_gain_meters NUMERIC(8, 2),
    cumulative_elevation_loss_meters NUMERIC(8, 2),

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(run_id, split_unit, split_number)
);

CREATE INDEX idx_splits_run_id ON splits(run_id);

COMMENT ON TABLE splits IS 'Per-mile or per-km splits for runs';

-- =====================================================
-- RECORDING DATA (GPS Tracks, Time Series)
-- =====================================================

CREATE TABLE recording_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID NOT NULL UNIQUE REFERENCES runs(id) ON DELETE CASCADE,

    -- Time series data (stored as PostgreSQL arrays)
    recording_keys TEXT[],
    recording_values NUMERIC[][],

    -- Pause information
    pause_indexes INTEGER[],

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_recording_data_run_id ON recording_data(run_id);

COMMENT ON TABLE recording_data IS 'GPS tracks and time-series sensor data';
COMMENT ON COLUMN recording_data.recording_values IS '2D array where recording_values[i] corresponds to recording_keys[i]';

-- =====================================================
-- LAPS (Interval Training)
-- =====================================================

CREATE TYPE lap_type AS ENUM ('general', 'warmup', 'work', 'recovery', 'cooldown');

CREATE TABLE laps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,

    lap_number INTEGER NOT NULL,
    lap_type lap_type NOT NULL DEFAULT 'general',

    -- Lap can be time-based OR distance-based
    end_time_seconds NUMERIC(10, 2),
    end_distance_meters NUMERIC(10, 2),

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(run_id, lap_number)
);

CREATE INDEX idx_laps_run_id ON laps(run_id);

COMMENT ON TABLE laps IS 'Lap/interval data for structured workouts';

-- =====================================================
-- SYNC STATE (Track last successful sync per source)
-- =====================================================

CREATE TABLE sync_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID NOT NULL REFERENCES user_sources(id) ON DELETE CASCADE,

    -- Sync execution
    sync_started_at TIMESTAMPTZ NOT NULL,
    sync_completed_at TIMESTAMPTZ,
    sync_status VARCHAR(50) NOT NULL,

    -- Results
    runs_fetched INTEGER DEFAULT 0,
    runs_inserted INTEGER DEFAULT 0,
    runs_updated INTEGER DEFAULT 0,
    runs_failed INTEGER DEFAULT 0,

    -- Date range synced
    date_from DATE,
    date_to DATE,

    -- Error details
    error_message TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sync_history_source ON sync_history(source_id, sync_started_at DESC);

COMMENT ON TABLE sync_history IS 'Audit log of all sync operations';

-- =====================================================
-- ROW LEVEL SECURITY (RLS)
-- =====================================================

-- Enable RLS on all user data tables
ALTER TABLE runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE splits ENABLE ROW LEVEL SECURITY;
ALTER TABLE recording_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE laps ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_sources ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own data
-- Note: auth.uid() will be NULL until proper Supabase Auth is implemented
-- For now, service role (Lambda) bypasses RLS

CREATE POLICY "Users can view their own runs"
    ON runs FOR SELECT
    USING (user_id = auth.uid() OR auth.uid() IS NULL);

CREATE POLICY "Users can insert their own runs"
    ON runs FOR INSERT
    WITH CHECK (user_id = auth.uid() OR auth.uid() IS NULL);

CREATE POLICY "Users can update their own runs"
    ON runs FOR UPDATE
    USING (user_id = auth.uid() OR auth.uid() IS NULL);

CREATE POLICY "Users can view their own splits"
    ON splits FOR SELECT
    USING (run_id IN (SELECT id FROM runs WHERE user_id = auth.uid() OR auth.uid() IS NULL));

CREATE POLICY "Users can view their own user_sources"
    ON user_sources FOR SELECT
    USING (user_id = auth.uid() OR auth.uid() IS NULL);

-- =====================================================
-- FUNCTIONS & TRIGGERS
-- =====================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_runs_updated_at BEFORE UPDATE ON runs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_sources_updated_at BEFORE UPDATE ON user_sources
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Auto-populate computed fields in runs
CREATE OR REPLACE FUNCTION compute_run_metrics()
RETURNS TRIGGER AS $$
BEGIN
    -- Compute derived date fields
    NEW.start_date := DATE(NEW.start_date_time_local);
    NEW.start_year := EXTRACT(YEAR FROM NEW.start_date_time_local);
    NEW.start_month := EXTRACT(MONTH FROM NEW.start_date_time_local);
    NEW.start_day_of_week := EXTRACT(ISODOW FROM NEW.start_date_time_local) - 1;

    -- Compute pace and speed
    IF NEW.duration_seconds > 0 AND NEW.distance_km > 0 THEN
        NEW.average_pace_min_per_km := NEW.duration_seconds / 60.0 / NEW.distance_km;
        NEW.average_speed_kph := NEW.distance_km / (NEW.duration_seconds / 3600.0);
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER compute_run_metrics_trigger BEFORE INSERT OR UPDATE ON runs
    FOR EACH ROW EXECUTE FUNCTION compute_run_metrics();

-- =====================================================
-- VIEWS FOR ANALYTICS
-- =====================================================

-- Daily summary per user
CREATE VIEW daily_summary AS
SELECT
    user_id,
    start_date,
    COUNT(*) AS run_count,
    SUM(distance_km) AS total_km,
    AVG(distance_km) AS avg_km,
    AVG(average_pace_min_per_km) AS avg_pace,
    MIN(start_date_time_local) AS first_run,
    MAX(start_date_time_local) AS last_run
FROM runs
GROUP BY user_id, start_date
ORDER BY user_id, start_date DESC;

-- Monthly summary per user
CREATE VIEW monthly_summary AS
SELECT
    user_id,
    start_year,
    start_month,
    TO_DATE(start_year || '-' || start_month || '-01', 'YYYY-MM-DD') AS month_start,
    COUNT(*) AS run_count,
    SUM(distance_km) AS total_km,
    AVG(distance_km) AS avg_km,
    MAX(distance_km) AS longest_run_km,
    AVG(average_pace_min_per_km) AS avg_pace
FROM runs
GROUP BY user_id, start_year, start_month
ORDER BY user_id, start_year DESC, start_month DESC;

COMMENT ON VIEW daily_summary IS 'Daily statistics per user';
COMMENT ON VIEW monthly_summary IS 'Monthly statistics per user';

-- =====================================================
-- SEED DATA (Development/Testing)
-- =====================================================

-- Create a test user for development
INSERT INTO users (user_id, email, display_name) VALUES
    ('00000000-0000-0000-0000-000000000001', 'test@myrunstreak.com', 'Test Runner');

-- Create SmashRun source for test user
INSERT INTO user_sources (user_id, source_type, source_user_id, access_token_secret) VALUES
    ('00000000-0000-0000-0000-000000000001', 'smashrun', 'test_smashrun_user', 'myrunstreak/users/00000000-0000-0000-0000-000000000001/sources/smashrun/tokens');

COMMENT ON TABLE users IS 'Seed data: Test user for local development';
