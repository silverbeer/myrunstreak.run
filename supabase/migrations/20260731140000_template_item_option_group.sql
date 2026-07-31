-- Option groups on template_items (SB-448): "pick one of N".
--
-- Matthew's in-season aerobic day is an either/or, not a list:
--
--   "20 minute steady run, 40 minute steady bike, or 5 minute steady jump rope
--    keeping your heart rate between 120 and 145"
--
-- `section` groups items and `position` orders them, but nothing expressed
-- alternatives — so the printed sheet told Gabe to do all three.
--
-- Items sharing an `option_group` value within a template are alternatives;
-- NULL means mandatory, which is every existing row and today's behaviour.
-- Choose-1 is the only cardinality any plan has needed, so there is no
-- choose_n column until one asks for it.

ALTER TABLE template_items
    ADD COLUMN option_group TEXT,
    ADD COLUMN option_group_label TEXT;

COMMENT ON COLUMN template_items.option_group IS
    'Items sharing this value within a template are alternatives — do one of them. NULL = mandatory.';
COMMENT ON COLUMN template_items.option_group_label IS
    'Heading shown above the alternatives, e.g. "Aerobic engine — pick one". Read from any member of the group.';

-- Rendering and logging both walk a template's items grouped by option_group;
-- the partial index keeps that lookup off a full scan without carrying the
-- overwhelming majority of rows, which are NULL.
CREATE INDEX idx_template_items_option_group
    ON template_items (template_id, option_group)
    WHERE option_group IS NOT NULL;
