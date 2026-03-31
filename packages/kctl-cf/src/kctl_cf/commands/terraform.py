"""Terraform wrapper commands for Cloudflare infrastructure."""

from __future__ import annotations

import getpass
import subprocess
from typing import Annotated

import typer

from kctl_cf.core.callbacks import AppContext
from kctl_cf.core.config import get_service_config, resolve_active_profile_name
from kctl_cf.core.notify import notify_terraform

app = typer.Typer(help="Run Terraform commands for Cloudflare infrastructure.")


def _get_terraform_dir(c: AppContext) -> str:
    """Resolve terraform working directory from profile config."""
    svc = get_service_config(resolve_active_profile_name(c.profile))
    terraform_dir = svc.terraform_dir or "."
    return terraform_dir


def _run_terraform(c: AppContext, args: list[str]) -> None:
    """Execute a terraform command in the configured directory."""
    terraform_dir = _get_terraform_dir(c)
    cmd = ["terraform", *args]
    c.output.info(f"Running: {' '.join(cmd)} (cwd: {terraform_dir})")
    try:
        subprocess.run(cmd, cwd=terraform_dir, check=True)  # noqa: S603, S607
    except FileNotFoundError as exc:
        c.output.error("terraform binary not found. Install: https://developer.hashicorp.com/terraform/install")
        raise typer.Exit(1) from exc
    except subprocess.CalledProcessError as e:
        c.output.error(f"terraform exited with code {e.returncode}")
        raise typer.Exit(e.returncode) from e


@app.command()
def init(ctx: typer.Context) -> None:
    """Initialize Terraform working directory."""
    c: AppContext = ctx.obj
    _run_terraform(c, ["init"])


@app.command()
def plan(ctx: typer.Context) -> None:
    """Show Terraform execution plan."""
    c: AppContext = ctx.obj
    _run_terraform(c, ["plan"])


@app.command()
def apply(
    ctx: typer.Context,
    auto_approve: Annotated[bool, typer.Option("--auto-approve", help="Skip interactive approval")] = False,
    notify: Annotated[bool, typer.Option("--notify", "-n", help="Send webhook notification on completion")] = False,
) -> None:
    """Apply Terraform changes."""
    c: AppContext = ctx.obj
    args = ["apply"]
    if auto_approve:
        args.append("-auto-approve")
    try:
        _run_terraform(c, args)
        if notify:
            notify_terraform("apply", success=True, user=getpass.getuser())
    except (typer.Exit, SystemExit):
        if notify:
            notify_terraform("apply", success=False, user=getpass.getuser())
        raise


@app.command()
def destroy(
    ctx: typer.Context,
    auto_approve: Annotated[bool, typer.Option("--auto-approve", help="Skip interactive approval")] = False,
    notify: Annotated[bool, typer.Option("--notify", "-n", help="Send webhook notification on completion")] = False,
) -> None:
    """Destroy Terraform-managed infrastructure."""
    c: AppContext = ctx.obj
    args = ["destroy"]
    if auto_approve:
        args.append("-auto-approve")
    try:
        _run_terraform(c, args)
        if notify:
            notify_terraform("destroy", success=True, user=getpass.getuser())
    except (typer.Exit, SystemExit):
        if notify:
            notify_terraform("destroy", success=False, user=getpass.getuser())
        raise


@app.command()
def output(ctx: typer.Context) -> None:
    """Show Terraform outputs."""
    c: AppContext = ctx.obj
    _run_terraform(c, ["output"])


@app.command()
def validate(ctx: typer.Context) -> None:
    """Validate Terraform configuration."""
    c: AppContext = ctx.obj
    _run_terraform(c, ["validate"])
