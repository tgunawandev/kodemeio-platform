"""Tests for modules extended commands: snapshot round-trip and diff-snapshots.

These are local-only tests (no network / Docker required).
They exercise the snapshot and diff-snapshots commands via the core
snapshot engine, which is already unit-tested in test_snapshots.py.
Here we validate the CLI-level wiring and output consistency.
"""

from __future__ import annotations

import json
from datetime import UTC
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from kctl_odoo.core.output import Output
from kctl_odoo.core.snapshots import (
    ModuleSnapshot,
    SnapshotEntry,
    SnapshotMetadata,
    diff_snapshots,
    load_snapshot,
    save_snapshot,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actx(*, json_mode: bool = False, client: MagicMock | None = None) -> MagicMock:
    actx = MagicMock()
    actx.json_mode = json_mode
    actx.output = Output(json_mode=json_mode)
    actx.client = client or MagicMock()
    actx.profile = "test-profile"
    return actx


def _make_ctx(actx: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.obj = actx
    return ctx


def _build_snapshot(
    database: str,
    modules: list[tuple[str, str, str]],
) -> ModuleSnapshot:
    """Build a ModuleSnapshot from (name, version, state) tuples."""
    return ModuleSnapshot(
        metadata=SnapshotMetadata(database=database, profile="test"),
        modules=[SnapshotEntry(name=n, version=v, state=s) for n, v, s in modules],
    )


# ---------------------------------------------------------------------------
# TestSnapshotRoundTrip
# ---------------------------------------------------------------------------


class TestSnapshotRoundTrip:
    """Verify save → load produces equivalent data (used by the snapshot command)."""

    def test_save_and_load(self, tmp_path: Path) -> None:
        """Round-trip: create a snapshot, save to disk, load back and verify."""
        snap = _build_snapshot(
            "odoo_prod",
            [
                ("base", "18.0.1.0.0", "installed"),
                ("sale", "18.0.2.0.0", "installed"),
                ("purchase", "18.0.1.0.0", "installed"),
            ],
        )
        path = tmp_path / "roundtrip.json"
        save_snapshot(snap, path)

        loaded = load_snapshot(path)

        assert loaded.metadata.database == "odoo_prod"
        assert len(loaded.modules) == 3
        names = {m.name for m in loaded.modules}
        assert names == {"base", "sale", "purchase"}

    def test_metadata_exported_at_set_on_save(self, tmp_path: Path) -> None:
        """save_snapshot fills exported_at when it is empty."""
        snap = _build_snapshot("mydb", [("base", "18.0.1.0.0", "installed")])
        assert snap.metadata.exported_at == ""

        path = tmp_path / "ts.json"
        save_snapshot(snap, path)

        data = json.loads(path.read_text())
        assert data["metadata"]["exported_at"] != ""

    def test_module_fields_preserved(self, tmp_path: Path) -> None:
        """All SnapshotEntry fields survive the round-trip."""
        snap = ModuleSnapshot(
            metadata=SnapshotMetadata(database="db1", profile="prod", odoo_version="18.0"),
            modules=[
                SnapshotEntry(
                    name="sfa_management",
                    version="18.0.3.1.0",
                    state="installed",
                    author="Kodemeio",
                    category="Sales",
                )
            ],
        )
        path = tmp_path / "fields.json"
        save_snapshot(snap, path)
        loaded = load_snapshot(path)

        m = loaded.modules[0]
        assert m.name == "sfa_management"
        assert m.version == "18.0.3.1.0"
        assert m.state == "installed"
        assert m.author == "Kodemeio"
        assert m.category == "Sales"

    def test_empty_modules_list(self, tmp_path: Path) -> None:
        """A snapshot with zero modules saves and loads cleanly."""
        snap = _build_snapshot("empty_db", [])
        path = tmp_path / "empty.json"
        save_snapshot(snap, path)
        loaded = load_snapshot(path)
        assert loaded.modules == []
        assert loaded.metadata.database == "empty_db"

    def test_json_file_is_valid_and_pretty(self, tmp_path: Path) -> None:
        """The written file is valid JSON and is pretty-printed (has newlines)."""
        snap = _build_snapshot("db", [("base", "18.0", "installed")])
        path = tmp_path / "pretty.json"
        save_snapshot(snap, path)
        raw = path.read_text()
        assert "\n" in raw
        parsed = json.loads(raw)
        assert "metadata" in parsed
        assert "modules" in parsed


# ---------------------------------------------------------------------------
# TestDiffSnapshotsFromModules
# ---------------------------------------------------------------------------


class TestDiffSnapshotsFromModules:
    """Test the diff logic used by the diff-snapshots command."""

    def test_full_diff(self, tmp_path: Path) -> None:
        """Create two snapshots with all four diff categories and verify results."""
        snap_a = _build_snapshot(
            "prod",
            [
                ("base", "18.0.1.0.0", "installed"),
                ("sale", "18.0.1.0.0", "installed"),  # version will change
                ("old_mod", "18.0.1.0.0", "installed"),  # will be removed
                ("frozen", "18.0.1.0.0", "installed"),  # state will change
            ],
        )
        snap_b = _build_snapshot(
            "staging",
            [
                ("base", "18.0.1.0.0", "installed"),  # unchanged
                ("sale", "18.0.2.0.0", "installed"),  # version changed
                ("new_mod", "18.0.1.0.0", "installed"),  # added
                ("frozen", "18.0.1.0.0", "to upgrade"),  # state changed
                # old_mod absent → removed
            ],
        )

        path_a = tmp_path / "a.json"
        path_b = tmp_path / "b.json"
        save_snapshot(snap_a, path_a)
        save_snapshot(snap_b, path_b)

        loaded_a = load_snapshot(path_a)
        loaded_b = load_snapshot(path_b)
        diff = diff_snapshots(loaded_a, loaded_b)

        # Sources from metadata
        assert diff.source_a == "prod"
        assert diff.source_b == "staging"

        # Added
        assert diff.added == ["new_mod"]

        # Removed
        assert diff.removed == ["old_mod"]

        # Version changed
        assert len(diff.version_changed) == 1
        name, va, vb = diff.version_changed[0]
        assert name == "sale"
        assert va == "18.0.1.0.0"
        assert vb == "18.0.2.0.0"

        # State changed
        assert len(diff.state_changed) == 1
        name2, sa, sb = diff.state_changed[0]
        assert name2 == "frozen"
        assert sa == "installed"
        assert sb == "to upgrade"

    def test_no_changes(self, tmp_path: Path) -> None:
        """Two identical snapshots produce an empty diff."""
        modules = [
            ("base", "18.0.1.0.0", "installed"),
            ("sale", "18.0.2.0.0", "installed"),
        ]
        snap_a = _build_snapshot("prod", modules)
        snap_b = _build_snapshot("staging", modules)

        path_a = tmp_path / "a.json"
        path_b = tmp_path / "b.json"
        save_snapshot(snap_a, path_a)
        save_snapshot(snap_b, path_b)

        diff = diff_snapshots(load_snapshot(path_a), load_snapshot(path_b))
        assert diff.added == []
        assert diff.removed == []
        assert diff.version_changed == []
        assert diff.state_changed == []

    def test_diff_snapshots_cmd_json_output(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """diff-snapshots command produces valid JSON output in json_mode."""
        snap_a = _build_snapshot("prod", [("base", "18.0.1.0.0", "installed")])
        snap_b = _build_snapshot(
            "staging",
            [
                ("base", "18.0.1.0.0", "installed"),
                ("sale", "18.0.2.0.0", "installed"),
            ],
        )
        path_a = tmp_path / "a.json"
        path_b = tmp_path / "b.json"
        save_snapshot(snap_a, path_a)
        save_snapshot(snap_b, path_b)

        actx = _make_actx(json_mode=True)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.modules import diff_snapshots_cmd

        diff_snapshots_cmd(ctx, file_a=str(path_a), file_b=str(path_b))

        data = json.loads(capsys.readouterr().out)
        assert data["source_a"] == "prod"
        assert data["source_b"] == "staging"
        assert "sale" in data["added"]
        assert data["removed"] == []
        assert data["version_changed"] == []
        assert data["state_changed"] == []

    def test_diff_snapshots_cmd_text_output(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """diff-snapshots command text output includes summary and diff sections."""
        snap_a = _build_snapshot("prod", [("base", "18.0.1.0.0", "installed"), ("old", "1.0", "installed")])
        snap_b = _build_snapshot("staging", [("base", "18.0.1.0.0", "installed"), ("new", "1.0", "installed")])
        path_a = tmp_path / "a.json"
        path_b = tmp_path / "b.json"
        save_snapshot(snap_a, path_a)
        save_snapshot(snap_b, path_b)

        actx = _make_actx(json_mode=False)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.modules import diff_snapshots_cmd

        diff_snapshots_cmd(ctx, file_a=str(path_a), file_b=str(path_b))

        captured = capsys.readouterr().out
        assert "Summary" in captured or "Snapshot Diff" in captured or "Added" in captured or "Removed" in captured


# ---------------------------------------------------------------------------
# TestSnapshotCommand (mocked client)
# ---------------------------------------------------------------------------


class TestSnapshotCommand:
    """Test the snapshot command via a mocked OdooClient."""

    def _make_mock_modules(self) -> list[dict]:
        return [
            {
                "name": "base",
                "installed_version": "18.0.1.0.0",
                "state": "installed",
                "author": "Odoo S.A.",
                "category_id": [1, "Technical"],
            },
            {
                "name": "sale",
                "installed_version": "18.0.2.0.0",
                "state": "installed",
                "author": "Odoo S.A.",
                "category_id": [2, "Sales"],
            },
        ]

    def test_snapshot_creates_file(self, tmp_path: Path) -> None:
        """snapshot command creates a JSON file with module data."""
        client = MagicMock()
        client.database = "test_db"
        client.search_read.return_value = self._make_mock_modules()

        output_path = tmp_path / "out.json"
        actx = _make_actx(client=client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.modules import snapshot

        snapshot(ctx, output=str(output_path), state="installed")

        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert data["metadata"]["database"] == "test_db"
        assert len(data["modules"]) == 2

    def test_snapshot_category_id_list(self, tmp_path: Path) -> None:
        """snapshot command handles category_id as [id, name] list."""
        client = MagicMock()
        client.database = "db"
        client.search_read.return_value = [
            {
                "name": "sale",
                "installed_version": "18.0.1.0.0",
                "state": "installed",
                "author": "OCA",
                "category_id": [5, "Sales/CRM"],
            }
        ]
        output_path = tmp_path / "cat.json"
        actx = _make_actx(client=client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.modules import snapshot

        snapshot(ctx, output=str(output_path), state="installed")

        data = json.loads(output_path.read_text())
        assert data["modules"][0]["category"] == "Sales/CRM"

    def test_snapshot_category_id_false(self, tmp_path: Path) -> None:
        """snapshot command handles category_id=False gracefully."""
        client = MagicMock()
        client.database = "db"
        client.search_read.return_value = [
            {
                "name": "base",
                "installed_version": "18.0.1.0.0",
                "state": "installed",
                "author": "Odoo S.A.",
                "category_id": False,
            }
        ]
        output_path = tmp_path / "no_cat.json"
        actx = _make_actx(client=client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.modules import snapshot

        snapshot(ctx, output=str(output_path), state="installed")

        data = json.loads(output_path.read_text())
        assert data["modules"][0]["category"] == ""

    def test_snapshot_default_filename(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """snapshot without --output creates snapshot-{db}-{date}.json in cwd."""

        monkeypatch.chdir(tmp_path)

        client = MagicMock()
        client.database = "mydb"
        client.search_read.return_value = []

        actx = _make_actx(client=client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.modules import snapshot

        snapshot(ctx, output=None, state="installed")

        from datetime import datetime

        date_str = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        expected = tmp_path / f"snapshot-mydb-{date_str}.json"
        assert expected.exists()
