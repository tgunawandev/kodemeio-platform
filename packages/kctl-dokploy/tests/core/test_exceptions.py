"""Tests for custom exception hierarchy."""

from __future__ import annotations

from kctl_dokploy.core.exceptions import (
    APIError,
    AuthenticationError,
    ConfigError,
    ConnectionError,
    KctlError,
    NotFoundError,
    TimeoutError,
    ValidationError,
)


class TestExceptionHierarchy:
    def test_all_inherit_from_kctl_error(self) -> None:
        assert issubclass(ConfigError, KctlError)
        assert issubclass(AuthenticationError, KctlError)
        assert issubclass(NotFoundError, KctlError)
        assert issubclass(ValidationError, KctlError)
        assert issubclass(TimeoutError, KctlError)
        assert issubclass(APIError, KctlError)
        assert issubclass(ConnectionError, KctlError)

    def test_timeout_inherits_from_connection_error(self) -> None:
        assert issubclass(TimeoutError, ConnectionError)


class TestNotFoundError:
    def test_message_includes_type_and_id(self) -> None:
        e = NotFoundError("project", "my-project")
        assert "project" in str(e)
        assert "my-project" in str(e)
        assert e.resource_type == "project"
        assert e.identifier == "my-project"


class TestTimeoutError:
    def test_message_includes_url_and_timeout(self) -> None:
        e = TimeoutError("https://api.example.com", 30.0)
        assert "https://api.example.com" in str(e)
        assert "30.0" in str(e)


class TestConnectionError:
    def test_message_includes_url(self) -> None:
        cause = Exception("connection refused")
        e = ConnectionError("https://api.example.com", cause)
        assert "https://api.example.com" in str(e)
        assert e.cause is cause


class TestAPIError:
    def test_includes_status_code_and_detail(self) -> None:
        e = APIError(status_code=422, detail="Validation failed")
        assert e.status_code == 422
        assert "Validation failed" in str(e)

    def test_detail_only(self) -> None:
        e = APIError(detail="Internal Server Error")
        assert "Internal Server Error" in str(e)


class TestValidationError:
    def test_basic_message(self) -> None:
        e = ValidationError(["name is required"])
        assert "name is required" in str(e)

    def test_multiple_errors(self) -> None:
        e = ValidationError(["field a missing", "field b invalid"])
        assert "2 validation error" in str(e)
        assert "field a missing" in str(e)
        assert "field b invalid" in str(e)
