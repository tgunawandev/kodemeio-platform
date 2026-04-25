"""Database migration management commands for kctl-supa."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.docker import DockerOps
from kctl_supa.core.exceptions import DockerError

app = typer.Typer(help="Database migration management.")

_MIGRATIONS_DIR = "migrations"


def _get_docker(actx: AppContext) -> DockerOps:
    return DockerOps(actx.config)


@app.command()
def run(
    ctx: typer.Context,
    file: Annotated[str, typer.Argument(help="SQL migration file to execute")],
) -> None:
    """Execute a SQL migration file on the remote database."""
    actx: AppContext = ctx.obj
    out = actx.output

    migration_path = Path(file)
    if not migration_path.exists():
        out.error(f"Migration file not found: {migration_path}")
        raise typer.Exit(1)

    sql = migration_path.read_text(encoding="utf-8")
    if not sql.strip():
        out.error("Migration file is empty")
        raise typer.Exit(1)

    out.info(f"Running migration: {migration_path.name}")
    try:
        docker = _get_docker(actx)
        result = docker.psql(sql)
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    typer.echo(result)
    out.success(f"Migration complete: {migration_path.name}")


@app.command()
def status(ctx: typer.Context) -> None:
    """Show applied migration history."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        docker = _get_docker(actx)
        result = docker.psql(
            "SELECT version, statements, name, inserted_at "
            "FROM supabase_migrations.schema_migrations "
            "ORDER BY version DESC LIMIT 20"
        )
        docker.close()
        typer.echo(result)
    except DockerError as exc:
        err_msg = str(exc)
        if "supabase_migrations" in err_msg or "does not exist" in err_msg:
            out.info("Migration tracking table not found (supabase_migrations.schema_migrations).")
            out.info("Run 'supabase db push' or apply migrations manually to initialize it.")
        else:
            out.error(err_msg)
            raise typer.Exit(1) from exc


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Migration name (snake_case)")],
) -> None:
    """Generate a new timestamped SQL migration file."""
    actx: AppContext = ctx.obj
    out = actx.output

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    filename = f"{timestamp}_{name}.sql"

    migrations_dir = Path(_MIGRATIONS_DIR)
    migrations_dir.mkdir(parents=True, exist_ok=True)

    migration_file = migrations_dir / filename
    header = (
        f"-- Migration: {name}\n"
        f"-- Created: {datetime.utcnow().isoformat()}Z\n"
        f"-- Description: <describe what this migration does>\n\n"
        f"-- Write your SQL below:\n\n"
    )
    migration_file.write_text(header, encoding="utf-8")

    out.success(f"Created migration file: {migration_file}")


@app.command()
def diff(ctx: typer.Context) -> None:
    """Compare public schema tables and columns."""
    actx: AppContext = ctx.obj

    try:
        docker = _get_docker(actx)
        result = docker.psql(
            "SELECT table_name, column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_schema='public' "
            "ORDER BY table_name, ordinal_position"
        )
        docker.close()
    except DockerError as exc:
        actx.output.error(str(exc))
        raise typer.Exit(1) from exc

    typer.echo(result)
