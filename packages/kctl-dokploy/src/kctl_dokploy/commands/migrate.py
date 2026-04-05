"""Migration subcommands: validate, plan, apply, rollback, cleanup."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext
from kctl_dokploy.core.migration_manifest import load_migration_manifest
from kctl_dokploy.core.migrator import Migrator, StepResult

app = typer.Typer(help="Server-to-server migration pipeline.")


def _print_results(c: AppContext, title: str, results: list[StepResult]) -> bool:
    """Print step results table. Return True if any step failed."""
    status_icons = {"done": "✓", "failed": "✗", "skipped": "→", "pending": "○"}
    rows = []
    json_data = []
    for r in results:
        icon = status_icons.get(r.status, "?")
        rows.append([f"{icon} {r.step}", r.status.upper(), r.message])
        json_data.append({"step": r.step, "status": r.status, "message": r.message})

    c.output.table(
        title,
        [("Step", "cyan"), ("Status", ""), ("Details", "dim")],
        rows,
        data_for_json=json_data,
    )
    return any(r.status == "failed" for r in results)


@app.command()
def validate(
    ctx: typer.Context,
    file: Annotated[Path, typer.Option("--file", "-f", help="Migration manifest YAML", exists=True)] = ...,  # type: ignore[assignment]
) -> None:
    """Validate a migration manifest without executing."""
    c: AppContext = ctx.obj
    try:
        manifest = load_migration_manifest(file)
    except Exception as exc:
        c.output.error(f"Invalid migration manifest: {exc}")
        raise typer.Exit(1) from exc

    summary = {
        "name": manifest.name,
        "tenant": manifest.tenant,
        "source": manifest.source.server,
        "target": manifest.target.server,
        "databases": len(manifest.databases),
        "services": len(manifest.services),
        "dns_records": len(manifest.dns.records),
    }
    c.output.table(
        f"Migration Manifest: {manifest.name}",
        [("Property", "cyan"), ("Value", "")],
        [[k, str(v)] for k, v in summary.items()],
        data_for_json=summary,
    )
    c.output.success(f"Migration manifest is valid: {manifest.name}")


@app.command()
def plan(
    ctx: typer.Context,
    file: Annotated[Path, typer.Option("--file", "-f", help="Migration manifest YAML", exists=True)] = ...,  # type: ignore[assignment]
) -> None:
    """Dry-run: show all steps without executing."""
    c: AppContext = ctx.obj
    manifest = load_migration_manifest(file)
    c.output.info(f"Planning migration: {manifest.name}")

    migrator = Migrator(manifest=manifest, dry_run=True)
    results = migrator.plan()

    _print_results(c, f"Migration Plan: {manifest.name}", results)
    c.output.success("Plan complete — no changes made")


@app.command()
def apply(
    ctx: typer.Context,
    file: Annotated[Path, typer.Option("--file", "-f", help="Migration manifest YAML", exists=True)] = ...,  # type: ignore[assignment]
    resume: Annotated[bool, typer.Option("--resume", help="Resume a failed migration")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview changes")] = False,
) -> None:
    """Execute the migration pipeline."""
    c: AppContext = ctx.obj
    manifest = load_migration_manifest(file)

    mode = " [dry-run]" if dry_run else ""
    resume_msg = " (resuming)" if resume else ""
    c.output.info(f"Migration: {manifest.name}{mode}{resume_msg}")
    c.output.info(f"  {manifest.source.server} → {manifest.target.server}")

    migrator = Migrator(manifest=manifest, dry_run=dry_run, resume=resume)
    results = migrator.run_all()

    has_failures = _print_results(c, f"Migration: {manifest.name}", results)
    if has_failures:
        c.output.error(f"Migration failed at step {migrator.state.current_step}")
        c.output.info(f"State saved: {migrator.state.id}")
        c.output.info(f"Resume with: kctl-dokploy deploy migrate apply -f {file} --resume")
        sys.exit(1)
    else:
        c.output.success(f"Migration complete: {manifest.name}")
        c.output.info(f"State: {migrator.state.id}")


@app.command()
def rollback(
    ctx: typer.Context,
    file: Annotated[Path, typer.Option("--file", "-f", help="Migration manifest YAML", exists=True)] = ...,  # type: ignore[assignment]
) -> None:
    """Rollback a failed migration."""
    c: AppContext = ctx.obj
    manifest = load_migration_manifest(file)

    migrator = Migrator(manifest=manifest, resume=True)
    c.output.info(f"Rolling back: {migrator.state.id}")

    results = migrator.rollback()
    _print_results(c, f"Rollback: {manifest.name}", results)
    c.output.success("Rollback complete")


@app.command()
def cleanup(
    ctx: typer.Context,
    file: Annotated[Path, typer.Option("--file", "-f", help="Migration manifest YAML", exists=True)] = ...,  # type: ignore[assignment]
) -> None:
    """Post-soak cleanup: remove dump files and mark as done."""
    c: AppContext = ctx.obj
    manifest = load_migration_manifest(file)

    migrator = Migrator(manifest=manifest, resume=True)
    c.output.info(f"Cleaning up: {migrator.state.id}")

    results = migrator.cleanup()
    has_failures = _print_results(c, f"Cleanup: {manifest.name}", results)
    if has_failures:
        c.output.error("Cleanup had failures")
        sys.exit(1)
    else:
        c.output.success("Cleanup complete")
