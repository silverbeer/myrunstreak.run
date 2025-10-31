# Unit System: Miles by Default

MyRunStreak.com stores data in kilometers (international standard) but **displays everything in miles by default**. You'll never see kilometers unless you specifically want to.

## 🎯 The Simple Truth

**You ran 6.2 miles → You see 6.2 miles → Everything is in miles**

No conversion math. No thinking about kilometers. Just miles.

## How It Works

### 1. Data Storage (Behind the Scenes)
```python
# SmashRun API gives us: 10 kilometers
# We store: 10 kilometers in the database
# This is the "source of truth" - never changed
```

### 2. What You See (Everywhere)
```python
# API returns
{
  "distance": 6.21,        # miles
  "pace": "8:23 /mi",      # minutes per mile
  "speed": 7.15            # mph
}

# Database views automatically convert
SELECT * FROM runs_miles;            # All distances in miles
SELECT * FROM daily_summary_miles;   # Daily totals in miles
SELECT * FROM monthly_summary_miles; # Monthly totals in miles
```

### 3. Python Models (Automatic)
```python
from src.shared.models import Activity

# Create activity (SmashRun gives km)
activity = Activity(
    activityId="run-123",
    startDateTimeLocal=datetime.now(),
    distance=10.0,  # kilometers (from API)
    duration=3600
)

# Access as miles (automatic conversion)
print(activity.distance_miles)           # 6.21 miles
print(activity.average_pace_min_per_mile)  # 9.656 min/mile
print(activity.average_speed_mph)        # 6.21 mph

# Metric properties still available if needed
print(activity.distance)                 # 10.0 km (original)
print(activity.average_pace_min_per_km)  # 6.0 min/km
```

## 📊 Examples: What You'll See

### Example 1: Single Run
```python
# You ran 6.2 miles in 52 minutes

# API Response (JSON)
{
  "activity_id": "run-456",
  "distance_miles": 6.2,
  "duration_seconds": 3120,
  "pace_per_mile": "8:23 /mi",
  "speed_mph": 7.15,
  "date": "2024-10-30"
}
```

### Example 2: Daily Summary
```sql
-- SQL Query (using miles view)
SELECT * FROM daily_summary_miles
WHERE start_date = '2024-10-30';

-- Result
start_date    | total_distance_miles | avg_pace_min_per_mile | run_count
2024-10-30    | 6.21                | 8.38                  | 1
```

### Example 3: Current Streak
```json
{
  "current_streak_days": 47,
  "total_distance_miles": 327.4,
  "avg_distance_per_run_miles": 6.97,
  "longest_run_miles": 13.1
}
```

### Example 4: Monthly Stats
```json
{
  "month": "October 2024",
  "total_runs": 23,
  "total_distance_miles": 143.2,
  "avg_pace_per_mile": "8:32 /mi",
  "longest_run_miles": 13.1,
  "avg_distance_per_run": 6.23
}
```

## 🔧 Technical Details (If You're Curious)

### Conversion Constants
- **1 kilometer = 0.621371 miles**
- **1 mile = 1.609344 kilometers**

### Where Conversion Happens

#### 1. Pydantic Models
```python
class Activity(BaseModel):
    distance: float  # Stored in km

    @property
    def distance_miles(self) -> float:
        """Automatic conversion to miles"""
        return self.distance * 0.621371
```

#### 2. DuckDB Views
```sql
CREATE VIEW runs_miles AS
SELECT
    activity_id,
    distance_km * 0.621371 as distance_miles,
    average_pace_min_per_km / 0.621371 as average_pace_min_per_mile,
    average_speed_kph * 0.621371 as average_speed_mph,
    ...
FROM runs;
```

#### 3. API Layer (Future)
```python
# Lambda function automatically uses imperial views
def get_run_summary():
    # Queries runs_miles view by default
    result = db.execute("SELECT * FROM runs_miles")
    return result  # Already in miles!
```

## 🌍 Supporting Future Users (Metric System)

If you ever want to support other users who prefer kilometers:

### Option 1: User Preference
```python
class UserPreferences:
    unit_system: UnitSystem = UnitSystem.IMPERIAL  # Your default

# Other users could set:
preferences.unit_system = UnitSystem.METRIC
```

### Option 2: Query Parameter
```
GET /api/runs?units=imperial  # Your default
GET /api/runs?units=metric    # For metric users
```

### Option 3: Multiple Views
```sql
-- You use:
SELECT * FROM runs_miles;

-- Metric users use:
SELECT * FROM runs;  -- Original km data
```

**The beauty:** It's already built in! Adding metric support is trivial because we store km as the source of truth.

## 📈 Complexity Rating

**For You (US Runner):**
- Complexity: **0/10** (You never think about it)
- Everything is miles, always

**For Future Multi-User Support:**
- Complexity: **2/10** (Add user preference, use existing views)
- All the hard work is done

## ❓ FAQ

### Do I ever need to convert manually?
**No.** Just use the `_miles` properties and views.

### What if SmashRun gives me bad data?
The data flows through Pydantic validation first, so invalid values are caught before storage.

### Can I see kilometers if I want?
Yes! Use the original properties:
- `activity.distance` (km)
- `activity.average_pace_min_per_km`
- Or query the `runs` table directly

### What about weight (kg vs lbs)?
Also converted! The `runs_miles` view includes:
- `body_weight_lbs` (from kg)

### What about temperature (C vs F)?
Yes! The view converts:
- `temperature_fahrenheit` (from Celsius)

### What about wind speed?
Yep!
- `wind_speed_mph` (from kph)

## 🎨 The Goal: Invisible Complexity

**You think:** "I ran 10 miles today"

**The system:**
1. Receives data in km from SmashRun
2. Validates and stores in km
3. Converts to miles when you query
4. Returns "10.0 miles" to you

**You see:** "10 miles" ✅

**You never see:** "16.09 kilometers" ❌

## 🏃 Summary

| Aspect | What You See | What's Stored | Complexity |
|--------|-------------|---------------|------------|
| Distance | 6.2 miles | 10 km | Zero |
| Pace | 8:23 /mi | 5:12 /km | Zero |
| Speed | 7.15 mph | 11.5 kph | Zero |
| Weight | 154 lbs | 70 kg | Zero |
| Temperature | 59°F | 15°C | Zero |

**Bottom line:** Everything you interact with is in miles. The conversion is automatic and invisible.
