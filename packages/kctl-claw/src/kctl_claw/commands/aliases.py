"""Short aliases for common commands."""

from __future__ import annotations

import subprocess
import sys

import typer


def _get_base_cmd(ctx: typer.Context) -> list[str]:
    """Reconstruct the base kctl-claw command with global options."""
    cmd = [sys.executable, "-m", "kctl_claw"]
    parent_params = ctx.parent.params if ctx.parent else {}
    if parent_params.get("json_output"):
        cmd.append("--json")
    if parent_params.get("quiet"):
        cmd.append("--quiet")
    if parent_params.get("output_format") and parent_params["output_format"] != "pretty":
        cmd.extend(["--format", parent_params["output_format"]])
    if parent_params.get("profile"):
        cmd.extend(["--profile", parent_params["profile"]])
    if parent_params.get("root"):
        cmd.extend(["--root", parent_params["root"]])
    if parent_params.get("live"):
        cmd.append("--live")
    return cmd


def register_aliases(main_app: typer.Typer) -> None:
    """Register short aliases as hidden commands."""

    @main_app.command("st", hidden=True, help="Alias: status overview")
    def st(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "status", "overview"]))

    @main_app.command("hl", hidden=True, help="Alias: health check")
    def hl(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "health", "check"]))

    @main_app.command("cl", hidden=True, help="Alias: cron list")
    def cl(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "cron", "list"]))

    @main_app.command("al", hidden=True, help="Alias: agents list")
    def al(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "agents", "list"]))

    @main_app.command("ml", hidden=True, help="Alias: mcp list")
    def ml(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "mcp", "list"]))

    @main_app.command("lt", hidden=True, help="Alias: logs tail")
    def lt(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "logs", "tail"]))

    @main_app.command("bc", hidden=True, help="Alias: backup create")
    def bc(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "backup", "create"]))

    @main_app.command("du", hidden=True, help="Alias: deploy up")
    def du(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "deploy", "up"]))
