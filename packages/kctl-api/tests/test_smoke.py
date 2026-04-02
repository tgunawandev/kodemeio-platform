"""Smoke tests for all kctl-api command groups.

Each test invokes `GROUP --help` and asserts exit_code == 0.
This ensures every command group is importable, registers correctly
in the Typer app, and exposes a working --help output.
"""

from __future__ import annotations

from typing import ClassVar

import pytest
from typer.testing import CliRunner

from kctl_api.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# Authentication & access
# ---------------------------------------------------------------------------
class TestConfigHelp:
    def test_config_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0

    def test_config_init_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["config", "init", "--help"])
        assert result.exit_code == 0

    def test_config_add_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["config", "add", "--help"])
        assert result.exit_code == 0

    def test_config_show_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["config", "show", "--help"])
        assert result.exit_code == 0


class TestAuthHelp:
    def test_auth_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["auth", "--help"])
        assert result.exit_code == 0

    def test_auth_login_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["auth", "login", "--help"])
        assert result.exit_code == 0

    def test_auth_logout_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["auth", "logout", "--help"])
        assert result.exit_code == 0


class TestHealthHelp:
    def test_health_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["health", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# API resources
# ---------------------------------------------------------------------------
class TestUsersHelp:
    def test_users_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["users", "--help"])
        assert result.exit_code == 0

    def test_users_list_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["users", "list", "--help"])
        assert result.exit_code == 0

    def test_users_get_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["users", "get", "--help"])
        assert result.exit_code == 0


class TestFilesHelp:
    def test_files_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["files", "--help"])
        assert result.exit_code == 0

    def test_files_list_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["files", "list", "--help"])
        assert result.exit_code == 0

    def test_files_info_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["files", "info", "--help"])
        assert result.exit_code == 0


class TestJobsHelp:
    def test_jobs_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["jobs", "--help"])
        assert result.exit_code == 0

    def test_jobs_overview_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["jobs", "overview", "--help"])
        assert result.exit_code == 0

    def test_jobs_status_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["jobs", "status", "--help"])
        assert result.exit_code == 0


class TestWorkflowsHelp:
    def test_workflows_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["workflows", "--help"])
        assert result.exit_code == 0

    def test_workflows_start_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["workflows", "start", "--help"])
        assert result.exit_code == 0

    def test_workflows_status_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["workflows", "status", "--help"])
        assert result.exit_code == 0

    def test_workflows_list_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["workflows", "list", "--help"])
        assert result.exit_code == 0


class TestAutomationHelp:
    def test_automation_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["automation", "--help"])
        assert result.exit_code == 0

    def test_automation_list_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["automation", "list", "--help"])
        assert result.exit_code == 0

    def test_automation_create_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["automation", "create", "--help"])
        assert result.exit_code == 0


class TestNotificationsHelp:
    def test_notifications_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["notifications", "--help"])
        assert result.exit_code == 0

    def test_notifications_mattermost_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["notifications", "mattermost", "--help"])
        assert result.exit_code == 0

    def test_notifications_telegram_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["notifications", "telegram", "--help"])
        assert result.exit_code == 0


class TestWebhooksHelp:
    def test_webhooks_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["webhooks", "--help"])
        assert result.exit_code == 0

    def test_webhooks_recent_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["webhooks", "recent", "--help"])
        assert result.exit_code == 0

    def test_webhooks_replay_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["webhooks", "replay", "--help"])
        assert result.exit_code == 0


class TestMarketplaceHelp:
    def test_marketplace_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["marketplace", "--help"])
        assert result.exit_code == 0

    def test_marketplace_list_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["marketplace", "list", "--help"])
        assert result.exit_code == 0

    def test_marketplace_search_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["marketplace", "search", "--help"])
        assert result.exit_code == 0


class TestSaasHelp:
    def test_saas_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["saas", "--help"])
        assert result.exit_code == 0

    def test_saas_create_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["saas", "create", "--help"])
        assert result.exit_code == 0

    def test_saas_status_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["saas", "status", "--help"])
        assert result.exit_code == 0


class TestStripeHelp:
    def test_stripe_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["stripe", "--help"])
        assert result.exit_code == 0

    def test_stripe_checkout_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["stripe", "checkout", "--help"])
        assert result.exit_code == 0

    def test_stripe_portal_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["stripe", "portal", "--help"])
        assert result.exit_code == 0

    def test_stripe_webhook_status_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["stripe", "webhook-status", "--help"])
        assert result.exit_code == 0


class TestOdooHelp:
    def test_odoo_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["odoo", "--help"])
        assert result.exit_code == 0

    def test_odoo_search_read_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["odoo", "search-read", "--help"])
        assert result.exit_code == 0

    def test_odoo_call_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["odoo", "call", "--help"])
        assert result.exit_code == 0


