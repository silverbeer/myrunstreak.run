# Targets: where they live and how they move

**Status:** proposed model (SB-489). Sections marked _pending Matthew_ are the
author's reading, not the coach's confirmed answer. Everything else follows from
the existing schema and from Matthew's 2026-07-30 plan.

This is the discovery SB-449 (progression rules engine) needs, and it answers
the target-derivation question blocking SB-488 (copy/promote).

## The question

Targets are not static. Improvement is the point:

> "when the runs get easy, increase speed."
> "when the lifts get easy, add one cycle before increasing resistance."

Today every target lives on `template_items` — `target_reps`, `target_load_kg`,
`target_duration_seconds`, `target_hr_min/max`, and nine more. A template holds
one frozen set of numbers, edited by hand, with no memory. That models a
prescription captured at a moment, which is the opposite of what the coaching is.

## 1. Three kinds of number, not one

| | what it is | how it moves | example |
| --- | --- | --- | --- |
| **calibration** | what the athlete should work at *now* | up **and** down; a bad month lowers it | 200s at 40-42s |
| **personal best** | the best ever done | one direction only — a PB that regresses is a bug | 40yd in 5.1 |
| **goal** | a dated future target | set by hand, by coach or athlete | 4.9 40yd by June 2027 |

Same underlying number, opposite rules, so they cannot be the same row. Goals
are SB-450's territory. This document is mostly about calibration.

## 2. The line between design and calibration

The intuitive split — the workout owns structure, the athlete owns numbers —
breaks on a real line of Matthew's plan. Two tests:

- **Substitution:** hand the workout to a different athlete unchanged. Does the
  number stay?
- **Time:** leave it with the same athlete for three months while they improve.
  Does the number move?

Applied to the 2026-07-30 plan:

| prescription | substitution | time | |
| --- | --- | --- | --- |
| 200m distance | stays | never | design |
| 30s work period | stays | never | design |
| 2 min on / 1 min recovery | stays | never | design |
| 3 min between rounds | stays | never | design |
| "full recovery" | stays | never | design (`rest_mode`) |
| "60-90s, go off how you feel" | stays | never | design (`rest_mode`) |
| 40yd x 3 attempts, video each | stays | never | design |
| 10yd accel from 4 start positions | stays | never | design |
| 40-42s at 200m | changes | moves | calibration |
| 5-8lb dumbbells | changes | moves | calibration |
| HR 160-175 | changes | moves slowly | calibration |
| 8-12 reps | changes | moves | **conflict** |
| **2 rounds** | **stays** | **moves** | **conflict** |

Rounds is the counterexample that matters. It survives substitution — it is
Matthew's design, the same for any athlete — and yet "add one cycle before
increasing resistance" makes it the *first* thing progression touches. A
dimension-level split (reps are design, load is calibration) cannot express that.

**So the line is not per-dimension. It is per item, per dimension, and the coach
chooses which side by writing a name instead of a number.**

## 3. The model

Every target slot on a template item holds exactly one of:

1. **A literal** — `200m`, `30s`, `2 rounds`, `3 min rest`. Frozen. The coach's
   design. Progression never rewrites it.
2. **A reference** — "threshold 200 pace", "working dumbbell load", "aerobic
   zone". Resolves against the athlete's current calibration at render, print
   and log time.
3. **A mode** — `full`, `autoregulated`. Already shipped as
   `template_items.rest_mode`.

The same quantity can be either, and the coach's intent decides. HR 160-175 is
the clearest case: Matthew wrote an absolute, so today it is a literal — but it
is really Gabe's aerobic zone, and can be promoted to a reference the day he
wants it to track.

Ranges are preserved on both sides. A calibration is a `min`/`max` pair, not a
scalar, because 40-42s and 5-8lb are how the coaching is actually written. This
mirrors the convention already in the schema (`target_reps` / `target_reps_max`,
and the same for load, duration, rest and HR).

## 4. What moves, and who moves it

- The progression engine (SB-449) may write **only to calibrations**. It never
  edits a template.
- Structure changes — adding a cycle, changing the rep range — stay an explicit
  coach edit. The engine may *propose* one; it may not apply it. This is the same
  propose/approve flow SB-449 already assumes, with a sharper boundary: proposals
  against calibration are cheap and reversible, proposals against design need a
  human.

