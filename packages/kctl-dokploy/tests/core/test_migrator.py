"""Tests for the migration pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kctl_dokploy.core.migration_manifest import MigrationManifest, load_migration_manifest
from kctl_dokploy.core.migrator import Migrator, MigrationState, MigrationStep, _STATE_DIR


def _make_manifest(**kwargs) -> MigrationManifest:
    defaults = dict(
        name="test-migration",
        source={"server": "src-01", "postgres_profile": "src"},
        target={"server": "tgt-01", "postgres_profile": "tgt"},
        tenant="test",
    )
    defaults.update(kwargs)
    return MigrationManifest(**defaults)


class TestMigrationManifest:
    def test_basic_manifest(self):
        m = _make_manifest()
        assert m.tenant == "test"
        assert m.source.server == "src-01"
        assert m.target.server == "tgt-01"

    def test_manifest_with_databases(self):
        m = _make_manifest(databases=[{"name": "db1", "owner": "odoo"}])
        assert len(m.databases) == 1
        assert m.databases[0].name == "db1"

    def test_load_from_yaml(self, tmp_path):
        yaml_content = """
kind: migration
name: test
source:
  server: src-01
target:
  server: tgt-01
tenant: test
databases:
  - name: db1
    owner: odoo
services:
  - instances/production/test.yaml
"""
        f = tmp_path / "migration.yaml"
        f.write_text(yaml_content)
        m = load_migration_manifest(f)
        assert m.name == "test"
        assert len(m.databases) == 1
        assert len(m.services) == 1


class TestMigrationState:
    def test_save_and_load(self, tmp_path, monkeypatch):
        monkeypatch.setattr("kctl_dokploy.core.migrator._STATE_DIR", tmp_path)
        state = MigrationState(id="test-123", tenant="test", from_server="src", to_server="tgt")
        state.save()
        loaded = MigrationState.load("test-123")
        assert loaded.id == "test-123"
        assert loaded.tenant == "test"

    def test_record_step(self, tmp_path, monkeypatch):
        monkeypatch.setattr("kctl_dokploy.core.migrator._STATE_DIR", tmp_path)
        state = MigrationState(id="test-456", tenant="test", from_server="src", to_server="tgt")
        state.record_step("1_preflight", "done", "All passed")
        assert state.step_done("1_preflight")
        assert not state.step_done("2_postgres")


class TestMigrator:
    def test_dry_run_completes_all_steps(self, tmp_path, monkeypatch):
        monkeypatch.setattr("kctl_dokploy.core.migrator._STATE_DIR", tmp_path)
        m = _make_manifest()
        migrator = Migrator(manifest=m, dry_run=True)
        results = migrator.run_all()
        assert len(results) == 12
        assert all(r.status in ("done", "skipped") for r in results)
        assert migrator.state.status == "completed"

    def test_plan_is_dry_run(self, tmp_path, monkeypatch):
        monkeypatch.setattr("kctl_dokploy.core.migrator._STATE_DIR", tmp_path)
        m = _make_manifest()
        migrator = Migrator(manifest=m)
        results = migrator.plan()
        assert len(results) == 12
        assert migrator.state.status == "completed"

    def test_state_persisted(self, tmp_path, monkeypatch):
        monkeypatch.setattr("kctl_dokploy.core.migrator._STATE_DIR", tmp_path)
        m = _make_manifest()
        migrator = Migrator(manifest=m, dry_run=True)
        migrator.run_all()
        # State file should exist
        files = list(tmp_path.glob("migrate-test-*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text())
        assert data["status"] == "completed"
        assert data["tenant"] == "test"
