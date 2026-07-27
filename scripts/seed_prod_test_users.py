"""Seed the flagged PROD test accounts for STK (SB-368).

The mirror image of ``seed_local_users.py``: that one refuses to run against
anything but localhost, this one refuses to run against localhost. It is
deliberately non-destructive — it never deletes an auth user, never touches a
row outside the test-email domain, and re-running it is a no-op.

Creates (all with ``is_test_account = TRUE``):

    coach@test.myrunstreak.run   -> roles: coach + runner
    runner@test.myrunstreak.run  -> roles: runner
    a1@test.myrunstreak.run      -> roles: runner; athlete "Test Athlete One",
                                    linked to this login and coached by coach@

``coach@`` holding two roles is the working proof that ``user_roles``
(PK ``(user_id, role)``) supports a coach who also runs.

The domain has no MX record, so mail to these addresses dead-ends. Accounts are
created with ``email_confirm: true``, so no mail is ever sent to them either.

Requires migration 20260727000000 (runner role + is_test_account).

Run:
    export SUPABASE_URL=https://<prod-ref>.supabase.co
    export SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
    export STK_TEST_PASSWORD=<password for all three logins; 6+ chars>
    uv run python scripts/seed_prod_test_users.py --confirm-prod

    # see what it would do, touching nothing:
    uv run python scripts/seed_prod_test_users.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

TEST_DOMAIN = "test.myrunstreak.run"

COACH_EMAIL = f"coach@{TEST_DOMAIN}"
RUNNER_EMAIL = f"runner@{TEST_DOMAIN}"
ATHLETE_EMAIL = f"a1@{TEST_DOMAIN}"
ATHLETE_NAME = "Test Athlete One"

# email -> (display_name, granted roles)
ACCOUNTS: dict[str, tuple[str, tuple[str, ...]]] = {
    COACH_EMAIL: ("Test Coach", ("coach", "runner")),
    RUNNER_EMAIL: ("Test Runner", ("runner",)),
    ATHLETE_EMAIL: ("Test Athlete One", ("runner",)),
}

_LOCAL_HOSTS = ("127.0.0.1", "localhost", "0.0.0.0", "::1", "host.docker.internal")

# Supabase Auth's default minimum. Matching it keeps these hand-typed test
# logins as short as the platform allows (seed_local_users.py uses 6-8 too).
MIN_PASSWORD_LEN = 6


# --------------------------------------------------------------------------- #
# Guards — pure, so they are unit-testable without a live project
# --------------------------------------------------------------------------- #
class GuardError(RuntimeError):
    """A safety precondition was not met. Never raised mid-write."""


def assert_not_local(url: str) -> None:
    """This script writes real accounts; running it at a local stack is a mistake.

    Use ``seed_local_users.py`` for that — it seeds a richer set and is free to
    delete rows, which this script must never do.
    """
    if not url:
        raise GuardError("SUPABASE_URL is not set.")
    if any(h in url for h in _LOCAL_HOSTS):
        raise GuardError(
            f"REFUSING: SUPABASE_URL looks local ({url}). Use seed_local_users.py instead."
        )


def assert_test_domain(email: str) -> None:
    """No row outside the test domain may ever be written by this script."""
    if not email.endswith(f"@{TEST_DOMAIN}"):
        raise GuardError(f"REFUSING: {email!r} is not on @{TEST_DOMAIN}.")


def assert_confirmed(confirmed: bool, dry_run: bool) -> None:
    if not (confirmed or dry_run):
        raise GuardError(
            "REFUSING: pass --confirm-prod to write to a remote project (or --dry-run to preview)."
        )


def assert_password(password: str) -> None:
    """Passwords come from the environment; nothing is ever hardcoded here.

    The floor is Supabase Auth's own default minimum, not a stricter house rule:
    these accounts are typed by hand during manual testing, they hold no data,
    and they carry ``is_test_account``. Anything shorter fails at the admin API
    anyway, so checking here just turns a 422 into a readable message.
    """
    if not password:
        raise GuardError("STK_TEST_PASSWORD is not set.")
    if len(password) < MIN_PASSWORD_LEN:
        raise GuardError(
            f"STK_TEST_PASSWORD must be at least {MIN_PASSWORD_LEN} characters "
            "(Supabase Auth's minimum)."
        )


# --------------------------------------------------------------------------- #
# Supabase REST / admin API
# --------------------------------------------------------------------------- #
_SECRET_KEYS = frozenset({"password", "access_token", "refresh_token"})


def _redact(body: Any) -> Any:
    """Mask secrets before a dry run prints a request body to the terminal.

    ``--dry-run`` needs no password, but it does not *reject* one either — so
    without this, previewing with STK_TEST_PASSWORD exported would echo it into
    the scrollback and any CI log.
    """
    if isinstance(body, dict):
        return {k: ("***" if k in _SECRET_KEYS else v) for k, v in body.items()}
    if isinstance(body, list):
        return [_redact(item) for item in body]
    return body


class Client:
    def __init__(self, url: str, key: str, *, dry_run: bool = False):
        self.url = url.rstrip("/")
        self.key = key
        self.dry_run = dry_run
        self._placeholders = 0
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    def next_placeholder_id(self) -> str:
        """A stand-in id for a row a dry run did not actually insert.

        It must be a syntactically valid UUID: these ids flow straight into
        PostgREST filters (`user_id=neq.…`, `athlete_id=eq.…`) and Postgres
        rejects anything else with a 22P02 before the query runs. The zero
        prefix guarantees no real row collides, so the conflict checks a dry
        run performs still report truthfully.
        """
        self._placeholders += 1
        # The counter is repeated in the first group so the abbreviated `id[:8]`
        # the plan prints stays distinguishable between accounts.
        return f"000000{self._placeholders:02d}-0000-0000-0000-{self._placeholders:012d}"

    def _req(
        self,
        method: str,
        path: str,
        body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        if self.dry_run and method != "GET":
            shown = json.dumps(_redact(body)) if body else ""
            print(f"  [dry-run] {method} {path} {shown}".rstrip())
            return None
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            self.url + path, data=data, method=method, headers={**self.headers, **(headers or {})}
        )
        try:
            with urllib.request.urlopen(req) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{method} {path} -> {e.code}: {e.read().decode()[:300]}") from e

    def rest(self, method: str, table: str, body: Any = None, params: str = "", prefer: str = ""):
        out = self._req(
            method, f"/rest/v1/{table}{params}", body, {"Prefer": prefer} if prefer else None
        )
        return out or []

    # -- auth admin ---------------------------------------------------------
    def auth_by_email(self, email: str) -> dict[str, Any] | None:
        out = self._req("GET", f"/auth/v1/admin/users?per_page=200&filter={email}")
        users = out.get("users", []) if isinstance(out, dict) else (out or [])
        return next((u for u in users if u.get("email") == email), None)

    def create_auth_user(self, email: str, password: str) -> str:
        out = self._req(
            "POST",
            "/auth/v1/admin/users",
            {"email": email, "password": password, "email_confirm": True},
        )
        # dry-run skips the POST, so there is no id to read back.
        return out["id"] if out else self.next_placeholder_id()

    def set_password(self, uid: str, password: str) -> None:
        self._req("PUT", f"/auth/v1/admin/users/{uid}", {"password": password})


def assert_migration_applied(client: Client) -> None:
    """Fail early and clearly if migration 20260727000000 has not been pushed."""
    try:
        client.rest("GET", "users", params="?select=is_test_account&limit=1")
    except RuntimeError as exc:
        raise GuardError(
            "REFUSING: `users.is_test_account` is missing — apply migration "
            "20260727000000_runner_role_and_test_accounts first "
            "(Supabase Migrations workflow, confirm with 'migrate').\n"
            f"  underlying error: {exc}"
        ) from exc


# --------------------------------------------------------------------------- #
# Seeding
# --------------------------------------------------------------------------- #
def ensure_login(client: Client, email: str, display_name: str, password: str) -> str:
    """Create-or-update the auth user and its `users` row. Returns the uid.

    Unlike the local seeder this never deletes or re-points orphan rows: on prod
    an unexpected duplicate is a situation for a human, not for a script.
    """
    assert_test_domain(email)
    existing = client.auth_by_email(email)
    if existing:
        uid = existing["id"]
        client.set_password(uid, password)
        print(f"  login {email} -> {uid[:8]} (existing, password reset)")
    else:
        uid = client.create_auth_user(email, password)
        print(f"  login {email} -> {uid[:8]} (created)")

    conflicting = [
        row["user_id"]
        for row in client.rest(
            "GET", "users", params=f"?email=eq.{email}&user_id=neq.{uid}&select=user_id"
        )
    ]
    if conflicting:
        raise GuardError(
            f"REFUSING: `users` rows {conflicting} already hold {email} under a different "
            "id. Resolve by hand — this script will not repoint prod rows."
        )

    client.rest(
        "POST",
        "users",
        {"user_id": uid, "email": email, "display_name": display_name, "is_test_account": True},
        prefer="resolution=merge-duplicates",
    )
    return uid


def grant_roles(client: Client, uid: str, roles: tuple[str, ...]) -> None:
    for role in roles:
        client.rest(
            "POST",
            "user_roles",
            {"user_id": uid, "role": role},
            prefer="resolution=merge-duplicates",
        )
    print(f"  roles {'+'.join(roles)}")


def ensure_athlete(client: Client, *, coach_id: str, linked_uid: str, display_name: str) -> None:
    """The athlete row for a1@, linked to its login and coached by coach@.

    Matched on `linked_user_id` (stable) rather than display name, so renaming
    the athlete in the UI doesn't make a re-run create a duplicate.
    """
    existing = client.rest("GET", "athletes", params=f"?linked_user_id=eq.{linked_uid}&select=id")
    if existing:
        athlete_id = existing[0]["id"]
        client.rest(
            "PATCH",
            "athletes",
            {"display_name": display_name, "is_test_account": True},
            params=f"?id=eq.{athlete_id}",
        )
        print(f"  athlete {display_name!r} -> {athlete_id[:8]} (existing)")
    else:
        created = client.rest(
            "POST",
            "athletes",
            {
                "created_by": coach_id,
                "linked_user_id": linked_uid,
                "display_name": display_name,
                "is_test_account": True,
            },
            prefer="return=representation",
        )
        athlete_id = created[0]["id"] if created else client.next_placeholder_id()
        print(f"  athlete {display_name!r} -> {athlete_id[:8]} (created)")

    link = client.rest(
        "GET",
        "coach_athletes",
        params=f"?coach_id=eq.{coach_id}&athlete_id=eq.{athlete_id}&status=eq.active&select=id",
    )
    if link:
        print("  coach link already active")
    else:
        client.rest("POST", "coach_athletes", {"coach_id": coach_id, "athlete_id": athlete_id})
        print("  coach link created")


def seed(client: Client, password: str) -> None:
    assert_migration_applied(client)

    uids: dict[str, str] = {}
    for email, (display_name, roles) in ACCOUNTS.items():
        print(f"\n{email}")
        uid = ensure_login(client, email, display_name, password)
        grant_roles(client, uid, roles)
        uids[email] = uid

    print(f"\n{ATHLETE_NAME}")
    ensure_athlete(
        client,
        coach_id=uids[COACH_EMAIL],
        linked_uid=uids[ATHLETE_EMAIL],
        display_name=ATHLETE_NAME,
    )

    print("\nseeded prod test accounts (password from $STK_TEST_PASSWORD):")
    for email, (_, roles) in ACCOUNTS.items():
        print(f"  {email:<32} {'+'.join(roles)}")
    print(f"  {ATHLETE_NAME} — linked to {ATHLETE_EMAIL}, coached by {COACH_EMAIL}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-prod", action="store_true", help="required to write to a remote project"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print the writes instead of performing them"
    )
    args = parser.parse_args(argv)

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SERVICE_KEY", "")
    password = os.environ.get("STK_TEST_PASSWORD", "")

    try:
        assert_not_local(url)
        assert_confirmed(args.confirm_prod, args.dry_run)
        if not key:
            raise GuardError("SUPABASE_SERVICE_ROLE_KEY is not set.")
        if not args.dry_run:
            assert_password(password)
    except GuardError as exc:
        print(exc, file=sys.stderr)
        return 1

    print(f"target: {url}{' (DRY RUN)' if args.dry_run else ''}")
    seed(Client(url, key, dry_run=args.dry_run), password)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
