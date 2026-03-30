"""Tests for core/exceptions.py."""

from __future__ import annotations

from kctl_react.core.exceptions import (
    AppNotFoundError,
    CommandError,
    ConfigError,
    KctlError,
    NotFoundError,
)


class TestExceptionHierarchy:
    def test_all_inherit_kctl_error(self) -> None:
        assert issubclass(ConfigError, KctlError)
        assert issubclass(NotFoundError, KctlError)
        assert issubclass(CommandError, KctlError)
        assert issubclass(AppNotFoundError, KctlError)

    def test_app_not_found_inherits_not_found(self) -> None:
        assert issubclass(AppNotFoundError, NotFoundError)


class TestNotFoundError:
    def test_attributes(self) -> None:
        err = NotFoundError("user", "alice")
        assert err.resource_type == "user"
        assert err.identifier == "alice"
        assert "user not found: alice" in str(err)


class TestAppNotFoundError:
    def test_with_valid_apps(self) -> None:
        err = AppNotFoundError("xyz", ["sfa", "wms"])
        assert err.identifier == "xyz"
        assert err.resource_type == "app"
        assert err.valid_apps == ["sfa", "wms"]
        assert "xyz" in str(err)
        assert "sfa" in str(err)

    def test_without_valid_apps(self) -> None:
        err = AppNotFoundError("bad")
        assert err.valid_apps == []
        assert "bad" in str(err)


class TestCommandError:
    def test_attributes(self) -> None:
        err = CommandError("pnpm build", 1, "error output")
        assert err.command == "pnpm build"
        assert err.returncode == 1
        assert err.stderr == "error output"
        assert "exit 1" in str(err)

    def test_empty_stderr(self) -> None:
        err = CommandError("cmd", 2)
        assert "exit 2" in str(err)
