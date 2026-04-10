"""End-to-end test of the refactored sync run command via Typer's CliRunner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from typer.testing import CliRunner

from kctl_outline.cli import app


def _write_v2_config(repo: Path, mappings: list[dict]) -> None:
    cfg = {"mappings": mappings}
    (repo / ".outline-sync.yaml").write_text(yaml.safe_dump(cfg))


def test_sync_run_dry_run_v2_config(tmp_repo: Path, fake_client, monkeypatch) -> None:
    # Set up a docs repo with one push mapping
    (tmp_repo / "shared" / "01-getting-started").mkdir(parents=True)
    (tmp_repo / "shared" / "01-getting-started" / "intro.md").write_text("# Intro\n")
    _write_v2_config(
        tmp_repo,
        [
            {"src": "shared", "collection": "Shared — Engineering", "mode": "push"},
        ],
    )

    # Patch the client constructor in commands/sync.py to return our fake
    monkeypatch.setattr(
        "kctl_outline.commands.sync._build_client_for_mapping",
        lambda ctx, mapping, cfg=None: fake_client,
    )

    runner = CliRunner()
    result = runner.invoke(app, ["sync", "run", str(tmp_repo)])
    assert result.exit_code == 0, result.output
    # Dry run by default — fake client should NOT have create calls
    create_calls = [c for c in fake_client.calls if c[0] == "documents.create"]
    assert create_calls == [], f"dry-run should not create docs; got {create_calls}"
    assert "create" in result.output.lower()
    assert "intro.md" in result.output


def test_sync_run_no_dry_run_pushes_to_outline(tmp_repo: Path, fake_client, monkeypatch) -> None:
    (tmp_repo / "shared" / "01-getting-started").mkdir(parents=True)
    (tmp_repo / "shared" / "01-getting-started" / "intro.md").write_text("# Intro\n")
    _write_v2_config(
        tmp_repo,
        [
            {"src": "shared", "collection": "Shared — Engineering", "mode": "push"},
        ],
    )
    monkeypatch.setattr(
        "kctl_outline.commands.sync._build_client_for_mapping",
        lambda ctx, mapping, cfg=None: fake_client,
    )
    # Avoid touching real state file
    state_path = tmp_repo / "outline-sync.json"
    monkeypatch.setattr("kctl_outline.core.sync_state.STATE_FILE", state_path)
    monkeypatch.setattr("kctl_outline.core.sync_state.STATE_DIR", tmp_repo)

    runner = CliRunner()
    result = runner.invoke(app, ["sync", "run", str(tmp_repo), "--no-dry-run"])
    assert result.exit_code == 0, result.output
    create_calls = [c for c in fake_client.calls if c[0] == "documents.create"]
    assert len(create_calls) >= 1


def test_sync_run_mode_filter_skips_other_modes(tmp_repo: Path, fake_client, monkeypatch) -> None:
    """When --mode push is passed, pull mappings should be skipped."""
    (tmp_repo / "shared").mkdir()
    (tmp_repo / "shared" / "intro.md").write_text("# Intro\n")
    _write_v2_config(
        tmp_repo,
        [
            {"src": "shared", "collection": "C1", "mode": "push"},
            {"src": "shared", "collection": "C2", "mode": "pull"},
        ],
    )
    monkeypatch.setattr(
        "kctl_outline.commands.sync._build_client_for_mapping",
        lambda ctx, mapping, cfg=None: fake_client,
    )

    runner = CliRunner()
    result = runner.invoke(app, ["sync", "run", str(tmp_repo), "--mode", "push"])
    assert result.exit_code == 0, result.output
    assert "C1" in result.output
    assert "C2" not in result.output  # pull mapping skipped
