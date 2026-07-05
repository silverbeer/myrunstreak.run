-- Section grouping for template items (SB-229 workout builder).
--
-- Matthew's plans are organised into sections (warm-up / speed / strength+core /
-- circuit / cool-down). template_items was a flat ordered list; add a `section`
-- so the builder can group items and the printable can render them under
-- headings. Additive + defaulted, so existing rows and the create path are
-- unaffected (they read as the single default section).

ALTER TABLE template_items
    ADD COLUMN section TEXT NOT NULL DEFAULT 'main';

COMMENT ON COLUMN template_items.section IS
    'Grouping within a template: warmup | main | cooldown (free text; builder-defined)';
