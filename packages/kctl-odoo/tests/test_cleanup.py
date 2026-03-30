"""Tests for the cleanup command group (transients, auto-fix)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import click
import pytest

from kctl_odoo.core.output import Output

# Typer raises click.exceptions.Exit (not SystemExit) for raise typer.Exit(code).
# SystemExit uses .code; click.exceptions.Exit uses .exit_code.
_EXIT = (SystemExit, click.exceptions.Exit)


def _exit_code(exc_info: pytest.ExceptionInfo) -> int:
    """Return the integer exit code from a caught SystemExit or click.exceptions.Exit."""
    exc = exc_info.value
    if isinstance(exc, SystemExit):
        return int(exc.code)
    return int(exc.exit_code)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actx(*, json_mode: bool = False, client: MagicMock | None = None) -> MagicMock:
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
# cleanup transients
# ---------------------------------------------------------------------------


class TestCleanupTransients:
    def test_counts_deleted_in_json_mode(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """transients reports how many records were deleted in JSON mode."""
        # Two transient models, each with 5 old records
        mock_client.search_read.return_value = [
            {"model": "account.report.wizard"},
            {"model": "stock.picking.wizard"},
        ]
        mock_client.search.side_effect = [
            list(range(1, 6)),  # 5 IDs for first model
            list(range(6, 11)),  # 5 IDs for second model
        ]
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.cleanup import cleanup_transients

        cleanup_transients(ctx, days=1)

        data = json.loads(capsys.readouterr().out)
        assert data["deleted"] == 10
        assert data["models_checked"] == 2
        assert data["days"] == 1

    def test_no_old_records_reports_zero(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """transients reports 0 deleted when no old records exist."""
        mock_client.search_read.return_value = [{"model": "some.wizard"}]
        mock_client.search.return_value = []  # no old records
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.cleanup import cleanup_transients

        cleanup_transients(ctx, days=7)

        data = json.loads(capsys.readouterr().out)
        assert data["deleted"] == 0

    def test_transient_model_query_error_exits(self, mock_client: MagicMock) -> None:
        """transients exits 1 when ir.model cannot be queried."""
        mock_client.search_read.side_effect = Exception("DB error")
        actx = _make_actx(client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.cleanup import cleanup_transients

        with pytest.raises(_EXIT) as exc_info:
            cleanup_transients(ctx, days=1)

        assert _exit_code(exc_info) == 1

    def test_individual_model_errors_are_skipped(
        self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """transients skips inaccessible individual models and continues."""
        mock_client.search_read.return_value = [
            {"model": "good.wizard"},
            {"model": "bad.wizard"},
        ]

        def _search(model: str, domain, limit=None):
            if model == "bad.wizard":
                raise Exception("access denied")
            return [1, 2, 3]

        mock_client.search.side_effect = _search
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.cleanup import cleanup_transients

        # Should not raise — bad model is silently skipped
        cleanup_transients(ctx, days=1)

        data = json.loads(capsys.readouterr().out)
        # Only the good.wizard records count
        assert data["deleted"] == 3


# ---------------------------------------------------------------------------
# cleanup auto-fix
# ---------------------------------------------------------------------------


class TestAutoFix:
    def test_dry_run_shows_would_fix(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """auto-fix --dry-run reports 'would_fix' status without changing data."""
        # All models have records to fix
        mock_client.search_count.return_value = 5
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.cleanup import auto_fix

        auto_fix(ctx, dry_run=True)

        # write/unlink must NOT be called in dry-run
        mock_client.write.assert_not_called()
        mock_client.unlink.assert_not_called()

        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        would_fix = [item for item in data if item["status"] == "would_fix"]
        assert len(would_fix) > 0

    def test_live_run_calls_fix_actions(self, mock_client: MagicMock) -> None:
        """auto-fix (live) calls write or unlink when records need fixing."""
        # All four fix actions have matching records — guarantees at least one write/unlink
        mock_client.search_count.return_value = 3
        mock_client.search.return_value = [10, 11, 12]
        actx = _make_actx(client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.cleanup import auto_fix

        auto_fix(ctx, dry_run=False)

        # At least one write or unlink must have been called
        assert mock_client.write.called or mock_client.unlink.called

    def test_all_clean_reports_clean_status(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """auto-fix shows 'clean' for all actions when no records need fixing."""
        mock_client.search_count.return_value = 0
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.cleanup import auto_fix

        auto_fix(ctx, dry_run=False)

        data = json.loads(capsys.readouterr().out)
        statuses = {item["status"] for item in data}
        # All items should be 'clean' or 'skipped' (no errors, no would_fix)
        assert statuses <= {"clean", "skipped"}

    def test_inaccessible_model_reports_skipped(
        self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """auto-fix marks an action as 'skipped' when the model is inaccessible."""
        mock_client.search_count.side_effect = Exception("model not found")
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.cleanup import auto_fix

        auto_fix(ctx, dry_run=False)

        data = json.loads(capsys.readouterr().out)
        skipped = [item for item in data if item["status"] == "skipped"]
        assert len(skipped) > 0
