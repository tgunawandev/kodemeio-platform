"""Tests for pipeline commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest
import typer

from kctl_odoo.core.output import Output

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actx(*, json_mode: bool = False, client: MagicMock | None = None) -> MagicMock:
    """Build a minimal AppContext mock."""
    actx = MagicMock()
    actx.json_mode = json_mode
    actx.output = Output(json_mode=json_mode)
    actx.client = client or MagicMock()
    return actx


def _make_ctx(actx: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.obj = actx
    return ctx


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


class TestValidate:
    """pipeline validate command tests."""

    def test_validate_all_pass_json(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """All steps pass -> exit code 0, JSON with passed=true."""
        mock_client.check_health.return_value = (True, "18.0")
        mock_client.search_read.return_value = []  # no broken modules
        mock_client.search_count.return_value = 10  # smoke test counts

        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.pipeline import validate

        validate(ctx, skip_lint=True, skip_test=True)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["passed"] is True
        assert len(data["steps"]) == 2  # preflight + smoke_test
        assert all(s["passed"] for s in data["steps"])

    def test_validate_broken_modules_fail(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """Broken modules cause preflight to fail."""
        mock_client.check_health.return_value = (True, "18.0")
        mock_client.search_read.return_value = [{"name": "sale", "state": "to upgrade"}]
        mock_client.search_count.return_value = 5

        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.pipeline import validate

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            validate(ctx, skip_lint=True, skip_test=True)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["passed"] is False
        preflight = next(s for s in data["steps"] if s["name"] == "preflight")
        assert preflight["passed"] is False

    def test_validate_unhealthy_instance(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """Unhealthy instance causes preflight to fail."""
        mock_client.check_health.return_value = (False, "Connection refused")
        mock_client.search_read.return_value = []
        mock_client.search_count.return_value = 0

        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.pipeline import validate

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            validate(ctx, skip_lint=True, skip_test=True)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["passed"] is False

    def test_validate_pretty_output(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """Pretty mode renders a table without JSON."""
        mock_client.check_health.return_value = (True, "18.0")
        mock_client.search_read.return_value = []
        mock_client.search_count.return_value = 5

        actx = _make_actx(json_mode=False, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.pipeline import validate

        validate(ctx, skip_lint=True, skip_test=True)

        captured = capsys.readouterr()
        # Pretty mode should not produce valid JSON on stdout
        with pytest.raises(json.JSONDecodeError):
            json.loads(captured.out)


# ---------------------------------------------------------------------------
# promote
# ---------------------------------------------------------------------------


class TestPromote:
    """pipeline promote command tests."""

    @patch("kctl_odoo.commands.pipeline._get_client_for_profile")
    def test_promote_diff_json(self, mock_get_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """Promote shows diff between two instances in JSON."""
        src_client = MagicMock()
        src_client.search_read.side_effect = [
            [
                {"name": "module_a", "installed_version": "18.0.1.0.0", "state": "installed"},
                {"name": "module_b", "installed_version": "18.0.1.0.0", "state": "installed"},
            ],
            [{"key": "web.base.url", "value": "https://staging.example.com"}],
        ]

        tgt_client = MagicMock()
        tgt_client.search_read.side_effect = [
            [{"name": "module_b", "installed_version": "18.0.1.0.0", "state": "installed"}],
            [{"key": "web.base.url", "value": "https://prod.example.com"}],
        ]

        mock_get_client.side_effect = [src_client, tgt_client]

        actx = _make_actx(json_mode=True)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.pipeline import promote

        promote(
            ctx,
            source="staging",
            target="production",
            dry_run=False,
            sync_modules=False,
            sync_params=False,
            force=False,
        )

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["source"] == "staging"
        assert data["target"] == "production"
        assert "module_a" in data["modules"]["only_in_source"]
        assert len(data["config_params"]["value_diff"]) == 1

        # Verify clients are closed
        src_client.close.assert_called_once()
        tgt_client.close.assert_called_once()

    @patch("kctl_odoo.commands.pipeline._get_client_for_profile")
    def test_promote_sync_modules(self, mock_get_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """Sync modules installs missing modules on target."""
        src_client = MagicMock()
        src_client.search_read.side_effect = [
            [{"name": "module_a", "installed_version": "18.0.1.0.0", "state": "installed"}],
            [],  # config params
        ]

        tgt_client = MagicMock()
        tgt_client.search_read.side_effect = [
            [],  # no modules
            [],  # config params
        ]
        tgt_client.search.return_value = [42]  # module record ID

        mock_get_client.side_effect = [src_client, tgt_client]

        actx = _make_actx(json_mode=True)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.pipeline import promote

        promote(ctx, source="staging", target="prod", dry_run=False, sync_modules=True, sync_params=False, force=True)

        tgt_client.execute_kw.assert_called_once_with(
            "ir.module.module",
            "button_immediate_install",
            [[42]],
        )

    @patch("kctl_odoo.commands.pipeline._get_client_for_profile")
    def test_promote_clients_closed_on_error(self, mock_get_client: MagicMock) -> None:
        """Clients are closed even when an RPC error occurs."""
        src_client = MagicMock()
        src_client.search_read.side_effect = Exception("Network error")

        tgt_client = MagicMock()
        mock_get_client.side_effect = [src_client, tgt_client]

        actx = _make_actx(json_mode=False)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.pipeline import promote

        with pytest.raises(Exception, match="Network error"):
            promote(ctx, source="a", target="b", dry_run=False, sync_modules=False, sync_params=False, force=False)

        src_client.close.assert_called_once()
        tgt_client.close.assert_called_once()


# ---------------------------------------------------------------------------
# rollback
# ---------------------------------------------------------------------------


class TestRollback:
    """pipeline rollback command tests."""

    @patch("kctl_odoo.commands.pipeline._get_client_for_profile")
    def test_rollback_file_not_found(self, mock_get_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """Rollback exits with error when backup file does not exist."""
        actx = _make_actx(json_mode=False)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.pipeline import rollback

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            rollback(
                ctx,
                profile="prod",
                backup_file="/nonexistent/backup.zip",
                database=None,
                copy=True,
                skip_pre_backup=True,
                force=True,
            )

    @patch("kctl_odoo.commands.pipeline._get_client_for_profile")
    def test_rollback_success_json(
        self, mock_get_client: MagicMock, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Successful rollback with pre/post health check in JSON."""
        # Create a temp backup file
        backup = tmp_path / "test_backup.zip"
        backup.write_bytes(b"fake backup data")

        client = MagicMock()
        client.database = "test_db"
        client.check_health.return_value = (True, "18.0")
        client.search_count.return_value = 50
        client.db_restore.return_value = True
        mock_get_client.return_value = client

        actx = _make_actx(json_mode=True)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.pipeline import rollback

        rollback(
            ctx, profile="prod", backup_file=str(backup), database=None, copy=True, skip_pre_backup=True, force=True
        )

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["success"] is True
        assert data["database"] == "test_db"
        assert data["pre_restore"]["healthy"] is True
        assert data["post_restore"]["healthy"] is True

        client.close.assert_called_once()

    @patch("kctl_odoo.commands.pipeline._get_client_for_profile")
    def test_rollback_restore_failure(
        self, mock_get_client: MagicMock, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Failed restore shows error and exits with code 1."""
        backup = tmp_path / "test_backup.zip"
        backup.write_bytes(b"fake backup data")

        client = MagicMock()
        client.database = "test_db"
        client.check_health.return_value = (True, "18.0")
        client.search_count.return_value = 50
        client.db_restore.side_effect = Exception("Disk full")
        mock_get_client.return_value = client

        actx = _make_actx(json_mode=True)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.pipeline import rollback

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            rollback(
                ctx, profile="prod", backup_file=str(backup), database=None, copy=True, skip_pre_backup=True, force=True
            )

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["success"] is False
        assert "Disk full" in data["error"]

        # Client should still be closed via finally
        client.close.assert_called_once()


# ---------------------------------------------------------------------------
# changelog
# ---------------------------------------------------------------------------


class TestChangelog:
    """pipeline changelog command tests."""

    @patch("subprocess.run")
    def test_changelog_json(self, mock_run: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """Changelog parses Conventional Commits into categories."""
        log_output = (
            "abc12345|feat(sale): add discount field|Alice|2026-03-25 10:00:00 +0700\n"
            "def67890|fix(stock): correct qty calc|Bob|2026-03-26 11:00:00 +0700\n"
            "ghi11111|chore: update deps|Charlie|2026-03-27 09:00:00 +0700\n"
        )
        diff_output = "src/private/sale_management/models/sale.py\nsrc/private/stock_management/models/stock.py\n"

        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=log_output, stderr=""),
            MagicMock(returncode=0, stdout=diff_output, stderr=""),
        ]

        actx = _make_actx(json_mode=True)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.pipeline import changelog

        changelog(ctx, from_ref="v1.0.0", to_ref="v1.1.0", path_filter=None)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["total_commits"] == 3
        assert len(data["categories"]["feat"]) == 1
        assert len(data["categories"]["fix"]) == 1
        assert len(data["categories"]["chore"]) == 1
        # Verify scope extraction
        feat_commit = data["categories"]["feat"][0]
        assert feat_commit["scope"] == "sale"
        assert feat_commit["description"] == "add discount field"
        assert feat_commit["type"] == "feat"
        assert "sale_management" in data["changed_modules"]
        assert "stock_management" in data["changed_modules"]

    @patch("subprocess.run")
    def test_changelog_empty(self, mock_run: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """Empty commit range produces empty output."""
        # Only one subprocess.run call happens (git log) — no git diff
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        actx = _make_actx(json_mode=True)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.pipeline import changelog

        changelog(ctx, from_ref="v1.0.0", to_ref="v1.0.0", path_filter=None)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["commits"] == []

    def test_changelog_invalid_ref(self) -> None:
        """Invalid git refs are rejected."""
        actx = _make_actx(json_mode=True)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.pipeline import changelog

        with pytest.raises(typer.BadParameter, match="Invalid git ref"):
            changelog(ctx, from_ref="--evil-flag", to_ref="HEAD", path_filter=None)


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------


class TestMetrics:
    """pipeline metrics command tests."""

    def test_metrics_json(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """Metrics collects and outputs all gauges as JSON."""
        mock_client.version_info.return_value = {"server_version": "18.0"}
        mock_client.search_count.return_value = 42

        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.pipeline import metrics

        metrics(ctx, prefix="odoo", warn=False)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        m = data["metrics"]
        assert "odoo_modules_installed" in m
        assert "odoo_rpc_response_seconds" in m
        assert "odoo_cron_total" in m
        assert "odoo_mail_outgoing" in m
        assert "odoo_users_active" in m
        assert "alerts" not in data  # --warn not set

    def test_metrics_json_with_alerts(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """--warn includes alerts in JSON output."""
        mock_client.version_info.return_value = {"server_version": "18.0"}
        mock_client.search_count.return_value = 5  # exceeds threshold for some metrics

        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.pipeline import metrics

        metrics(ctx, prefix="odoo", warn=True)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "alerts" in data
        assert isinstance(data["alerts"], list)

    def test_metrics_custom_prefix(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """Custom prefix is applied to all metric names."""
        mock_client.version_info.return_value = {"server_version": "18.0"}
        mock_client.search_count.return_value = 10

        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.pipeline import metrics

        metrics(ctx, prefix="kodemeio", warn=False)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert all(k.startswith("kodemeio_") for k in data["metrics"])

    def test_metrics_queue_job_not_installed(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """When queue_job is not installed, queue metrics are silently skipped."""
        from kctl_odoo.core.exceptions import RPCError

        def search_count_side_effect(model: str, domain: list) -> int:
            if model == "queue.job":
                raise RPCError({"message": "Model 'queue.job' does not exist"})
            return 5

        mock_client.version_info.return_value = {"server_version": "18.0"}
        mock_client.search_count.side_effect = search_count_side_effect

        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.pipeline import metrics

        metrics(ctx, prefix="odoo", warn=False)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        m = data["metrics"]
        assert not any("queue_jobs" in k for k in m)
        assert "odoo_modules_installed" in m

    def test_metrics_pretty_output(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """Pretty mode renders a table."""
        mock_client.version_info.return_value = {"server_version": "18.0"}
        mock_client.search_count.return_value = 10

        actx = _make_actx(json_mode=False, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.pipeline import metrics

        metrics(ctx, prefix="odoo", warn=False)

        captured = capsys.readouterr()
        # Pretty mode should not produce valid JSON on stdout
        with pytest.raises(json.JSONDecodeError):
            json.loads(captured.out)


# ---------------------------------------------------------------------------
# _validate_git_ref
# ---------------------------------------------------------------------------


class TestValidateGitRef:
    """Test the git ref validation helper."""

    def test_valid_refs(self) -> None:
        from kctl_odoo.commands.pipeline import _validate_git_ref

        for ref in ["v1.0.0", "HEAD", "main", "HEAD~20", "origin/main", "abc123", "v1.0.0-rc1"]:
            _validate_git_ref(ref, "test")  # Should not raise

    def test_invalid_refs(self) -> None:
        from kctl_odoo.commands.pipeline import _validate_git_ref

        for ref in ["--evil", "-flag", ""]:
            with pytest.raises(typer.BadParameter):
                _validate_git_ref(ref, "test")
