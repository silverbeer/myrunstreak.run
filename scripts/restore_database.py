#!/usr/bin/env python3
"""REST-based restore of an STK data backup into a LOCAL Supabase (SB-224).

Loads a gzip'd JSON dump produced by ``backup_database.py`` into the local
Supabase over the REST API. Clears the run-data tables (child → parent) then
re-inserts them (parent → child), sanitizing foreign keys so only rows that
resolve against local ``users`` survive.

LOCAL ONLY: this truncates tables, so it refuses to run against any URL that is
not 127.0.0.1 / localhost.

Ordering contract (run these BEFORE this script):
    1. `jt supabase sync-users stk` — recreates silverbeer.io@gmail.com locally
       with the SAME prod uid, so runs.user_id resolves.
Then AFTER this script:
    2. `scripts/seed_local_users.py` — owns the coach/athlete test data.

Env:
    SUPABASE_URL          http://127.0.0.1:54321 (local)
    SUPABASE_SERVICE_KEY  local service_role key (SUPABASE_SERVICE_ROLE_KEY also accepted)

Usage:
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... \
      uv run --project backend python scripts/restore_database.py --latest --backup-dir ~/backups/stk
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

from _db_env import is_local, require_env

from supabase import Client, create_client

# Restore order = FK-parent order (parents first). Clearing runs in reverse.
#
# Per table:
#   pk       primary-key column used to clear and to track surviving rows
#   user_col column referencing users.user_id — row dropped if uid not local
#   parents  [(fk_col, parent_table)] — row dropped if fk not among survivors
#   upsert   merge on the pk instead of clear+insert (reference data)
RESTORE_ORDER: list[dict] = [
    {"table": "user_sources", "pk": "id", "user_col": "user_id"},
    {"table": "metric_types", "pk": "key", "upsert": True},
    {
        "table": "runs",
        "pk": "id",
        "user_col": "user_id",
        "parents": [("source_id", "user_sources")],
    },
    {"table": "splits", "pk": "id", "parents": [("run_id", "runs")]},
    {
        "table": "goals",
        "pk": "id",
        "user_col": "user_id",
        "parents": [("source_id", "user_sources")],
    },
    {"table": "metric_entries", "pk": "id", "user_col": "user_id"},
    {"table": "metric_goals", "pk": "id", "user_col": "user_id"},
]

BATCH_SIZE = 100
PAGE_SIZE = 1000


def local_user_ids(sb: Client) -> set[str]:
    """All users.user_id present locally (populated by `jt sync-users`)."""
    result = sb.table("users").select("user_id").execute()
    return {row["user_id"] for row in (result.data or [])}


def clear_table(sb: Client, table: str, pk: str) -> None:
    """Delete every row from a table, paginating to handle >1000 rows."""
    total = 0
    while True:
        result = sb.table(table).select(pk).limit(PAGE_SIZE).execute()
        rows = result.data or []
        if not rows:
            break
        ids = [r[pk] for r in rows]
        for i in range(0, len(ids), BATCH_SIZE):
            chunk = ids[i : i + BATCH_SIZE]
            sb.table(table).delete().in_(pk, chunk).execute()
            total += len(chunk)
        if len(rows) < PAGE_SIZE:
            break
    print(f"  ✓ cleared {total} from {table}")


def sanitize(
    rows: list[dict], spec: dict, local_ids: set[str], survivors: dict[str, set]
) -> list[dict]:
    """Drop rows whose user_id / parent FKs don't resolve locally."""
    user_col = spec.get("user_col")
    parents = spec.get("parents", [])
    kept: list[dict] = []
    dropped = 0
    for row in rows:
        if user_col and row.get(user_col) not in local_ids:
            dropped += 1
            continue
        if any(row.get(col) not in survivors[parent] for col, parent in parents):
            dropped += 1
            continue
        kept.append(row)
    if dropped:
        print(f"  ℹ️  dropped {dropped} row(s) with FK not present locally")
    return kept


def restore_table(
    sb: Client, spec: dict, rows: list[dict], local_ids: set[str], survivors: dict[str, set]
) -> None:
    table, pk = spec["table"], spec["pk"]
    if not rows:
        print(f"Restoring {table}: no data")
        survivors[table] = set()
        return

    rows = sanitize(rows, spec, local_ids, survivors)
    survivors[table] = {row[pk] for row in rows}
    if not rows:
        print(f"Restoring {table}: nothing left after sanitize")
        return

    print(f"Restoring {table} ({len(rows)} rows)...")
    inserted = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        if spec.get("upsert"):
            sb.table(table).upsert(batch, on_conflict=pk).execute()
        else:
            sb.table(table).insert(batch).execute()
        inserted += len(batch)
    print(f"  ✅ {inserted} rows into {table}")


def restore(sb: Client, backup_file: Path) -> None:
    with gzip.open(backup_file, "rt", encoding="utf-8") as f:
        payload = json.load(f)
    if "tables" not in payload:
        raise SystemExit("❌ invalid backup file: no 'tables' key")

    tables = payload["tables"]
    info = payload.get("backup_info", {})
    print(f"Restoring from {backup_file.name} (created {info.get('created_at', '?')})")
    print("=" * 50)

    # Clear child → parent. metric_types is upserted, not cleared (it is
    # reference data seeded by migration and referenced by metric_entries/goals).
    print("🧹 Clearing existing run-data...")
    for spec in reversed(RESTORE_ORDER):
        if spec.get("upsert"):
            continue
        clear_table(sb, spec["table"], spec["pk"])

    local_ids = local_user_ids(sb)
    print(f"🔍 {len(local_ids)} local user(s) for FK sanitization")
    if not local_ids:
        print(
            "  ⚠️  no local users — run `jt supabase sync-users stk` first, "
            "or all run-data will be dropped."
        )

    survivors: dict[str, set] = {}
    print("📥 Restoring parent → child...")
    for spec in RESTORE_ORDER:
        restore_table(sb, spec, tables.get(spec["table"], []), local_ids, survivors)

    print("=" * 50)
    restored = sum(len(s) for s in survivors.values())
    print(f"✅ Restore complete: {restored} rows")


def find_latest(backup_dir: Path) -> Path | None:
    candidates = sorted(backup_dir.glob("stk_backup_*.json.gz"), reverse=True)
    return candidates[0] if candidates else None


def main() -> None:
    parser = argparse.ArgumentParser(description="STK REST data restore (SB-224)")
    parser.add_argument("backup_file", nargs="?", help="Backup file (path or name)")
    parser.add_argument("--latest", action="store_true", help="Use newest backup in --backup-dir")
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=Path.home() / "backups" / "stk",
        help="Directory holding backups (default: ~/backups/stk)",
    )
    args = parser.parse_args()

    url, key = require_env()
    if not is_local(url):
        raise SystemExit(
            f"REFUSING: SUPABASE_URL is not local ({url}). "
            "Restore truncates tables and is local-only."
        )

    if args.latest:
        backup_file = find_latest(args.backup_dir)
        if not backup_file:
            raise SystemExit(f"❌ no backups found in {args.backup_dir}")
    elif args.backup_file:
        backup_file = Path(args.backup_file)
        if not backup_file.is_absolute() and "/" not in args.backup_file:
            backup_file = args.backup_dir / args.backup_file
    else:
        raise SystemExit("❌ specify a backup file or --latest")

    if not backup_file.exists():
        raise SystemExit(f"❌ backup file not found: {backup_file}")

    sb = create_client(url, key)
    try:
        restore(sb, backup_file)
    except Exception as e:  # noqa: BLE001 — top-level guard, surface and exit
        print(f"❌ Restore failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
