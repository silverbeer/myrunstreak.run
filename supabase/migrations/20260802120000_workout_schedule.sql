-- =====================================================
-- workout_schedule — a plan put on a day, by someone (SB-534)
-- =====================================================
-- SB-530 shipped a "Coming up" section that renders whatever is scheduled and
-- is absent while nothing is. Nothing ever was: `workout_templates.scheduled_for`
-- (SB-335) is set on 0 of 11 templates, and it could not carry the decision
-- anyway.
--
-- Three reasons a DATE column on the template is the wrong grain:
--
--   1. NO AUTHOR. Either side may schedule — Matthew assigns Thursday, or Gabe
--      plans his own week — and the screen has to say which. A column records
--      the date and nothing about who set it.
--
--   2. A PLAN COULD ONLY BE SCHEDULED ONCE, EVER. "Monday At-Home" every Monday
--      overwrites its own date. The column conflates *this plan* with *this
--      occasion*, which are different things: the plan is reused, the occasion
--      happens once.
--
--   3. SCHEDULING AND COMPLETING NEVER MEET. A session references a template,
--      not the occasion it answers, so "did he do Thursday's?" is not a query.
--
-- One row per planned occasion fixes all three, and is the shape recurrence
-- expands INTO rather than replaces (SB-535): a weekly rule generates rows
-- here, so moving or skipping one Thursday never has to cancel Thursdays.
--
-- `workout_templates.scheduled_for` is left in place and unread. It is NULL on
-- every row, so there is nothing to migrate; it can be dropped once no code
-- references it.
-- =====================================================

CREATE TABLE workout_schedule (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,  -- denormalized for RLS
    template_id UUID NOT NULL REFERENCES workout_templates(id) ON DELETE CASCADE,
    athlete_id UUID REFERENCES athletes(id) ON DELETE CASCADE,
    -- Who put it on the day. This is the whole point of the table over a column:
    -- "From Matthew" and "Mine" have to read the same on Training as on Plans.
    created_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
    scheduled_for DATE NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- The Coming-up read: one athlete, forward from today, soonest first.
CREATE INDEX idx_workout_schedule_athlete_date ON workout_schedule (athlete_id, scheduled_for);
CREATE INDEX idx_workout_schedule_user_date ON workout_schedule (user_id, scheduled_for);
CREATE INDEX idx_workout_schedule_template ON workout_schedule (template_id);

-- The same plan twice on one day is a mistake, not a double session — but the
-- same plan on two days is exactly what this table exists to allow.
CREATE UNIQUE INDEX idx_workout_schedule_no_duplicate
    ON workout_schedule (template_id, scheduled_for, COALESCE(athlete_id, user_id));

COMMENT ON TABLE workout_schedule IS
    'One planned occasion: a template put on a date by a coach or the athlete (SB-534)';
COMMENT ON COLUMN workout_schedule.created_by IS
    'Who scheduled it — the coach, or the athlete themselves. Drives the "who" on Coming up.';

-- =====================================================
-- RLS — mirrors template_items / template_blocks exactly
-- =====================================================
ALTER TABLE workout_schedule ENABLE ROW LEVEL SECURITY;

CREATE POLICY "own workout_schedule select" ON workout_schedule FOR SELECT
    USING (user_id = auth.uid());
CREATE POLICY "own workout_schedule insert" ON workout_schedule FOR INSERT
    WITH CHECK (user_id = auth.uid());
CREATE POLICY "own workout_schedule update" ON workout_schedule FOR UPDATE
    USING (user_id = auth.uid());
CREATE POLICY "own workout_schedule delete" ON workout_schedule FOR DELETE
    USING (user_id = auth.uid());

CREATE POLICY "coach workout_schedule select" ON workout_schedule FOR SELECT
    USING (can_coach_athlete(athlete_id));
CREATE POLICY "coach workout_schedule insert" ON workout_schedule FOR INSERT
    WITH CHECK (can_coach_athlete(athlete_id));
CREATE POLICY "coach workout_schedule update" ON workout_schedule FOR UPDATE
    USING (can_coach_athlete(athlete_id));
CREATE POLICY "coach workout_schedule delete" ON workout_schedule FOR DELETE
    USING (can_coach_athlete(athlete_id));
