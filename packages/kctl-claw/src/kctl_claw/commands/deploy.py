"""Deployment commands."""

from __future__ import annotations

import glob
import json
import shutil
from typing import Annotated

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.config_manager import ConfigFile
from kctl_claw.core.exceptions import DockerError, GatewayError

_GATEWAY_HINT = "Start the gateway first: kctl-claw deploy up"

app = typer.Typer(help="Deploy and manage the OpenClaw gateway container.")


@app.command()
def up(
    ctx: typer.Context,
    build: Annotated[bool, typer.Option("--build", help="Rebuild image before starting")] = True,
) -> None:
    """Build and start the gateway."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Starting gateway..." + (" (with build)" if build else ""))
    try:
        actx.docker.up(build=build)
        out.success("Gateway started successfully.")
    except DockerError as e:
        out.error(f"Docker error: {e}")
        raise typer.Exit(1) from e


@app.command()
def down(ctx: typer.Context) -> None:
    """Stop and remove gateway services (requires confirmation)."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.warn("This will stop and remove all gateway containers.")
    confirmation = typer.prompt("Type 'STOP' to confirm")
    if confirmation != "STOP":
        out.info("Aborted.")
        return

    try:
        actx.docker.down()
        out.success("Gateway stopped.")
    except DockerError as e:
        out.error(f"Docker error: {e}")
        raise typer.Exit(1) from e


@app.command()
def restart(ctx: typer.Context) -> None:
    """Restart the gateway service."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Restarting gateway...")
    try:
        actx.docker.restart()
        out.success("Gateway restarted successfully.")
    except DockerError as e:
        out.error(f"Docker error: {e}")
        out.info("Is Docker running? Check with: docker ps")
        raise typer.Exit(1) from e


@app.command()
def pull(ctx: typer.Context) -> None:
    """Pull the latest gateway image."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Pulling latest image...")
    try:
        actx.docker.pull()
        out.success("Image pulled successfully. Run 'kctl-claw deploy up' to apply.")
    except DockerError as e:
        out.error(f"Docker error: {e}")
        raise typer.Exit(1) from e


@app.command()
def status(ctx: typer.Context) -> None:
    """Show container status."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        output = actx.docker.ps()
        typer.echo(output)
    except DockerError as e:
        out.error(f"Docker error: {e}")
        out.info("Is Docker running?")
        raise typer.Exit(1) from e


def _read_deployed_config(actx: AppContext) -> dict | None:
    """Read openclaw.json from running container."""
    try:
        # Use docker client to read file from container (parameterized, no shell injection)
        raw = actx.docker.exec("openclaw", ["cat", "/opt/openclaw-config/openclaw.json"])
        return json.loads(raw)
    except Exception:
        return None


@app.command()
def diff(ctx: typer.Context) -> None:
    """Show config diff between local and deployed container config."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Comparing local config to deployed container config...")
    try:
        actx.config_mgr.read(ConfigFile.OPENCLAW)
    except FileNotFoundError as e:
        out.error(f"Local config not found: {e}")
        raise typer.Exit(1) from e

    remote_data = _read_deployed_config(actx)
    if remote_data is None:
        out.warn("Cannot read container config. Is the container running?")
        out.info("Start with: kctl-claw deploy up")
        return

    diffs = actx.config_mgr.diff(ConfigFile.OPENCLAW, remote_data)
    if not diffs:
        out.success("No diff — local and deployed configs are identical.")
        return

    rows = [[d.path, str(d.local_value)[:50], str(d.remote_value)[:50]] for d in diffs]
    json_data = [{"path": d.path, "local": d.local_value, "remote": d.remote_value} for d in diffs]
    out.table(
        f"Deploy Diff ({len(diffs)} differences)",
        [("Path", "cyan"), ("Local", "green"), ("Deployed", "red")],
        rows,
        data_for_json=json_data,
    )
    out.info("To deploy local changes: kctl-claw deploy up --build")


@app.command()
def rollback(ctx: typer.Context) -> None:
    """Rollback to the previous deployment (restore latest backup config)."""
    actx: AppContext = ctx.obj
    out = actx.output

    config_path = actx.project_root / ConfigFile.OPENCLAW.value
    bak_pattern = str(config_path.with_name(f"{config_path.stem}.bak.*{config_path.suffix}"))
    backups = sorted(glob.glob(bak_pattern), reverse=True)

    if not backups:
        out.error("No backup configs found. Cannot rollback.")
        out.info("Backups are created automatically before config modifications.")
        raise typer.Exit(1)

    latest_bak = backups[0]
    out.info(f"Rolling back to: {latest_bak}")
    out.warn("This will replace local openclaw.json with the backup, then redeploy.")
    confirmed = typer.confirm("Proceed with rollback?")
    if not confirmed:
        out.info("Aborted.")
        return

    shutil.copy2(latest_bak, config_path)
    out.success(f"Restored openclaw.json from backup: {latest_bak}")

    out.info("Redeploying with rolled-back config...")
    try:
        actx.docker.up(build=True)
        out.success("Rollback complete — gateway redeployed.")
    except DockerError as e:
        out.error(f"Docker error during rollback deploy: {e}")
        raise typer.Exit(1) from e


@app.command()
def canary(
    ctx: typer.Context,
    bot: Annotated[str, typer.Argument(help="Bot name to deploy to first")],
) -> None:
    """Deploy to a single bot first (canary deployment)."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info(f"Canary deployment — targeting bot {bot!r} first...")

    # Validate config
    errors = actx.config_mgr.validate_json(ConfigFile.OPENCLAW)
    if errors:
        for err in errors:
            out.error(f"  Config error: {err}")
        raise typer.Exit(1)

    out.success("Config validated.")
    out.info(f"Deploying canary to bot {bot!r}...")

    try:
        data = actx.gateway.post("/api/deploy/canary", {"bot": bot})
        if isinstance(data, dict):
            out.success(f"Canary deployed to {bot!r}: {data.get('status', 'ok')}")
            out.info("Monitor with: kctl-claw telegram webhook-status " + bot)
            out.info("Then promote with: kctl-claw deploy up --build")
        else:
            out.success(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)
        out.info("For manual canary: deploy to staging, test, then full deploy.")
