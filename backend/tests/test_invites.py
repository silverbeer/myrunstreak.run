"""SB-188: invite-only onboarding — repo round-trip + admin gate + route."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from src.shared.supabase_ops.invites_repository import InvitesRepository


class _FakeQ:
    def __init__(self, store: list[dict[str, Any]]) -> None:
        self.store = store
        self._mode = "select"
        self._payload: Any = None
        self._eq: dict[str, Any] = {}

    def insert(self, payload: Any) -> _FakeQ:
        self._mode, self._payload = "insert", payload
        return self

    def select(self, *a: Any, **k: Any) -> _FakeQ:
        self._mode = "select"
        return self

    def update(self, payload: Any) -> _FakeQ:
        self._mode, self._payload = "update", payload
        return self

    def eq(self, col: str, val: Any) -> _FakeQ:
        self._eq[col] = val
        return self

    def order(self, *a: Any, **k: Any) -> _FakeQ:
        return self

    def _match(self) -> list[dict[str, Any]]:
        return [r for r in self.store if all(r.get(k) == v for k, v in self._eq.items())]

    def execute(self) -> SimpleNamespace:
        if self._mode == "insert":
            row = {
                "id": str(uuid4()),
                "redeemed_at": None,
                "redeemed_by": None,
                "created_at": "2026-06-20T00:00:00+00:00",
                **self._payload,
            }
            self.store.append(row)
            return SimpleNamespace(data=[row])
        if self._mode == "update":
            rows = self._match()
            for r in rows:
                r.update(self._payload)
            return SimpleNamespace(data=rows)
        return SimpleNamespace(data=self._match())


class _FakeClient:
    def __init__(self) -> None:
        self.store: list[dict[str, Any]] = []

    def table(self, _name: str) -> _FakeQ:
        return _FakeQ(self.store)


def test_invite_create_list_get_redeem_roundtrip() -> None:
    repo = InvitesRepository(_FakeClient())  # type: ignore[arg-type]
    admin = uuid4()
    exp = datetime.now(UTC) + timedelta(days=14)

    created = repo.create(admin, "friend@example.com", "tok-abc", exp)
    assert created["token"] == "tok-abc"
    assert created["redeemed_at"] is None

    listed = repo.list_by_creator(admin)
    assert len(listed) == 1 and listed[0]["email"] == "friend@example.com"

    found = repo.get_by_token("tok-abc")
    assert found is not None and found["email"] == "friend@example.com"
    assert repo.get_by_token("nope") is None

    invitee = uuid4()
    redeemed = repo.mark_redeemed("tok-abc", invitee, datetime.now(UTC))
    assert redeemed["redeemed_by"] == str(invitee)
    assert repo.get_by_token("tok-abc")["redeemed_at"] is not None  # type: ignore[index]


def test_require_admin_allows_listed_denies_others() -> None:
    from backend.admin import require_admin

    admin = uuid4()
    other = uuid4()
    settings = SimpleNamespace(admin_ids=lambda: {str(admin).lower()})

    with patch("backend.admin.get_settings", return_value=settings):
        require_admin(admin)  # no raise
        with pytest.raises(HTTPException) as exc:
            require_admin(other)
    assert exc.value.status_code == 403


def test_settings_admin_ids_parsing() -> None:
    from backend.config import Settings

    s = Settings(
        supabase_url="x",
        supabase_anon_key="x",
        supabase_service_role_key="x",
        supabase_jwt_secret="x",
        admin_user_ids=" ABC , def,, ",
    )
    assert s.admin_ids() == {"abc", "def"}


def test_issue_invite_route_denies_non_admin() -> None:
    from backend.routes.invites import issue_invite
    from src.shared.models import InviteCreate

    empty = SimpleNamespace(admin_ids=lambda: set())
    with patch("backend.admin.get_settings", return_value=empty):
        with pytest.raises(HTTPException) as exc:
            issue_invite(InviteCreate(email="x@example.com"), user_id=uuid4())
    assert exc.value.status_code == 403


def test_issue_invite_route_admin_issues_token() -> None:
    from backend.routes.invites import issue_invite
    from src.shared.models import InviteCreate

    admin = uuid4()
    repo = MagicMock()
    repo.create.side_effect = lambda created_by, email, token, expires_at: {
        "id": str(uuid4()),
        "token": token,
        "email": email,
        "created_by": str(created_by),
        "expires_at": expires_at.isoformat(),
        "redeemed_at": None,
        "redeemed_by": None,
        "created_at": "2026-06-20T00:00:00+00:00",
    }

    with (
        patch("backend.routes.invites.require_admin", return_value=None),
        patch("backend.routes.invites.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.invites.InvitesRepository", return_value=repo),
    ):
        out = issue_invite(
            InviteCreate(email="friend@example.com", expires_in_days=7), user_id=admin
        )

    assert out.email == "friend@example.com"
    assert out.token  # a token was generated
    _, kwargs = repo.create.call_args
    assert kwargs["created_by"] == admin
    assert len(kwargs["token"]) >= 32  # token_urlsafe(32)
