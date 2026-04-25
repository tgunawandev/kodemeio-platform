"""Security and access management commands for kctl-supa."""

from __future__ import annotations

import base64
import json
from typing import Annotated

import typer
from rich import print as rprint
from rich.table import Table

from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.docker import DockerOps
from kctl_supa.core.exceptions import DockerError

app = typer.Typer(help="Security and access management.")


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


def _decode_jwt(token: str) -> dict:
    """Decode a JWT payload without verification."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")
    payload = parts[1]
    padding = 4 - len(payload) % 4
    payload += "=" * padding
    return json.loads(base64.urlsafe_b64decode(payload))


def _decode_jwt_header(token: str) -> dict:
    """Decode a JWT header without verification."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")
    header = parts[0]
    padding = 4 - len(header) % 4
    header += "=" * padding
    return json.loads(base64.urlsafe_b64decode(header))


@app.command("rls-policies")
def rls_policies(ctx: typer.Context) -> None:
    """List RLS policies for all tables."""
    actx: AppContext = ctx.obj

    result = _run_psql(
        actx,
        "SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual "
        "FROM pg_policies ORDER BY schemaname, tablename",
    )
    typer.echo(result)


@app.command("jwt-inspect")
def jwt_inspect(
    ctx: typer.Context,
    token: Annotated[str, typer.Argument(help="JWT token to decode and inspect")],
) -> None:
    """Decode and display JWT claims locally (no verification)."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        header = _decode_jwt_header(token)
        payload = _decode_jwt(token)
    except (ValueError, Exception) as exc:
        out.error(f"Failed to decode JWT: {exc}")
        raise typer.Exit(1) from exc

    out.info("JWT Header:")
    typer.echo(json.dumps(header, indent=2))

    out.info("JWT Payload:")
    typer.echo(json.dumps(payload, indent=2))

    import time
    now = int(time.time())

    if "exp" in payload:
        exp = payload["exp"]
        if exp < now:
            out.error(f"Token EXPIRED at {exp} (now={now})")
        else:
            remaining = exp - now
            out.info(f"Token valid for {remaining}s (expires at {exp})")

    if "iss" in payload:
        out.kv("Issuer", payload["iss"])
    if "sub" in payload:
        out.kv("Subject", payload["sub"])
    if "role" in payload:
        out.kv("Role", payload["role"])


@app.command("api-keys")
def api_keys(ctx: typer.Context) -> None:
    """Show masked API keys from config."""
    actx: AppContext = ctx.obj
    out = actx.output

    cfg = actx.config

    def mask(key: str) -> str:
        if not key or len(key) < 16:
            return "****" if key else "(not set)"
        return f"{key[:8]}****{key[-8:]}"

    table = Table(title="API Keys", show_header=True, header_style="bold cyan")
    table.add_column("Key", style="cyan")
    table.add_column("Value")

    table.add_row("service_role_key", mask(cfg.service_role_key))
    table.add_row("anon_key", mask(cfg.anon_key))

    rprint(table)


@app.command()
def audit(ctx: typer.Context) -> None:
    """Recent DDL changes (CREATE/ALTER/DROP) from pg_stat_activity."""
    actx: AppContext = ctx.obj

    result = _run_psql(
        actx,
        "SELECT pid, usename, application_name, state, query_start, query "
        "FROM pg_stat_activity "
        "WHERE query LIKE '%CREATE%' OR query LIKE '%ALTER%' OR query LIKE '%DROP%' "
        "ORDER BY query_start DESC NULLS LAST LIMIT 20",
    )
    typer.echo(result)
