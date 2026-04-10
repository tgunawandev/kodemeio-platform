"""Sync config schema and loader for kctl-outline.

The .outline-sync.yaml file describes how a repository syncs to one or more
Outline collections. The v2 schema supports multi-mapping with per-mapping
mode (push/pull/mixed), include/exclude globs, and subpath nesting.

A v1 config (top-level `sync.collection` + `sync.files`) is auto-upgraded
to a single push mapping for backwards compatibility.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class SyncMode(str, Enum):
    PUSH = "push"
    PULL = "pull"
    MIXED = "mixed"


class SyncMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    src: Path
    collection: str
    mode: SyncMode
    subpath: str = ""
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)

    @field_validator("src", mode="before")
    @classmethod
    def _coerce_src(cls, v: Any) -> Path:
        if isinstance(v, Path):
            return v
        if isinstance(v, str):
            # Strip trailing slash to normalize "shared/" → "shared"
            return Path(v.rstrip("/") or ".")
        raise TypeError(f"src must be a string or Path, got {type(v).__name__}")


class SyncConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instance: str | None = None
    profile: str | None = None
    mappings: list[SyncMapping]


def _is_v1(data: dict[str, Any]) -> bool:
    return "sync" in data and "mappings" not in data


def _upgrade_v1(data: dict[str, Any]) -> dict[str, Any]:
    """Translate v1 single-collection format to v2 single-mapping."""
    s = data.get("sync") or {}
    return {
        "mappings": [
            {
                "src": ".",
                "collection": s.get("collection", "Documentation"),
                "mode": "push",
                "include": list(s.get("files") or []),
            }
        ]
    }


def load_sync_config(repo_path: Path) -> SyncConfig | None:
    """Load .outline-sync.yaml from a repo directory.

    Returns None if no config file is present. Raises ValueError on
    schema/validation errors (with the original ValidationError chained).
    """
    cfg_file = repo_path / ".outline-sync.yaml"
    if not cfg_file.is_file():
        return None
    try:
        data = yaml.safe_load(cfg_file.read_text()) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"{cfg_file}: invalid YAML: {e}") from e
    if not isinstance(data, dict):
        raise ValueError(f"{cfg_file}: top level must be a mapping")
    if _is_v1(data):
        data = _upgrade_v1(data)
    try:
        return SyncConfig.model_validate(data)
    except ValidationError as e:
        raise ValueError(f"{cfg_file}: {e}") from e
