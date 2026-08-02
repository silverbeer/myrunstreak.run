-- =====================================================
-- A week that repeats (SB-535)
-- =====================================================
-- SB-534 made one occasion schedulable. Matthew's week repeats — Monday
-- At-Home every Monday, Track Thursday every Thursday — and re-entering that by
-- hand every week is the kind of chore that stops happening in week three,
-- after which Coming up is empty again and the screen is back where it started.
--
-- A rule GENERATES occasions; it does not replace them. `workout_schedule` stays
-- the single answer to "what is coming up", so everything built on it in SB-530
-- and SB-534 — the Start card, the who-scheduled-it line, unscheduling — keeps
-- working with no knowledge that recurrence exists.
--
-- SKIPPING ONE THURSDAY MUST NOT CANCEL THURSDAYS. That is what recurring
-- calendars are always asked for and rarely support, and it is why generation
-- carries a watermark rather than reconciling. `generated_through` records the
-- last date this rule has already produced rows for; generation only ever moves
-- forward from it. So a generated occasion that gets deleted is simply gone —
-- there is no reconciliation pass to notice its absence and put it back — while
-- the rule keeps producing every Thursday after it.
--
-- The corollary, deliberately: editing a rule never rewrites the past, and
-- never revisits dates it has already generated. Changing Thursday to Friday
-- takes effect from the next ungenerated day forward, which is the only reading
-- that does not silently rearrange a week the athlete has already seen.

CREATE TABLE workout_recurrence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,  -- denormalized for RLS
    template_id UUID NOT NULL REFERENCES workout_templates(id) ON DELETE CASCADE,
    athlete_id UUID REFERENCES athletes(id) ON DELETE CASCADE,
    -- Who set the pattern. Carried onto every occasion it generates, so the
    -- "From Matthew" / "Mine" line on Coming up needs no special case (SB-534).
    created_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
    -- Days of the week, 0 = Sunday .. 6 = Saturday — the JavaScript convention,
    -- because the UI is what produces these. Python converts once, in the
    -- expansion helper, rather than at every call site.
    byweekday SMALLINT[] NOT NULL CHECK (
        array_length(byweekday, 1) BETWEEN 1 AND 7
        AND byweekday <@ ARRAY[0,1,2,3,4,5,6]::SMALLINT[]
    ),
    starts_on DATE NOT NULL,
    -- NULL = until turned off. An explicit end date covers "in-season"; naming
    -- seasons as first-class blocks is a bigger idea and not this.
    ends_on DATE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    -- The watermark described above. NULL = nothing generated yet.
    generated_through DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_workout_recurrence_athlete ON workout_recurrence (athlete_id, active);
CREATE INDEX idx_workout_recurrence_user ON workout_recurrence (user_id, active);
CREATE INDEX idx_workout_recurrence_template ON workout_recurrence (template_id);

COMMENT ON TABLE workout_recurrence IS
    'A weekly pattern that generates workout_schedule rows (SB-535)';
COMMENT ON COLUMN workout_recurrence.byweekday IS
    'Days of week, 0=Sunday..6=Saturday (JS Date.getDay convention)';
COMMENT ON COLUMN workout_recurrence.generated_through IS
    'Last date already generated. Generation moves forward only, so a deleted '
    'occasion never comes back and one skipped Thursday does not cancel Thursdays.';

-- Which rule produced an occasion, if any. NULL = someone scheduled it by hand
-- (SB-534), and those are untouched by any of this.
ALTER TABLE workout_schedule
    ADD COLUMN recurrence_id UUID REFERENCES workout_recurrence(id) ON DELETE SET NULL;
CREATE INDEX idx_workout_schedule_recurrence ON workout_schedule (recurrence_id);

COMMENT ON COLUMN workout_schedule.recurrence_id IS
    'The pattern that generated this occasion; NULL when scheduled by hand (SB-535)';

-- =====================================================
-- RLS — mirrors workout_schedule exactly
-- =====================================================
ALTER TABLE workout_recurrence ENABLE ROW LEVEL SECURITY;

CREATE POLICY "own workout_recurrence select" ON workout_recurrence FOR SELECT
    USING (user_id = auth.uid());
CREATE POLICY "own workout_recurrence insert" ON workout_recurrence FOR INSERT
    WITH CHECK (user_id = auth.uid());
CREATE POLICY "own workout_recurrence update" ON workout_recurrence FOR UPDATE
    USING (user_id = auth.uid());
CREATE POLICY "own workout_recurrence delete" ON workout_recurrence FOR DELETE
    USING (user_id = auth.uid());

CREATE POLICY "coach workout_recurrence select" ON workout_recurrence FOR SELECT
    USING (can_coach_athlete(athlete_id));
CREATE POLICY "coach workout_recurrence insert" ON workout_recurrence FOR INSERT
    WITH CHECK (can_coach_athlete(athlete_id));
CREATE POLICY "coach workout_recurrence update" ON workout_recurrence FOR UPDATE
    USING (can_coach_athlete(athlete_id));
CREATE POLICY "coach workout_recurrence delete" ON workout_recurrence FOR DELETE
    USING (can_coach_athlete(athlete_id));
