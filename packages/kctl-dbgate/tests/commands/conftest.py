"""Shared fixtures for commands tests."""

from __future__ import annotations

import pytest

BASE = "https://dbgate.example.com"


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KCTL_DBGATE_URL", BASE)
    monkeypatch.setenv("KCTL_DBGATE_LOGIN", "admin")
    monkeypatch.setenv("KCTL_DBGATE_PASSWORD", "hunter2")
    monkeypatch.setenv("KCTL_DBGATE_PROFILE", "default")
