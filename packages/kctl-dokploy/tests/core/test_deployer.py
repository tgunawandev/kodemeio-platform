"""Tests for the Deployer executor (12-phase deployment pipeline)."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from unittest.mock import MagicMock, call, patch

import pytest

from kctl_dokploy.core.deployer import Deployer, PhaseResult
from kctl_dokploy.core.manifest import (
    BackupConfig,
    DatabaseConfig,
    DeployManifest,
    DnsConfig,
    DomainConfig,
    HealthcheckConfig,
    InstanceConfig,
    PostDeployConfig,
    ScheduleConfig,
    SourceConfig,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manifest(**kwargs) -> DeployManifest:
    """Return a minimal but valid DeployManifest."""
    defaults = dict(
        server="srv-001",
        project="my-project",
        source=SourceConfig(owner="acme", repo="my-app", branch="main"),
        instance=InstanceConfig(name="my-app-prod"),
        dns=DnsConfig(zone="example.com", name="app.example.com", content="1.2.3.4"),
        domain=DomainConfig(host="app.example.com", port=8000, service="web"),
        database=DatabaseConfig(host="pg.example.com", name="mydb", user="myuser"),
        healthcheck=HealthcheckConfig(path="/health", port=8000, timeout=5, interval=1),
        env_defaults={"FOO": "bar"},
        post_deploy=PostDeployConfig(),
    )
    defaults.update(kwargs)
    return DeployManifest(**defaults)


def _mock_proc(returncode: int = 0, stdout: str = "") -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = ""
    return proc


# ---------------------------------------------------------------------------
# PhaseResult
# ---------------------------------------------------------------------------


class TestPhaseResult:
    def test_fields(self) -> None:
        r = PhaseResult(phase="dns", action="created", message="A record added")
        assert r.phase == "dns"
        assert r.action == "created"
        assert r.message == "A record added"

    def test_repr_contains_fields(self) -> None:
        r = PhaseResult(phase="deploy", action="skipped", message="dry run")
        assert "deploy" in repr(r)
        assert "skipped" in repr(r)


# ---------------------------------------------------------------------------
# _run_kctl
# ---------------------------------------------------------------------------


class TestRunKctl:
    def test_run_kctl_success(self) -> None:
        """Successful subprocess call returns (0, stdout)."""
        manifest = _make_manifest()
        deployer = Deployer(manifest=manifest, dry_run=False)

        with patch("subprocess.run", return_value=_mock_proc(0, "hello")) as mock_run:
            code, out = deployer._run_kctl(["kctl-dokploy", "compose", "list"])
            assert code == 0
            assert out == "hello"
            mock_run.assert_called_once()

    def test_run_kctl_failure(self) -> None:
        """Non-zero exit code is surfaced correctly."""
        manifest = _make_manifest()
        deployer = Deployer(manifest=manifest, dry_run=False)

        with patch("subprocess.run", return_value=_mock_proc(1, "")):
            code, out = deployer._run_kctl(["kctl-dokploy", "compose", "list"])
            assert code == 1

    def test_run_kctl_dry_run_skips_mutating(self) -> None:
        """In dry_run mode, mutating commands are skipped (not executed)."""
        manifest = _make_manifest()
        deployer = Deployer(manifest=manifest, dry_run=True)

        with patch("subprocess.run") as mock_run:
            code, out = deployer._run_kctl(["kctl-dokploy", "compose", "create", "--name", "x"])
            mock_run.assert_not_called()
            assert code == 0
            assert out == "[dry-run] skipped"

    def test_run_kctl_dry_run_allows_readonly(self) -> None:
        """In dry_run mode, read-only commands are still executed."""
        manifest = _make_manifest()
        deployer = Deployer(manifest=manifest, dry_run=True)

        with patch("subprocess.run", return_value=_mock_proc(0, "[]")) as mock_run:
            code, out = deployer._run_kctl(["kctl-dokploy", "compose", "list"])
            mock_run.assert_called_once()
            assert code == 0

    def test_run_kctl_dry_run_allows_get(self) -> None:
        """'get' commands are read-only and run even in dry_run mode."""
        manifest = _make_manifest()
        deployer = Deployer(manifest=manifest, dry_run=True)

        with patch("subprocess.run", return_value=_mock_proc(0, "{}")) as mock_run:
            code, _out = deployer._run_kctl(["kctl-dokploy", "domains", "get", "comp-abc"])
            mock_run.assert_called_once()

    def test_run_kctl_dry_run_skips_redeploy(self) -> None:
        """'redeploy' is a mutating command and must be skipped in dry_run."""
        manifest = _make_manifest()
        deployer = Deployer(manifest=manifest, dry_run=True)

        with patch("subprocess.run") as mock_run:
            code, _out = deployer._run_kctl(["kctl-dokploy", "compose", "redeploy", "comp-abc"])
            mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# _run_kctl_json
# ---------------------------------------------------------------------------


class TestRunKctlJson:
    def test_inserts_json_flag_and_parses(self) -> None:
        manifest = _make_manifest()
        deployer = Deployer(manifest=manifest, dry_run=False)
        payload = [{"id": "1"}]

        with patch("subprocess.run", return_value=_mock_proc(0, json.dumps(payload))):
            result = deployer._run_kctl_json(["kctl-dokploy", "compose", "list"])
            assert result == payload

    def test_returns_empty_list_on_failure(self) -> None:
        manifest = _make_manifest()
        deployer = Deployer(manifest=manifest, dry_run=False)

        with patch("subprocess.run", return_value=_mock_proc(1, "")):
            result = deployer._run_kctl_json(["kctl-dokploy", "compose", "list"])
            assert result == []

    def test_returns_empty_list_on_invalid_json(self) -> None:
        manifest = _make_manifest()
        deployer = Deployer(manifest=manifest, dry_run=False)

        with patch("subprocess.run", return_value=_mock_proc(0, "not-json")):
            result = deployer._run_kctl_json(["kctl-dokploy", "compose", "list"])
            assert result == []


# ---------------------------------------------------------------------------
# _record_phase
# ---------------------------------------------------------------------------


class TestRecordPhase:
    def test_phase_result_tracking(self) -> None:
        """_record_phase appends a PhaseResult to the results list."""
        manifest = _make_manifest()
        deployer = Deployer(manifest=manifest, dry_run=False)

        deployer._record_phase("dns", "created", "DNS record added")
        deployer._record_phase("database", "skipped", "already exists")

        assert len(deployer.results) == 2
        assert deployer.results[0].phase == "dns"
        assert deployer.results[0].action == "created"
        assert deployer.results[1].phase == "database"
        assert deployer.results[1].action == "skipped"

    def test_results_initially_empty(self) -> None:
        manifest = _make_manifest()
        deployer = Deployer(manifest=manifest, dry_run=False)
        assert deployer.results == []


# ---------------------------------------------------------------------------
# Individual phases — smoke tests (verify they record a result)
# ---------------------------------------------------------------------------


class TestPhaseDns:
    def test_creates_record_when_missing(self) -> None:
        manifest = _make_manifest()
        deployer = Deployer(manifest=manifest, dry_run=False)

        # First call (list) returns text without the FQDN; second call (create) succeeds
        list_empty = _mock_proc(0, "No records found")
        create_ok = _mock_proc(0, "{}")

        with patch("subprocess.run", side_effect=[list_empty, create_ok]):
            deployer.phase_dns()

        assert any(r.phase == "dns" for r in deployer.results)
        dns_result = next(r for r in deployer.results if r.phase == "dns")
        assert dns_result.action == "created"

    def test_skips_when_record_exists(self) -> None:
        manifest = _make_manifest(dns=DnsConfig(zone="example.com", name="app.example.com", content="1.2.3.4"))
        deployer = Deployer(manifest=manifest, dry_run=False)

        # JSON output from kctl-cf records list containing matching FQDN
        existing_records = [{"name": "app.example.com", "type": "A", "content": "1.2.3.4"}]
        with patch("subprocess.run", return_value=_mock_proc(0, json.dumps(existing_records))):
            deployer.phase_dns()

        dns_result = next(r for r in deployer.results if r.phase == "dns")
        assert dns_result.action == "skipped"


class TestPhaseDatabase:
    def test_creates_user_and_db_when_missing(self) -> None:
        manifest = _make_manifest()
        deployer = Deployer(manifest=manifest, dry_run=False)

        # users list → empty, create user → ok, db list → empty, create db → ok
        responses = [
            _mock_proc(0, json.dumps([])),
            _mock_proc(0, ""),
            _mock_proc(0, json.dumps([])),
            _mock_proc(0, ""),
        ]
        with patch("subprocess.run", side_effect=responses):
            deployer.phase_database()

        db_result = next(r for r in deployer.results if r.phase == "database")
        assert db_result.action == "created"

    def test_skips_when_db_exists(self) -> None:
        manifest = _make_manifest()
        deployer = Deployer(manifest=manifest, dry_run=False)

        # phase_database checks db list first (via _run_kctl_json which adds --json)
        dbs = [{"datname": "mydb"}]
        with patch(
            "subprocess.run",
            return_value=_mock_proc(0, json.dumps(dbs)),
        ):
            deployer.phase_database()

        db_result = next(r for r in deployer.results if r.phase == "database")
        assert db_result.action == "skipped"


class TestPhaseRegistry:
    def test_skips_when_ghcr_exists(self) -> None:
        manifest = _make_manifest()
        deployer = Deployer(manifest=manifest, dry_run=False)

        registries = [{"registryType": "ghcr", "registryName": "ghcr"}]
        with patch("subprocess.run", return_value=_mock_proc(0, json.dumps(registries))):
            deployer.phase_registry()

        reg_result = next(r for r in deployer.results if r.phase == "registry")
        assert reg_result.action == "skipped"

    def test_skips_with_manual_note_when_missing(self) -> None:
        manifest = _make_manifest()
        deployer = Deployer(manifest=manifest, dry_run=False)

        with patch("subprocess.run", return_value=_mock_proc(0, json.dumps([]))):
            deployer.phase_registry()

        reg_result = next(r for r in deployer.results if r.phase == "registry")
        assert reg_result.action == "skipped"
        assert "manual" in reg_result.message.lower()


class TestPhaseCompose:
    def test_creates_when_missing(self) -> None:
        manifest = _make_manifest()
        deployer = Deployer(manifest=manifest, dry_run=False)

        projects = [
            {
                "projectId": "proj-1",
                "name": "my-project",
                "environments": [
                    {"environmentId": "env-1", "isDefault": True, "compose": []},
                ],
            }
        ]
        servers = [{"name": "srv-001", "serverId": "server-1"}]
        create_resp = {"composeId": "comp-new-1"}
        git_providers = [{"providerType": "github", "github": {"githubId": "gh-1"}}]

        with patch(
            "subprocess.run",
            side_effect=[
                _mock_proc(0, json.dumps(projects)),  # projects list
                _mock_proc(0, json.dumps(servers)),  # servers list (resolve server)
                _mock_proc(0, json.dumps(create_resp)),  # compose create
                _mock_proc(0, json.dumps(git_providers)),  # git providers list
                _mock_proc(0, "{}"),  # compose update (source)
            ],
        ):
            deployer.phase_compose()

        assert deployer._compose_id == "comp-new-1"
        comp_result = next(r for r in deployer.results if r.phase == "compose")
        assert comp_result.action == "created"

    def test_updates_when_exists(self) -> None:
        manifest = _make_manifest(instance=InstanceConfig(name="web-app"))
        deployer = Deployer(manifest=manifest, dry_run=False)

        projects = [
            {
                "projectId": "proj-1",
                "name": "my-project",
                "environments": [
                    {
                        "environmentId": "env-1",
                        "isDefault": True,
                        "compose": [{"composeId": "comp-abc", "name": "web-app", "githubId": "gh-123"}],
                    },
                ],
            }
        ]
        with patch(
            "subprocess.run",
            side_effect=[
                _mock_proc(0, json.dumps(projects)),
                _mock_proc(0, "{}"),  # update
            ],
        ):
            deployer.phase_compose()

        assert deployer._compose_id == "comp-abc"
        comp_result = next(r for r in deployer.results if r.phase == "compose")
        assert comp_result.action == "updated"


class TestPhaseDeploy:
    def test_calls_redeploy(self) -> None:
        manifest = _make_manifest()
        deployer = Deployer(manifest=manifest, dry_run=False)
        deployer._compose_id = "comp-abc"

        # redeploy returns OK, then polling returns deployment with status=done
        done_deployment = [{"status": "done", "deploymentId": "dep-1"}]
        with patch(
            "subprocess.run",
            side_effect=[
                _mock_proc(0, ""),  # redeploy
                _mock_proc(0, json.dumps(done_deployment)),  # poll status
            ],
        ):
            deployer.phase_deploy()

        deploy_result = next(r for r in deployer.results if r.phase == "deploy")
        assert deploy_result.action == "updated"

    def test_fails_without_compose_id(self) -> None:
        manifest = _make_manifest()
        deployer = Deployer(manifest=manifest, dry_run=False)
        # _compose_id not set

        with patch("subprocess.run", return_value=_mock_proc(1, "error")):
            deployer.phase_deploy()

        deploy_result = next(r for r in deployer.results if r.phase == "deploy")
        assert deploy_result.action == "failed"


class TestPhaseVerify:
    def test_success_on_200(self) -> None:
        manifest = _make_manifest()
        deployer = Deployer(manifest=manifest, dry_run=False)

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("httpx.get", return_value=mock_resp):
            deployer.phase_verify()

        verify_result = next(r for r in deployer.results if r.phase == "verify")
        assert verify_result.action != "failed"

    def test_fails_on_timeout(self) -> None:
        manifest = _make_manifest(healthcheck=HealthcheckConfig(path="/health", port=8000, timeout=1, interval=1))
        deployer = Deployer(manifest=manifest, dry_run=False)

        import httpx

        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            deployer.phase_verify()

        verify_result = next(r for r in deployer.results if r.phase == "verify")
        assert verify_result.action == "failed"


class TestPhaseBackup:
    def test_creates_backup_config(self) -> None:
        manifest = _make_manifest(backup=BackupConfig(destination="my-s3", schedule="0 3 * * *"))
        deployer = Deployer(manifest=manifest, dry_run=False)
        deployer._compose_id = "comp-abc"

        destinations = [{"name": "my-s3", "destinationId": "dest-123"}]
        with patch(
            "subprocess.run",
            side_effect=[
                _mock_proc(0, json.dumps([])),  # backups list
                _mock_proc(0, json.dumps(destinations)),  # destinations list
                _mock_proc(0, "{}"),  # backup create
            ],
        ):
            deployer.phase_backup()

        backup_result = next(r for r in deployer.results if r.phase == "backup")
        assert backup_result.action == "created"

    def test_fails_when_destination_not_found(self) -> None:
        manifest = _make_manifest(backup=BackupConfig(destination="nonexistent"))
        deployer = Deployer(manifest=manifest, dry_run=False)
        deployer._compose_id = "comp-abc"

        with patch(
            "subprocess.run",
            side_effect=[
                _mock_proc(0, json.dumps([])),  # backups list (empty)
                _mock_proc(0, json.dumps([])),  # destinations list (empty)
            ],
        ):
            deployer.phase_backup()

        backup_result = next(r for r in deployer.results if r.phase == "backup")
        assert backup_result.action == "failed"
        assert "not found" in backup_result.message

    def test_skips_when_no_backup_config(self) -> None:
        manifest = _make_manifest(backup=None)
        deployer = Deployer(manifest=manifest, dry_run=False)

        with patch("subprocess.run") as mock_run:
            deployer.phase_backup()
            mock_run.assert_not_called()

        backup_result = next(r for r in deployer.results if r.phase == "backup")
        assert backup_result.action == "skipped"

    def test_skips_when_backup_already_exists(self) -> None:
        manifest = _make_manifest(backup=BackupConfig(destination="my-s3"))
        deployer = Deployer(manifest=manifest, dry_run=False)
        deployer._compose_id = "comp-abc"

        existing_backups = [{"backupId": "bk-1", "status": "active"}]
        with patch(
            "subprocess.run",
            return_value=_mock_proc(0, json.dumps(existing_backups)),
        ):
            deployer.phase_backup()

        backup_result = next(r for r in deployer.results if r.phase == "backup")
        assert backup_result.action == "skipped"


class TestPhaseSchedules:
    def test_creates_missing_schedules(self) -> None:
        manifest = _make_manifest(
            schedules=[ScheduleConfig(name="cleanup", cron="0 4 * * *", command="echo hi", service="web")]
        )
        deployer = Deployer(manifest=manifest, dry_run=False)
        deployer._compose_id = "comp-abc"

        with patch(
            "subprocess.run",
            side_effect=[
                _mock_proc(0, json.dumps([])),  # schedules list
                _mock_proc(0, "{}"),  # schedule create
            ],
        ):
            deployer.phase_schedules()

        sched_result = next(r for r in deployer.results if r.phase == "schedules")
        assert sched_result.action == "created"

    def test_normalizes_shell_path(self) -> None:
        """Shell paths like /bin/sh should be normalized to 'sh'."""
        manifest = _make_manifest(
            schedules=[ScheduleConfig(name="job", cron="0 * * * *", command="ls", shell="/bin/bash")]
        )
        deployer = Deployer(manifest=manifest, dry_run=False)
        deployer._compose_id = "comp-abc"

        with patch(
            "subprocess.run",
            side_effect=[
                _mock_proc(0, json.dumps([])),  # schedules list
                _mock_proc(0, "{}"),  # schedule create
            ],
        ) as mock_run:
            deployer.phase_schedules()

        # Verify the create command uses normalized shell name
        create_call = mock_run.call_args_list[-1]
        cmd_args = create_call.args[0]
        shell_idx = cmd_args.index("--shell") + 1
        assert cmd_args[shell_idx] == "bash"  # /bin/bash → bash

    def test_skips_when_no_schedules(self) -> None:
        manifest = _make_manifest(schedules=[])
        deployer = Deployer(manifest=manifest, dry_run=False)

        with patch("subprocess.run") as mock_run:
            deployer.phase_schedules()
            mock_run.assert_not_called()

        sched_result = next(r for r in deployer.results if r.phase == "schedules")
        assert sched_result.action == "skipped"

    def test_skips_without_compose_id(self) -> None:
        manifest = _make_manifest(schedules=[ScheduleConfig(name="cleanup", cron="0 4 * * *", command="echo hi")])
        deployer = Deployer(manifest=manifest, dry_run=False)
        # No compose_id set

        with patch("subprocess.run") as mock_run:
            deployer.phase_schedules()
            mock_run.assert_not_called()

        sched_result = next(r for r in deployer.results if r.phase == "schedules")
        assert sched_result.action == "skipped"


class TestPhasePostDeploy:
    def test_runs_odoo_bundles_when_profile_set(self) -> None:
        manifest = _make_manifest(post_deploy=PostDeployConfig(odoo_profile="profile-hrms"))
        deployer = Deployer(manifest=manifest, dry_run=False)

        with patch("subprocess.run", return_value=_mock_proc(0, "")) as mock_run:
            deployer.phase_post_deploy()

        # Should have called kctl-odoo bundles profile-install
        calls_flat = [arg for c in mock_run.call_args_list for arg in c.args[0]]
        assert "kctl-odoo" in calls_flat
        assert "hrms" in calls_flat  # profile- prefix stripped
        post_result = next(r for r in deployer.results if r.phase == "post_deploy")
        assert post_result.action != "failed"

    def test_runs_custom_commands(self) -> None:
        manifest = _make_manifest(post_deploy=PostDeployConfig(commands=["kctl-odoo doctor check"]))
        deployer = Deployer(manifest=manifest, dry_run=False)

        with patch("subprocess.run", return_value=_mock_proc(0, "")):
            deployer.phase_post_deploy()

        post_result = next(r for r in deployer.results if r.phase == "post_deploy")
        assert post_result.action != "failed"

    def test_skips_when_no_actions(self) -> None:
        manifest = _make_manifest(post_deploy=PostDeployConfig())
        deployer = Deployer(manifest=manifest, dry_run=False)

        with patch("subprocess.run") as mock_run:
            deployer.phase_post_deploy()
            mock_run.assert_not_called()

        post_result = next(r for r in deployer.results if r.phase == "post_deploy")
        assert post_result.action == "skipped"


# ---------------------------------------------------------------------------
# run_all
# ---------------------------------------------------------------------------


class TestRunAll:
    def test_returns_13_results(self) -> None:
        """run_all must produce one result per execution phase (13 phases: validate + 12)."""
        manifest = _make_manifest()
        deployer = Deployer(manifest=manifest, dry_run=True)

        # Provide enough mock responses to feed every subprocess call
        generic = _mock_proc(0, json.dumps([]))

        with patch("subprocess.run", return_value=generic):
            results = deployer.run_all()

        phases = [r.phase for r in results]
        assert len(results) == 13
        expected_phases = [
            "validate",
            "dns",
            "database",
            "registry",
            "compose",
            "environment",
            "domain",
            "deploy",
            "verify",
            "backup",
            "schedules",
            "volume_backups",
            "post_deploy",
        ]
        for phase in expected_phases:
            assert phase in phases, f"Missing phase: {phase}"

    def test_returns_list_of_phase_results(self) -> None:
        manifest = _make_manifest()
        deployer = Deployer(manifest=manifest, dry_run=True)

        with patch("subprocess.run", return_value=_mock_proc(0, json.dumps([]))):
            results = deployer.run_all()

        assert all(isinstance(r, PhaseResult) for r in results)
