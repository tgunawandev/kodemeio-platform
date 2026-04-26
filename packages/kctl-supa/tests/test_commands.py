"""Integration tests for kctl-supa commands using mocks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_supa.cli import app
from kctl_supa.core.config import ServiceConfig

runner = CliRunner()

MOCK_CONFIG = ServiceConfig(
    url="https://supa.test.local",
    service_role_key="test-service-role-key-1234567890",
    anon_key="test-anon-key-1234567890",
    db_password="testpass",
    ssh_host="1.2.3.4",
    container_prefix="test-prefix",
)


_DOCKER_PATCH_TARGETS = [
    "kctl_supa.commands.db_cmd.DockerOps",
    "kctl_supa.commands.auth_cmd.DockerOps",
    "kctl_supa.commands.storage_cmd.DockerOps",
    "kctl_supa.commands.realtime_cmd.DockerOps",
    "kctl_supa.commands.functions_cmd.DockerOps",
    "kctl_supa.commands.cron_cmd.DockerOps",
    "kctl_supa.commands.vault_cmd.DockerOps",
    "kctl_supa.commands.publications_cmd.DockerOps",
    "kctl_supa.commands.integrations_cmd.DockerOps",
    "kctl_supa.commands.settings_cmd.DockerOps",
    "kctl_supa.commands.security_cmd.DockerOps",
    "kctl_supa.commands.monitor_cmd.DockerOps",
    "kctl_supa.commands.maintenance_cmd.DockerOps",
    "kctl_supa.commands.advisors_cmd.DockerOps",
    "kctl_supa.commands.logs_cmd.DockerOps",
    "kctl_supa.commands.doctor_cmd.DockerOps",
    "kctl_supa.commands.backup_cmd.DockerOps",
    "kctl_supa.commands.status_cmd.DockerOps",
    "kctl_supa.commands.dashboard_cmd.DockerOps",
]


@pytest.fixture()
def mock_docker():
    instance = MagicMock()
    instance.psql.return_value = " count \n-------\n    42\n(1 row)"
    instance.container_status.return_value = [
        {"Names": "test-db-1", "State": "running", "Status": "Up 5m (healthy)", "RunningFor": "5 minutes ago"}
    ]
    instance.docker_exec.return_value = "OK"
    instance.logs.return_value = "2026-01-01 test log line"
    instance.exec.return_value = "/dev/sda1 100G 30G 65G 32% /"
    patches = [patch(t, return_value=instance) for t in _DOCKER_PATCH_TARGETS]
    for p in patches:
        p.start()
    yield instance
    for p in patches:
        p.stop()


@pytest.fixture()
def mock_resolve():
    with patch("kctl_supa.core.callbacks.resolve_connection", return_value=MOCK_CONFIG):
        yield


class TestDbCommands:
    def test_db_size(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = "pg_size_pretty\n---------\n 50 MB\n(1 row)"
        result = runner.invoke(app, ["db", "size"])
        assert result.exit_code == 0
        assert "50 MB" in result.output

    def test_db_tables(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = "schemaname|table|n_live_tup\n---|---|---\npublic|users|100"
        result = runner.invoke(app, ["db", "tables"])
        assert result.exit_code == 0
        assert "users" in result.output

    def test_db_schemas(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = "schema_name\n---\npublic\nauth"
        result = runner.invoke(app, ["db", "schemas"])
        assert result.exit_code == 0
        assert "public" in result.output

    def test_db_extensions(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = "extname\n---\nplpgsql\npg_cron"
        result = runner.invoke(app, ["db", "extensions"])
        assert result.exit_code == 0
        assert "plpgsql" in result.output

    def test_db_roles(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = "rolname|rolsuper\n---|---\npostgres|t\nanon|f"
        result = runner.invoke(app, ["db", "roles"])
        assert result.exit_code == 0
        assert "postgres" in result.output

    def test_db_columns(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = "column_name|data_type\n---|---\nid|uuid\nemail|text"
        result = runner.invoke(app, ["db", "columns", "auth.users"])
        assert result.exit_code == 0
        assert "email" in result.output

    def test_db_webhooks_no_extension(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = " count \n-------\n    0\n(1 row)"
        result = runner.invoke(app, ["db", "webhooks"])
        assert result.exit_code == 0


class TestAuthCommands:
    def test_auth_stats(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = " count \n-------\n    5\n(1 row)"
        result = runner.invoke(app, ["auth", "stats"])
        assert result.exit_code == 0

    def test_auth_providers(self, mock_docker, mock_resolve):
        mock_docker.docker_exec.return_value = (
            "GOTRUE_EXTERNAL_EMAIL_ENABLED=true\nGOTRUE_EXTERNAL_GOOGLE_ENABLED=false"
        )
        result = runner.invoke(app, ["auth", "providers"])
        assert result.exit_code == 0
        assert "email" in result.output

    def test_auth_policies(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = "tablename|policyname\n---|---\n(0 rows)"
        result = runner.invoke(app, ["auth", "policies"])
        assert result.exit_code == 0


class TestStorageCommands:
    @patch("kctl_supa.commands.storage_cmd.SupabaseClient")
    def test_storage_buckets(self, mock_client_cls, mock_resolve, mock_docker):
        instance = MagicMock()
        mock_client_cls.return_value = instance
        instance.storage_list_buckets.return_value = [
            {"id": "avatars", "name": "avatars", "public": True, "created_at": "2026-01-01T00:00:00"}
        ]
        result = runner.invoke(app, ["storage", "buckets"])
        assert result.exit_code == 0
        assert "avatars" in result.output

    def test_storage_policies(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = "tablename|policyname\n---|---\n(0 rows)"
        result = runner.invoke(app, ["storage", "policies"])
        assert result.exit_code == 0

    def test_storage_usage(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = "pg_size_pretty\n---\n 1 MB\n(1 row)"
        result = runner.invoke(app, ["storage", "usage"])
        assert result.exit_code == 0
        assert "1 MB" in result.output


class TestRealtimeCommands:
    def test_realtime_status(self, mock_docker, mock_resolve):
        mock_docker.docker_exec.return_value = "healthy"
        result = runner.invoke(app, ["realtime", "status"])
        assert result.exit_code == 0
        assert "healthy" in result.output

    def test_realtime_connections(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = "active_connections\n---\n 3\n(1 row)"
        result = runner.invoke(app, ["realtime", "connections"])
        assert result.exit_code == 0


class TestCronCommands:
    def test_cron_list(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = "jobid|schedule|command\n---|---|---\n(0 rows)"
        result = runner.invoke(app, ["cron", "list"])
        assert result.exit_code == 0

    def test_cron_history(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = "jobid|status\n---|---\n(0 rows)"
        result = runner.invoke(app, ["cron", "history"])
        assert result.exit_code == 0


class TestVaultCommands:
    def test_vault_list_no_extension(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = " count \n-------\n    0\n(1 row)"
        result = runner.invoke(app, ["vault", "list"])
        assert result.exit_code == 0


class TestMonitorCommands:
    def test_monitor_overview(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = " count \n-------\n    10\n(1 row)"
        result = runner.invoke(app, ["monitor", "overview"])
        assert result.exit_code == 0

    def test_monitor_connections(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = "state|count\n---|---\nidle|5\nactive|2"
        result = runner.invoke(app, ["monitor", "connections"])
        assert result.exit_code == 0

    def test_monitor_slow_queries(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = "pid|duration|state|query\n---|---|---|---\n(0 rows)"
        result = runner.invoke(app, ["monitor", "slow-queries"])
        assert result.exit_code == 0


class TestSecurityCommands:
    def test_rls_policies(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = "schemaname|tablename|policyname\n---|---|---\n(0 rows)"
        result = runner.invoke(app, ["security", "rls-policies"])
        assert result.exit_code == 0

    def test_api_keys(self, mock_resolve):
        result = runner.invoke(app, ["security", "api-keys"])
        assert result.exit_code == 0
        assert "****" in result.output


class TestSettingsCommands:
    def test_settings_show(self, mock_resolve):
        result = runner.invoke(app, ["settings", "show"])
        assert result.exit_code == 0
        assert "supa.test.local" in result.output

    def test_settings_auth_config(self, mock_docker, mock_resolve):
        mock_docker.docker_exec.return_value = "GOTRUE_API_HOST=0.0.0.0\nGOTRUE_SMTP_HOST=mail.test"
        result = runner.invoke(app, ["settings", "auth-config"])
        assert result.exit_code == 0

    def test_settings_log_drains(self, mock_docker, mock_resolve):
        mock_docker.docker_exec.return_value = "sources:\n  docker_logs:"
        result = runner.invoke(app, ["settings", "log-drains"])
        assert result.exit_code == 0


class TestIntegrationsCommands:
    def test_integrations_status(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = " ?column? \n----------\n(0 rows)"
        result = runner.invoke(app, ["integrations", "status"])
        assert result.exit_code == 0

    def test_integrations_graphql(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = "routine_name|routine_type\n---|---\n(0 rows)"
        result = runner.invoke(app, ["integrations", "graphql"])
        assert result.exit_code == 0


class TestPublicationsCommands:
    def test_publications_list(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = "pubname\n---\nsupabase_realtime"
        result = runner.invoke(app, ["publications", "list"])
        assert result.exit_code == 0
        assert "supabase_realtime" in result.output


class TestAdvisorsCommands:
    def test_advisors_security(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = " count \n-------\n    0\n(1 row)"
        result = runner.invoke(app, ["advisors", "security"])
        assert result.exit_code == 0

    def test_advisors_performance(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = " count \n-------\n    99.5\n(1 row)"
        result = runner.invoke(app, ["advisors", "performance"])
        assert result.exit_code == 0

    def test_advisors_rls_audit(self, mock_docker, mock_resolve):
        mock_docker.psql.return_value = "schemaname|tablename\n---|---\n(0 rows)"
        result = runner.invoke(app, ["advisors", "rls-audit"])
        assert result.exit_code == 0
