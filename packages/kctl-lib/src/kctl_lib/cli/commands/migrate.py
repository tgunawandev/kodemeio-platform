"""`kctl-profiles migrate` — one-shot config rewrite to the new taxonomy."""

from __future__ import annotations

import difflib
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
import yaml

from kctl_lib._migration import migrate_config

DEFAULT_CONFIG = Path.home() / ".config" / "kodemeio" / "config.yaml"


def _dump(data: dict[str, Any]) -> str:
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
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        if Path(tmp).exists():
            Path(tmp).unlink()
        raise


def migrate(
    config: Path = typer.Option(DEFAULT_CONFIG, "--config", help="Path to config.yaml."),
    yes: bool = typer.Option(False, "--yes", help="Apply the migration (otherwise preview)."),
) -> None:
    """Rewrite a kctl-* config file to the new taxonomy, with backup."""
    if not config.exists():
        typer.echo(f"ERROR: config file not found: {config}", err=True)
        raise typer.Exit(code=2)

    before_text = config.read_text()
    before_data = yaml.safe_load(before_text) or {}
    after_data = migrate_config(before_data)
    after_text = _dump(after_data)

    diff = _diff(before_text, after_text, config)

    if not diff:
        typer.echo(f"No changes — {config} is already migrated.")
        raise typer.Exit(code=0)

    typer.echo(diff)

    if not yes:
        typer.echo(
            f"\nPreview only. Re-run with --yes to apply (will back up to {config}.bak.<timestamp>).",
            err=True,
        )
        raise typer.Exit(code=1)

    backup = _backup(config)
    _atomic_write(config, after_text)
    typer.echo(f"\nMigration applied.\n  Backup: {backup}\n  New:    {config}")
