"""Circuits as data, and sets that can name what they answer (SB-527).

Both halves of the same gap: the prescription was not structured enough to be
referred back to. Rounds lived on the template as one number (Gabe's said 1
while Circuit A was genuinely two), circuit membership was retyped into every
item's notes, and `exercise_sets` pointed at an exercise rather than at the
prescribed item — so with `lunge` appearing five times in one template, a
logged set was unattributable.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from src.shared.models.workout import (
    ExerciseSetCreate,
    TemplateBlockCreate,
    TemplateItemCreate,
    WorkoutTemplateCreate,
)
from src.shared.supabase_ops.workout_repository import WorkoutTemplatesRepository

# --------------------------------------------------------------- recording fake


class _Query:
    def __init__(self, store: dict[str, list[dict[str, Any]]], table: str):
        self.store, self.table = store, table
        self._mode = "select"
        self._payload: Any = None
        self._preds: list[Any] = []

    def select(self, *a: Any, **k: Any) -> _Query:
        return self

    def eq(self, col: str, val: Any) -> _Query:
        self._preds.append(lambda r: str(r.get(col)) == str(val))
        return self

    def is_(self, col: str, val: Any) -> _Query:
        if str(val).lower() == "null":
            self._preds.append(lambda r: r.get(col) is None)
        return self

    def in_(self, col: str, vals: Any) -> _Query:
        wanted = {str(v) for v in vals}
        self._preds.append(lambda r: str(r.get(col)) in wanted)
        return self

    def order(self, *a: Any, **k: Any) -> _Query:
        return self

    def insert(self, payload: Any) -> _Query:
        self._mode, self._payload = "insert", payload
        return self

    def update(self, payload: Any) -> _Query:
        self._mode, self._payload = "update", payload
        return self

    def delete(self) -> _Query:
        self._mode = "delete"
        return self

    def execute(self) -> SimpleNamespace:
        rows = self.store.setdefault(self.table, [])
        if self._mode == "insert":
            payload = self._payload if isinstance(self._payload, list) else [self._payload]
            out = [{"id": str(uuid4()), **r} for r in payload]
            rows.extend(out)
            return SimpleNamespace(data=out)
        matched = [r for r in rows if all(p(r) for p in self._preds)]
        if self._mode == "update":
            for r in matched:
                r.update(self._payload)
            return SimpleNamespace(data=matched)
        if self._mode == "delete":
            self.store[self.table] = [r for r in rows if r not in matched]
            return SimpleNamespace(data=matched)
        return SimpleNamespace(data=matched)


class _Client:
    def __init__(self) -> None:
        self.store: dict[str, list[dict[str, Any]]] = {}

    def table(self, name: str) -> _Query:
        return _Query(self.store, name)


USER = uuid4()


def _monday() -> dict[str, Any]:
    """Gabe's Monday shape: two circuits, the first run twice with rest after."""
    return WorkoutTemplateCreate(
        name="Monday At-Home",
        rounds=1,
        blocks=[
            TemplateBlockCreate(label="Circuit A", position=0, rounds=2, rest_after_seconds=240),
            TemplateBlockCreate(label="Circuit B", position=1, rounds=1),
        ],
        items=[
            TemplateItemCreate(exercise_key="lunge", position=0, block_index=0),
            TemplateItemCreate(exercise_key="aquaman", position=1, block_index=0),
            TemplateItemCreate(exercise_key="bird_dog", position=2, block_index=1),
            TemplateItemCreate(exercise_key="warmup", position=3, section="warmup"),
        ],
    ).model_dump(mode="json")


# --------------------------------------------------------------- the model


def test_rounds_belong_to_the_circuit_not_the_template() -> None:
    t = WorkoutTemplateCreate(**{**_monday(), "rounds": 1})
    assert t.rounds == 1, "the template-level number stays 1..."
    assert [b.rounds for b in t.blocks] == [2, 1], "...while the circuits carry the real counts"


def test_a_dangling_block_index_is_rejected() -> None:
    """Silently orphaning the item would be worse than failing."""
    with pytest.raises(ValidationError, match="block_index 5 has no matching block"):
        WorkoutTemplateCreate(
            name="Bad",
            blocks=[TemplateBlockCreate(label="Circuit A")],
            items=[TemplateItemCreate(exercise_key="lunge", block_index=5)],
        )


def test_a_set_can_name_the_prescribed_item() -> None:
    item_id = uuid4()
    s = ExerciseSetCreate(exercise_key="lunge", template_item_id=item_id, round_number=2, reps=10)
    assert s.template_item_id == item_id


def test_an_ad_hoc_set_still_needs_no_prescription() -> None:
    assert ExerciseSetCreate(exercise_key="pushups", reps=20).template_item_id is None


# --------------------------------------------------------------- the repository


def test_create_resolves_block_index_to_real_ids() -> None:
    client = _Client()
    repo = WorkoutTemplatesRepository(client)  # type: ignore[arg-type]
    got = repo.create(USER, _monday())

    blocks = {b["label"]: b for b in got["blocks"]}
    assert set(blocks) == {"Circuit A", "Circuit B"}
    assert blocks["Circuit A"]["rounds"] == 2
    assert blocks["Circuit A"]["rest_after_seconds"] == 240

    by_ex = {i["exercise_key"]: i for i in got["items"]}
    assert by_ex["lunge"]["block_id"] == blocks["Circuit A"]["id"]
    assert by_ex["aquaman"]["block_id"] == blocks["Circuit A"]["id"]
    assert by_ex["bird_dog"]["block_id"] == blocks["Circuit B"]["id"]


def test_items_outside_a_circuit_keep_no_block() -> None:
    """The warm-up is not part of any circuit and must not be swept into one."""
    repo = WorkoutTemplatesRepository(_Client())  # type: ignore[arg-type]
    got = repo.create(USER, _monday())
    warmup = next(i for i in got["items"] if i["exercise_key"] == "warmup")
    assert warmup.get("block_id") is None


def test_block_index_never_reaches_the_database() -> None:
    """It is a payload convenience — persisting it would be the string-key
    pattern this table exists to escape."""
    client = _Client()
    WorkoutTemplatesRepository(client).create(USER, _monday())  # type: ignore[arg-type]
    assert all("block_index" not in row for row in client.store["template_items"])


def test_update_replaces_circuits_with_the_items() -> None:
    client = _Client()
    repo = WorkoutTemplatesRepository(client)  # type: ignore[arg-type]
    created = repo.create(USER, _monday())

    changed = WorkoutTemplateCreate(
        name="Monday At-Home",
        blocks=[TemplateBlockCreate(label="Circuit A", rounds=3)],
        items=[TemplateItemCreate(exercise_key="lunge", block_index=0)],
    ).model_dump(mode="json")
    out = repo.update(USER, UUID(created["id"]), changed)

    assert out is not None
    assert [b["label"] for b in out["blocks"]] == ["Circuit A"]
    assert out["blocks"][0]["rounds"] == 3
    assert out["items"][0]["block_id"] == out["blocks"][0]["id"]
    # No orphans left behind from the previous shape.
    assert len(client.store["template_blocks"]) == 1


def test_a_template_with_no_circuits_still_works() -> None:
    """Blocks are optional — most templates are a flat list."""
    repo = WorkoutTemplatesRepository(_Client())  # type: ignore[arg-type]
    payload = WorkoutTemplateCreate(
        name="Simple",
        items=[TemplateItemCreate(exercise_key="pushups")],
    ).model_dump(mode="json")
    got = repo.create(USER, payload)
    assert got["blocks"] == []
    assert got["items"][0].get("block_id") is None
