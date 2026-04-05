"""Tests for kctl-api auth commands."""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_api.cli import app
from kctl_api.commands.auth import _decode_jwt_payload, _format_timestamp

runner = CliRunner()


# ---------------------------------------------------------------------------
# JWT helper unit tests
# ---------------------------------------------------------------------------
def _make_jwt(payload: dict) -> str:
    """Create a fake JWT token with the given payload."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    sig = "fake_sig"
    return f"{header}.{body}.{sig}"


class TestDecodeJwtPayload:
    def test_decode_basic_payload(self) -> None:
        token = _make_jwt({"sub": "user123", "email": "test@example.com"})
        claims = _decode_jwt_payload(token)
        assert claims["sub"] == "user123"
        assert claims["email"] == "test@example.com"

    def test_decode_with_exp(self) -> None:
        future = int(time.time()) + 3600
        token = _make_jwt({"sub": "u1", "exp": future})
        claims = _decode_jwt_payload(token)
        assert claims["exp"] == future

    def test_invalid_jwt_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid JWT format"):
            _decode_jwt_payload("not.a.valid.jwt.token.with.too.many.parts")

    def test_invalid_jwt_only_two_parts(self) -> None:
        with pytest.raises(ValueError, match="Invalid JWT format"):
            _decode_jwt_payload("header.payload")

    def test_decode_with_padding(self) -> None:
        """Tokens whose base64 payload needs padding should decode correctly."""
        payload = {"sub": "abc", "role": "admin", "extra": "x" * 5}
        token = _make_jwt(payload)
        claims = _decode_jwt_payload(token)
        assert claims["sub"] == "abc"
        assert claims["role"] == "admin"


class TestFormatTimestamp:
    def test_none_returns_not_set(self) -> None:
        assert _format_timestamp(None) == "(not set)"

    def test_valid_timestamp(self) -> None:
        ts = 1700000000
        result = _format_timestamp(ts)
        assert "UTC" in result
        assert "2023" in result

    def test_invalid_timestamp(self) -> None:
        # Very large value that may overflow on some platforms
        result = _format_timestamp(999999999999999)
        # Should return str representation without crashing
        assert result is not None


# ---------------------------------------------------------------------------
# auth --help checks
# ---------------------------------------------------------------------------
class TestAuthHelp:
    def test_auth_help(self) -> None:
        result = runner.invoke(app, ["auth", "--help"])
        assert result.exit_code == 0

    def test_auth_login_help(self) -> None:
        result = runner.invoke(app, ["auth", "login", "--help"])
        assert result.exit_code == 0
        assert "--email" in result.output
        assert "--password" in result.output

    def test_auth_logout_help(self) -> None:
        result = runner.invoke(app, ["auth", "logout", "--help"])
        assert result.exit_code == 0

    def test_auth_whoami_help(self) -> None:
        result = runner.invoke(app, ["auth", "whoami", "--help"])
        assert result.exit_code == 0

    def test_auth_refresh_help(self) -> None:
        result = runner.invoke(app, ["auth", "refresh", "--help"])
        assert result.exit_code == 0

    def test_auth_token_info_help(self) -> None:
        result = runner.invoke(app, ["auth", "token-info", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# auth login
# ---------------------------------------------------------------------------
class TestAuthLogin:
    def test_login_success(self, tmp_path: Path) -> None:
        mock_client = MagicMock()
        mock_client.login.return_value = {"access_token": "tok123", "refresh_token": "ref456"}

        config_file = tmp_path / "config.yaml"
        config_file.write_text("default_profile: default\nprofiles:\n  default:\n    api: {}\n")

        with (
            patch("kctl_api.commands.auth.resolve_active_profile_name", return_value="default"),
            patch("kctl_api.commands.auth.get_service_config") as mock_get,
            patch("kctl_api.commands.auth.set_service_config") as mock_set,
            patch("kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)),
        ):
            from kctl_api.core.config import ServiceConfig

            mock_get.return_value = ServiceConfig(url="http://localhost:8000")
            result = runner.invoke(app, ["auth", "login", "--email", "user@test.com", "--password", "pass"])

        assert result.exit_code == 0
        assert "user@test.com" in result.output or "Logged in" in result.output

    def test_login_connection_error(self, tmp_path: Path) -> None:
        from kctl_api.core.exceptions import ConnectionError as KctlConnectionError

        mock_client = MagicMock()
        mock_client.login.side_effect = KctlConnectionError("http://localhost:8000", ConnectionError("refused"))

        with patch(
            "kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)
        ):
            result = runner.invoke(app, ["auth", "login", "--email", "user@test.com", "--password", "pass"])

        assert result.exit_code == 1
        assert "Connection failed" in result.output

    def test_login_auth_error(self, tmp_path: Path) -> None:
        from kctl_api.core.exceptions import AuthenticationError

        mock_client = MagicMock()
        mock_client.login.side_effect = AuthenticationError("Invalid credentials")

        with patch(
            "kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)
        ):
            result = runner.invoke(app, ["auth", "login", "--email", "user@test.com", "--password", "wrong"])

        assert result.exit_code == 1
        assert "Login failed" in result.output


# ---------------------------------------------------------------------------
# auth token-info
# ---------------------------------------------------------------------------
class TestAuthTokenInfo:
    def test_token_info_with_valid_token(self) -> None:
        future = int(time.time()) + 3600
        token = _make_jwt({"sub": "user42", "email": "me@test.com", "role": "admin", "exp": future})
        result = runner.invoke(app, ["auth", "token-info", "--token", token])
        assert result.exit_code == 0
        assert "user42" in result.output
        assert "me@test.com" in result.output

    def test_token_info_expired(self) -> None:
        past = int(time.time()) - 3600
        token = _make_jwt({"sub": "u1", "exp": past})
        result = runner.invoke(app, ["auth", "token-info", "--token", token])
        assert result.exit_code == 0
        assert "EXPIRED" in result.output

    def test_token_info_invalid_token(self) -> None:
        result = runner.invoke(app, ["auth", "token-info", "--token", "not-a-jwt"])
        assert result.exit_code == 1

    def test_token_info_no_token_no_profile(self, tmp_path: Path) -> None:
        """Without a token in profile or CLI, should error."""
        from kctl_api.core.config import ServiceConfig

        with (
            patch("kctl_api.commands.auth.resolve_active_profile_name", return_value="default"),
            patch("kctl_api.commands.auth.get_service_config", return_value=ServiceConfig(api_key="")),
        ):
            result = runner.invoke(app, ["auth", "token-info"])
        assert result.exit_code == 1
        assert "No token" in result.output or "Login first" in result.output


# ---------------------------------------------------------------------------
# auth logout
# ---------------------------------------------------------------------------
class TestAuthLogout:
    def test_logout_clears_token(self, tmp_path: Path) -> None:
        from kctl_api.core.config import ServiceConfig

        mock_client = MagicMock()
        mock_client.post.return_value = {}

        with (
            patch("kctl_api.commands.auth.resolve_active_profile_name", return_value="default"),
            patch("kctl_api.commands.auth.get_service_config", return_value=ServiceConfig(url="http://localhost")),
            patch("kctl_api.commands.auth.set_service_config") as mock_set,
            patch("kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)),
        ):
            result = runner.invoke(app, ["auth", "logout"])

        assert result.exit_code == 0
        assert "Logged out" in result.output

    def test_logout_json_mode(self) -> None:
        from kctl_api.core.config import ServiceConfig

        mock_client = MagicMock()
        mock_client.post.return_value = {}

        with (
            patch("kctl_api.commands.auth.resolve_active_profile_name", return_value="default"),
            patch("kctl_api.commands.auth.get_service_config", return_value=ServiceConfig(url="http://localhost")),
            patch("kctl_api.commands.auth.set_service_config"),
            patch("kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)),
        ):
            result = runner.invoke(app, ["--json", "auth", "logout"])

        assert result.exit_code == 0
        assert '"logged_out": true' in result.output


# ---------------------------------------------------------------------------
# auth whoami
# ---------------------------------------------------------------------------
class TestAuthWhoami:
    def test_whoami_success(self) -> None:
        user_data = {
            "id": 1,
            "email": "admin@kodeme.io",
            "name": "Admin User",
            "role": "admin",
            "tier": "premium",
            "is_active": True,
        }
        mock_client = MagicMock()
        mock_client.get.return_value = user_data

        with patch(
            "kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)
        ):
            result = runner.invoke(app, ["auth", "whoami"])

        assert result.exit_code == 0
        assert "admin@kodeme.io" in result.output

    def test_whoami_auth_error(self) -> None:
        from kctl_api.core.exceptions import AuthenticationError

        mock_client = MagicMock()
        mock_client.get.side_effect = AuthenticationError("Unauthorized")

        with patch(
            "kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)
        ):
            result = runner.invoke(app, ["auth", "whoami"])

        assert result.exit_code == 1
        assert "Not authenticated" in result.output

    def test_whoami_json_mode(self) -> None:
        user_data = {"id": 2, "email": "user@test.com", "role": "user", "tier": "free", "is_active": True}
        mock_client = MagicMock()
        mock_client.get.return_value = user_data

        with patch(
            "kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)
        ):
            result = runner.invoke(app, ["--json", "auth", "whoami"])

        assert result.exit_code == 0
        assert "user@test.com" in result.output
