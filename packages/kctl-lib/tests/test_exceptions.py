"""Tests for kctl_lib.exceptions."""

from __future__ import annotations

import pytest

from kctl_lib.exceptions import (
    APIError,
    AppNotFoundError,
    AuthenticationError,
    CommandError,
    ConfigError,
    DockerError,
    KctlError,
    NotFoundError,
    ValidationError,
)
from kctl_lib.exceptions import (
    ConnectionError as KctlConnectionError,
)


class TestKctlError:
    def test_is_exception(self) -> None:
        assert issubclass(KctlError, Exception)

    def test_message(self) -> None:
        e = KctlError("something broke")
        assert str(e) == "something broke"


class TestConfigError:
    def test_inherits_kctl_error(self) -> None:
        assert issubclass(ConfigError, KctlError)


class TestNotFoundError:
    def test_attributes(self) -> None:
        e = NotFoundError("module", "sale_management")
        assert e.resource_type == "module"
        assert e.identifier == "sale_management"
        assert "module not found: sale_management" in str(e)


class TestAppNotFoundError:
    def test_with_valid_apps(self) -> None:
        e = AppNotFoundError("foo", valid_apps=["bar", "baz"])
        assert e.valid_apps == ["bar", "baz"]
        assert "foo" in str(e)
        assert "bar, baz" in str(e)

    def test_without_valid_apps(self) -> None:
        e = AppNotFoundError("foo")
        assert e.valid_apps == []
        assert "foo" in str(e)


class TestCommandError:
    def test_attributes(self) -> None:
        e = CommandError("pnpm build", 1, "error output")
        assert e.command == "pnpm build"
        assert e.returncode == 1
        assert e.stderr == "error output"
        assert "exit 1" in str(e)

    def test_inherits_kctl_error(self) -> None:
        assert issubclass(CommandError, KctlError)


class TestAuthenticationError:
    def test_inherits_kctl_error(self) -> None:
        assert issubclass(AuthenticationError, KctlError)


class TestAPIError:
    def test_with_detail(self) -> None:
        e = APIError(status_code=404, detail="not found")
        assert e.status_code == 404
        assert e.detail == "not found"
        assert "404" in str(e)

    def test_without_detail(self) -> None:
        e = APIError(status_code=500)
        assert e.status_code == 500


class TestConnectionError:
    def test_attributes(self) -> None:
        cause = OSError("refused")
        e = KctlConnectionError("https://erp.kodeme.io", cause)
        assert e.url == "https://erp.kodeme.io"
        assert e.cause is cause
        assert "erp.kodeme.io" in str(e)


class TestDockerError:
    def test_attributes(self) -> None:
        e = DockerError("docker compose up", 1, "no space")
        assert e.command == "docker compose up"
        assert e.returncode == 1
        assert e.stderr == "no space"
        assert "exit 1" in str(e)


class TestValidationError:
    def test_multiple_errors(self) -> None:
        e = ValidationError(["missing url", "bad format"])
        assert len(e.errors) == 2
        assert "2 validation error(s)" in str(e)
        assert "missing url" in str(e)


class TestHierarchy:
    @pytest.mark.parametrize(
        "exc_class",
        [
            ConfigError,
            NotFoundError,
            AppNotFoundError,
            CommandError,
            AuthenticationError,
            APIError,
            KctlConnectionError,
            DockerError,
            ValidationError,
        ],
    )
    def test_inherits_kctl_error(self, exc_class: type) -> None:
        assert issubclass(exc_class, KctlError)
