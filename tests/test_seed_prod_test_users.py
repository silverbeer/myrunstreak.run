"""Tests for scripts/seed_prod_test_users.py (SB-368).

The script writes real accounts to prod, so its safety rails are the part worth
testing: refuse localhost, refuse without confirmation, refuse a weak or absent
password, refuse anything off the test domain, refuse before the migration is
applied, and never repoint an existing prod row. The seeding itself is checked
against a fake client that records the REST calls.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "seed_prod_test_users.py"
_spec = importlib.util.spec_from_file_location("seed_prod_test_users", _PATH)
assert _spec and _spec.loader
seed_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed_mod)

GuardError = seed_mod.GuardError
PROD_URL = "https://abcdefgh.supabase.co"


# --------------------------------------------------------------------------- #
# Guards
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:54321",
        "http://localhost:54321",
        "http://0.0.0.0:54321",
        "http://host.docker.internal:54321",
    ],
)
def test_refuses_local_supabase_urls(url: str) -> None:
    with pytest.raises(GuardError, match="REFUSING"):
        seed_mod.assert_not_local(url)


def test_refuses_empty_supabase_url() -> None:
    with pytest.raises(GuardError):
        seed_mod.assert_not_local("")


def test_accepts_a_remote_supabase_url() -> None:
    seed_mod.assert_not_local(PROD_URL)  # no raise


def test_refuses_emails_off_the_test_domain() -> None:
    with pytest.raises(GuardError, match="test.myrunstreak.run"):
        seed_mod.assert_test_domain("silverbeer.io@gmail.com")


def test_refuses_a_lookalike_domain_suffix() -> None:
    # "eviltest.myrunstreak.run" must not pass as "test.myrunstreak.run".
    with pytest.raises(GuardError):
        seed_mod.assert_test_domain("a1@eviltest.myrunstreak.run.example.com")


def test_accepts_the_configured_test_accounts() -> None:
    for email in seed_mod.ACCOUNTS:
        seed_mod.assert_test_domain(email)  # no raise


def test_requires_confirmation_to_write() -> None:
    with pytest.raises(GuardError, match="--confirm-prod"):
        seed_mod.assert_confirmed(False, False)


def test_dry_run_needs_no_confirmation() -> None:
    seed_mod.assert_confirmed(False, True)  # no raise


@pytest.mark.parametrize("password", ["", "abc", "12345"])
def test_refuses_missing_or_too_short_password(password: str) -> None:
    with pytest.raises(GuardError):
        seed_mod.assert_password(password)


@pytest.mark.parametrize("password", ["a12345", "coach123", "a-long-enough-password"])
def test_accepts_anything_supabase_would_accept(password: str) -> None:
    """The floor is Supabase Auth's minimum, not a stricter house rule — these
    are hand-typed test logins, and seed_local_users.py already uses 6-8."""
    seed_mod.assert_password(password)  # no raise


def test_password_floor_matches_supabase_minimum() -> None:
    assert seed_mod.MIN_PASSWORD_LEN == 6


# --------------------------------------------------------------------------- #
# Dry-run mode on the real Client
#
# These exercise the real Client, not the fake — the dry-run defect that shipped
# in SB-368 lived entirely in the branches the fake never reached.
# --------------------------------------------------------------------------- #
def _dry_client() -> Any:
    return seed_mod.Client(PROD_URL, "service-key", dry_run=True)


def test_dry_run_placeholder_ids_are_valid_uuids() -> None:
    """They land in PostgREST filters; Postgres rejects anything else (22P02)."""
    client = _dry_client()

    for _ in range(3):
        UUID(client.next_placeholder_id())  # raises if malformed


def test_dry_run_placeholder_ids_are_unique() -> None:
    client = _dry_client()

    ids = [client.next_placeholder_id() for _ in range(5)]

    assert len(set(ids)) == 5


def test_dry_run_created_auth_user_id_is_a_valid_uuid() -> None:
    """The SB-376 regression: this used to return '<new:email>' and 400 downstream."""
    client = _dry_client()

    uid = client.create_auth_user(seed_mod.COACH_EMAIL, "a-long-password")

    UUID(uid)


def test_dry_run_placeholders_cannot_collide_with_real_rows() -> None:
    """Zero-heavy, so a dry run's conflict checks still report truthfully."""
    client = _dry_client()

    assert client.next_placeholder_id().startswith("000000")


def test_dry_run_placeholders_differ_in_their_abbreviated_form() -> None:
    """The plan prints id[:8]; identical prefixes would make it unreadable."""
    client = _dry_client()

    shorts = [client.next_placeholder_id()[:8] for _ in range(3)]

    assert len(set(shorts)) == 3


