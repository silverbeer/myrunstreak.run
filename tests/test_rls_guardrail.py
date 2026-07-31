"""The RLS anon-leak guardrail, enforced (SB-227, SB-453).

`auth.uid()` is NULL for the anon role, so `OR auth.uid() IS NULL` in a policy
evaluates TRUE for every unauthenticated caller and the policy degrades to
"allow everyone". The anon key is public — it ships in the frontend bundle — so
on Supabase-hosted prod, where anon holds the default SELECT grant, that is a
full table read for anyone who asks.

This has now been introduced three times: the initial schema, the goals table,
and again inside `20260704010000_fix_security_advisor.sql` — a migration whose
stated purpose was fixing security. Hence a test rather than a convention.

Local dev does not reveal it: the anon role there lacks the table grant, so RLS
is never reached. A clean local database is not evidence.
"""

from __future__ import annotations

import re
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parent.parent / "supabase" / "migrations"

# The defect, in the forms Postgres accepts: `auth.uid() IS NULL` with any
# spacing, and the parenthesised form pg_policies echoes back.
ANON_ESCAPE = re.compile(r"auth\s*\.\s*uid\s*\(\s*\)\s*\)?\s+IS\s+NULL", re.IGNORECASE)

# Lines that merely *talk* about the antipattern — the fix migrations explain it
# at length, and this file's own name would otherwise trip the scan.
_COMMENT = re.compile(r"^\s*--")


def _offending_lines() -> list[str]:
    hits: list[str] = []
    for path in sorted(MIGRATIONS.glob("*.sql")):
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if _COMMENT.match(line):
                continue
            if ANON_ESCAPE.search(line):
                hits.append(f"{path.name}:{lineno}: {line.strip()}")
    return hits


def test_no_migration_grants_anon_an_rls_escape() -> None:
    offenders = _offending_lines()
    assert not offenders, (
        "`auth.uid() IS NULL` in an RLS policy lets any unauthenticated caller "
        "read the whole table (SB-227, SB-453). Scope the policy to "
        "`user_id = auth.uid()` instead:\n  " + "\n  ".join(offenders)
    )


def test_the_detector_actually_matches_the_defect() -> None:
    """A guard that cannot fail guards nothing."""
    assert ANON_ESCAPE.search("USING (user_id = auth.uid() OR auth.uid() IS NULL);")
    assert ANON_ESCAPE.search("WHERE user_id = auth.uid() OR auth.uid( ) is null")
    # the form pg_policies renders
    assert ANON_ESCAPE.search("((user_id = auth.uid()) OR (auth.uid() IS NULL))")
    # and does not fire on a correctly scoped policy
    assert not ANON_ESCAPE.search("USING (user_id = auth.uid());")


def test_the_fix_migrations_are_present() -> None:
    """Both halves of the fix — users/sync_history, then everything else."""
    names = {p.name for p in MIGRATIONS.glob("*.sql")}
    assert "20260704020000_rls_owner_only_no_anon_leak.sql" in names
    assert "20260731120000_rls_owner_only_runs_splits_goals_sources.sql" in names
