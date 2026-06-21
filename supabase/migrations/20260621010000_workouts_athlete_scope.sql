-- =====================================================
-- Scope workouts to an athlete (SB-198). A coach acting-as an athlete creates
-- templates/sessions owned by that athlete (athlete_id) with created_by = the
-- coach. Self workouts keep athlete_id NULL (existing rows unaffected).
--
-- Access stays additive: the existing "own" policies (user_id = auth.uid())
-- are untouched; we ADD coach policies via can_coach_athlete so a current coach
-- (or the linked athlete) reaches athlete-owned rows — which is what lets a NEW
-- coach see the full history. The backend (service-role) enforces act-as in
-- code; these policies are the second line of defence.
-- =====================================================

-- True if the caller actively coaches the athlete, or is the linked athlete.
CREATE FUNCTION can_coach_athlete(aid UUID) RETURNS BOOLEAN
LANGUAGE sql STABLE AS $$
    SELECT aid IS NOT NULL AND (
        EXISTS (
            SELECT 1 FROM coach_athletes
            WHERE athlete_id = aid AND coach_id = auth.uid() AND status = 'active'
        )
        OR EXISTS (SELECT 1 FROM athletes WHERE id = aid AND linked_user_id = auth.uid())
    );
$$;

-- workout_templates
ALTER TABLE workout_templates ADD COLUMN athlete_id UUID REFERENCES athletes(id) ON DELETE CASCADE;
ALTER TABLE workout_templates ADD COLUMN created_by UUID REFERENCES users(user_id) ON DELETE SET NULL;
CREATE INDEX idx_workout_templates_athlete ON workout_templates (athlete_id);
CREATE POLICY "coach workout_templates select" ON workout_templates FOR SELECT
    USING (can_coach_athlete(athlete_id));
CREATE POLICY "coach workout_templates insert" ON workout_templates FOR INSERT
    WITH CHECK (can_coach_athlete(athlete_id));
CREATE POLICY "coach workout_templates update" ON workout_templates FOR UPDATE
    USING (can_coach_athlete(athlete_id));
CREATE POLICY "coach workout_templates delete" ON workout_templates FOR DELETE
    USING (can_coach_athlete(athlete_id));

-- template_items
ALTER TABLE template_items ADD COLUMN athlete_id UUID REFERENCES athletes(id) ON DELETE CASCADE;
ALTER TABLE template_items ADD COLUMN created_by UUID REFERENCES users(user_id) ON DELETE SET NULL;
CREATE INDEX idx_template_items_athlete ON template_items (athlete_id);
CREATE POLICY "coach template_items select" ON template_items FOR SELECT
    USING (can_coach_athlete(athlete_id));
CREATE POLICY "coach template_items insert" ON template_items FOR INSERT
    WITH CHECK (can_coach_athlete(athlete_id));
CREATE POLICY "coach template_items update" ON template_items FOR UPDATE
    USING (can_coach_athlete(athlete_id));
CREATE POLICY "coach template_items delete" ON template_items FOR DELETE
    USING (can_coach_athlete(athlete_id));

-- workout_sessions
ALTER TABLE workout_sessions ADD COLUMN athlete_id UUID REFERENCES athletes(id) ON DELETE CASCADE;
ALTER TABLE workout_sessions ADD COLUMN created_by UUID REFERENCES users(user_id) ON DELETE SET NULL;
CREATE INDEX idx_workout_sessions_athlete ON workout_sessions (athlete_id, session_date DESC);
CREATE POLICY "coach workout_sessions select" ON workout_sessions FOR SELECT
    USING (can_coach_athlete(athlete_id));
CREATE POLICY "coach workout_sessions insert" ON workout_sessions FOR INSERT
    WITH CHECK (can_coach_athlete(athlete_id));
CREATE POLICY "coach workout_sessions update" ON workout_sessions FOR UPDATE
    USING (can_coach_athlete(athlete_id));
CREATE POLICY "coach workout_sessions delete" ON workout_sessions FOR DELETE
    USING (can_coach_athlete(athlete_id));

-- exercise_sets
ALTER TABLE exercise_sets ADD COLUMN athlete_id UUID REFERENCES athletes(id) ON DELETE CASCADE;
ALTER TABLE exercise_sets ADD COLUMN created_by UUID REFERENCES users(user_id) ON DELETE SET NULL;
CREATE INDEX idx_exercise_sets_athlete ON exercise_sets (athlete_id, exercise_key);
CREATE POLICY "coach exercise_sets select" ON exercise_sets FOR SELECT
    USING (can_coach_athlete(athlete_id));
CREATE POLICY "coach exercise_sets insert" ON exercise_sets FOR INSERT
    WITH CHECK (can_coach_athlete(athlete_id));
CREATE POLICY "coach exercise_sets update" ON exercise_sets FOR UPDATE
    USING (can_coach_athlete(athlete_id));
CREATE POLICY "coach exercise_sets delete" ON exercise_sets FOR DELETE
    USING (can_coach_athlete(athlete_id));
