"""Tests for kctl-gatus exception re-exports."""

from kctl_gatus.core.exceptions import (
    APIError,
    AuthenticationError,
    ConfigError,
    ConnectionError,
    KctlError,
    NotFoundError,
    ValidationError,
)


class TestExceptions:
    def test_hierarchy(self):
        assert issubclass(ConfigError, KctlError)
        assert issubclass(APIError, KctlError)
        assert issubclass(AuthenticationError, KctlError)
        assert issubclass(NotFoundError, KctlError)
        assert issubclass(ConnectionError, KctlError)
        assert issubclass(ValidationError, KctlError)

    def test_instantiation(self):
        err = ConfigError("bad config")
        assert str(err) == "bad config"
        assert isinstance(err, KctlError)

    def test_all_exports_present(self):
        from kctl_gatus.core import exceptions

        for name in [
            "KctlError",
            "ConfigError",
            "APIError",
            "AuthenticationError",
            "ConnectionError",
            "NotFoundError",
            "ValidationError",
        ]:
            assert hasattr(exceptions, name)
