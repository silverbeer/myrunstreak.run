"""Tests for role-based (1Password-backed) login in the stk CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer

from cli.commands import auth


def _write_config(tmp_path: Path, cfg: dict) -> Path:
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return path


def test_resolve_role_builds_op_ref_per_env(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    cfg = {
        "op_vault": "Personal",
        "roles": {"admin": {"email": "me@example.com", "op_field": "admin_password"}},
    }
    monkeypatch.setattr(auth, "CONFIG_FILE", _write_config(tmp_path, cfg))
    email, op_ref = auth._resolve_role("admin", "prod")
    assert email == "me@example.com"
    assert op_ref == "op://Personal/stk-prod/admin_password"
    # Same role, different env -> different item.
    _, local_ref = auth._resolve_role("admin", "local")
    assert local_ref == "op://Personal/stk-local/admin_password"


def test_resolve_role_unknown_exits(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(auth, "CONFIG_FILE", _write_config(tmp_path, {"roles": {}}))
    with pytest.raises(typer.Exit):
        auth._resolve_role("admin", "prod")


def test_op_read_missing_cli_exits(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(auth.shutil, "which", lambda _: None)
    with pytest.raises(typer.Exit):
        auth._op_read("op://Personal/stk-local/admin_password")


def test_op_read_returns_secret(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(auth.shutil, "which", lambda _: "/usr/bin/op")

    class _Result:
        stdout = "s3cret\n"

    monkeypatch.setattr(auth.subprocess, "run", lambda *a, **k: _Result())
    assert auth._op_read("op://Personal/stk-local/admin_password") == "s3cret"
