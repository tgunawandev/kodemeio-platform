#!/usr/bin/env python3
"""One-shot migration of ~/.config/kodemeio/config.yaml to the new taxonomy.

DEPRECATED: prefer `kctl-profiles migrate` (same behavior, proper CLI).
This script is retained so Stage A's history remains reproducible.

See docs/superpowers/specs/2026-04-19-kctl-profiles-standardization-design.md.

Usage:
    # Preview (default): prints unified diff, exits 0 if already migrated,
    # exits 1 if changes would be applied.
    uv run python scripts/migrate_profiles.py

    # Apply the migration (writes .bak.<timestamp> first, then atomic replace).
    uv run python scripts/migrate_profiles.py --yes

    # Operate on a non-default path (for testing).
    uv run python scripts/migrate_profiles.py --config /tmp/config.yaml --yes
"""

from __future__ import annotations

import argparse
import difflib
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

# kctl-lib ships the pure-logic transforms.
from kctl_lib._migration import migrate_config

DEFAULT_CONFIG = Path.home() / ".config" / "kodemeio" / "config.yaml"


def _dump(data: dict) -> str:
    return yaml.dump(data, default_flow_style=False, sort_keys=False)


def _diff(before: str, after: str, path: Path) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=str(path),
            tofile=f"{path} (migrated)",
        )
    )


def _backup(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = path.with_suffix(path.suffix + f".bak.{stamp}")
    target.write_bytes(path.read_bytes())
    return target


def _atomic_write(path: Path, content: str) -> None:
    """Write atomically via tempfile + rename (same filesystem)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        if Path(tmp).exists():
            Path(tmp).unlink()
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Path to config.yaml (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Apply the migration. Without this flag, the script only previews.",
    )
    args = parser.parse_args(argv)

    if not args.config.exists():
        print(f"ERROR: config file not found: {args.config}", file=sys.stderr)
        return 2

    before_text = args.config.read_text()
    before_data = yaml.safe_load(before_text) or {}
    after_data = migrate_config(before_data)
    after_text = _dump(after_data)

    diff = _diff(before_text, after_text, args.config)

    if not diff:
        print(f"No changes — {args.config} is already migrated.")
        return 0

    print(diff)

    if not args.yes:
        print(
            f"\nPreview only. Re-run with --yes to apply (will back up to {args.config}.bak.<timestamp>).",
            file=sys.stderr,
        )
        return 1

    backup = _backup(args.config)
    _atomic_write(args.config, after_text)
    print(f"\nMigration applied.\n  Backup: {backup}\n  New:    {args.config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
