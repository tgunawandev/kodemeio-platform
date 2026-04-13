from __future__ import annotations

import os

import typer

from kctl_lib.ssh import scp_upload

from kctl_mm.core.callbacks import AppContext

app = typer.Typer(help="Plugin management (mmctl).", no_args_is_help=True)


def _c(ctx: typer.Context) -> AppContext:
    return ctx.ensure_object(AppContext)


@app.command("list")
def list_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    c.output.raw_json(c.mm_exec.mmctl_json(["plugin", "list"]))


@app.command("install")
def install_cmd(ctx: typer.Context, local_path: str) -> None:
    c = _c(ctx)
    settings = c.settings
    remote_path = f"/tmp/{os.path.basename(local_path)}"
    scp_upload(
        str(settings["ssh_host"]),
        local_path,
        remote_path,
        user=str(settings.get("ssh_user", "root")),
    )
    r = c.mm_exec.mmctl(["plugin", "install", remote_path])
    typer.echo(r.stdout)


@app.command("enable")
def enable_cmd(ctx: typer.Context, plugin_id: str) -> None:
    c = _c(ctx)
    r = c.mm_exec.mmctl(["plugin", "enable", plugin_id])
    typer.echo(r.stdout)


@app.command("disable")
def disable_cmd(ctx: typer.Context, plugin_id: str) -> None:
    c = _c(ctx)
    r = c.mm_exec.mmctl(["plugin", "disable", plugin_id])
    typer.echo(r.stdout)


@app.command("delete")
def delete_cmd(ctx: typer.Context, plugin_id: str) -> None:
    c = _c(ctx)
    r = c.mm_exec.mmctl(["plugin", "delete", plugin_id])
    typer.echo(r.stdout)