class TestRealtimeHelp:
    def test_realtime_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["realtime", "--help"])
        assert result.exit_code == 0

    def test_realtime_presence_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["realtime", "presence", "--help"])
        assert result.exit_code == 0

    def test_realtime_heartbeat_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["realtime", "heartbeat", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# AI platform
# ---------------------------------------------------------------------------
class TestAiHelp:
    def test_ai_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["ai", "--help"])
        assert result.exit_code == 0

    def test_ai_copilots_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["ai", "copilots", "--help"])
        assert result.exit_code == 0

    def test_ai_health_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["ai", "health", "--help"])
        assert result.exit_code == 0


class TestTenantAiHelp:
    def test_tenant_ai_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["tenant-ai", "--help"])
        assert result.exit_code == 0

    def test_tenant_ai_chat_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["tenant-ai", "chat", "--help"])
        assert result.exit_code == 0

    def test_tenant_ai_stream_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["tenant-ai", "stream", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------
class TestDbHelp:
    def test_db_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["db", "--help"])
        assert result.exit_code == 0

    def test_db_tables_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["db", "tables", "--help"])
        assert result.exit_code == 0

    def test_db_count_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["db", "count", "--help"])
        assert result.exit_code == 0


class TestRedisHelp:
    def test_redis_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["redis", "--help"])
        assert result.exit_code == 0

    def test_redis_info_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["redis", "info", "--help"])
        assert result.exit_code == 0

    def test_redis_keys_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["redis", "keys", "--help"])
        assert result.exit_code == 0

    def test_redis_get_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["redis", "get", "--help"])
        assert result.exit_code == 0


class TestStreamsHelp:
    def test_streams_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["streams", "--help"])
        assert result.exit_code == 0

    def test_streams_list_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["streams", "list", "--help"])
        assert result.exit_code == 0

    def test_streams_read_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["streams", "read", "--help"])
        assert result.exit_code == 0


class TestServicesHelp:
    def test_services_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["services", "--help"])
        assert result.exit_code == 0

    def test_services_list_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["services", "list", "--help"])
        assert result.exit_code == 0

    def test_services_status_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["services", "status", "--help"])
        assert result.exit_code == 0


class TestDeployHelp:
    def test_deploy_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["deploy", "--help"])
        assert result.exit_code == 0

    def test_deploy_status_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["deploy", "status", "--help"])
        assert result.exit_code == 0

    def test_deploy_logs_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["deploy", "logs", "--help"])
        assert result.exit_code == 0


class TestAppsHelp:
    def test_apps_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["apps", "--help"])
        assert result.exit_code == 0

    def test_apps_list_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["apps", "list", "--help"])
        assert result.exit_code == 0

    def test_apps_info_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["apps", "info", "--help"])
        assert result.exit_code == 0


class TestDockerHelp:
    def test_docker_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["docker", "--help"])
        assert result.exit_code == 0

    def test_docker_images_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["docker", "images", "--help"])
        assert result.exit_code == 0

    def test_docker_containers_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["docker", "containers", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Development tools
# ---------------------------------------------------------------------------
class TestDevHelp:
    def test_dev_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["dev", "--help"])
        assert result.exit_code == 0

    def test_dev_up_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["dev", "up", "--help"])
        assert result.exit_code == 0

    def test_dev_down_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["dev", "down", "--help"])
        assert result.exit_code == 0


class TestTestHelp:
    def test_test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["test", "--help"])
        assert result.exit_code == 0

    def test_test_run_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["test", "run", "--help"])
        assert result.exit_code == 0

    def test_test_coverage_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["test", "coverage", "--help"])
        assert result.exit_code == 0


class TestLintHelp:
    def test_lint_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["lint", "--help"])
        assert result.exit_code == 0

    def test_lint_check_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["lint", "check", "--help"])
        assert result.exit_code == 0

    def test_lint_fix_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["lint", "fix", "--help"])
        assert result.exit_code == 0


class TestFmtHelp:
    def test_fmt_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["fmt", "--help"])
        assert result.exit_code == 0

    def test_fmt_run_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["fmt", "run", "--help"])
        assert result.exit_code == 0

    def test_fmt_check_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["fmt", "check", "--help"])
        assert result.exit_code == 0


class TestBuildHelp:
    def test_build_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["build", "--help"])
        assert result.exit_code == 0

    def test_build_dev_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["build", "dev", "--help"])
        assert result.exit_code == 0

    def test_build_prod_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["build", "prod", "--help"])
        assert result.exit_code == 0

    def test_build_all_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["build", "all", "--help"])
        assert result.exit_code == 0


class TestScaffoldHelp:
    def test_scaffold_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["scaffold", "--help"])
        assert result.exit_code == 0

    def test_scaffold_app_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["scaffold", "app", "--help"])
        assert result.exit_code == 0

    def test_scaffold_endpoint_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["scaffold", "endpoint", "--help"])
        assert result.exit_code == 0


