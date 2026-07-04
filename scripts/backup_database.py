#!/usr/bin/env python3
"""REST-based production data dump for STK (SB-224).

Dumps STK's run-data tables over the Supabase REST API (HTTPS, IPv4-safe) into
a gzip'd JSON file. This is the IPv4-safe alternative to ``pg_dump``: the prod
direct DB host is IPv6-only and the session pooler rejects the tenant on this
network, so we go through PostgREST with the service-role key instead.

Only run-data tables are dumped — the tables that power the dashboard's
personal bests, streak, records and goals. Auth users, OAuth tokens and invites
are intentionally excluded (managed per-environment).

Env:
    SUPABASE_URL          e.g. https://dnwllbukmvdddwhlsmqb.supabase.co (prod)
    SUPABASE_SERVICE_KEY  prod service_role key (SUPABASE_SERVICE_ROLE_KEY also accepted)

Usage:
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... \
      uv run --project backend python scripts/backup_database.py --backup-dir ~/backups/stk
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from datetime import datetime
from pathlib import Path

from _db_env import require_env

from supabase import Client, create_client

# Run-data tables in FK-parent order (parents first). This is the data that
# powers the dashboard: PB / streak / records / monthly + yearly goals.
#
#   users ─┬─ user_sources ─┬─ runs ── splits
#          │                └─ goals
#          └─ (runs/goals also ref users)
#   metric_types ─┬─ metric_entries
#                 └─ metric_goals
#
# public.users is dumped (no secrets — just user_id/email/display_name) so the
# restore has a FK target. On restore it is gated to local auth.users, so only
# prod users that `jt sync-users` recreated locally get added.
#
# EXCLUDED (managed per-environment, contain secrets, or per-env identity):
#   auth.users        -> handled by `jt supabase sync-users stk`
#   oauth tokens      -> stripped from user_sources below; never leave prod
#   invites           -> per-environment
#   coach/athlete dom -> owned by scripts/seed_local_users.py locally
BACKUP_TABLES = [
    "users",
    "user_sources",
    "metric_types",
    "runs",
    "splits",
    "goals",
    "metric_entries",
    "metric_goals",
]

# Columns scrubbed to NULL before the dump ever touches disk. user_sources rows
# are needed because runs.source_id / goals.source_id reference them (NOT NULL),
# but the OAuth secrets they carry must never land in a backup file on a laptop.
SENSITIVE_COLUMNS: dict[str, list[str]] = {
    "user_sources": [
        "access_token",
        "refresh_token",
        "token_expires_at",
        "access_token_secret",
    ],
}

PAGE_SIZE = 1000


def dump_table(sb: Client, table: str) -> list[dict]:
    """Fetch every row of a table, paginating in PAGE_SIZE chunks."""
    print(f"Dumping {table}...")
    rows: list[dict] = []
    offset = 0
    while True:
        result = sb.table(table).select("*").range(offset, offset + PAGE_SIZE - 1).execute()
        batch = result.data or []
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    scrub = SENSITIVE_COLUMNS.get(table)
    if scrub:
        for row in rows:
            for col in scrub:
                if col in row:
                    row[col] = None
        print(f"  🔒 scrubbed {', '.join(scrub)}")

    print(f"  ✓ {len(rows)} rows")
    return rows


def create_backup(sb: Client, url: str, backup_dir: Path) -> Path:
    """Dump all run-data tables into a single gzip'd JSON file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_file = backup_dir / f"stk_backup_{timestamp}.json.gz"

    print(f"Creating STK data backup: {backup_file}")
    print("=" * 50)

    payload: dict = {
        "backup_info": {
            "timestamp": timestamp,
            "created_at": datetime.now().isoformat(),
            "source_url": url,
            "version": "1.0",
        },
        "tables": {},
    }
    for table in BACKUP_TABLES:
        payload["tables"][table] = dump_table(sb, table)

    with gzip.open(backup_file, "wt", encoding="utf-8") as f:
        json.dump(payload, f, default=str)

    total = sum(len(v) for v in payload["tables"].values())
    print("=" * 50)
    print(f"✅ Backup complete: {backup_file}")
    print(
        f"📊 {backup_file.stat().st_size / 1024:.1f} KB, {total} rows across {len(BACKUP_TABLES)} tables"
    )
    return backup_file


def main() -> None:
    parser = argparse.ArgumentParser(description="STK REST data backup (SB-224)")
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=Path.home() / "backups" / "stk",
        help="Directory to write the backup into (default: ~/backups/stk)",
    )
    args = parser.parse_args()

    url, key = require_env()
    sb = create_client(url, key)
    try:
        create_backup(sb, url, args.backup_dir)
    except Exception as e:  # noqa: BLE001 — top-level guard, surface and exit
        print(f"❌ Backup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
