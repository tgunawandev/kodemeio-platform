"""Core unit tests for kctl-rustdesk.

Tests service key, config resolution, executor logic, and AppContext
without making any real SSH or Docker connections.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestVersion:
    def test_version_string_is_set(self) -> None:
        from kctl_rustdesk import __version__

        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_version_semver_format(self) -> None:
        from kctl_rustdesk import __version__

        parts = __version__.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)


class TestServiceKey:
    def test_service_key_value(self) -> None:
        from kctl_rustdesk.core.config import SERVICE_KEY

        assert SERVICE_KEY == "rustdesk"

    def test_env_prefix_value(self) -> None:
        from kctl_rustdesk.core.config import ENV_PREFIX

        assert ENV_PREFIX == "KCTL_RUSTDESK"


class TestServiceConfig:
    def test_default_config_values(self) -> None:
        from kctl_rustdesk.core.config import ServiceConfig

        cfg = ServiceConfig()
        assert cfg.host == "localhost"
        assert cfg.ssh_user == "root"
        assert cfg.project_name == "kodemeio-rustdesk"
        assert cfg.domain == "rustdesk.kodeme.io"
        assert "/opt/kodemeio-rustdesk" in cfg.compose_file
        assert "/opt/kodemeio-rustdesk" in cfg.env_file

    def test_config_accepts_custom_values(self) -> None:
        from kctl_rustdesk.core.config import ServiceConfig

        cfg = ServiceConfig(host="10.0.0.5", ssh_user="admin", project_name="myproject")
        assert cfg.host == "10.0.0.5"
        assert cfg.ssh_user == "admin"
        assert cfg.project_name == "myproject"


class TestResolveConnection:
    def test_host_override_takes_priority(self) -> None:
        from kctl_rustdesk.core.config import resolve_connection

        with (
            patch("kctl_rustdesk.core.config._resolve_active_profile_name", return_value="default"),
            patch("kctl_rustdesk.core.config._get_service_config", return_value={}),
        ):
            cfg = resolve_connection(host_override="192.168.1.10")
            assert cfg.host == "192.168.1.10"

    def test_env_var_host_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from kctl_rustdesk.core.config import resolve_connection

        monkeypatch.setenv("KCTL_RUSTDESK_HOST", "env-host.example.com")
        with (
            patch("kctl_rustdesk.core.config._resolve_active_profile_name", return_value="default"),
            patch("kctl_rustdesk.core.config._get_service_config", return_value={}),
        ):
            cfg = resolve_connection()
            assert cfg.host == "env-host.example.com"

    def test_explicit_override_beats_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from kctl_rustdesk.core.config import resolve_connection

        monkeypatch.setenv("KCTL_RUSTDESK_HOST", "env-host.example.com")
        with (
            patch("kctl_rustdesk.core.config._resolve_active_profile_name", return_value="default"),
            patch("kctl_rustdesk.core.config._get_service_config", return_value={}),
        ):
            cfg = resolve_connection(host_override="cli-override.example.com")
            assert cfg.host == "cli-override.example.com"

    def test_env_var_ssh_user_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from kctl_rustdesk.core.config import resolve_connection

        monkeypatch.setenv("KCTL_RUSTDESK_SSH_USER", "deploy")
        with (
            patch("kctl_rustdesk.core.config._resolve_active_profile_name", return_value="default"),
            patch("kctl_rustdesk.core.config._get_service_config", return_value={}),
        ):
            cfg = resolve_connection()
            assert cfg.ssh_user == "deploy"


class TestRustDeskExecutor:
    def test_local_host_is_not_remote(self) -> None:
        from kctl_rustdesk.core.config import ServiceConfig
        from kctl_rustdesk.core.executor import RustDeskExecutor

        cfg = ServiceConfig(host="localhost")
        ex = RustDeskExecutor(cfg)
        assert ex.is_remote is False

    def test_loopback_is_not_remote(self) -> None:
        from kctl_rustdesk.core.config import ServiceConfig
        from kctl_rustdesk.core.executor import RustDeskExecutor

        cfg = ServiceConfig(host="127.0.0.1")
        ex = RustDeskExecutor(cfg)
        assert ex.is_remote is False

    def test_remote_host_is_remote(self) -> None:
        from kctl_rustdesk.core.config import ServiceConfig
        from kctl_rustdesk.core.executor import RustDeskExecutor

        cfg = ServiceConfig(host="10.0.0.5")
        ex = RustDeskExecutor(cfg)
        assert ex.is_remote is True

    def test_container_names_use_project(self) -> None:
        from kctl_rustdesk.core.config import ServiceConfig
        from kctl_rustdesk.core.executor import RustDeskExecutor

        cfg = ServiceConfig(project_name="my-rustdesk")
        ex = RustDeskExecutor(cfg)
        assert ex.hbbs_container == "my-rustdesk-hbbs-1"
        assert ex.hbbr_container == "my-rustdesk-hbbr-1"

    def test_wrap_ssh_adds_ssh_for_remote(self) -> None:
        from kctl_rustdesk.core.config import ServiceConfig
        from kctl_rustdesk.core.executor import RustDeskExecutor

        cfg = ServiceConfig(host="10.0.0.5", ssh_user="admin")
        ex = RustDeskExecutor(cfg)
        wrapped = ex._wrap_ssh(["docker", "ps"])
        assert wrapped[0] == "ssh"
        assert "admin@10.0.0.5" in wrapped

    def test_wrap_ssh_passthrough_for_local(self) -> None:
        from kctl_rustdesk.core.config import ServiceConfig
        from kctl_rustdesk.core.executor import RustDeskExecutor

        cfg = ServiceConfig(host="localhost")
        ex = RustDeskExecutor(cfg)
        cmd = ["docker", "ps"]
        assert ex._wrap_ssh(cmd) == cmd

    def test_docker_ps_returns_empty_on_failure(self) -> None:
        from kctl_rustdesk.core.config import ServiceConfig
        from kctl_rustdesk.core.executor import RustDeskExecutor
        from kctl_lib.exceptions import CommandError

        cfg = ServiceConfig()
        ex = RustDeskExecutor(cfg)
        with patch.object(ex, "shell", side_effect=CommandError("docker", 1, "not found")):
            result = ex.docker_ps()
            assert result == []

    def test_container_running_returns_false_on_failure(self) -> None:
        from kctl_rustdesk.core.config import ServiceConfig
        from kctl_rustdesk.core.executor import RustDeskExecutor
        from kctl_lib.exceptions import CommandError

        cfg = ServiceConfig()
        ex = RustDeskExecutor(cfg)
        with patch.object(ex, "shell", side_effect=CommandError("ssh", 255, "connection refused")):
            assert ex.container_running("hbbs") is False

    def test_container_running_detects_service_in_output(self) -> None:
        from kctl_rustdesk.core.config import ServiceConfig
        from kctl_rustdesk.core.executor import RustDeskExecutor

        cfg = ServiceConfig()
        ex = RustDeskExecutor(cfg)
        with patch.object(ex, "shell", return_value="hbbs\nhbbr"):
            assert ex.container_running("hbbs") is True
            assert ex.container_running("hbbr") is True

    def test_container_running_returns_false_when_absent(self) -> None:
        from kctl_rustdesk.core.config import ServiceConfig
        from kctl_rustdesk.core.executor import RustDeskExecutor

        cfg = ServiceConfig()
        ex = RustDeskExecutor(cfg)
        with patch.object(ex, "shell", return_value="hbbr"):
            assert ex.container_running("hbbs") is False

    def test_get_container_stats_returns_dashes_on_empty(self) -> None:
        from kctl_rustdesk.core.config import ServiceConfig
        from kctl_rustdesk.core.executor import RustDeskExecutor

        cfg = ServiceConfig()
        ex = RustDeskExecutor(cfg)
        with patch.object(ex, "shell", return_value=""):
            stats = ex.get_container_stats("hbbs")
            assert stats["cpu"] == "-"
            assert stats["mem_usage"] == "-"
            assert stats["mem_pct"] == "-"

    def test_get_container_stats_parses_output(self) -> None:
        from kctl_rustdesk.core.config import ServiceConfig
        from kctl_rustdesk.core.executor import RustDeskExecutor

        cfg = ServiceConfig()
        ex = RustDeskExecutor(cfg)
        with patch.object(ex, "shell", return_value="1.5%\t50MiB / 1GiB\t5%"):
            stats = ex.get_container_stats("hbbs")
            assert stats["cpu"] == "1.5%"
            assert stats["mem_usage"] == "50MiB / 1GiB"
            assert stats["mem_pct"] == "5%"

    def test_query_db_returns_empty_on_blank_output(self) -> None:
        from kctl_rustdesk.core.config import ServiceConfig
        from kctl_rustdesk.core.executor import RustDeskExecutor

        cfg = ServiceConfig()
        ex = RustDeskExecutor(cfg)
        with patch.object(ex, "exec_hbbs", return_value=""):
            result = ex.query_db("SELECT * FROM peer;")
            assert result == []

    def test_query_db_parses_csv(self) -> None:
        from kctl_rustdesk.core.config import ServiceConfig
        from kctl_rustdesk.core.executor import RustDeskExecutor

        cfg = ServiceConfig()
        ex = RustDeskExecutor(cfg)
        with patch.object(ex, "exec_hbbs", return_value="id,uuid\nabc,def\n"):
            rows = ex.query_db("SELECT id, uuid FROM peer;")
            assert len(rows) == 1
            assert rows[0]["id"] == "abc"
            assert rows[0]["uuid"] == "def"


class TestAppContext:
    def test_app_context_extends_base(self) -> None:
        from kctl_lib.callbacks import AppContextBase
        from kctl_rustdesk.core.callbacks import AppContext

        assert issubclass(AppContext, AppContextBase)

    def test_app_context_has_host_override_field(self) -> None:
        from kctl_rustdesk.core.callbacks import AppContext

        ctx = AppContext(quiet=True, host_override="10.0.0.1")
        assert ctx.host_override == "10.0.0.1"

    def test_app_context_host_override_defaults_to_none(self) -> None:
        from kctl_rustdesk.core.callbacks import AppContext

        ctx = AppContext(quiet=True)
        assert ctx.host_override is None

    def test_executor_is_lazy_loaded(self) -> None:
        from kctl_rustdesk.core.callbacks import AppContext
        from kctl_rustdesk.core.executor import RustDeskExecutor

        ctx = AppContext(quiet=True)
        assert ctx._executor is None

        with patch("kctl_rustdesk.core.callbacks.resolve_connection") as mock_resolve:
            from kctl_rustdesk.core.config import ServiceConfig

            mock_resolve.return_value = ServiceConfig()
            executor = ctx.executor
            assert isinstance(executor, RustDeskExecutor)
            mock_resolve.assert_called_once_with(
                profile_name=None,
                host_override=None,
            )


class TestCLIRegistration:
    def test_all_command_groups_registered(self) -> None:
        from kctl_rustdesk.cli import app

        group_names = sorted(g.name for g in app.registered_groups)
        expected = sorted(
            [
                "audit",
                "backup",
                "config",
                "dashboard",
                "doctor",
                "health",
                "maintenance",
                "peers",
                "setup",
                "skill",
                "users",
            ]
        )
        assert group_names == expected

    def test_app_name(self) -> None:
        from kctl_rustdesk.cli import app

        assert app.info.name == "kctl-rustdesk"


class TestExceptions:
    def test_kctl_error_importable_from_lib(self) -> None:
        from kctl_lib.exceptions import KctlError, CommandError, DockerError

        assert issubclass(CommandError, KctlError)
        assert issubclass(DockerError, KctlError)
