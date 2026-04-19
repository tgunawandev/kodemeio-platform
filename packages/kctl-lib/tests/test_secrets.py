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


class TestOpRefs:
    def test_op_ref_resolved_via_subprocess(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from kctl_lib import secrets as secrets_mod
        from kctl_lib.config import expand_env

        calls: list[list[str]] = []

        def fake_run(cmd: list[str], **kwargs: object) -> object:
            calls.append(cmd)

            class Res:
                returncode = 0
                stdout = "resolved-secret-value\n"
                stderr = ""

            return Res()

        monkeypatch.setattr(secrets_mod.subprocess, "run", fake_run)
        secrets_mod._cache.clear()

        out = expand_env("api=${op://Kodemeio/my-item/token}")
        assert out == "api=resolved-secret-value"
        assert calls and "op" == calls[0][0]

    def test_op_ref_cached_per_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from kctl_lib import secrets as secrets_mod
        from kctl_lib.config import expand_env

        call_count = {"n": 0}

        def fake_run(cmd: list[str], **kwargs: object) -> object:
            call_count["n"] += 1

            class Res:
                returncode = 0
                stdout = "v\n"
                stderr = ""

            return Res()

        monkeypatch.setattr(secrets_mod.subprocess, "run", fake_run)
        secrets_mod._cache.clear()

        expand_env("a=${op://V/I/F}")
        expand_env("b=${op://V/I/F}")
        assert call_count["n"] == 1

    def test_op_ref_failure_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from kctl_lib import secrets as secrets_mod
        from kctl_lib.config import expand_env

        def fake_run(cmd: list[str], **kwargs: object) -> object:
            class Res:
                returncode = 1
                stdout = ""
                stderr = "item not found"

            return Res()

        monkeypatch.setattr(secrets_mod.subprocess, "run", fake_run)
        secrets_mod._cache.clear()

        try:
            expand_env("a=${op://V/I/F}")
        except RuntimeError as exc:
            assert "op" in str(exc).lower()
            assert "V/I/F" in str(exc)
        else:
            raise AssertionError("Expected RuntimeError on op resolution failure")
