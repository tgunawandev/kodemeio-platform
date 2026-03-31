"""Tests for error handling — API errors, connection errors, auth errors."""

from __future__ import annotations

import pytest
from kctl_common.exceptions import APIError, ConfigError
from kctl_common.exceptions import ConnectionError as KctlConnectionError

from kctl_ak.core.client import AuthentikClient
from kctl_ak.core.exceptions import NotFoundError


class TestAPIErrors:
    def test_api_error_attributes(self) -> None:
        err = APIError(status_code=404, detail="Not found")
        assert err.status_code == 404
        assert "Not found" in str(err)

    def test_api_error_is_kctl_error(self) -> None:
        from kctl_common.exceptions import KctlError

        err = APIError(status_code=500, detail="Internal error")
        assert isinstance(err, KctlError)

    def test_connection_error(self) -> None:
        err = KctlConnectionError("https://auth.kodeme.io", Exception("timed out"))
        assert "auth.kodeme.io" in str(err)

    def test_config_error_missing_url(self) -> None:
        with pytest.raises(ConfigError, match="No API URL"):
            AuthentikClient(base_url="", credential="test")

    def test_config_error_missing_credential(self) -> None:
        with pytest.raises(ConfigError):
            AuthentikClient(base_url="https://example.com", credential="")


class TestNotFoundError:
    def test_user_not_found(self) -> None:
        err = NotFoundError("User", "alice")
        assert "User" in str(err)
        assert "alice" in str(err)

    def test_group_not_found(self) -> None:
        err = NotFoundError("Group", "ak-role-admin")
        assert "Group" in str(err)


class TestClientConstruction:
    def test_api_prefix_applied(self) -> None:
        client = AuthentikClient(base_url="https://example.com", credential="tok")
        assert "/api/v3" in client._base_url
        client.close()

    def test_trailing_slash_handling(self) -> None:
        client = AuthentikClient(base_url="https://example.com", credential="tok")
        assert client._ensure_trailing_slash("users") == "users/"
        assert client._ensure_trailing_slash("users/") == "users/"
        assert client._ensure_trailing_slash("/users") == "users/"
        assert client._ensure_trailing_slash("users?page=1") == "users?page=1"
        client.close()

    def test_auth_header(self) -> None:
        client = AuthentikClient(base_url="https://example.com", credential="my-token")
        headers = client._build_auth_header()
        assert headers["Authorization"] == "Bearer my-token"
        client.close()