class TestShellHelp:
    def test_shell_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["shell", "--help"])
        assert result.exit_code == 0

    def test_shell_start_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["shell", "start", "--help"])
        assert result.exit_code == 0

    def test_shell_db_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["shell", "db", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# API analysis & testing
# ---------------------------------------------------------------------------
class TestOpenApiHelp:
    def test_openapi_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["openapi", "--help"])
        assert result.exit_code == 0

    def test_openapi_export_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["openapi", "export", "--help"])
        assert result.exit_code == 0

    def test_openapi_validate_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["openapi", "validate", "--help"])
        assert result.exit_code == 0


class TestRoutesHelp:
    def test_routes_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["routes", "--help"])
        assert result.exit_code == 0

    def test_routes_list_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["routes", "list", "--help"])
        assert result.exit_code == 0


class TestRateLimitHelp:
    def test_rate_limit_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["rate-limit", "--help"])
        assert result.exit_code == 0

    def test_rate_limit_tiers_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["rate-limit", "tiers", "--help"])
        assert result.exit_code == 0

    def test_rate_limit_test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["rate-limit", "test", "--help"])
        assert result.exit_code == 0


class TestWsHelp:
    def test_ws_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["ws", "--help"])
        assert result.exit_code == 0

    def test_ws_connect_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["ws", "connect", "--help"])
        assert result.exit_code == 0

    def test_ws_send_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["ws", "send", "--help"])
        assert result.exit_code == 0


class TestPerfHelp:
    def test_perf_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["perf", "--help"])
        assert result.exit_code == 0

    def test_perf_bench_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["perf", "bench", "--help"])
        assert result.exit_code == 0

    def test_perf_profile_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["perf", "profile", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Environment & security
# ---------------------------------------------------------------------------
class TestDoctorHelp:
    def test_doctor_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["doctor", "--help"])
        assert result.exit_code == 0


class TestEnvHelp:
    def test_env_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["env", "--help"])
        assert result.exit_code == 0

    def test_env_validate_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["env", "validate", "--help"])
        assert result.exit_code == 0


class TestSecurityHelp:
    def test_security_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["security", "--help"])
        assert result.exit_code == 0

    def test_security_audit_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["security", "audit", "--help"])
        assert result.exit_code == 0


class TestDepsHelp:
    def test_deps_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["deps", "--help"])
        assert result.exit_code == 0

    def test_deps_audit_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["deps", "audit", "--help"])
        assert result.exit_code == 0

    def test_deps_outdated_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["deps", "outdated", "--help"])
        assert result.exit_code == 0


class TestCleanHelp:
    def test_clean_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["clean", "--help"])
        assert result.exit_code == 0

    def test_clean_all_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["clean", "all", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Observability & monitoring
# ---------------------------------------------------------------------------
class TestLogsHelp:
    def test_logs_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["logs", "--help"])
        assert result.exit_code == 0

    def test_logs_follow_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["logs", "follow", "--help"])
        assert result.exit_code == 0

    def test_logs_errors_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["logs", "errors", "--help"])
        assert result.exit_code == 0


class TestDashboardHelp:
    def test_dashboard_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["dashboard", "--help"])
        assert result.exit_code == 0

    def test_dashboard_overview_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["dashboard", "overview", "--help"])
        assert result.exit_code == 0

    def test_dashboard_live_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["dashboard", "live", "--help"])
        assert result.exit_code == 0


class TestMonitorHelp:
    def test_monitor_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["monitor", "--help"])
        assert result.exit_code == 0

    def test_monitor_live_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["monitor", "live", "--help"])
        assert result.exit_code == 0

    def test_monitor_metrics_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["monitor", "metrics", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Skill generation
# ---------------------------------------------------------------------------
class TestSkillHelp:
    def test_skill_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["skill", "--help"])
        assert result.exit_code == 0

    def test_skill_generate_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["skill", "generate", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Comprehensive group registration check
# ---------------------------------------------------------------------------
class TestAllGroupsRegistered:
    """Verify every registered command group name appears in the top-level --help."""

    ALL_GROUPS: ClassVar[list[str]] = [
        # Authentication & access
        "config",
        "auth",
        "health",
        # API resources
        "users",
        "files",
        "jobs",
        "workflows",
        "automation",
        "notifications",
        "webhooks",
        "marketplace",
        "saas",
        "stripe",
        "odoo",
        "realtime",
        # AI platform
        "ai",
        "tenant-ai",
        # Infrastructure
        "db",
        "redis",
        "streams",
        "services",
        "deploy",
        "apps",
        "docker",
        # Development tools
        "dev",
        "test",
        "lint",
        "fmt",
        "build",
        "scaffold",
        "shell",
        # API analysis & testing
        "openapi",
        "routes",
        "rate-limit",
        "ws",
        "perf",
        # Environment & security
        "doctor",
        "env",
        "security",
        "deps",
        "clean",
        # Observability & monitoring
        "logs",
        "dashboard",
        "monitor",
        # Skill generation
        "skill",
    ]

    def test_all_groups_in_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for group in self.ALL_GROUPS:
            assert group in result.output, f"Command group '{group}' missing from --help output"
