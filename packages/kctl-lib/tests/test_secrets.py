"""Secret-reference resolution tests (Stage C)."""

from __future__ import annotations

import pytest


class TestEnvVarRefs:
    def test_legacy_brace_syntax_still_works(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from kctl_lib.config import expand_env

        monkeypatch.setenv("MY_TOKEN", "abc")
        assert expand_env("key=${MY_TOKEN}") == "key=abc"

    def test_explicit_env_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from kctl_lib.config import expand_env

        monkeypatch.setenv("MY_TOKEN", "abc")
        assert expand_env("key=${env:MY_TOKEN}") == "key=abc"

    def test_env_prefix_missing_kept_literal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from kctl_lib.config import expand_env

        monkeypatch.delenv("MISSING_VAR_ABC", raising=False)
        assert expand_env("k=${env:MISSING_VAR_ABC}") == "k=${env:MISSING_VAR_ABC}"
