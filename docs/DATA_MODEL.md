# MyRunStreak.com Data Model & Schema

This document describes the data model and database schema design for MyRunStreak.com.

## Overview

The data model is designed to support:
1. **Efficient ingestion** of running data from SmashRun API
2. **Fast analytical queries** for streak calculations, trends, and aggregations
3. **Type safety** using Pydantic models for validation
4. **Flexibility** for future data source integrations (Garmin, Strava, etc.)

## Architecture

```
SmashRun API → Pydantic Models → DuckDB Tables → Analytics Views
```

### Why This Stack?

- **Pydantic**: Type-safe data validation, serialization, and documentation
- **DuckDB**: Optimized for analytical queries, lightweight, S3-compatible
- **S3 Storage**: Serverless, durable, cost-effective for analytical workloads

## Pydantic Models

Location: `src/shared/models/`

### Core Models

#### `Activity` (activity.py)

Represents a complete running activity with summary metrics and optional time series data.

**Key Features:**
- Strict type validation using Pydantic v2
- Automatic conversion of camelCase API fields to snake_case Python fields
- Computed properties for pace and speed
- Custom validators to ensure data consistency

**Required Fields:**
- `activity_id`: Unique identifier
- `start_date_time_local`: Run timestamp with timezone
- `distance`: Total distance in kilometers
- `duration`: Total duration in seconds (excluding pauses)

**Optional Performance Metrics:**
- Cadence (average, min, max)
- Heart rate (average, min, max)
- Body weight, subjective feeling

**Environmental Data:**
- Terrain type (road, trail, track, etc.)
- Weather conditions (temperature, weather type, humidity, wind)

**Time Series Data:**
- `recording_keys`: Array of metric names
- `recording_values`: 2D array of time series values
- Supports: GPS coordinates, elevation, heart rate, cadence, power, etc.

#### `Lap` (nested.py)

Represents interval segments within a run.

**Types:** general, work, recovery, warmup, cooldown

#### `Song` (nested.py)

Music played during the run (if available from device).

#### `HeartRateRecovery` (nested.py)

Post-run heart rate recovery measurements.

### Enums (enums.py)

Type-safe enumerations for categorical data:
- `ActivityType`: Currently only "running"
- `HowFelt`: Subjective feeling (Unstoppable, great, soso, tired, injured)
- `Terrain`: Surface type (road, trail, track, treadmill, beach, snowpack)
- `WeatherType`: Conditions (indoor, clear, cloudy, rain, storm, snow)
- `DeviceType`: Recording platform
- `LapType`: Interval segment type

## DuckDB Schema

Location: `src/shared/duckdb_ops/schema.sql`

### Design Principles

1. **Denormalization for Performance**
   - Store computed metrics (pace, speed) to avoid recalculation
   - Extract date components (year, month, day_of_week) for fast grouping

2. **Indexing Strategy**
   - Primary index on `start_date` (DESC) for recent runs and streak queries
   - Composite index on `(start_year, start_month)` for monthly aggregations
   - Index on `external_id` for deduplication

3. **Data Types**
   - `TIMESTAMP WITH TIME ZONE` for accurate temporal data
   - `DOUBLE` for floating-point metrics
   - `INTEGER` for discrete values (duration, humidity, etc.)
   - `VARCHAR` for text and enums

### Table Structure

#### `runs` Table

Primary table storing run summary data.

**Temporal Fields:**
```sql
start_date_time_local TIMESTAMP WITH TIME ZONE NOT NULL
start_date DATE NOT NULL                  -- Denormalized for fast queries
start_year INTEGER NOT NULL
start_month INTEGER NOT NULL
start_day_of_week INTEGER NOT NULL        -- 0=Monday, 6=Sunday
```

**Core Metrics:**
```sql
distance_km DOUBLE NOT NULL CHECK (distance_km > 0)
duration_seconds INTEGER NOT NULL CHECK (duration_seconds > 0)
average_pace_min_per_km DOUBLE           -- Computed and stored
average_speed_kph DOUBLE                 -- Computed and stored
```

**Performance Metrics:**
- Cadence (average, min, max)
- Heart rate (average, min, max)

**Environmental:**
- Body weight, subjective feeling
- Terrain, temperature, weather, humidity, wind speed

**Metadata:**
- Activity type, device type, app version
- Boolean flags for data availability (GPS, HR, cadence, laps)

**Audit:**
- `created_at`, `updated_at`, `synced_at`

#### `recording_data` Table

Stores time series data for detailed analysis.

**Structure:**
```sql
activity_id VARCHAR NOT NULL (FK to runs)
recording_keys VARCHAR[]      -- e.g., ['clock', 'distance', 'heartRate']
recording_values DOUBLE[][]   -- Parallel arrays of metric values
pause_indexes INTEGER[]       -- Indexes where pauses occurred
```

**Note:** This table is optional - summary-only runs don't need time series data.

#### `laps` Table

Stores structured interval training segments.

```sql
activity_id VARCHAR NOT NULL (FK to runs)
lap_number INTEGER NOT NULL
lap_type VARCHAR NOT NULL
end_time_seconds DOUBLE
end_distance_meters DOUBLE
```

### Analytics Views

Pre-computed views for common queries:

#### `daily_summary`
Aggregates all runs by date:
- Total distance, duration, run count
- Average pace and heart rate
- First and last run times