_Pending Matthew:_ what "easy" means measurably (top of the rep range twice
running? beating target by a margin? an RPE threshold? his own eye), the
precedence between dimensions for the running work, and whether Gabe sees a
proposal before or after the coach acts on it.

## 5. History and regression

Calibration rows are dated. That makes the progression record a query rather
than a feature: "you were at 42s in July, you're at 40s now" falls out of the
table. Templates do not need versioning for this story to work — the numbers
that move were never on the template.

A calibration coming down after illness or a layoff is correct behaviour, not
failure. _Pending Matthew:_ how that is surfaced to a 14-year-old. The current
inclination is that calibration is presented as "where you're working right now"
and only personal bests and goals are framed as achievement — a PB never drops,
so the achievement surface never regresses.

## 6. Personal bests

PBs are derived, not stored: the best value across an athlete's logged sets for
a benchmark movement. "Better" is a property of the measure, not the exercise —
`time_s` lower is better, `distance_m` higher is better — which is exactly the
missing `min` aggregation SB-450 covers.

Two carve-outs:

- **`interval_run` is flagged `is_benchmark` and probably should not be.** It is
  the workhorse of the speed-endurance day (8-12x200, 6-10x300), so treating
  every rep as a PB attempt buries the real bests under training volume. A PB
  should come from a test, not from a Tuesday. _Pending Matthew:_ which of the
  six flagged movements he actually tests.
- **Does a PB need context?** A 40 tested fresh and a 40 run at the end of a
  session are not the same number. _Pending Matthew._

## 7. Schema sketch

Enough to size SB-449; not a migration.

```sql
CREATE TABLE athlete_calibrations (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    athlete_id     UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    exercise_key   TEXT NOT NULL REFERENCES exercises(key),
    dimension      TEXT NOT NULL,  -- reps | duration_s | load_kg | distance_m
                                   -- | time_s | hr_bpm | cadence | speed_kph
    value_min      NUMERIC,
    value_max      NUMERIC,        -- NULL when not a range
    effective_from DATE NOT NULL,
    effective_to   DATE,           -- NULL = current
    source         TEXT,           -- coach | proposal_accepted | test
    set_by         UUID REFERENCES users(user_id),
    note           TEXT
);
```

The reference side needs a way for an item to say "this dimension resolves from
calibration". The cheap, additive option is a `calibrated_dimensions TEXT[]` on
`template_items`: the literal columns stay as the coach's fallback and last
rendered value, and nothing migrates. The cleaner long-run shape is a
`template_item_targets` child table keyed on (item, dimension) with an explicit
`literal | reference | mode`, retiring all thirteen `target_*` columns — worth
doing eventually, not worth doing first.

## 8. Consequences

- **Migration: none.** All six of Matthew's existing templates stay literal and
  remain valid. Calibration is purely additive. The "migrate the templates or
  keep them as snapshots" question was a false dilemma; the answer is neither,
  and individual numbers get promoted to references when the coach wants them to
  move.
- **SB-488's blocker dissolves.** A copy carries literals and references
  verbatim. References resolve against whoever is doing the work, so
  session→template promotion never has to decide whether the target is the best,
  the first or the average actual — it does not derive a target at all.
- **A workout becomes genuinely shareable.** One structure serves many athletes,
  which is what the "Emergency Workouts" were always meant to be.
- **SB-449 gets a narrow, safe write surface** — calibration rows only.

## 9. The one question left for Matthew

Everything in section 2 reduces to a single question, walked down his own plan
line by line:

> Which of these numbers would you change for a different athlete, without
> changing the workout?

What he points at becomes a reference. Everything else is a literal.

The residual questions are section 4's ("easy", precedence, who sees a proposal
first), section 5's (how a drop is shown), and section 6's (which movements are
tested, and whether a PB needs context).

## Related

- **SB-449** — progression rules engine. This is its discovery.
- **SB-488** — copy/promote. Answered by section 8.
- **SB-450** — benchmark goals + `min` aggregation. The goal leg of section 1.
- **SB-451** — coach/athlete loop. A proposed progression is one of the things
  worth talking about there.
