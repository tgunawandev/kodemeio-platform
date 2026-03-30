"""Tests for the history command group and core/history.py module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kctl_odoo.core.output import Output

# ---------------------------------------------------------------------------
# Helpers for command-level tests
# ---------------------------------------------------------------------------


def _make_actx(*, json_mode: bool = False) -> MagicMock:
    actx = MagicMock()
    actx.json_mode = json_mode
    actx.output = Output(json_mode=json_mode)
    return actx


def _make_ctx(actx: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.obj = actx
    return ctx


# ---------------------------------------------------------------------------
# core/history.py — module-level unit tests
# ---------------------------------------------------------------------------


class TestHistoryModule:
    """Tests for the SQLite history module using a temporary database."""

    def _patch_db_path(self, tmp_path: Path):
        """Return a pair of patches that redirect DATA_DIR and DB_PATH to tmp_path."""
        return (
            patch("kctl_odoo.core.history.DATA_DIR", tmp_path),
            patch("kctl_odoo.core.history.DB_PATH", tmp_path / "history.db"),
            patch("kctl_odoo.core.history._schema_initialized", False),
        )

    def test_record_and_retrieve_module_op(self, tmp_path: Path) -> None:
        """record_module_op persists a row that get_module_op_history returns."""
        with (
            patch("kctl_odoo.core.history.DATA_DIR", tmp_path),
            patch("kctl_odoo.core.history.DB_PATH", tmp_path / "history.db"),
            patch("kctl_odoo.core.history._schema_initialized", False),
        ):
            import kctl_odoo.core.history as h

            h._schema_initialized = False  # force re-init for tmp DB

            row_id = h.record_module_op(
                operation="install",
                modules="sale,stock",
                database="odoo_prod",
                profile="prod",
                success=True,
                duration_s=4.2,
            )
            assert row_id > 0

            rows = h.get_module_op_history(database="odoo_prod", limit=10)
            assert len(rows) == 1
            assert rows[0]["operation"] == "install"
            assert rows[0]["modules"] == "sale,stock"
            assert rows[0]["success"] == 1
            assert abs(rows[0]["duration_s"] - 4.2) < 0.01

    def test_record_and_retrieve_backup(self, tmp_path: Path) -> None:
        """record_backup persists a row that get_backup_history returns."""
        with (
            patch("kctl_odoo.core.history.DATA_DIR", tmp_path),
            patch("kctl_odoo.core.history.DB_PATH", tmp_path / "history.db"),
            patch("kctl_odoo.core.history._schema_initialized", False),
        ):
            import kctl_odoo.core.history as h

            h._schema_initialized = False

            row_id = h.record_backup(
                database="odoo_prod",
                backup_type="full",
                file_path="/backups/odoo_prod_20260101.sql.gz",
                size_bytes=1024 * 1024 * 50,
                success=True,
            )
            assert row_id > 0

            rows = h.get_backup_history(database="odoo_prod", limit=5)
            assert len(rows) == 1
            assert rows[0]["backup_type"] == "full"
            assert rows[0]["size_bytes"] == 1024 * 1024 * 50

    def test_record_and_retrieve_health_check(self, tmp_path: Path) -> None:
        """record_health_check persists a row with version and user counts."""
        with (
            patch("kctl_odoo.core.history.DATA_DIR", tmp_path),
            patch("kctl_odoo.core.history.DB_PATH", tmp_path / "history.db"),
            patch("kctl_odoo.core.history._schema_initialized", False),
        ):
            import kctl_odoo.core.history as h

            h._schema_initialized = False

            h.record_health_check(
                database="odoo_dev",
                healthy=True,
                version="18.0",
                active_users=10,
                installed_modules=250,
            )

            rows = h.get_health_check_history(limit=5)
            assert len(rows) == 1
            assert rows[0]["healthy"] == 1
            assert rows[0]["version"] == "18.0"
            assert rows[0]["active_users"] == 10
            assert rows[0]["installed_modules"] == 250

    def test_record_and_retrieve_deployment(self, tmp_path: Path) -> None:
        """record_deployment persists a row that get_deployment_history returns."""
        with (
            patch("kctl_odoo.core.history.DATA_DIR", tmp_path),
            patch("kctl_odoo.core.history.DB_PATH", tmp_path / "history.db"),
            patch("kctl_odoo.core.history._schema_initialized", False),
        ):
            import kctl_odoo.core.history as h

            h._schema_initialized = False

            h.record_deployment(
                database="odoo_prod",
                profile="prod",
                modules="sale,crm",
                success=False,
                notes="Rollback required",
            )

            rows = h.get_deployment_history(database="odoo_prod", limit=5)
            assert len(rows) == 1
            assert rows[0]["success"] == 0
            assert rows[0]["notes"] == "Rollback required"

    def test_clear_all_history_returns_counts(self, tmp_path: Path) -> None:
        """clear_all_history deletes all rows and returns per-table counts."""
        with (
            patch("kctl_odoo.core.history.DATA_DIR", tmp_path),
            patch("kctl_odoo.core.history.DB_PATH", tmp_path / "history.db"),
            patch("kctl_odoo.core.history._schema_initialized", False),
        ):
            import kctl_odoo.core.history as h

            h._schema_initialized = False

            h.record_module_op("install", "sale", "odoo_dev")
            h.record_backup("odoo_dev", "full")

            counts = h.clear_all_history()
            assert counts["module_ops"] == 1
            assert counts["backups"] == 1
            assert counts["health_checks"] == 0  # never inserted
            assert counts["deployments"] == 0

            # After clear, queries return nothing
            assert h.get_module_op_history() == []

    def test_database_filter_isolates_results(self, tmp_path: Path) -> None:
        """get_*_history with database= only returns rows for that database."""
        with (
            patch("kctl_odoo.core.history.DATA_DIR", tmp_path),
            patch("kctl_odoo.core.history.DB_PATH", tmp_path / "history.db"),
            patch("kctl_odoo.core.history._schema_initialized", False),
        ):
            import kctl_odoo.core.history as h

            h._schema_initialized = False

            h.record_module_op("install", "sale", "odoo_prod")
            h.record_module_op("install", "stock", "odoo_dev")

            prod_rows = h.get_module_op_history(database="odoo_prod")
            dev_rows = h.get_module_op_history(database="odoo_dev")

            assert len(prod_rows) == 1
            assert prod_rows[0]["modules"] == "sale"
            assert len(dev_rows) == 1
            assert dev_rows[0]["modules"] == "stock"


# ---------------------------------------------------------------------------
# history_cmd commands — command-level tests using mocked history functions
# ---------------------------------------------------------------------------


class TestHistoryCmdModules:
    def test_empty_history_shows_info(self, capsys: pytest.CaptureFixture[str]) -> None:
        """history modules shows an info message when no history exists."""
        actx = _make_actx()
        ctx = _make_ctx(actx)

        with patch("kctl_odoo.commands.history_cmd.get_module_op_history", return_value=[]):
            from kctl_odoo.commands.history_cmd import modules

            modules(ctx, database=None, limit=20)

        # No crash; output consumed
        capsys.readouterr()

    def test_module_history_renders_table(self, capsys: pytest.CaptureFixture[str]) -> None:
        """history modules renders rows as JSON array in JSON mode."""
        rows = [
            {
                "id": 1,
                "timestamp": "2026-03-28T10:00:00",
                "operation": "install",
                "modules": "sale,stock",
                "database": "odoo_prod",
                "profile": "prod",
                "success": 1,
                "duration_s": 12.5,
            }
        ]
        actx = _make_actx(json_mode=True)
        ctx = _make_ctx(actx)

        with patch("kctl_odoo.commands.history_cmd.get_module_op_history", return_value=rows):
            from kctl_odoo.commands.history_cmd import modules

            modules(ctx, database=None, limit=20)

        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["operation"] == "install"

    def test_database_filter_passed_to_getter(self) -> None:
        """history modules passes the --database option to get_module_op_history."""
        actx = _make_actx()
        ctx = _make_ctx(actx)

        with patch("kctl_odoo.commands.history_cmd.get_module_op_history", return_value=[]) as mock_getter:
            from kctl_odoo.commands.history_cmd import modules

            modules(ctx, database="odoo_prod", limit=10)

        mock_getter.assert_called_once_with(database="odoo_prod", limit=10)


class TestHistoryCmdBackups:
    def test_backup_history_renders_with_size_formatting(self, capsys: pytest.CaptureFixture[str]) -> None:
        """history backups outputs size in JSON with raw byte count."""
        rows = [
            {
                "id": 1,
                "timestamp": "2026-03-28T10:00:00",
                "database": "odoo_prod",
                "backup_type": "full",
                "file_path": "/backups/odoo_prod.sql.gz",
                "size_bytes": 1024 * 1024 * 50,  # 50 MB
                "success": 1,
            }
        ]
        actx = _make_actx(json_mode=True)
        ctx = _make_ctx(actx)

        with patch("kctl_odoo.commands.history_cmd.get_backup_history", return_value=rows):
            from kctl_odoo.commands.history_cmd import backups

            backups(ctx, database=None, limit=20)

        data = json.loads(capsys.readouterr().out)
        assert data[0]["backup_type"] == "full"
        assert data[0]["size_bytes"] == 1024 * 1024 * 50


class TestHistoryCmdClear:
    def test_clear_with_force_clears_all(self, capsys: pytest.CaptureFixture[str]) -> None:
        """history clear --force calls clear_all_history and outputs totals as JSON."""
        counts = {"module_ops": 5, "backups": 2, "health_checks": 10, "deployments": 1}
        actx = _make_actx(json_mode=True)
        ctx = _make_ctx(actx)

        with patch("kctl_odoo.commands.history_cmd.clear_all_history", return_value=counts):
            from kctl_odoo.commands.history_cmd import clear

            clear(ctx, force=True)

        data = json.loads(capsys.readouterr().out)
        assert data["total_rows"] == 18
        assert data["cleared"]["module_ops"] == 5

    def test_clear_without_force_requires_confirm(self) -> None:
        """history clear without --force prompts for confirmation."""
        actx = _make_actx()
        ctx = _make_ctx(actx)

        with (
            patch("kctl_odoo.commands.history_cmd.clear_all_history") as mock_clear,
            patch("typer.confirm", return_value=False),
        ):
            from kctl_odoo.commands.history_cmd import clear

            clear(ctx, force=False)

        # clear_all_history must NOT be called when user declines
        mock_clear.assert_not_called()
