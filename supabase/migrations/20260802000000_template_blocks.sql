-- =====================================================
-- Circuits as data, and a logged set that can name what it was (SB-527).
--
-- Two gaps, one migration, because both need to touch exercise_sets and doing
-- them separately would migrate that table twice.
--
-- 1. CIRCUITS AND ROUNDS WERE PROSE.
--
--    Gabe's Monday template carried its real structure in free text:
--
--      template.rounds = 1
--      template.notes  = "Circuit A = 2 cycles x 1 min each; then 4-min water
--                         rest; Circuit B = 1 cycle, timing not prescribed."
--      item 4  notes = "Circuit A x2 - 1 min"
--      item 15 notes = "Circuit B - alternate sides each extension"
--
--    Circuit membership was retyped into every item, the round count lived in
--    one item's note, and the rest between circuits was tacked onto the last
--    item of the first. Meanwhile workout_templates.rounds is a single number
--    for the whole template and said 1, so nothing could render "2 rounds".
--
--    Note the asymmetry this fixes: exercise_sets.round_number already existed,
--    so the performance side modelled rounds while the prescription side did
--    not. You could record round 2; you could not prescribe it.
--
--    A real table rather than a `circuit TEXT` column: `section` and
--    `option_group` are already string groupings resolved client-side, and a
--    third would mean every rendering surface re-implements the fold — which is
--    exactly why groupOptionItems had to be extracted after SB-448.
--
-- 2. A LOGGED SET COULD NOT NAME THE PRESCRIBED ITEM.
--
--    exercise_sets referenced exercise_key, not template_items.id. `lunge`
--    appears five times in one template (side-step L/R, Circuit B single-leg
--    L/R, plain), so "lunge, round 1, 45s" was unattributable. "Did he do what
--    was prescribed?" was not answerable by query.
-- =====================================================

-- =====================================================
-- template_blocks — a circuit within a template
-- =====================================================
CREATE TABLE template_blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,   -- denormalized for RLS
    template_id UUID NOT NULL REFERENCES workout_templates(id) ON DELETE CASCADE,
    athlete_id UUID REFERENCES athletes(id) ON DELETE CASCADE,
    created_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
    label TEXT NOT NULL,                                    -- "Circuit A"
    position INTEGER NOT NULL DEFAULT 0,                    -- order within the template
    rounds INTEGER NOT NULL DEFAULT 1 CHECK (rounds >= 1),  -- the grain that was missing
    rest_after_seconds NUMERIC(8, 2),                       -- the 4-minute water break
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_template_blocks_template ON template_blocks (template_id, position);
CREATE INDEX idx_template_blocks_athlete ON template_blocks (athlete_id);

COMMENT ON TABLE template_blocks IS
    'A circuit within a template: its own round count and trailing rest (SB-527)';
COMMENT ON COLUMN template_blocks.rounds IS
    'Rounds for THIS circuit. workout_templates.rounds stays for blockless templates.';

-- Nullable: a simple template needs no blocks, and every existing row has none.
ALTER TABLE template_items
    ADD COLUMN block_id UUID REFERENCES template_blocks(id) ON DELETE SET NULL;
CREATE INDEX idx_template_items_block ON template_items (block_id, position);

COMMENT ON COLUMN template_items.block_id IS
    'The circuit this item belongs to; NULL for items outside any circuit (SB-527)';

-- Nullable: logging an ad-hoc set with no prescription behind it is legitimate.
ALTER TABLE exercise_sets
    ADD COLUMN template_item_id UUID REFERENCES template_items(id) ON DELETE SET NULL;
CREATE INDEX idx_exercise_sets_template_item ON exercise_sets (template_item_id);

COMMENT ON COLUMN exercise_sets.template_item_id IS
    'The prescribed item this set answers; NULL for ad-hoc sets (SB-527)';

-- =====================================================
-- RLS — mirrors template_items exactly
-- =====================================================
ALTER TABLE template_blocks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "own template_blocks select" ON template_blocks FOR SELECT
    USING (user_id = auth.uid());
CREATE POLICY "own template_blocks insert" ON template_blocks FOR INSERT
    WITH CHECK (user_id = auth.uid());
CREATE POLICY "own template_blocks update" ON template_blocks FOR UPDATE
    USING (user_id = auth.uid());
