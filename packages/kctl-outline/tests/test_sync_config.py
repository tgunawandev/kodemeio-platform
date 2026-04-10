"""Tests for cli/src/kctl_outline/core/sync_config.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from kctl_outline.core.sync_config import (
    SyncConfig,
    SyncMapping,
    SyncMode,
    load_sync_config,
)


def test_minimal_v2_config(tmp_repo: Path) -> None:
    cfg_text = """
mappings:
  - src: shared/
    collection: "Shared — Engineering"
    mode: push
"""
    (tmp_repo / ".outline-sync.yaml").write_text(cfg_text)
    cfg = load_sync_config(tmp_repo)
    assert isinstance(cfg, SyncConfig)
    assert len(cfg.mappings) == 1
    m = cfg.mappings[0]
    assert m.src == Path("shared")
    assert m.collection == "Shared — Engineering"
    assert m.mode == SyncMode.PUSH
    assert m.subpath == ""
    assert m.include == []
    assert m.exclude == []


def test_full_v2_config_with_all_fields(tmp_repo: Path) -> None:
    cfg_text = """
instance: outline.kodeme.io
profile: kod
mappings:
  - src: shared/
    collection: "Shared — Engineering"
    mode: push
    include:
      - "01-*/**"
      - "02-*/**"
    exclude:
      - "**/draft/**"
  - src: tenants/kod
    collection: "Kod — Internal"
    mode: mixed
    subpath: "Mobile Apps"
"""
    (tmp_repo / ".outline-sync.yaml").write_text(cfg_text)
    cfg = load_sync_config(tmp_repo)
    assert cfg.instance == "outline.kodeme.io"
    assert cfg.profile == "kod"
    assert len(cfg.mappings) == 2
    eng = cfg.mappings[0]
    assert eng.include == ["01-*/**", "02-*/**"]
    assert eng.exclude == ["**/draft/**"]
    kod = cfg.mappings[1]
    assert kod.mode == SyncMode.MIXED
    assert kod.subpath == "Mobile Apps"


def test_v1_config_auto_migrates(tmp_repo: Path) -> None:
    """Old single-collection format is read as one push mapping."""
    cfg_text = """
sync:
  collection: "Documentation"
  files:
    - README.md
    - CLAUDE.md
    - "**/README.md"
"""
    (tmp_repo / ".outline-sync.yaml").write_text(cfg_text)
    cfg = load_sync_config(tmp_repo)
    assert len(cfg.mappings) == 1
    m = cfg.mappings[0]
    assert m.collection == "Documentation"
    assert m.mode == SyncMode.PUSH
    assert m.src == Path(".")
    assert m.include == ["README.md", "CLAUDE.md", "**/README.md"]


def test_missing_config_returns_none(tmp_repo: Path) -> None:
    assert load_sync_config(tmp_repo) is None


def test_invalid_mode_rejected(tmp_repo: Path) -> None:
    cfg_text = """
mappings:
  - src: shared/
    collection: X
    mode: bogus
"""
    (tmp_repo / ".outline-sync.yaml").write_text(cfg_text)
    with pytest.raises(ValueError, match="bogus"):
        load_sync_config(tmp_repo)


def test_missing_required_fields_rejected(tmp_repo: Path) -> None:
    cfg_text = """
mappings:
  - src: shared/
    # collection missing
    mode: push
"""
    (tmp_repo / ".outline-sync.yaml").write_text(cfg_text)
    with pytest.raises(ValueError):
        load_sync_config(tmp_repo)
