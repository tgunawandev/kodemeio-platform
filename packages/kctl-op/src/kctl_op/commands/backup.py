"""Backup management commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from kctl_op.core.callbacks import AppContext

BACKUP_DIR = Path.home() / ".kodemeio-op" / "backups"

app = typer.Typer(help="Backup management for .env files.")


@app.command(name="list")
def list_backups(
    ctx: typer.Context,
    project: Annotated[str | None, typer.Argument(help="Filter by project name.")] = None,
) -> None:
    """List available backups."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not BACKUP_DIR.exists():
        out.info("No backups found.")
        return

    rows = []
    json_data = []

    for project_dir in sorted(BACKUP_DIR.iterdir()):
        if not project_dir.is_dir():
            continue
        if project and project_dir.name != project:
            continue

        for env_dir in sorted(project_dir.iterdir()):
            if not env_dir.is_dir():
                continue

            backups = sorted(env_dir.glob("*.bak"), reverse=True)
            for bak in backups:
                size = bak.stat().st_size
                rows.append(
                    [
                        project_dir.name,
                        env_dir.name,
                        bak.name,
                        f"{size:,} bytes",
                    ]
                )
                json_data.append(
                    {
                        "project": project_dir.name,
                        "environment": env_dir.name,
                        "filename": bak.name,
                        "size": size,
                        "path": str(bak),
                    }
                )

    if not rows:
        out.info("No backups found." + (f" (project: {project})" if project else ""))
        return

    out.table(
        title=f"Backups ({len(rows)})",
        columns=[
            ("Project", "green"),
            ("Environment", "cyan"),
            ("Filename", ""),
            ("Size", "dim"),
        ],
        rows=rows,
        data_for_json=json_data,
    )


@app.command()
def restore(
    ctx: typer.Context,
    project: Annotated[str, typer.Argument(help="Project name.")],
    environment: Annotated[str, typer.Argument(help="Environment name.")],
    timestamp: Annotated[
        str | None, typer.Argument(help="Backup timestamp (from filename). Latest if omitted.")
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation.")] = False,
) -> None:
    """Restore a .env file from backup."""
    actx: AppContext = ctx.obj
    out = actx.output

    env_backup_dir = BACKUP_DIR / project / environment
    if not env_backup_dir.exists():
        out.error(f"No backups found for {project}/{environment}")
        raise typer.Exit(code=1)

    backups = sorted(env_backup_dir.glob("*.bak"), reverse=True)
    if not backups:
        out.error(f"No backup files in {env_backup_dir}")
        raise typer.Exit(code=1)

    if timestamp:
        selected = [b for b in backups if timestamp in b.name]
        if not selected:
            out.error(f"No backup matching timestamp '{timestamp}'")
            raise typer.Exit(code=1)
        backup_file = selected[0]
    else:
        backup_file = backups[0]

    out.info(f"Restoring from: {backup_file.name}")

    # Find the target .env file
    cfg = actx.service_config
    client = actx.client
    files = client.discover_files(
        cfg.scan_roots,
        cfg.exclude_patterns,
        cfg.env_mappings,
        cfg.custom_env_pattern,
    )
    matches = [f for f in files if f.project == project and f.environment == environment]

    if not matches:
        out.error(f"Cannot find target .env file for {project}/{environment}")
        raise typer.Exit(code=1)

    target = matches[0].path

    if not force and not typer.confirm(f"Restore {backup_file.name} to {target}?"):
        raise typer.Exit()

    # Read backup and write to target
    content = backup_file.read_text()
    target.write_text(content)
    out.success(f"Restored {backup_file.name} -> {target}")


@app.command()
def clean(
    ctx: typer.Context,
    keep: Annotated[int, typer.Option("--keep", "-k", help="Number of backups to keep per file.")] = 10,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation.")] = False,
) -> None:
    """Clean old backups, keeping the N most recent per file."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not BACKUP_DIR.exists():
        out.info("No backups to clean.")
        return

    to_delete: list[Path] = []
    for project_dir in BACKUP_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        for env_dir in project_dir.iterdir():
            if not env_dir.is_dir():
                continue
            backups = sorted(env_dir.glob("*.bak"), reverse=True)
            if len(backups) > keep:
                to_delete.extend(backups[keep:])

    if not to_delete:
        out.info(f"Nothing to clean (keeping {keep} per file).")
        return

    out.info(f"Will delete {len(to_delete)} old backup(s).")

    if not force and not typer.confirm("Proceed?"):
        raise typer.Exit()

    for f in to_delete:
        f.unlink()
    out.success(f"Deleted {len(to_delete)} old backup(s).")