CREATE POLICY "own template_blocks delete" ON template_blocks FOR DELETE
    USING (user_id = auth.uid());

CREATE POLICY "coach template_blocks select" ON template_blocks FOR SELECT
    USING (can_coach_athlete(athlete_id));
CREATE POLICY "coach template_blocks insert" ON template_blocks FOR INSERT
    WITH CHECK (can_coach_athlete(athlete_id));
CREATE POLICY "coach template_blocks update" ON template_blocks FOR UPDATE
    USING (can_coach_athlete(athlete_id));
CREATE POLICY "coach template_blocks delete" ON template_blocks FOR DELETE
    USING (can_coach_athlete(athlete_id));

-- =====================================================
-- Backfill: lift circuits out of the notes prose
-- =====================================================
-- Existing templates encode circuit membership as a "Circuit X" prefix in an
-- item's notes — but only on SOME items. Gabe's Monday template labels items
-- 4-9 and 15-20, and leaves 10-14 unlabelled even though they are plainly the
-- back half of Circuit A ("Side-step lunge", "Side plank"...).
--
-- So a label starts a circuit and every following item in the same section
-- belongs to it until the next label. That is how a person reads the list, and
-- a purely per-item match would strand five of Gabe's eleven Circuit A items.
--
-- Conservative at the edges: items BEFORE the first label (the warm-up) stay
-- NULL, and the carry-forward resets at a section boundary so the cool-down is
-- never swept into the last circuit.
DO $$
DECLARE
    t RECORD;
    it RECORD;
    current_block UUID;
    current_label TEXT;
    current_section TEXT;
    found_label TEXT;
    next_pos INTEGER;
    n_rounds INTEGER;
BEGIN
    FOR t IN
        SELECT DISTINCT template_id FROM template_items WHERE notes ~* '^\s*Circuit\s+[A-Za-z0-9]+'
    LOOP
        current_block := NULL;
        current_label := NULL;
        current_section := NULL;
        next_pos := 0;

        FOR it IN
            SELECT id, position, section, notes, user_id, athlete_id, created_by
            FROM template_items WHERE template_id = t.template_id ORDER BY position
        LOOP
            -- A new section ends whatever circuit was running.
            IF current_section IS DISTINCT FROM it.section THEN
                current_section := it.section;
                current_block := NULL;
                current_label := NULL;
            END IF;

            found_label := substring(it.notes from '^\s*[Cc]ircuit\s+([A-Za-z0-9]+)');

            IF found_label IS NOT NULL AND ('Circuit ' || upper(found_label)) IS DISTINCT FROM current_label THEN
                current_label := 'Circuit ' || upper(found_label);
                -- "x2" / "×2" anywhere in this circuit's run of items.
                n_rounds := COALESCE((
                    SELECT MAX(NULLIF(substring(notes from '[×xX]\s*(\d+)'), '')::INTEGER)
                    FROM template_items
                    WHERE template_id = t.template_id
                      AND substring(notes from '^\s*[Cc]ircuit\s+([A-Za-z0-9]+)') = found_label
                ), 1);

                INSERT INTO template_blocks
                    (user_id, template_id, athlete_id, created_by, label, position, rounds)
                VALUES
                    (it.user_id, t.template_id, it.athlete_id, it.created_by,
                     current_label, next_pos, n_rounds)
                RETURNING id INTO current_block;
                next_pos := next_pos + 1;
            END IF;

            IF current_block IS NOT NULL THEN
                UPDATE template_items SET block_id = current_block WHERE id = it.id;
            END IF;
        END LOOP;
    END LOOP;
END $$;

-- The rest between circuits was tacked onto the last item of the preceding one
-- ("...; then 4-min rest"). Lift it onto the block that owns that item.
UPDATE template_blocks b
SET rest_after_seconds = 60 * sub.mins
FROM (
    SELECT ti.block_id,
           MAX(NULLIF(substring(ti.notes from '(\d+)\s*-?\s*min[a-z]*\s+rest'), '')::NUMERIC) AS mins
    FROM template_items ti
    WHERE ti.block_id IS NOT NULL AND ti.notes ~* '\d+\s*-?\s*min[a-z]*\s+rest'
    GROUP BY ti.block_id
) sub
WHERE b.id = sub.block_id AND sub.mins IS NOT NULL;
