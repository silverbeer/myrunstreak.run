"""
Scan the exercise catalog for duplicates and unresolved rows.

Two sources, same checks:

  * ``--from-migrations`` (default) parses every ``INSERT INTO exercises`` and
    ``UPDATE exercises SET aliases`` statement under ``supabase/migrations/``.
    No database, no network — safe to run in CI on every PR.
  * ``--from-json FILE`` reads a live catalog dump (``stk workout exercises
    --json``), which also covers coach-created rows that never appear in a
    migration.

Exit code is 1 for the two failures that are never defensible: a hard duplicate
(identical name, colliding alias) and a search blind spot (a row its own search
cannot find). Near-duplicate *candidates* are reported but never fail the build —
real variants (push-up vs incline push-up) must be allowed to coexist, so that
call stays with a human.

Usage:
    uv run python scripts/audit_exercise_catalog.py
    uv run python scripts/audit_exercise_catalog.py --from-json /tmp/catalog.json
    uv run python scripts/audit_exercise_catalog.py --threshold 0.90
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"

# Words that distinguish real variants rather than signalling a duplicate. A pair
# whose only difference is one of these is a variant, not a dupe, so it is not
# reported even when the strings are otherwise near-identical.
VARIANT_MARKERS = {
    "left",
    "right",
    "single",
    "double",
    "incline",
    "decline",
    "hold",
    "jump",
    "reverse",
    "front",
    "back",
    "side",
    "wide",
    "narrow",
    "seated",
    "standing",
    "weighted",
}

PLACEHOLDER_PATTERNS = (
    re.compile(r"\bTBD\b", re.I),
    re.compile(r"confirm with", re.I),
    re.compile(r"\bunknown\b", re.I),
)


# The normalizer is the one the running service uses (SB-454), imported rather
# than reimplemented so this audit can never drift from production behaviour —
# the search-blind-spot check below is only meaningful if they agree.
sys.path.insert(0, str(REPO_ROOT))
from src.shared.exercise_matching import matches_query, normalize  # noqa: E402


@dataclass
class ExerciseRow:
    key: str
    display_name: str
    aliases: list[str] = field(default_factory=list)
    instructions: str | None = None
    source: str = ""

    @property
    def norm_name(self) -> str:
        return normalize(self.display_name)

    @property
    def norm_aliases(self) -> list[str]:
        """Deduped — two spellings of one alias on the same row ("press-up" and
        "press up") are intentional, not a collision."""
        return sorted({normalize(a) for a in self.aliases if a.strip()})


# --------------------------------------------------------------- SQL parsing


def _split_top_level(text: str, sep: str = ",") -> list[str]:
    """Split on `sep`, ignoring separators inside quotes, parens or brackets.

    Postgres escapes a quote by doubling it ("Farmer''s carry"), which this
    handles because the doubled quote simply toggles the flag twice.
    """
    parts: list[str] = []
    depth = 0
    in_quote = False
    current: list[str] = []
    for ch in text:
        if ch == "'":
            in_quote = not in_quote
        elif not in_quote and ch in "([":
            depth += 1
        elif not in_quote and ch in ")]":
            depth -= 1
        if ch == sep and depth == 0 and not in_quote:
            parts.append("".join(current))
            current = []
            continue
        current.append(ch)
    parts.append("".join(current))
    return parts


def _unquote(literal: str) -> str | None:
    literal = literal.strip()
    if literal.upper().startswith("NULL"):
        return None
    if literal.startswith("'"):
        end = literal.rfind("'")
        return literal[1:end].replace("''", "'")
    return None


def _parse_array(literal: str) -> list[str]:
    """ARRAY['a','b'] / ARRAY[]::text[] / '{"a","b"}' -> list[str]."""
    literal = literal.strip()
    match = re.match(r"ARRAY\s*\[(.*?)\]", literal, re.S | re.I)
    if match:
        inner = match.group(1).strip()
        if not inner:
            return []
        return [v for v in (_unquote(p) for p in _split_top_level(inner)) if v]
    curly = _unquote(literal)
    if curly and curly.startswith("{"):
        return [v.strip().strip('"') for v in curly[1:-1].split(",") if v.strip()]
    return []


def _strip_sql_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def _statement_end(sql: str, start: int) -> int:
    """Index of the `;` that ends the statement beginning at `start`.

    A plain non-greedy `.*?;` is wrong here: seeded `instructions` text contains
    semicolons ("Feet together; bend down into..."), which silently truncated the
    scan and dropped every row after it. Walk the string tracking quotes and
    bracket depth instead.
    """
    depth = 0
    in_quote = False
    i = start
    while i < len(sql):
        ch = sql[i]
        if ch == "'":
            # A doubled quote is an escaped literal quote, not a delimiter.
            if in_quote and i + 1 < len(sql) and sql[i + 1] == "'":
                i += 2
                continue
            in_quote = not in_quote
        elif not in_quote:
            if ch in "([":
                depth += 1
            elif ch in ")]":
                depth -= 1
            elif ch == ";" and depth == 0:
                return i
        i += 1
    return len(sql)


def parse_migrations(directory: Path) -> list[ExerciseRow]:
    """Reconstruct the seeded catalog from the migration SQL.

    INSERTs build the rows; later `UPDATE exercises SET aliases = ...` statements
    overwrite them, mirroring what the database actually ends up holding.
    """
    rows: dict[str, ExerciseRow] = {}
    insert_re = re.compile(
        r"INSERT\s+INTO\s+exercises\s*\((?P<cols>[^)]*)\)\s*VALUES",
        re.S | re.I,
    )
    alias_update_re = re.compile(
        r"UPDATE\s+exercises\s+SET\s+(?P<sets>.*?)WHERE\s+key\s*=\s*'(?P<key>[^']+)'",
        re.S | re.I,
    )

    for path in sorted(directory.glob("*.sql")):
        sql = _strip_sql_comments(path.read_text())

        for match in insert_re.finditer(sql):
            columns = [c.strip().lower() for c in match.group("cols").split(",")]
            body = sql[match.end() : _statement_end(sql, match.end())]
            # Drop a trailing upsert clause so it isn't mistaken for a tuple.
            body = re.split(r"\bON\s+CONFLICT\b", body, flags=re.I)[0]
            # Values are a comma-separated list of parenthesised tuples; the
            # top-level split isolates each tuple with its arrays intact.
            for chunk in _split_top_level(body):
                chunk = chunk.strip()
                if not chunk.startswith("("):
                    continue
                tuple_body = chunk[1 : chunk.rfind(")")]
                values = _split_top_level(tuple_body)
                if len(values) != len(columns):
                    continue
                record = dict(zip(columns, values, strict=True))
                key = _unquote(record.get("key", ""))
                name = _unquote(record.get("display_name", ""))
                if not key or not name:
                    continue
                rows[key] = ExerciseRow(
                    key=key,
                    display_name=name,
                    aliases=_parse_array(record.get("aliases", "")),
                    instructions=_unquote(record.get("instructions", "")),
                    source=path.name,
                )

        for match in alias_update_re.finditer(sql):
            key = match.group("key")
            if key not in rows:
                continue
            for assignment in _split_top_level(match.group("sets")):
                field_name, _, value = assignment.partition("=")
                if field_name.strip().lower() == "aliases":
                    rows[key].aliases = _parse_array(value)

    return list(rows.values())


def parse_json(path: Path) -> list[ExerciseRow]:
    payload: Any = json.loads(path.read_text())
    records = payload if isinstance(payload, list) else payload.get("exercises", [])
    return [
        ExerciseRow(
            key=r["key"],
            display_name=r["display_name"],
            aliases=list(r.get("aliases") or []),
            instructions=r.get("instructions"),
            source="live",
        )
        for r in records
    ]


# ------------------------------------------------------------------- checks


def _is_variant_pair(a: str, b: str) -> bool:
    """True when the two names differ only by a variant marker."""
    diff = set(a.split()) ^ set(b.split())
    return bool(diff) and diff <= VARIANT_MARKERS


def find_hard_duplicates(rows: list[ExerciseRow]) -> list[str]:
    """Collisions that are always wrong: same name, or a shared/shadowed alias."""
    problems: list[str] = []

    by_name: dict[str, list[ExerciseRow]] = {}
    for row in rows:
        by_name.setdefault(row.norm_name, []).append(row)
    for name, group in sorted(by_name.items()):
        if len(group) > 1:
            keys = ", ".join(f"{r.key} ({r.source})" for r in group)
            problems.append(f"duplicate display_name {name!r}: {keys}")

    alias_owner: dict[str, list[ExerciseRow]] = {}
    for row in rows:
        for alias in row.norm_aliases:
            alias_owner.setdefault(alias, []).append(row)
    for alias, group in sorted(alias_owner.items()):
        if len(group) > 1:
            keys = ", ".join(r.key for r in group)
            problems.append(f"alias {alias!r} claimed by {len(group)} rows: {keys}")
        owner = by_name.get(alias)
        if owner:
            for holder in group:
                for target in owner:
                    if target.key != holder.key:
                        problems.append(
                            f"alias {alias!r} on {holder.key} shadows the display_name "
                            f"of {target.key} — searching it returns both"
                        )

    return problems


def find_near_duplicates(rows: list[ExerciseRow], threshold: float) -> list[str]:
    """Name pairs similar enough to warrant a human look."""
    candidates: list[tuple[float, str]] = []
    for i, a in enumerate(rows):
        for b in rows[i + 1 :]:
            if _is_variant_pair(a.norm_name, b.norm_name):
                continue
            ratio = SequenceMatcher(None, a.norm_name, b.norm_name).ratio()
            tokens_a, tokens_b = set(a.norm_name.split()), set(b.norm_name.split())
            jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
            score = max(ratio, jaccard)
            if score >= threshold:
                candidates.append(
                    (
                        score,
                        f"{score:.2f}  {a.key} ({a.display_name!r})  ~  {b.key} ({b.display_name!r})",
                    )
                )
    return [line for _, line in sorted(candidates, reverse=True)]


def find_placeholders(rows: list[ExerciseRow]) -> list[str]:
    """Rows seeded with a note that says the movement was never pinned down."""
    out = []
    for row in rows:
        text = row.instructions or ""
        if any(p.search(text) for p in PLACEHOLDER_PATTERNS):
            out.append(f"{row.key}: {text.strip()}")
    return out


def find_self_aliases(rows: list[ExerciseRow]) -> list[str]:
    """Aliases that exist only to paper over the missing normalization.

    "bicep curl" on a row already called "Bicep curls" adds nothing once search
    folds case, punctuation and plurals. They are harmless, but they are a
    symptom: the catalog is hand-maintaining what the matcher should do.
    """
    return [
        f"{r.key}: alias {a!r} collapses onto its own display_name {r.display_name!r}"
        for r in rows
        for a in r.aliases
        if normalize(a) == r.norm_name
    ]


def _plausible_queries(row: ExerciseRow) -> list[str]:
    """Spellings a coach might reasonably type for this exercise.

    Punctuation dropped, hyphens opened up, and the plural flipped — the three
    ways a typed name diverges from the seeded one.
    """
    name = row.display_name
    queries = {
        name.lower(),
        row.norm_name,
        name.lower().replace("-", " "),
        name.lower().replace("-", ""),
        re.sub(r"[^a-z0-9 ]+", "", name.lower()),
        row.norm_name.replace(" ", ""),
    }
    words = row.norm_name.split()
    if words and not words[-1].endswith("s"):
        queries.add(" ".join([*words[:-1], words[-1] + "s"]))
    return [q for q in queries if q.strip()]


def find_search_blind_spots(rows: list[ExerciseRow]) -> list[str]:
    """Reasonable queries that production search fails to match.

    Replays ``ExercisesRepository.search``'s real matcher against each row. A
    zero-hit search is precisely when a coach gives up and creates a duplicate,
    so this doubles as the regression guard for SB-454: if normalization is ever
    weakened, these come back.
    """
    blind = []
    for row in rows:
        payload = {"display_name": row.display_name, "aliases": row.aliases}
        for query in sorted(_plausible_queries(row)):
            if not matches_query(query, payload):
                blind.append(f"{row.key}: searching {query!r} does not match {row.display_name!r}")
    return blind


def find_aliasless(rows: list[ExerciseRow]) -> list[str]:
    """No aliases means search-first selection can't find it, which is how a
    coach ends up creating a second copy under a different name."""
    return [f"{r.key} ({r.display_name})" for r in rows if not r.norm_aliases]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-json", type=Path, help="Live catalog dump instead of migrations")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.82,
        help="Similarity at or above which a pair is reported as a candidate (default 0.82)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Also fail the run on near-duplicate candidates",
    )
    args = parser.parse_args()

    rows = parse_json(args.from_json) if args.from_json else parse_migrations(MIGRATIONS_DIR)
    if not rows:
        print("No exercises found — did the source move?", file=sys.stderr)
        return 2

    source = str(args.from_json) if args.from_json else str(MIGRATIONS_DIR)
    print(f"Exercise catalog audit — {len(rows)} rows from {source}\n")

    hard = find_hard_duplicates(rows)
    near = find_near_duplicates(rows, args.threshold)
    placeholders = find_placeholders(rows)
    aliasless = find_aliasless(rows)

    if hard:
        print(f"FAIL — {len(hard)} hard duplicate(s):")
        for line in hard:
            print(f"  ✗ {line}")
    else:
        print("OK — no identical names and no alias collisions")

    print(f"\nNear-duplicate candidates (>= {args.threshold:.2f}) — review, don't auto-merge:")
    if near:
        for line in near:
            print(f"  ? {line}")
    else:
        print("  none")

    blind = find_search_blind_spots(rows)
    if blind:
        print(f"\nFAIL — {len(blind)} search blind spot(s): the catalog's own name finds")
        print("nothing, so search-first selection fails and a coach creates a second copy:")
        for line in blind:
            print(f"  ✗ {line}")
    else:
        print("\nOK — every row is findable by its own name and plausible misspellings")

    self_aliases = find_self_aliases(rows)
    if self_aliases:
        print(f"\nAliases made redundant by normalization ({len(self_aliases)}) — they")
        print("hand-maintain what a normalizing matcher would do for free:")
        for line in self_aliases:
            print(f"  - {line}")

    if placeholders:
        print("\nUnresolved rows (movement never pinned down):")
        for line in placeholders:
            print(f"  ! {line}")

    if aliasless:
        print(f"\nRows with no aliases ({len(aliasless)}) — invisible to search-first selection,")
        print("which is the main way a duplicate gets created:")
        for line in aliasless:
            print(f"  - {line}")

    if hard or blind:
        return 1
    if args.strict and near:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
