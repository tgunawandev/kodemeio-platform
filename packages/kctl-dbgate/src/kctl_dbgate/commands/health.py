"""Health and monitoring commands."""

from __future__ import annotations

import subprocess

import typer
from kctl_lib.exceptions import KctlError

from kctl_dbgate.core.callbacks import AppContext

app = typer.Typer(help="Health checks and monitoring.")


def _container_status(name: str) -> str:
    """Get Docker container health status."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "not_running"
    except Exception:
        return "unknown"


@app.command("check")
def health_check(ctx: typer.Context) -> None:
    """HTTP + auth + container health."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.header("DBGate Health Check")

    try:
        c = actx.client
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    # Public HTTP root
    try:
        status = c.ping()
        if status < 400:
            out.success(f"HTTP /: {status}")
        else:
            out.error(f"HTTP /: {status}")
    except KctlError as e:
        out.error(f"HTTP /: {e}")

    # Auth
    try:
        c.login()
        out.success("Auth: logged in")
    except KctlError as e:
        out.error(f"Auth: {e}")

    # Container status
    status = _container_status("kodemeio-dbgate-dbgate-1")
    if status == "healthy":
        out.success(f"Container: {status}")
    elif status in ("starting", "running"):
        out.info(f"Container: {status}")
    else:
        out.warn(f"Container: {status}")
