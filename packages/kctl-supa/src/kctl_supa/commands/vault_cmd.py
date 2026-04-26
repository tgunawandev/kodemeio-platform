"""Supabase Vault (pgsodium) secret management commands for kctl-supa."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.docker import DockerOps
from kctl_supa.core.exceptions import DockerError

app = typer.Typer(help="Manage Supabase Vault encrypted secrets.")


def _get_docker(actx: AppContext) -> DockerOps:
    return DockerOps(actx.config)


def _run_psql(actx: AppContext, query: str) -> str:
    out = actx.output
    try:
        docker = _get_docker(actx)
        result = docker.psql(query)
        docker.close()
        return result
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc


@app.command(name="list")
def list_secrets(ctx: typer.Context) -> None:
    """List vault secrets (names and descriptions only)."""
    actx: AppContext = ctx.obj
    out = actx.output
    check = _run_psql(actx, "SELECT 1 FROM pg_extension WHERE extname = 'pgsodium'")
    if "1" not in check:
        out.warn("Vault (pgsodium) not installed. Enable it: CREATE EXTENSION pgsodium;")
        return
    schema_check = _run_psql(actx, "SELECT 1 FROM pg_namespace WHERE nspname = 'vault'")
    if "1" not in schema_check:
        out.warn("Vault schema not initialized. Supabase Vault migrations have not run yet.")
        out.info("pgsodium extension is installed — Vault schema will be created by Supabase migrations.")
        return
    result = _run_psql(
        actx,
        "SELECT id, name, description, created_at, updated_at FROM vault.secrets ORDER BY name",
    )
    typer.echo(result)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Secret name")],
    value: Annotated[str, typer.Option("--value", "-v", help="Secret value", prompt=True, hide_input=True)],
    description: Annotated[str, typer.Option("--description", "-d", help="Description")] = "",
) -> None:
    """Create a new vault secret."""
    actx: AppContext = ctx.obj
    out = actx.output
    desc = f", '{description}'" if description else ""
    result = _run_psql(
        actx,
        f"SELECT vault.create_secret('{value}', '{name}'{desc})",
    )
    out.success(f"Secret '{name}' created")
    typer.echo(result)


@app.command()
def update(
    ctx: typer.Context,
    secret_id: Annotated[str, typer.Argument(help="Secret UUID")],
    value: Annotated[str, typer.Option("--value", "-v", help="New secret value", prompt=True, hide_input=True)],
) -> None:
    """Update a vault secret value."""
    actx: AppContext = ctx.obj
    out = actx.output
    _run_psql(
        actx,
        f"SELECT vault.update_secret('{secret_id}', '{value}')",
    )
    out.success(f"Secret '{secret_id}' updated")


@app.command()
def delete(
    ctx: typer.Context,
    secret_id: Annotated[str, typer.Argument(help="Secret UUID to delete")],
) -> None:
    """Delete a vault secret."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not typer.confirm(f"Delete secret '{secret_id}'?"):
        raise typer.Exit(0)

    _run_psql(actx, f"DELETE FROM vault.secrets WHERE id = '{secret_id}'")
    out.success(f"Secret '{secret_id}' deleted")
