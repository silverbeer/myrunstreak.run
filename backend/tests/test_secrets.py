"""Tests for src/shared/secrets.py — primarily the env-var fast path."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from src.shared.secrets import get_smashrun_oauth_credentials


def test_smashrun_creds_from_env_skips_aws(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both env vars set → return them directly, no AWS call."""
    monkeypatch.setenv("SMASHRUN_CLIENT_ID", "id-from-env")
    monkeypatch.setenv("SMASHRUN_CLIENT_SECRET", "secret-from-env")

    with patch("src.shared.secrets.get_secret") as mock_aws:
        creds = get_smashrun_oauth_credentials()

    assert creds == {"client_id": "id-from-env", "client_secret": "secret-from-env"}
    mock_aws.assert_not_called()


def test_smashrun_creds_falls_back_to_aws_when_env_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Either env var unset → defer to AWS Secrets Manager."""
    monkeypatch.delenv("SMASHRUN_CLIENT_ID", raising=False)
    monkeypatch.delenv("SMASHRUN_CLIENT_SECRET", raising=False)

    expected = {"client_id": "from-aws", "client_secret": "from-aws-too"}
    with patch("src.shared.secrets.get_secret", return_value=expected) as mock_aws:
        creds = get_smashrun_oauth_credentials()

    assert creds == expected
    mock_aws.assert_called_once()


def test_smashrun_creds_falls_back_when_only_one_env_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Half-set env (only id, no secret) treats env as absent — don't ship a half-cred."""
    monkeypatch.setenv("SMASHRUN_CLIENT_ID", "id-from-env")
    monkeypatch.delenv("SMASHRUN_CLIENT_SECRET", raising=False)

    expected = {"client_id": "from-aws", "client_secret": "from-aws-too"}
    with patch("src.shared.secrets.get_secret", return_value=expected) as mock_aws:
        creds = get_smashrun_oauth_credentials()

    assert creds == expected
    mock_aws.assert_called_once()
