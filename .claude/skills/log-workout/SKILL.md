---
name: log-workout
description: >-
  Capture and review an athlete's strength & conditioning workouts via the `stk
  workout` CLI. Use when the user wants to turn a coach's workout plan
  (a screenshot or pasted text) into a reusable template, log what an athlete
  actually did (spoken or typed — "set 2, 18 reps, 40-dash 5.4"), or see
  progress ("how's his 40 trending", "is he getting stronger"). The data/API own
  every number; this skill parses, flags implausible values, confirms back, and
  narrates — it never invents results.
---

# Log Workout — capture + review for the Athlete Training Tracker

Turn a coach's plan into a **template**, log an athlete's **actuals** against it,
and read back **progress**. Built for the trainer-as-buyer flow: the coach (or
parent) speaks/screenshots; this skill structures it.

## The one rule

> **Never invent a number. Parse what you're given, flag what looks off, confirm
> before saving.** A test time or rep count is the athlete's real performance —
> getting it wrong corrupts the progress trend. When unsure, ask.

## Prerequisite

`stk` must be authed (`stk auth status` → active) and the `/workouts` API live.
The CLI is the deterministic interface; you build JSON and pipe it in via `-`.

## Units: store canonical, speak natural

The API stores **kg** (load) and **meters** (distance); the gym speaks **lb** and
**yards**. Convert when building JSON, convert back when narrating.
`lb × 0.453592 = kg` · `yd × 0.9144 = m` (40 yd = 36.58 m, 20 lb = 9.07 kg).

## Flow A — parse a plan → a template

When given a screenshot or pasted workout (the coach's prescription):

1. Get valid exercise keys: `stk workout exercises --json` (keys + which `measures`
   each uses). Map the plan's movements to keys (e.g. "push-ups" → `pushups`,
   "bicep 90° holds" → `bicep_hold`). If a movement has **no catalog key**, tell
   the user — the catalog is fixed; a new exercise needs adding (don't guess a key).
2. Build a template JSON:
   ```json
   {"name":"Saturday Circuit","type":"circuit","rounds":3,"source":"Matthew",
    "items":[{"exercise_key":"jump_rope","position":0,"target_duration_seconds":180},
             {"exercise_key":"bicep_hold","position":2,"target_duration_seconds":60,"target_load_kg":9.07}]}
   ```
   `type` ∈ circuit|intervals|test|session. Put per-exercise rounds in `rounds`.
3. Create it: `echo '<json>' | stk workout add-template --file -` (or write a temp
   file). Report the name + id.

## Flow B — log the actuals → a session (the live capture)

When the user reads/speaks what the athlete did ("set 2, interval 12s, 18 reps;
40-dash 5.4"):

1. Pull the matching template: `stk workout templates --json` → it tells you the
   expected exercises, rounds, and targets — **use them as expectations.**
2. Parse the actuals into `exercise_sets`. Map the spoken dimension to the right
   column:
   - reps → `reps`; held/timed → `duration_seconds`; a sprint/test result →
     `time_seconds`; a measured distance (frog jump, broad jump) → `distance_m`;
     load → `load_kg`. Tag `round_number`/`set_index` and `variant`
     (front|back|left|right|forward|backward).
   - Rest/interval timing → `started_at`/`ended_at` when given (enables density).
3. **Plausibility-check against the template + catalog:** a 40-yd dash of "54s"
   → "did you mean 5.4?"; 200 push-ups in 30s → confirm; a load far off the
   target → confirm. Flag, don't silently store.
4. **Confirm back** a compact summary, then log only on a yes:
   ```
   Logging — Sat Jun 20, Saturday Circuit:
     push-ups  R1 22 · R2 20 · R3 18
     40-yd dash  5.4 s   (vs last 5.6 — faster!)
     planks felt hard (RPE 8)
   Save? 
   ```
5. Save: `echo '<session json>' | stk workout log --file -`. Session JSON:
   ```json
   {"session_date":"2026-06-20","type":"circuit","template_id":"<id>","how_felt":"strong",
    "sets":[{"exercise_key":"pushups","round_number":1,"reps":22},
            {"exercise_key":"40yd_dash","distance_m":36.58,"time_seconds":5.4}]}
   ```

## Flow C — progress (the coach's feedback loop)

`stk workout sessions --since <date> --json` → read sets across sessions and
narrate, the same way running splits/PRs are analyzed:
- **Speed tests:** trend `time_seconds` for `40yd_dash` etc. **down** = faster.
  "His 40 went 5.8 → 5.4 over the block."
- **Strength/volume:** reps × load over time per exercise; max plank/hold.
- **Density:** from `started_at`/`ended_at`, work vs rest per session; rest
  shrinking while output holds = fitter.
Lead with what improved, name the marker, keep it short — it's coaching, not a dump.

## Voice / wearable note

The actuals can come from a transcript (phone memo, AirPods dictation, a wearable
recorder). Treat the transcript as the spoken input to Flow B — same parse,
same plausibility + confirm-back. Couple to the transcript, not any one device.

## Distribution

Version-controlled at `.claude/skills/log-workout/`. Copy/symlink into
`~/.claude/skills/log-workout/` to use outside this repo. Needs only the `stk`
CLI (authed).
