-- =====================================================
-- Run audio log (SB-302): what you listened to on a run
-- =====================================================
-- A user annotation layer on top of the SmashRun import — what was playing
-- (podcast / music / audiobook / other / none) plus an optional free-text note
-- ("Noah Kahan playlist today"). Set after the run syncs; SmashRun has none of
-- this. Longer term this pairs with a Spotify pull (podtelemetry.com).

ALTER TABLE runs ADD COLUMN IF NOT EXISTS audio_type TEXT
  CHECK (audio_type IN ('podcast', 'music', 'audiobook', 'other', 'none'));
ALTER TABLE runs ADD COLUMN IF NOT EXISTS audio_note TEXT;

COMMENT ON COLUMN runs.audio_type IS 'What was playing: podcast|music|audiobook|other|none (SB-302)';
COMMENT ON COLUMN runs.audio_note IS 'Free-text listening note, e.g. a playlist/show name (SB-302)';