def test_dry_run_redacts_the_password_from_printed_bodies(capsys: Any) -> None:
    """--dry-run takes no password but doesn't reject one; it must not echo it."""
    client = _dry_client()

    client.create_auth_user(seed_mod.COACH_EMAIL, "hunter2-hunter2")

    out = capsys.readouterr().out
    assert "hunter2-hunter2" not in out
    assert '"password": "***"' in out


def test_redact_leaves_ordinary_fields_alone() -> None:
    assert seed_mod._redact({"email": "a@b.c", "password": "s3cret"}) == {
        "email": "a@b.c",
        "password": "***",
    }


def test_redact_handles_list_payloads() -> None:
    assert seed_mod._redact([{"password": "s3cret"}]) == [{"password": "***"}]


def test_dry_run_performs_no_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any non-GET reaching urlopen in dry-run mode is a bug."""

    def _explode(*args: Any, **kwargs: Any):
        raise AssertionError("dry run attempted a network call")

    monkeypatch.setattr(seed_mod.urllib.request, "urlopen", _explode)
    client = _dry_client()

    client.rest("POST", "users", {"user_id": "x"})  # no raise
    client.create_auth_user(seed_mod.COACH_EMAIL, "a-long-password")
    client.set_password("00000000-0000-0000-0000-000000000001", "a-long-password")


# --------------------------------------------------------------------------- #
# Fake client
# --------------------------------------------------------------------------- #
class _FakeClient:
    """Records REST/admin calls; serves canned GET results keyed by table."""

    def __init__(
        self, gets: dict[str, list[dict[str, Any]]] | None = None, *, users_ok: bool = True
    ):
        self.gets = gets or {}
        self.users_ok = users_ok
        self.calls: list[tuple[str, str, Any, str]] = []
        self.auth_users: dict[str, dict[str, Any]] = {}
        self.created: list[str] = []
        self.passwords_set: list[str] = []
        self.placeholders = 0
        self.representation: list[dict[str, Any]] | None = None

    def rest(self, method: str, table: str, body: Any = None, params: str = "", prefer: str = ""):
        if table == "users" and "is_test_account" in params and not self.users_ok:
            raise RuntimeError(
                "GET /rest/v1/users -> 400: column users.is_test_account does not exist"
            )
        self.calls.append((method, table, body, params))
        if method == "GET":
            return list(self.gets.get(table, []))
        if prefer == "return=representation":
            # None models a dry run: the insert is skipped, so nothing comes back.
            return (
                self.representation
                if self.representation is not None
                else [{"id": "11111111-1111-1111-1111-111111111111"}]
            )
        return []

    def auth_by_email(self, email: str):
        return self.auth_users.get(email)

    def create_auth_user(self, email: str, password: str) -> str:
        self.created.append(email)
        uid = f"uid-{len(self.created)}"
        self.auth_users[email] = {"id": uid}
        return uid

    def set_password(self, uid: str, password: str) -> None:
        self.passwords_set.append(uid)

    def next_placeholder_id(self) -> str:
        self.placeholders += 1
        return f"00000000-0000-0000-0000-{self.placeholders:012d}"

    # -- helpers ------------------------------------------------------------
    def writes_to(self, table: str) -> list[Any]:
        return [body for m, t, body, _ in self.calls if t == table and m in ("POST", "PATCH")]


# --------------------------------------------------------------------------- #
# assert_migration_applied
# --------------------------------------------------------------------------- #
def test_refuses_when_is_test_account_column_is_missing() -> None:
    with pytest.raises(GuardError, match="20260727000000"):
        seed_mod.assert_migration_applied(_FakeClient(users_ok=False))


def test_proceeds_when_the_column_exists() -> None:
    seed_mod.assert_migration_applied(_FakeClient())  # no raise


# --------------------------------------------------------------------------- #
# ensure_login
# --------------------------------------------------------------------------- #
def test_ensure_login_creates_and_flags_the_users_row() -> None:
    client = _FakeClient()

    uid = seed_mod.ensure_login(client, seed_mod.COACH_EMAIL, "Test Coach", "a-long-password")

    assert client.created == [seed_mod.COACH_EMAIL]
    row = client.writes_to("users")[0]
    assert row == {
        "user_id": uid,
        "email": seed_mod.COACH_EMAIL,
        "display_name": "Test Coach",
        "is_test_account": True,
    }


def test_ensure_login_reuses_an_existing_auth_user() -> None:
    client = _FakeClient()
    client.auth_users[seed_mod.COACH_EMAIL] = {"id": "existing-uid"}

    uid = seed_mod.ensure_login(client, seed_mod.COACH_EMAIL, "Test Coach", "a-long-password")

    assert uid == "existing-uid"
    assert client.created == []  # no duplicate auth user
    assert client.passwords_set == ["existing-uid"]


def test_ensure_login_refuses_to_repoint_a_conflicting_prod_row() -> None:
    """The local seeder repoints orphans; on prod that is a human's decision."""
    client = _FakeClient(gets={"users": [{"user_id": "someone-else"}]})

    with pytest.raises(GuardError, match="Resolve by hand"):
        seed_mod.ensure_login(client, seed_mod.COACH_EMAIL, "Test Coach", "a-long-password")


