"""Tests for the snapshot export/import/diff engine.

The snapshot engine (``kctl_odoo.core.snapshots``) enables offline comparison
of module state between environments.  It is pure-logic (no network, no Docker)
and must work entirely from JSON files on disk.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kctl_odoo.core.snapshots import (
    ModuleSnapshot,
    SnapshotDiff,
    SnapshotEntry,
    SnapshotMetadata,
    diff_snapshots,
    load_snapshot,
    save_snapshot,
)

# ---------------------------------------------------------------------------
# Data model construction
# ---------------------------------------------------------------------------


class TestSnapshotEntry:
    """Test SnapshotEntry Pydantic model defaults and construction."""

    def test_minimal_construction(self) -> None:
        """Only name is required; all other fields have safe defaults."""
        entry = SnapshotEntry(name="sale_management")
        assert entry.name == "sale_management"
        assert entry.version == ""
        assert entry.state == "installed"
        assert entry.author == ""
        assert entry.category == ""

    def test_full_construction(self) -> None:
        """All fields can be explicitly set."""
        entry = SnapshotEntry(
            name="account_management",
            version="18.0.1.2.0",
            state="to upgrade",
            author="Kodemeio",
            category="Accounting",
        )
        assert entry.name == "account_management"
        assert entry.version == "18.0.1.2.0"
        assert entry.state == "to upgrade"
        assert entry.author == "Kodemeio"
        assert entry.category == "Accounting"


class TestSnapshotMetadata:
    """Test SnapshotMetadata Pydantic model defaults and construction."""

    def test_all_defaults_empty(self) -> None:
        """All fields default to empty strings when not provided."""
        meta = SnapshotMetadata()
        assert meta.exported_at == ""
        assert meta.database == ""
        assert meta.odoo_version == ""
        assert meta.profile == ""

    def test_full_construction(self) -> None:
        """All metadata fields can be explicitly set."""
        meta = SnapshotMetadata(
            exported_at="2026-04-01T10:00:00",
            database="odoo_prod",
            odoo_version="18.0",
            profile="profile-distribution",
        )
        assert meta.exported_at == "2026-04-01T10:00:00"
        assert meta.database == "odoo_prod"
        assert meta.odoo_version == "18.0"
        assert meta.profile == "profile-distribution"


class TestModuleSnapshot:
    """Test ModuleSnapshot Pydantic model construction."""

    def test_empty_modules(self) -> None:
        """ModuleSnapshot can be created with no modules."""
        snapshot = ModuleSnapshot(
            metadata=SnapshotMetadata(database="test"),
            modules=[],
        )
        assert snapshot.modules == []
        assert snapshot.metadata.database == "test"

    def test_with_modules(self) -> None:
        """ModuleSnapshot stores a list of SnapshotEntry objects."""
        snapshot = ModuleSnapshot(
            metadata=SnapshotMetadata(),
            modules=[
                SnapshotEntry(name="base", version="18.0.1.0.0", state="installed"),
                SnapshotEntry(name="sale", version="18.0.1.1.0", state="installed"),
            ],
        )
        assert len(snapshot.modules) == 2
        assert snapshot.modules[0].name == "base"
        assert snapshot.modules[1].name == "sale"


# ---------------------------------------------------------------------------
# save_snapshot
# ---------------------------------------------------------------------------


class TestSaveSnapshot:
    """Test save_snapshot writes valid JSON to disk."""

    def test_creates_json_file(self, tmp_path: Path) -> None:
        """save_snapshot creates the output file."""
        snapshot = ModuleSnapshot(
            metadata=SnapshotMetadata(database="mydb"),
            modules=[SnapshotEntry(name="base")],
        )
        out = tmp_path / "snap.json"
        save_snapshot(snapshot, out)
        assert out.exists()

    def test_output_is_valid_json(self, tmp_path: Path) -> None:
        """The written file must be parseable as JSON."""
        snapshot = ModuleSnapshot(
            metadata=SnapshotMetadata(database="mydb"),
            modules=[SnapshotEntry(name="base", version="18.0.1.0.0")],
        )
        out = tmp_path / "snap.json"
        save_snapshot(snapshot, out)
        data = json.loads(out.read_text())
        assert "metadata" in data
        assert "modules" in data

    def test_pretty_printed(self, tmp_path: Path) -> None:
        """JSON output is indented (pretty-printed) for readability."""
        snapshot = ModuleSnapshot(
            metadata=SnapshotMetadata(),
            modules=[SnapshotEntry(name="base")],
        )
        out = tmp_path / "snap.json"
        save_snapshot(snapshot, out)
        raw = out.read_text()
        # Pretty-printed JSON has newlines inside the content
        assert "\n" in raw

    def test_sets_exported_at_when_empty(self, tmp_path: Path) -> None:
        """If metadata.exported_at is empty, save_snapshot fills it automatically."""
        snapshot = ModuleSnapshot(
            metadata=SnapshotMetadata(database="mydb"),
            modules=[],
        )
        assert snapshot.metadata.exported_at == ""
        out = tmp_path / "snap.json"
        save_snapshot(snapshot, out)
        data = json.loads(out.read_text())
        # exported_at must be non-empty after save
        assert data["metadata"]["exported_at"] != ""

    def test_preserves_existing_exported_at(self, tmp_path: Path) -> None:
        """If exported_at is already set, save_snapshot does not overwrite it."""
        ts = "2026-01-15T08:30:00"
        snapshot = ModuleSnapshot(
            metadata=SnapshotMetadata(exported_at=ts, database="mydb"),
            modules=[],
        )
        out = tmp_path / "snap.json"
        save_snapshot(snapshot, out)
        data = json.loads(out.read_text())
        assert data["metadata"]["exported_at"] == ts

    def test_modules_preserved(self, tmp_path: Path) -> None:
        """All module entries are written to the JSON output."""
        snapshot = ModuleSnapshot(
            metadata=SnapshotMetadata(database="mydb"),
            modules=[
                SnapshotEntry(name="sale", version="18.0.2.0.0", state="installed"),
                SnapshotEntry(name="purchase", version="18.0.1.0.0", state="installed"),
            ],
        )
        out = tmp_path / "snap.json"
        save_snapshot(snapshot, out)
        data = json.loads(out.read_text())
        names = [m["name"] for m in data["modules"]]
        assert "sale" in names
        assert "purchase" in names


# ---------------------------------------------------------------------------
# load_snapshot (round-trip + error cases)
# ---------------------------------------------------------------------------


class TestLoadSnapshot:
    """Test load_snapshot reads JSON files and returns ModuleSnapshot objects."""

    def test_round_trip(self, tmp_path: Path) -> None:
        """save then load produces equivalent data."""
        original = ModuleSnapshot(
            metadata=SnapshotMetadata(
                database="roundtrip_db",
                odoo_version="18.0",
                profile="profile-distribution",
            ),
            modules=[
                SnapshotEntry(name="base", version="18.0.1.0.0", state="installed"),
                SnapshotEntry(name="sale", version="18.0.2.0.0", state="installed", author="OCA"),
            ],
        )
        path = tmp_path / "roundtrip.json"
        save_snapshot(original, path)
        loaded = load_snapshot(path)

        assert loaded.metadata.database == "roundtrip_db"
        assert loaded.metadata.odoo_version == "18.0"
        assert loaded.metadata.profile == "profile-distribution"
        assert len(loaded.modules) == 2
        assert loaded.modules[0].name == "base"
        assert loaded.modules[1].name == "sale"
        assert loaded.modules[1].author == "OCA"

    def test_load_preserves_state(self, tmp_path: Path) -> None:
        """Non-default state values survive the round-trip."""
        snapshot = ModuleSnapshot(
            metadata=SnapshotMetadata(),
            modules=[
                SnapshotEntry(name="broken_mod", state="to upgrade"),
            ],
        )
        path = tmp_path / "state.json"
        save_snapshot(snapshot, path)
        loaded = load_snapshot(path)
        assert loaded.modules[0].state == "to upgrade"

    def test_load_invalid_json_raises_value_error(self, tmp_path: Path) -> None:
        """Loading a file with invalid JSON raises ValueError."""
        bad = tmp_path / "bad.json"
        bad.write_text("this is not json!!!", encoding="utf-8")
        with pytest.raises(ValueError, match="invalid"):
            load_snapshot(bad)

    def test_load_wrong_structure_raises_value_error(self, tmp_path: Path) -> None:
        """Loading valid JSON but wrong structure raises ValueError."""
        bad = tmp_path / "wrong.json"
        bad.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
        with pytest.raises(ValueError):
            load_snapshot(bad)

    def test_load_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """Loading a file that does not exist raises an error."""
        missing = tmp_path / "does_not_exist.json"
        with pytest.raises((FileNotFoundError, OSError)):
            load_snapshot(missing)


# ---------------------------------------------------------------------------
# diff_snapshots
# ---------------------------------------------------------------------------


class TestDiffSnapshots:
    """Test diff_snapshots compares two snapshots correctly."""

    def _make_snapshot(
        self,
        modules: list[tuple[str, str, str]],
        source: str = "env_a",
    ) -> ModuleSnapshot:
        """Helper: build a ModuleSnapshot from (name, version, state) tuples."""
        return ModuleSnapshot(
            metadata=SnapshotMetadata(database=source),
            modules=[SnapshotEntry(name=n, version=v, state=s) for n, v, s in modules],
        )

    def test_diff_metadata_sources(self) -> None:
        """Diff records source_a and source_b from metadata.database."""
        a = self._make_snapshot([], source="prod")
        b = self._make_snapshot([], source="staging")
        diff = diff_snapshots(a, b)
        assert diff.source_a == "prod"
        assert diff.source_b == "staging"

    def test_identical_snapshots_produce_empty_diff(self) -> None:
        """Two identical snapshots produce no changes."""
        modules = [
            ("base", "18.0.1.0.0", "installed"),
            ("sale", "18.0.2.0.0", "installed"),
        ]
        a = self._make_snapshot(modules)
        b = self._make_snapshot(modules)
        diff = diff_snapshots(a, b)
        assert diff.added == []
        assert diff.removed == []
        assert diff.version_changed == []
        assert diff.state_changed == []

    def test_added_modules(self) -> None:
        """Modules in b but not in a are reported as added."""
        a = self._make_snapshot([("base", "18.0.1.0.0", "installed")])
        b = self._make_snapshot(
            [
                ("base", "18.0.1.0.0", "installed"),
                ("sale", "18.0.2.0.0", "installed"),
                ("crm", "18.0.1.0.0", "installed"),
            ]
        )
        diff = diff_snapshots(a, b)
        assert set(diff.added) == {"sale", "crm"}
        assert diff.removed == []

    def test_removed_modules(self) -> None:
        """Modules in a but not in b are reported as removed."""
        a = self._make_snapshot(
            [
                ("base", "18.0.1.0.0", "installed"),
                ("old_mod", "18.0.1.0.0", "installed"),
            ]
        )
        b = self._make_snapshot([("base", "18.0.1.0.0", "installed")])
        diff = diff_snapshots(a, b)
        assert diff.added == []
        assert diff.removed == ["old_mod"]

    def test_version_changed(self) -> None:
        """Modules with different versions are reported in version_changed."""
        a = self._make_snapshot(
            [
                ("base", "18.0.1.0.0", "installed"),
                ("sale", "18.0.1.0.0", "installed"),
            ]
        )
        b = self._make_snapshot(
            [
                ("base", "18.0.1.0.0", "installed"),
                ("sale", "18.0.2.0.0", "installed"),
            ]
        )
        diff = diff_snapshots(a, b)
        assert len(diff.version_changed) == 1
        name, v_a, v_b = diff.version_changed[0]
        assert name == "sale"
        assert v_a == "18.0.1.0.0"
        assert v_b == "18.0.2.0.0"

    def test_state_changed(self) -> None:
        """Modules with different states are reported in state_changed."""
        a = self._make_snapshot([("purchase", "18.0.1.0.0", "installed")])
        b = self._make_snapshot([("purchase", "18.0.1.0.0", "to upgrade")])
        diff = diff_snapshots(a, b)
        assert len(diff.state_changed) == 1
        name, s_a, s_b = diff.state_changed[0]
        assert name == "purchase"
        assert s_a == "installed"
        assert s_b == "to upgrade"

    def test_combined_changes(self) -> None:
        """All four change categories can appear in the same diff."""
        a = self._make_snapshot(
            [
                ("base", "18.0.1.0.0", "installed"),
                ("sale", "18.0.1.0.0", "installed"),
                ("old", "18.0.1.0.0", "installed"),
                ("stale", "18.0.1.0.0", "installed"),
            ]
        )
        b = self._make_snapshot(
            [
                ("base", "18.0.1.0.0", "installed"),  # unchanged
                ("sale", "18.0.2.0.0", "installed"),  # version changed
                ("new", "18.0.1.0.0", "installed"),  # added
                ("stale", "18.0.1.0.0", "to upgrade"),  # state changed
                # "old" is absent → removed
            ]
        )
        diff = diff_snapshots(a, b)
        assert diff.added == ["new"]
        assert diff.removed == ["old"]
        assert len(diff.version_changed) == 1
        assert diff.version_changed[0][0] == "sale"
        assert len(diff.state_changed) == 1
        assert diff.state_changed[0][0] == "stale"

    def test_version_and_state_both_changed(self) -> None:
        """A module with both version and state changes appears in both lists."""
        a = self._make_snapshot([("mod_x", "18.0.1.0.0", "installed")])
        b = self._make_snapshot([("mod_x", "18.0.2.0.0", "to upgrade")])
        diff = diff_snapshots(a, b)
        assert any(t[0] == "mod_x" for t in diff.version_changed)
        assert any(t[0] == "mod_x" for t in diff.state_changed)

    def test_empty_snapshots_produce_empty_diff(self) -> None:
        """Two empty snapshots produce an entirely empty diff."""
        a = self._make_snapshot([])
        b = self._make_snapshot([])
        diff = diff_snapshots(a, b)
        assert diff.added == []
        assert diff.removed == []
        assert diff.version_changed == []
        assert diff.state_changed == []

    def test_diff_returns_snapshot_diff_type(self) -> None:
        """diff_snapshots always returns a SnapshotDiff instance."""
        a = self._make_snapshot([])
        b = self._make_snapshot([])
        diff = diff_snapshots(a, b)
        assert isinstance(diff, SnapshotDiff)
