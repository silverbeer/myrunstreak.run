-- SB-99: file import needs a source of its own.
--
-- Runs are keyed (user_id, source_id, source_activity_id), so an imported run
-- has to hang off a user_sources row like any synced one. Typing that source
-- as 'import' — rather than reusing 'other' with a naming convention — keeps
-- provenance checkable in SQL: a run came from a file if and only if its
-- source is of type 'import'. Bulk zip import (SB-419) reuses the same source.
--
-- ALTER TYPE ... ADD VALUE is safe inside a transaction on PG 12+, but the new
-- value cannot be *used* until that transaction commits — which is why nothing
-- below inserts an 'import' source. Those rows are created lazily by the API on
-- a user's first upload.

ALTER TYPE source_type ADD VALUE IF NOT EXISTS 'import';

COMMENT ON TYPE source_type IS
    'Where a run came from. smashrun/strava/garmin are live-API syncs; import is a user-uploaded activity file (GPX/TCX/JSON); other is a fallback.';
