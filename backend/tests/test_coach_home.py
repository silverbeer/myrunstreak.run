"""Tests for the coach home aggregate (SB-266)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from backend.routes import coach as coach_module

USER = uuid4()
GABE = str(uuid4())
MAYA = str(uuid4())
TPL = str(uuid4())


def _athlete_row(athlete_id: str, name: str) -> dict[str, Any]:
    return {
        "id": athlete_id,
        "display_name": name,
        "birth_year": 2012,
        "linked_user_id": None,
        "created_by": str(USER),
        "notes": None,
        "created_at": "2026-07-01T00:00:00+00:00",
    }


class _Repo:
    """Stand-in for any repository: canned return values per method."""

    def __init__(self, **methods: Any) -> None:
        self._methods = methods

    def __call__(self, _supabase: Any) -> _Repo:
        return self

    def __getattr__(self, name: str) -> Any:
        if name in self._methods:
            return lambda *a, **k: self._methods[name]
        raise AttributeError(name)


def _patch(monkeypatch: Any, *, athletes: Any, sessions: Any, templates: Any, invites: Any = ()):
    monkeypatch.setattr(coach_module, "get_supabase_client", lambda: object())
    monkeypatch.setattr(coach_module, "require_coach", lambda _u: None)
    monkeypatch.setattr(coach_module, "AthletesRepository", _Repo(list_for_coach=athletes))
    monkeypatch.setattr(
        coach_module, "WorkoutSessionsRepository", _Repo(list_for_athletes=sessions)
    )
    monkeypatch.setattr(
        coach_module, "WorkoutTemplatesRepository", _Repo(list_for_athletes=templates)
    )
    monkeypatch.setattr(coach_module, "InvitesRepository", _Repo(list_by_creator=list(invites)))


def test_needs_attention_when_template_newer_than_last_session(monkeypatch: Any) -> None:
    _patch(
        monkeypatch,
        athletes=[_athlete_row(GABE, "Gabe"), _athlete_row(MAYA, "Maya")],
        sessions=[
            # Maya trained after her plan landed; Gabe hasn't logged since his.
            {
                "id": str(uuid4()),
                "athlete_id": MAYA,
                "session_date": "2026-07-10",
                "type": "intervals",
                "template_id": None,
                "how_felt": "good",
            },
            {
                "id": str(uuid4()),
                "athlete_id": GABE,
                "session_date": "2026-07-05",
                "type": "intervals",
                "template_id": None,
                "how_felt": None,
            },
        ],
        templates=[
            {
                "id": TPL,
                "athlete_id": GABE,
                "name": "Track Thursday",
                "created_at": "2026-07-08T12:00:00+00:00",
            },
            {
                "id": str(uuid4()),
                "athlete_id": MAYA,
                "name": "Hills",
                "created_at": "2026-07-09T12:00:00+00:00",
            },
        ],
    )
    monkeypatch.setattr(coach_module, "is_admin", lambda _u: False)
    out = coach_module.coach_home(user_id=USER)

    by_name = {c.athlete.display_name: c for c in out.athletes}
    assert by_name["Gabe"].needs_attention is True
    assert by_name["Gabe"].latest_template_name == "Track Thursday"
    assert by_name["Maya"].needs_attention is False
    # Flagged athletes sort first.
    assert out.athletes[0].athlete.display_name == "Gabe"


def test_feed_carries_names_and_template(monkeypatch: Any) -> None:
    sid = str(uuid4())
    _patch(
        monkeypatch,
        athletes=[_athlete_row(GABE, "Gabe")],
        sessions=[
            {
                "id": sid,
                "athlete_id": GABE,
                "session_date": "2026-07-09",
                "type": "intervals",
                "template_id": TPL,
                "how_felt": "strong",
            }
        ],
        templates=[
            {
                "id": TPL,
                "athlete_id": GABE,
                "name": "Track Thursday",
                "created_at": "2026-07-08T12:00:00+00:00",
            }
        ],
    )
    monkeypatch.setattr(coach_module, "is_admin", lambda _u: False)
    out = coach_module.coach_home(user_id=USER)

    assert len(out.recent_sessions) == 1
    row = out.recent_sessions[0]
    assert row.athlete_name == "Gabe"
    assert row.template_name == "Track Thursday"
    assert out.pending_invites == 0  # non-admin never counts invites


def test_pending_invites_counts_only_live_unredeemed_for_admin(monkeypatch: Any) -> None:
    future = (datetime.now(UTC) + timedelta(days=7)).isoformat()
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    _patch(
        monkeypatch,
        athletes=[],
        sessions=[],
        templates=[],
        invites=[
            {"redeemed_at": None, "expires_at": future},  # counts
            {"redeemed_at": "2026-07-01T00:00:00+00:00", "expires_at": future},  # redeemed
            {"redeemed_at": None, "expires_at": past},  # expired
        ],
    )
    monkeypatch.setattr(coach_module, "is_admin", lambda _u: True)
    out = coach_module.coach_home(user_id=USER)
    assert out.pending_invites == 1


def test_no_template_never_flags(monkeypatch: Any) -> None:
    _patch(
        monkeypatch,
        athletes=[_athlete_row(GABE, "Gabe")],
        sessions=[],
        templates=[],
    )
    monkeypatch.setattr(coach_module, "is_admin", lambda _u: False)
    out = coach_module.coach_home(user_id=USER)
    card = out.athletes[0]
    assert card.needs_attention is False
    assert card.last_session_date is None
    assert card.sessions_count == 0
