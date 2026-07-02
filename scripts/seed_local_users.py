"""Seed a clean set of LOCAL dev users for STK.

Idempotent + local-only (refuses to run against anything but 127.0.0.1/localhost
Supabase). Produces:

    admin@test.local / admin123   -> admin role
    coach@test.local / coach123   -> coach role, coaches both athletes below
    a1@test.local    / a12345     -> athlete "Athlete One" (logs in as self)
    a2@test.local    / a12345     -> athlete "Athlete Two" (logs in as self)

Removes ad-hoc throwaway users (p42.*, coach.verify*). Leaves any other user
(e.g. silverbeer.io@gmail.com from `jt sync-users`) untouched.

Run:
    eval "$(supabase status -o env | sed 's/^/export SB_/')"
    SUPABASE_URL=$SB_API_URL SERVICE_KEY=$SB_SERVICE_ROLE_KEY \
      uv run python scripts/seed_local_users.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

URL = os.environ.get("SUPABASE_URL", "http://127.0.0.1:54321").rstrip("/")
KEY = os.environ.get("SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not any(h in URL for h in ("127.0.0.1", "localhost")):
    sys.exit(f"REFUSING: SUPABASE_URL is not local ({URL}). This script is local-only.")
if not KEY:
    sys.exit("Missing SERVICE_KEY / SUPABASE_SERVICE_ROLE_KEY.")

H = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}


def _req(method: str, path: str, body: dict | list | None = None, headers: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        URL + path, data=data, method=method, headers={**H, **(headers or {})}
    )
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} -> {e.code}: {e.read().decode()[:200]}") from e


def list_auth_users() -> list[dict]:
    out = _req("GET", "/auth/v1/admin/users?per_page=200")
    return out.get("users", out) if isinstance(out, dict) else out


def auth_by_email(email: str) -> dict | None:
    return next((u for u in list_auth_users() if u.get("email") == email), None)


def delete_auth_user(uid: str) -> None:
    _req("DELETE", f"/auth/v1/admin/users/{uid}")


def create_auth_user(email: str, password: str) -> str:
    out = _req(
        "POST",
        "/auth/v1/admin/users",
        {"email": email, "password": password, "email_confirm": True},
    )
    return out["id"]


def set_password(uid: str, password: str) -> None:
    _req("PUT", f"/auth/v1/admin/users/{uid}", {"password": password, "email_confirm": True})


def rest(method: str, table: str, body=None, params: str = "", prefer: str = "") -> list:
    headers = {"Prefer": prefer} if prefer else {}
    out = _req(method, f"/rest/v1/{table}{params}", body, headers)
    return out or []


def main() -> None:
    users = list_auth_users()

    # 1. Purge ad-hoc throwaway users.
    for u in users:
        email = u["email"] or ""
        if email.startswith("p42.") or email.startswith("coach.verify"):
            delete_auth_user(u["id"])
            print(f"deleted junk user {email}")

    # 2. Ensure each target user: update-in-place if present (stable uid, just
    # reset the password), else create. Clear any orphaned public.users rows
    # sharing the email under a different uid (+ their roles), then upsert the
    # users row keyed on the live auth uid.
    def ensure_user(email: str, password: str) -> str:
        au = auth_by_email(email)
        if au:
            uid = au["id"]
            set_password(uid, password)
        else:
            uid = create_auth_user(email, password)
        orphans = [
            o["user_id"]
            for o in rest(
                "GET", "users", params=f"?email=eq.{email}&user_id=neq.{uid}&select=user_id"
            )
        ]
        # Free the email off any orphan row so the live row can take it.
        for oid in orphans:
            rest("PATCH", "users", {"email": f"stale+{oid}@local"}, params=f"?user_id=eq.{oid}")
        rest(
            "POST", "users", {"user_id": uid, "email": email}, prefer="resolution=merge-duplicates"
        )
        # Now the live users row exists: repoint the orphan's deps onto it, then
        # drop the orphan (athletes.created_by is NOT NULL, so it must move first).
        for oid in orphans:
            rest("PATCH", "athletes", {"created_by": uid}, params=f"?created_by=eq.{oid}")
            rest("DELETE", "coach_athletes", params=f"?coach_id=eq.{oid}")
            rest("DELETE", "user_roles", params=f"?user_id=eq.{oid}")
            rest("DELETE", "users", params=f"?user_id=eq.{oid}")
        print(f"user {email} -> {uid[:8]}")
        return uid

    admin_id = ensure_user("admin@test.local", "admin123")
    coach_id = ensure_user("coach@test.local", "coach123")
    a1_uid = ensure_user("a1@test.local", "a12345")
    a2_uid = ensure_user("a2@test.local", "a12345")

    # 3. Roles.
    rest(
        "POST",
        "user_roles",
        {"user_id": admin_id, "role": "admin"},
        prefer="resolution=merge-duplicates",
    )
    rest(
        "POST",
        "user_roles",
        {"user_id": coach_id, "role": "coach"},
        prefer="resolution=merge-duplicates",
    )

    # 4. Athletes coached by coach@, each linked to its login user.
    def ensure_athlete(display_name: str, linked_uid: str) -> None:
        # Match by name only so a row left over from an earlier run gets reused
        # (and re-pointed) rather than duplicated.
        existing = rest(
            "GET",
            "athletes",
            params=f"?display_name=eq.{display_name.replace(' ', '%20')}&select=id",
        )
        if existing:
            aid = existing[0]["id"]
        else:
            aid = rest(
                "POST",
                "athletes",
                {"created_by": coach_id, "display_name": display_name},
                prefer="return=representation",
            )[0]["id"]
        rest(
            "PATCH",
            "athletes",
            {"created_by": coach_id, "linked_user_id": linked_uid},
            params=f"?id=eq.{aid}",
        )
        # active coaching link (idempotent-ish: only insert if absent)
        link = rest(
            "GET",
            "coach_athletes",
            params=f"?coach_id=eq.{coach_id}&athlete_id=eq.{aid}&status=eq.active&select=id",
        )
        if not link:
            rest("POST", "coach_athletes", {"coach_id": coach_id, "athlete_id": aid})
        print(f"athlete '{display_name}' -> {aid[:8]} linked {linked_uid[:8]}")

    ensure_athlete("Athlete One", a1_uid)
    ensure_athlete("Athlete Two", a2_uid)

    print("\nseeded local users:")
    print("  admin@test.local / admin123   (admin)")
    print("  coach@test.local / coach123   (coach)")
    print("  a1@test.local    / a12345     (Athlete One)")
    print("  a2@test.local    / a12345     (Athlete Two)")


if __name__ == "__main__":
    main()