#### `monthly_summary`
Aggregates runs by year/month:
- Total distance, duration, run count
- Average metrics
- Longest run

#### `streak_analysis`
Identifies consecutive running streaks:
- Uses window functions to detect gaps
- Returns streak start/end dates and length
- Ordered by longest streaks

## Query Patterns

### Streak Calculation

```sql
WITH date_series AS (
    SELECT DISTINCT start_date FROM runs
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
```

**How it works:**
1. Get all distinct run dates
2. Calculate row numbers in date order
3. Subtract row number from date to create "streak groups"
4. Consecutive dates will have the same streak group
5. Group by streak group and count days

### Current Streak

```sql
WITH RECURSIVE date_check AS (
    SELECT CURRENT_DATE as check_date, 0 as days_back
    UNION ALL
    SELECT
        check_date - INTERVAL '1 day',
        days_back + 1
    FROM date_check
    WHERE
        days_back < 365
        AND EXISTS (SELECT 1 FROM runs WHERE start_date = check_date - INTERVAL '1 day')
)
SELECT MAX(days_back) as current_streak
FROM date_check
WHERE EXISTS (SELECT 1 FROM runs WHERE start_date = check_date);
```

**How it works:**
1. Start from today
2. Recursively check previous days
3. Stop when a day without a run is found
4. Return the maximum days back count

### Distance Trends

```sql
SELECT
    start_year,
    start_month,
    SUM(distance_km) as total_distance,
    AVG(distance_km) as avg_distance,
    COUNT(*) as run_count
FROM runs
GROUP BY start_year, start_month
ORDER BY start_year DESC, start_month DESC;
```

### Personal Records

```sql
-- Longest run
SELECT * FROM runs ORDER BY distance_km DESC LIMIT 1;

-- Fastest pace
SELECT * FROM runs ORDER BY average_pace_min_per_km ASC LIMIT 1;

-- Most runs in a day
SELECT start_date, COUNT(*) as runs
FROM runs
GROUP BY start_date
ORDER BY runs DESC
LIMIT 1;
```

## Repository Pattern

Location: `src/shared/duckdb_ops/repository.py`

The `RunRepository` class provides CRUD operations:

- `insert_run(activity)`: Insert new run
- `upsert_run(activity)`: Insert or update run
- `update_run(activity)`: Update existing run
- `get_run_by_id(activity_id)`: Fetch by ID
- `get_runs_by_date_range(start, end)`: Range query
- `get_latest_run()`: Most recent run
- `get_total_runs()`: Count all runs
- `get_current_streak()`: Calculate current streak

## Database Manager

Location: `src/shared/duckdb_ops/database.py`

The `DuckDBManager` class handles:
- Connection management (local or S3)
- Schema initialization
- S3 extension configuration for cloud storage
- Transaction management
- Context manager support (`with` statement)

## Data Flow

### Ingestion Flow

```
SmashRun API
    ↓ (OAuth authenticated request)
JSON Response
    ↓ (Pydantic validation)
Activity Model
    ↓ (RunRepository.upsert_run)
DuckDB on S3
```

### Query Flow

```
API Gateway Request
    ↓ (Lambda function)
RunRepository Query
    ↓ (DuckDB query execution)
Results
    ↓ (JSON serialization)
API Response
```

## Schema Versioning

The `schema_version` table tracks schema migrations:

```sql
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description VARCHAR
);
```

**Current Version:** 1

**Migration Strategy:**
1. Create new migration SQL file: `migrations/v{N}.sql`
2. Update `schema_version` table
3. Apply migration via `DuckDBManager.execute_script()`
4. Test with existing data

## Testing Strategy

### Unit Tests
- Pydantic model validation
- Repository CRUD operations
- Query correctness

### Integration Tests
- End-to-end data flow
- S3 database operations
- Schema migrations

### Test Data
- Use factory pattern for generating test Activities
- Mock SmashRun API responses
- Isolated test database instances

## Future Enhancements

### Planned Features

1. **Additional Metrics**
   - Running power (Stryd)
   - Elevation gain/loss
   - Training load/stress scores

2. **Multi-Sport Support**
   - Cycling, swimming, etc.
   - Sport-specific metrics

3. **Advanced Analytics**
   - Heart rate zones
   - Training effect
   - Recovery metrics
   - Weather correlations

4. **Data Sources**
   - Garmin Connect
   - Strava
   - Apple Health
   - Fitbit

### Schema Evolution

Future schema changes will:
1. Maintain backward compatibility
2. Use migrations for structural changes
3. Version all schema changes
4. Document breaking changes

## Performance Considerations

### Query Optimization

- **Use indexes**: All date-based queries use indexed columns
- **Denormalize**: Store computed values (pace, speed) to avoid recalculation
- **Partition by date**: Future enhancement for very large datasets
- **Materialize views**: Consider materializing analytics views for large datasets

### S3 Considerations

- **Caching**: Lambda can cache database file temporarily
- **Compression**: DuckDB compresses data efficiently
- **Incremental updates**: Only sync changed data
- **Read replicas**: Use separate databases for read-heavy operations

## References

- [SmashRun API Documentation](https://api.smashrun.com/v1/documentation)
- [DuckDB Documentation](https://duckdb.org/docs/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
