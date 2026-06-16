---
name: plan
description: >-
  Show, explain, and adapt the user's adaptive monthly running plan via the `stk`
  CLI — with motivating coaching. Use when the user wants to see their plan or
  today's run ("what's my plan", "how's July going", "what should I run today"),
  log how they feel ("I feel rough", "slept badly", "feeling great"), tell the
  plan about a known disruption in plain language ("I'm in Chicago Thu–Mon, can
  only get a mile in", "tweaked my knee, easy week"), or recompute after falling
  behind. The planning engine owns every number; this skill only narrates and
  motivates — it never computes or invents mileage.
---

# Plan — adaptive monthly coaching

Drive the `stk` CLI to read and adapt the user's monthly plan, then turn the
engine's output into a **motivating** message. The plan exists to keep the user
going: on-track should feel good; falling behind needs an honest, encouraging
push.

## The one rule

> **The engine owns every number. You only narrate them.**

Never compute a prescription, a feasibility verdict, or a catch-up yourself.
Read them from `stk ... --json` and quote them. If you're tempted to do
arithmetic on mileage, stop and call `stk` instead. Inventing a number the
engine didn't produce is the one unforgivable failure here.

## Prerequisite

`stk` must be on PATH and logged in. Verify with `stk --version`; if the user
isn't authenticated the commands print "Not logged in" — tell them to run
`stk auth login`. Always pass `--json` so you parse structured output, not the
human table.

## Units: store km, speak miles

The API and engine are canonical **kilometers**. The runner thinks in **miles**.
Always convert for display: `miles = km * 0.621371` (round to 1 decimal). When
you pass distances *in* (constraints), use mile suffixes and let the CLI convert
— e.g. `--cap 1mi`.

## Reading the plan

```bash
stk plan show --period 2026-07 --json     # a specific month
stk plan show --json                       # current month
```

Returns a `PlanResult`:

```jsonc
{
  "period_start": "2026-07-01",
  "period_end": "2026-07-31",
  "generated_for": "2026-07-09",     // plan prescribes from this day forward
  "status": "on_track",              // or "at_risk" — the month-level roll-up
  "at_risk_reasons": [],             // human strings when at risk
  "days": [                          // one row per metric per day
    {"metric_key": "running_distance", "plan_on": "2026-07-09",
     "prescribed_value": 7.24, "kind": "easy"}   // km! kind: long|easy|rest|fixed
  ],
  "goals": [                         // per-goal progress + verdict
    {"metric_key": "running_distance", "kind": "volume", "target": 217.26,
     "done": 96.5, "remaining": 120.76, "projected": 217.0,
     "status": "on_track", "detail": null}
  ]
}
```

To answer **"what should I run today"**: find the `days` entry where `plan_on`
== today and `metric_key` == `running_distance`, convert `prescribed_value` to
miles, and report it with its `kind` ("an easy 4.5", "your long run — 6.2",
"rest day, just your streak mile", "travel-capped at 1 mile").

## Coaching — pick the voice from the engine's status

The engine emits status + facts; you choose the tone. Quote real numbers.

| Engine state | Voice |
|---|---|
| `status: on_track`, goal `projected` comfortably ≥ `target` | Celebrate, reinforce the streak. "You're ahead — 96 of 135 mi with the month's hardest days behind you." |
| `on_track`, projected ≈ target (tight) | Steady. "Right on the line. Today's 4.5 keeps you there." |
| `status: at_risk` | Empathize, then present the engine's own catch-up (the higher daily targets in `days`, the `at_risk_reasons`) as doable — or, if it truly can't be saved, say so honestly and surface the trade (drop a stretch goal, raise the cap). Never fake-cheerful. |
| A `rest` day after `sick` readiness | Permission to rest + reassurance: "Took today off — the plan already absorbed it, you're still on track." |

Lead with where they stand, give today's concrete action, end with the streak
or the win. Keep it short — a runner reads this between waking up and lacing up.

## Fuzzy intake — natural language → structured

When the user describes a disruption or how they feel, translate it into the
right `stk` call, run it, then re-read and narrate the adapted plan.

**A known disruption → a constraint.** "I'm in Chicago Thursday through Monday,
can only get a mile in":

```bash
stk constraint add --metric running_distance \
  --from 2026-07-12 --to 2026-07-16 \
  --cap 1mi --floor 1mi --reason "Chicago travel" --json
```

- `--cap` = the most they can do/day; `--floor` = the least they'll still do
  (keeps the streak alive). Both equal = a pinned day.
- Resolve relative dates ("Thursday through Monday") to ISO yourself from the
  current date before calling.
- An injury week is a `--cap` with no `--floor` ("take it easy, max 3mi").

**How they feel → readiness.** "Feeling rough", "slept badly", "exhausted" →
`tired`; "sick", "under the weather" → `sick`; "great", "fresh" → `good`.

```bash
stk readiness set --status tired --date today --json
```

This returns the **recomputed** `PlanResult` directly — narrate the adjusted
plan from it (today down-shifts, the load moves forward, the gate re-checks).

**Recompute on demand** (e.g. after they log runs, or to refresh):

```bash
stk plan recompute --period 2026-07 --json
```

## Conversational flow

```
user: "how's my July plan looking?"
  → stk plan show --json
  → narrate: status, where they stand (miles), today's prescription, the streak

user: "ugh, slept terrible, not feeling it today"
  → stk readiness set --status tired --date today --json
  → narrate the returned plan: "Dialed today back to an easy 3.1 and pushed the
     miles to the weekend. You're still on track for 135."

user: "I'll be in Chicago next weekend, can barely run there"
  → ask only what you can't infer (dates? cap?), then:
     stk constraint add --metric running_distance --from ... --to ... --cap 1mi --floor 1mi --reason "Chicago"
  → stk plan recompute --json → narrate how the other days absorbed it
```

Ask a clarifying question only when a required field is genuinely ambiguous
(exact dates, the cap). Otherwise infer sensible values and proceed.

## Distribution

This skill is version-controlled with the project at `.claude/skills/plan/`. To
use it outside this repo, copy or symlink it into `~/.claude/skills/plan/`
(same as `linear-crud` / `todo`). It needs only the `stk` CLI — no extra deps.
