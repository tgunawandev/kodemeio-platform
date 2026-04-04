"""Test that exceptions are properly re-exported from kctl-lib."""

from kctl_mailcow.core.exceptions import (
    APIError,
    AuthenticationError,
    ConfigError,
    ConnectionError,
    KctlError,
    NotFoundError,
    ValidationError,
)


class TestExceptionHierarchy:
    def test_all_inherit_from_kctl_error(self) -> None:
        for exc_cls in [ConfigError, AuthenticationError, NotFoundError, APIError, ConnectionError, ValidationError]:
            assert issubclass(exc_cls, KctlError)

    def test_kctl_error_is_exception(self) -> None:
        assert issubclass(KctlError, Exception)
