"""Backup and restore commands."""

from __future__ import annotations

from datetime import UTC
from pathlib import Path
from typing import Annotated

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.exceptions import DockerError

app = typer.Typer(help="Backup and restore OpenClaw volumes.")


def _backups_dir(project_root: Path) -> Path:
    return project_root / "backups"


@app.command()
def create(ctx: typer.Context) -> None:
    """Create a timestamped backup of Docker volumes."""
    actx: AppContext = ctx.obj
    out = actx.output

    output_dir = _backups_dir(actx.project_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    out.info("Creating backup of openclaw-data and openclaw-workspace volumes...")
    try:
        backup_path = actx.docker.backup_volumes(output_dir=output_dir)
        out.success(f"Backup created: {backup_path}")
    except DockerError as e:
        out.error(f"Docker error: {e}")
        out.info("Is Docker running and are the volumes mounted?")
        raise typer.Exit(1) from e


@app.command()
def restore(
    ctx: typer.Context,
    backup: Annotated[str, typer.Argument(help="Backup directory name (e.g. 20260328-120000) or full path")],
) -> None:
    """Restore volumes from a backup (destructive — requires confirmation)."""
    actx: AppContext = ctx.obj
    out = actx.output

    # Resolve backup path
    backup_path = Path(backup)
    if not backup_path.is_absolute():
        backup_path = _backups_dir(actx.project_root) / backup

    if not backup_path.exists():
        out.error(f"Backup not found: {backup_path}")
        raise typer.Exit(1)

    out.warn("This will OVERWRITE all current volume data. This cannot be undone.")
    confirmation = typer.prompt("Type 'RESTORE' to confirm")
    if confirmation != "RESTORE":
        out.info("Aborted.")
        return

    out.info(f"Restoring from: {backup_path}")
    try:
        actx.docker.restore_volumes(backup_dir=backup_path)
        out.success("Volumes restored successfully.")
        out.info("Restart the gateway to apply: kctl-claw deploy restart")
    except DockerError as e:
        out.error(f"Docker error during restore: {e}")
        raise typer.Exit(1) from e


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List available backups with size and date."""
    actx: AppContext = ctx.obj
    out = actx.output

    backups_dir = _backups_dir(actx.project_root)
    if not backups_dir.exists():
        out.info("No backups found. Run: kctl-claw backup create")
        return

    entries = sorted(
        [d for d in backups_dir.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )

    if not entries:
        out.info("No backups found. Run: kctl-claw backup create")
        return

    rows = []
    json_data = []
    for d in entries:
        # Sum up sizes of tar.gz files
        total_bytes = sum(f.stat().st_size for f in d.iterdir() if f.suffix == ".gz")
        size_mb = f"{total_bytes / 1024 / 1024:.1f} MB"
        from datetime import datetime

        mtime = datetime.fromtimestamp(d.stat().st_mtime, tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
        rows.append([d.name, size_mb, mtime])
        json_data.append({"name": d.name, "size_bytes": total_bytes, "date": mtime})

    out.table(
        f"Backups ({len(entries)})",
        [("Name", "cyan"), ("Size", ""), ("Date", "dim")],
        rows,
        data_for_json=json_data,
    )
