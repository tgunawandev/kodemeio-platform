"""Tests for kctl-api core modules."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from kctl_api.core.config import (
    SERVICE_KEY,
    ServiceConfig,
    _is_service_scoped,
    get_service_config,
    load_config,
    load_raw_config,
    resolve_active_profile_name,
    resolve_connection,
    save_raw_config,
    set_service_config,
)
from kctl_api.core.exceptions import (
    APIError,
    AuthenticationError,
    ConfigError,
    KctlError,
    NotFoundError,
)
from kctl_api.core.exceptions import (
    ConnectionError as KctlConnectionError,
)
from kctl_api.core.output import Output
from kctl_api.core.utils import find_project_root, human_size, mask_secret, service_status_color


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------
class TestConfig:
    def test_service_key(self) -> None:
        assert SERVICE_KEY == "api"

    def test_service_config_defaults(self) -> None:
        cfg = ServiceConfig()
        assert cfg.url == ""
        assert cfg.ai_url == ""
        assert cfg.api_key == ""
        assert cfg.database_url == ""
        assert cfg.redis_url == ""

    def test_is_service_scoped(self) -> None:
        assert _is_service_scoped({"api": {"url": "http://x"}}) is True
        assert _is_service_scoped({"url": "http://x"}) is False
        assert _is_service_scoped({}) is False

    def test_load_save_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        with patch("kctl_api.core.config.CONFIG_FILE", config_file), patch("kctl_api.core.config.CONFIG_DIR", tmp_path):
            # Initially empty
            data = load_raw_config()
            assert data == {}

            # Save and reload
            save_raw_config({"default_profile": "test", "profiles": {"test": {"api": {"url": "http://x"}}}})
            cfg = load_config()
            assert cfg.default_profile == "test"
            assert "test" in cfg.profiles

    def test_get_set_service_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        with patch("kctl_api.core.config.CONFIG_FILE", config_file), patch("kctl_api.core.config.CONFIG_DIR", tmp_path):
            svc = ServiceConfig(url="http://localhost:8000", api_key="test-key")
            set_service_config("local", svc)

            loaded = get_service_config("local")
            assert loaded.url == "http://localhost:8000"
            assert loaded.api_key == "test-key"

    def test_resolve_active_profile_env(self) -> None:
        with patch.dict(os.environ, {"KCTL_API_PROFILE": "staging"}):
            assert resolve_active_profile_name() == "staging"

    def test_resolve_connection_overrides(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        with patch("kctl_api.core.config.CONFIG_FILE", config_file), patch("kctl_api.core.config.CONFIG_DIR", tmp_path):
            url, _ai_url, api_key, _db_url, _redis_url = resolve_connection(
                url_override="http://override:8000",
                api_key_override="override-key",
            )
            assert url == "http://override:8000"
            assert api_key == "override-key"


# ---------------------------------------------------------------------------
# Exceptions tests
# ---------------------------------------------------------------------------
class TestExceptions:
    def test_hierarchy(self) -> None:
        assert issubclass(ConfigError, KctlError)
        assert issubclass(AuthenticationError, KctlError)
        assert issubclass(NotFoundError, KctlError)
        assert issubclass(APIError, KctlError)
        assert issubclass(KctlConnectionError, KctlError)

    def test_not_found_error(self) -> None:
        e = NotFoundError("User", "42")
        assert "User" in str(e)
        assert "42" in str(e)
        assert e.resource_type == "User"
        assert e.identifier == "42"

    def test_connection_error(self) -> None:
        e = KctlConnectionError("http://localhost", ValueError("refused"))
        assert "localhost" in str(e)
        assert e.url == "http://localhost"

    def test_api_error_with_detail(self) -> None:
        e = APIError(detail="something went wrong")
        assert "something went wrong" in str(e)
        assert e.status_code == 0


# ---------------------------------------------------------------------------
# Output tests
# ---------------------------------------------------------------------------
class TestOutput:
    def test_json_mode(self, capsys: pytest.CaptureFixture) -> None:  # type: ignore[type-arg]
        out = Output(json_mode=True)
        out.table("Test", [("Col1", "")], [["val1"]])
        captured = capsys.readouterr()
        assert '"col1": "val1"' in captured.out

    def test_csv_mode(self, capsys: pytest.CaptureFixture) -> None:  # type: ignore[type-arg]
        out = Output(format="csv")
        out.table("Test", [("Name", ""), ("Age", "")], [["Alice", "30"]])
        captured = capsys.readouterr()
        assert "Name,Age" in captured.out
        assert "Alice,30" in captured.out

    def test_csv_no_header(self, capsys: pytest.CaptureFixture) -> None:  # type: ignore[type-arg]
        out = Output(format="csv", no_header=True)
        out.table("Test", [("Name", "")], [["Bob"]])
        captured = capsys.readouterr()
        assert "Name" not in captured.out
        assert "Bob" in captured.out

    def test_quiet_suppresses_info(self) -> None:
        out = Output(quiet=True)
        # These should not raise
        out.success("ok")
        out.info("info")
        out.warn("warn")

    def test_raw_json(self, capsys: pytest.CaptureFixture) -> None:  # type: ignore[type-arg]
        out = Output()
        out.raw_json({"key": "value"})
        captured = capsys.readouterr()
        assert '"key": "value"' in captured.out


# ---------------------------------------------------------------------------
# Utils tests
# ---------------------------------------------------------------------------
class TestUtils:
    def test_human_size(self) -> None:
        assert human_size(0) == "0.0 B"
        assert human_size(1024) == "1.0 KB"
        assert human_size(1024 * 1024) == "1.0 MB"
        assert human_size(1024 * 1024 * 1024) == "1.0 GB"

    def test_mask_secret(self) -> None:
        assert mask_secret("") == "***"
        assert mask_secret("short") == "***hort"
        assert mask_secret("my-very-long-secret-key") == "***-key"
        assert mask_secret("ab") == "***"

    def test_service_status_color(self) -> None:
        assert "[green]" in service_status_color("running")
        assert "[red]" in service_status_color("error")
        assert service_status_color("unknown") == "unknown"

    def test_find_project_root(self) -> None:
        # Should find a root from the cli/ directory
        root = find_project_root()
        assert (root / "pyproject.toml").exists()


# ---------------------------------------------------------------------------
# DB module tests
# ---------------------------------------------------------------------------
class TestDb:
    def test_validate_identifier(self) -> None:
        from kctl_api.core.db import validate_identifier

        assert validate_identifier("users") == "users"
        assert validate_identifier("my_table_123") == "my_table_123"
        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            validate_identifier("users; DROP TABLE users")
        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            validate_identifier("123abc")
        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            validate_identifier("table name")
