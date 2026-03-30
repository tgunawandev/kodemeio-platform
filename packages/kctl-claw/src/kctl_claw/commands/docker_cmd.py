"""Docker management commands."""

from __future__ import annotations

import subprocess
from typing import Annotated

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.exceptions import DockerError

app = typer.Typer(help="Docker container management for OpenClaw services.")


@app.command("ps")
def ps(ctx: typer.Context) -> None:
    """List running containers for the OpenClaw project."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        output = actx.docker.ps()
        typer.echo(output)
    except DockerError as e:
        out.error(f"Docker error: {e}")
        out.info("Is Docker running?")
        raise typer.Exit(1) from e


@app.command()
def logs(
    ctx: typer.Context,
    service: Annotated[str, typer.Argument(help="Service name (e.g. openclaw)")] = "openclaw",
    tail: Annotated[int, typer.Option("--tail", "-n", help="Number of lines to show")] = 100,
) -> None:
    """Show container logs for a service."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info(f"Logs for service {service!r} (tail={tail})...")
    try:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(actx.project_root / "docker-compose.prod.yml"),
                "logs",
                f"--tail={tail}",
                service,
            ],
            capture_output=False,
            check=False,
            timeout=30,
        )
        if result.returncode != 0:
            out.error("docker compose logs returned non-zero exit code")
    except subprocess.TimeoutExpired as err:
        out.error("Timed out waiting for docker logs.")
        raise typer.Exit(1) from err
    except FileNotFoundError as err:
        out.error("docker not found in PATH.")
        raise typer.Exit(1) from err


@app.command()
def restart(
    ctx: typer.Context,
    service: Annotated[str, typer.Argument(help="Service name to restart (default: all)")] = "",
) -> None:
    """Restart a specific Docker service or all services."""
    actx: AppContext = ctx.obj
    out = actx.output

    if service:
        out.info(f"Restarting service {service!r}...")
    else:
        out.info("Restarting all services...")

    try:
        actx.docker.restart()
        out.success("Restart complete.")
    except DockerError as e:
        out.error(f"Docker error: {e}")
        raise typer.Exit(1) from e


@app.command("run-cmd")
def run_cmd(
    ctx: typer.Context,
    service: Annotated[str, typer.Argument(help="Service name")],
    cmd: Annotated[str, typer.Argument(help="Command to run (quoted, e.g. 'ls /opt')")],
) -> None:
    """Execute a command in a running container (safe: uses parameterized args)."""
    actx: AppContext = ctx.obj
    out = actx.output

    # Split the command into args (user-supplied, non-shell)
    cmd_parts = cmd.split()
    out.info(f"Executing in {service!r}: {cmd_parts}")

    try:
        base_args = [
            "docker",
            "compose",
            "-f",
            str(actx.project_root / "docker-compose.prod.yml"),
            "run",
            "--rm",
            service,
        ] + cmd_parts
        result = subprocess.run(
            base_args,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if result.stdout:
            typer.echo(result.stdout)
        if result.returncode != 0:
            out.error(result.stderr[:200] if result.stderr else "Command failed")
            raise typer.Exit(result.returncode)
    except subprocess.TimeoutExpired as err:
        out.error("Command timed out.")
        raise typer.Exit(1) from err
    except FileNotFoundError as err:
        out.error("docker not found in PATH.")
        raise typer.Exit(1) from err


@app.command("resource-usage")
def resource_usage(ctx: typer.Context) -> None:
    """Show CPU and memory resource usage for OpenClaw containers."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Fetching resource usage via docker stats...")

    try:
        ps_result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(actx.project_root / "docker-compose.prod.yml"),
                "ps",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        container_names: list[str] = []
        if ps_result.returncode == 0 and ps_result.stdout:
            import json

            for line in ps_result.stdout.strip().splitlines():
                try:
                    entry = json.loads(line)
                    name = entry.get("Name") or entry.get("name", "")
                    if name:
                        container_names.append(name)
                except (json.JSONDecodeError, AttributeError):
                    pass

        if not container_names:
            out.warn("No running containers found.")
            return

        stats_args = [
            "docker",
            "stats",
            "--no-stream",
            "--format",
            "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}",
        ] + container_names

        stats_result = subprocess.run(
            stats_args,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        if stats_result.stdout:
            typer.echo(stats_result.stdout)
        else:
            out.warn("No stats output. Containers may not be running.")
    except subprocess.TimeoutExpired as err:
        out.error("docker stats timed out.")
        raise typer.Exit(1) from err
    except FileNotFoundError as err:
        out.error("docker not found in PATH.")
        raise typer.Exit(1) from err
