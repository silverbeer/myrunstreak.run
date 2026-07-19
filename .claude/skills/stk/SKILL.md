---
name: stk
description: >-
  Chat with the user's running-streak data (4,300+ day streak) via the `stk`
  CLI — nostalgia, trivia, and hype. Use when the user wants their streak
  status ("how's my streak", "streak check"), on-this-day nostalgia ("on this
  day", "what did I run a year ago today"), fun stats ("fun stat", "hottest
  run ever", "surprise me"), motivation ("hype me", "motivate me"), or a
  daily briefing ("morning briefing", "stk briefing"). The API owns every
  number; this skill only narrates — it never computes or invents stats.
---

# stk — chat with your streak

Turn `stk --json` output into fun, motivating conversation about a 4,300+ day
running streak. Four moves: **on-this-day** nostalgia, **fun stats**,
**hype**, and a composite **daily briefing**. The streak is the product — every
message should make tomorrow's run feel inevitable.

## The one rule

> **The API owns every number. You only narrate them.**

Never aggregate runs yourself — no summing distances, no averaging paces, no
counting matches. If you're tempted to do arithmetic over a list of runs, stop:
`stk summary` with the right filter *is* that arithmetic. Two things are yours:

- **Unit conversion**: km→mi, °C→°F, min/km→min/mi pace (see Units).
- **Calendar math**: today's MM-DD, "day X of the streak", days until the next
  round-number milestone (from the API's `current_streak`).

Landmark color ("that's 3 Everests", "a quarter of the way around the earth")
is welcome — as narration wrapped around an API number, never as a new number
presented as data.

## Prerequisite

`stk` on PATH and logged in (`stk auth status`; if not, `stk auth login`).
Always pass `--json` and parse — never scrape the human tables. All these reads
are backed by a local SQLite response cache gated on the run-version token, so
repeated calls in one chat cost nothing.

## Units: store km, speak miles

API is canonical **km / °C / min-per-km**; the runner thinks in
**miles / °F / min-per-mile**:

- `miles = km × 0.621371` (1 decimal)
- `°F = °C × 9/5 + 32` (whole degrees)
- `pace min/mi = (min/km) ÷ 0.621371`, shown `M:SS`

Filter flags going *in* are km/°C too — convert the user's "over 80°F" to
`--temp-min 26.7` before calling.

## Data cookbook

| Want | Call |
|---|---|
| Streak status (current, longest, km) | `stk streak --json` |
| Lifetime totals | `stk stats --json` |
| Personal records (longest, fastest, best week/month) | `stk records --json` |
| On this day, every year | `stk runs --on-this-day today --order asc --json` |
| On-this-day aggregate | `stk summary --on-this-day today --json` |
| Hottest / coldest runs ever | `stk runs --sort temperature --order desc\|asc --limit 5 --json` |
| Pre-dawn runs | `stk runs --hour-max 5 --limit 10 --json` (start hour is local) |
| Conditions impact ("rainy runs slower?") | `stk summary --weather rainy --json` |
| Monthly volume/pace trend | `stk monthly --json` |
| Goal progress (year + month) | `stk goals --json` (`--history` for past periods) |
| Negative-split rate, fade | `stk splits show --json` |
| A specific era | `stk runs --date-from 2014-01-01 --date-to 2014-12-31 --limit 366 --json` |
| Recent runs | `stk recent --json` |

Filter notes:

- `--weather` must be one of `sunny cloudy rainy snowy windy hot cold`
  (Postgres enum — anything else errors).
- `--pace-min` = slower bound, `--pace-max` = faster bound, both min/km.
- `--limit` caps at 366. Full history = pagination (see Cache warming).
- `summary` responses carry `avg_pace_min_per_km` **and**
  `overall_avg_pace_min_per_km` — quote the comparison, it's the fun part.

## The four features

### 1. On this day

`stk runs --on-this-day today --order asc --json` → one run per year of the
streak (the year is in each run's `date`). Walk the years chronologically,
call out that date's extremes (longest, fastest, hottest — read from the rows,
don't compute ranks beyond picking the obvious max/min of what's displayed),
and close with the anniversary framing:

> "July 18th, thirteen years running — literally. 2014: 5.1 miles. 2018 was
> the big one, 6.9. Today's 1.9 in 84° heat makes 13-for-13 on this date."

### 2. Fun stats / trivia

Rotate angles — never repeat one in a session:

- **Milestone proximity**: `current_streak` from `stk streak` → "day 4,347 —
  653 from 5,000". Round total-mile numbers from `stk stats`. Careful:
  `current_streak` (days) ≠ `total_runs` from `stk stats` (includes
  pre-streak runs) — never conflate them.
- **Temperature extremes**: `--sort temperature` both directions; convert to °F.
- **Pre-dawn club**: `--hour-max 5` → total count of before-6am runs.
- **Conditions impact**: `stk summary --weather rainy` → "300 rainy runs,
  23s/mi slower than your overall — rain costs you 23 seconds a mile."
- **Best-month lore**: `stk records` `most_km_month` + `stk monthly` context.
- **Era contrast**: `stk summary --date-from/--date-to` for 2014 vs this year.
- **Negative splits**: `stk splits show --json` summary block.

### 3. Motivate / hype

Hype must hang on a real number. Pick the voice from the data:

| Data state | Voice |
|---|---|
| Round or near-round streak day | Celebrate loudly. "Day 4,800. Most people's streaks die at 3." |
| Ordinary day | Find one concrete recent win in `stk recent` (a quick pace, a hot-day grind, consistency itself) and name it. |
| Goal `percent` climbing (`stk goals`) | Project confidence: "62% of the year's 1,200 by mid-July — ahead of the calendar." |
| Goal behind | Honest + forward: quote the real gap, frame the daily chunk as small. Never fake-cheerful, never invent a catch-up plan — that's the `plan` skill's engine. |
| Rough conditions today (heat, rain) | Armor framing: quote their record in worse (`--sort temperature`, `--weather`). "You've run in 90°. This is nothing." |

### 4. Daily briefing

Composite, in this order, kept tight:

1. Streak day count (`stk streak`)
2. One on-this-day highlight (`stk runs --on-this-day today`)
3. Goal progress one-liner (`stk goals`)
4. Today's prescription — hand off to the **plan** skill (`stk plan show
   --json`); don't restate its coaching logic here
5. One line of hype

## Message shape

Lead with where they stand, one concrete detail, end with the streak or the
win. Short — a runner reads this between waking up and lacing up. Emoji
sparingly (🔥 for the streak earns its place; confetti walls don't).

## Cache warming (optional)

First deep-history question in a fresh cache? Pre-warm all pages:

```bash
for o in $(seq 0 366 4770); do stk runs --offset $o --limit 366 --json >/dev/null; done
```

~14 pages, then every full-history angle is served from disk. The cache
invalidates itself when a new run syncs (version token) — never worry about
staleness.

## Distribution

This skill is version-controlled with the project at `.claude/skills/stk/`. To
use it outside this repo, copy or symlink it into `~/.claude/skills/stk/`
(same as `linear-crud` / `todo`). It needs only the `stk` CLI — no extra deps.