def test_ensure_login_refuses_an_email_off_the_test_domain() -> None:
    client = _FakeClient()

    with pytest.raises(GuardError):
        seed_mod.ensure_login(client, "silverbeer.io@gmail.com", "Owner", "a-long-password")

    assert client.created == []


# --------------------------------------------------------------------------- #
# grant_roles / ensure_athlete
# --------------------------------------------------------------------------- #
def test_grant_roles_writes_one_row_per_role() -> None:
    client = _FakeClient()

    seed_mod.grant_roles(client, "uid-1", ("coach", "runner"))

    assert client.writes_to("user_roles") == [
        {"user_id": "uid-1", "role": "coach"},
        {"user_id": "uid-1", "role": "runner"},
    ]


def test_ensure_athlete_creates_flagged_row_and_coach_link() -> None:
    client = _FakeClient()

    seed_mod.ensure_athlete(
        client, coach_id="coach-uid", linked_uid="a1-uid", display_name="Test Athlete One"
    )

    athlete = client.writes_to("athletes")[0]
    assert athlete["created_by"] == "coach-uid"
    assert athlete["linked_user_id"] == "a1-uid"
    assert athlete["is_test_account"] is True
    assert client.writes_to("coach_athletes") == [
        {"coach_id": "coach-uid", "athlete_id": "11111111-1111-1111-1111-111111111111"}
    ]


def test_ensure_athlete_falls_back_to_a_valid_uuid_when_the_insert_returns_nothing() -> None:
    """Dry run: the athlete id still has to survive the coach_athletes filter."""
    client = _FakeClient()
    client.representation = []  # insert skipped, nothing echoed back

    seed_mod.ensure_athlete(
        client, coach_id="coach-uid", linked_uid="a1-uid", display_name="Test Athlete One"
    )

    athlete_id = client.writes_to("coach_athletes")[0]["athlete_id"]
    UUID(athlete_id)


def test_ensure_athlete_is_idempotent_on_rerun() -> None:
    """Existing athlete + active link -> patch only, no second athlete or link."""
    client = _FakeClient(
        gets={"athletes": [{"id": "athlete-1"}], "coach_athletes": [{"id": "link-1"}]}
    )

    seed_mod.ensure_athlete(
        client, coach_id="coach-uid", linked_uid="a1-uid", display_name="Test Athlete One"
    )

    assert [m for m, t, _, _ in client.calls if t == "athletes"] == ["GET", "PATCH"]
    assert client.writes_to("coach_athletes") == []


def test_ensure_athlete_matches_on_linked_user_not_display_name() -> None:
    """Renaming the athlete in the UI must not cause a duplicate on re-run."""
    client = _FakeClient(gets={"athletes": [{"id": "athlete-1"}]})

    seed_mod.ensure_athlete(
        client, coach_id="coach-uid", linked_uid="a1-uid", display_name="Renamed Athlete"
    )

    lookup = next(params for m, t, _, params in client.calls if t == "athletes" and m == "GET")
    assert "linked_user_id=eq.a1-uid" in lookup
    assert "display_name" not in lookup


# --------------------------------------------------------------------------- #
# main() guard wiring
# --------------------------------------------------------------------------- #
def test_main_refuses_local_url(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "key")
    monkeypatch.setenv("STK_TEST_PASSWORD", "a-long-password")

    assert seed_mod.main(["--confirm-prod"]) == 1
    assert "REFUSING" in capsys.readouterr().err


def test_main_refuses_without_confirmation(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    monkeypatch.setenv("SUPABASE_URL", PROD_URL)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "key")
    monkeypatch.setenv("STK_TEST_PASSWORD", "a-long-password")

    assert seed_mod.main([]) == 1
    assert "--confirm-prod" in capsys.readouterr().err


def test_main_refuses_without_service_key(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    monkeypatch.setenv("SUPABASE_URL", PROD_URL)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SERVICE_KEY", raising=False)
    monkeypatch.setenv("STK_TEST_PASSWORD", "a-long-password")

    assert seed_mod.main(["--confirm-prod"]) == 1
    assert "SERVICE_ROLE_KEY" in capsys.readouterr().err


def test_main_refuses_without_password(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    monkeypatch.setenv("SUPABASE_URL", PROD_URL)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "key")
    monkeypatch.delenv("STK_TEST_PASSWORD", raising=False)

    assert seed_mod.main(["--confirm-prod"]) == 1
    assert "STK_TEST_PASSWORD" in capsys.readouterr().err
