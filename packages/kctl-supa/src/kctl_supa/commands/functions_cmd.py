"""Edge functions management commands for kctl-supa."""

from __future__ import annotations

import json as _json
from pathlib import Path
from typing import Annotated, Optional

import typer

from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.client import SupabaseClient
from kctl_supa.core.docker import DockerOps
from kctl_supa.core.exceptions import APIError, DockerError

app = typer.Typer(help="Edge functions management.")


def _get_docker(actx: AppContext) -> DockerOps:
    return DockerOps(actx.config)


def _get_client(actx: AppContext) -> SupabaseClient:
    cfg = actx.config
    return SupabaseClient(base_url=cfg.url, service_role_key=cfg.service_role_key, anon_key=cfg.anon_key)


@app.command(name="list")
def list_functions(ctx: typer.Context) -> None:
    """List deployed functions."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        docker = _get_docker(actx)
        result = docker.docker_exec(
            "functions",
            "ls /home/deno/functions/ 2>/dev/null || echo 'no functions directory found'",
        )
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    typer.echo(result)


@app.command()
def deploy(
    ctx: typer.Context,
    path: Annotated[str, typer.Argument(help="Path to function directory or file to deploy")],
) -> None:
    """Deploy a function to the edge-functions container."""
    actx: AppContext = ctx.obj
    out = actx.output

    func_path = Path(path).resolve()
    if not func_path.exists():
        out.error(f"Path does not exist: {func_path}")
        raise typer.Exit(1)

    func_name = func_path.name
    docker = _get_docker(actx)
    container = docker.resolve_container("edge-functions")
    docker.close()

    out.info(f"To deploy function '{func_name}', run:")
    typer.echo(f"  docker cp {func_path} {container}:/home/deno/functions/{func_name}")
    typer.echo(f"  docker restart {container}")
    out.info("Or use 'supabase functions deploy' from the Supabase CLI.")


@app.command()
def logs(ctx: typer.Context) -> None:
    """Show function execution logs."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        docker = _get_docker(actx)
        result = docker.logs("functions", tail=100)
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    typer.echo(result)


@app.command()
def invoke(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Function name to invoke")],
    data: Annotated[
        Optional[str],
        typer.Option("--data", "-d", help="JSON data to send as request body"),
    ] = None,
) -> None:
    """Call a deployed edge function via HTTP."""
    actx: AppContext = ctx.obj
    out = actx.output

    payload = None
    if data:
        try:
            payload = _json.loads(data)
        except _json.JSONDecodeError as exc:
            out.error(f"Invalid JSON data: {exc}")
            raise typer.Exit(1) from exc

    try:
        client = _get_client(actx)
        result = client.post(f"/functions/v1/{name}", json=payload)
        client.close()
    except APIError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    if isinstance(result, (dict, list)):
        typer.echo(_json.dumps(result, indent=2))
    else:
        typer.echo(str(result))


@app.command()
def secrets(ctx: typer.Context) -> None:
    """Show environment variables available to edge functions."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        docker = _get_docker(actx)
        result = docker.docker_exec(
            "functions",
            "env | sort",
        )
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    for line in result.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            if any(s in key.upper() for s in ("KEY", "SECRET", "PASSWORD", "TOKEN")):
                value = value[:4] + "****" if len(value) > 4 else "****"
            typer.echo(f"{key}={value}")
