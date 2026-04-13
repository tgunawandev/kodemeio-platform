from __future__ import annotations

import typer

from kctl_lib.ssh import scp_download

from kctl_mm.core.callbacks import AppContext

app = typer.Typer(help="Mattermost server config (REST + mmctl).", no_args_is_help=True)


def _c(ctx: typer.Context) -> AppContext:
    return ctx.ensure_object(AppContext)


@app.command("show")
def show_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.get_config())


@app.command("get")
def get_cmd(ctx: typer.Context, key: str) -> None:
    c = _c(ctx)
    cfg = c.client.get_config()
    value: object = cfg
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise typer.BadParameter(f"Key not found: {key}")
        value = value[part]
    typer.echo(str(value))


@app.command("set")
def set_cmd(ctx: typer.Context, key: str, value: str) -> None:
    c = _c(ctx)
    r = c.mm_exec.mmctl(["config", "set", key, value])
    typer.echo(r.stdout)


@app.command("export")
def export_cmd(ctx: typer.Context, local_path: str) -> None:
    c = _c(ctx)
    remote = "/tmp/mm-config.json"
    c.mm_exec.mmctl(["config", "export", remote])
    settings = c.settings
    scp_download(
        str(settings["ssh_host"]),
        remote,
        local_path,
        user=str(settings.get("ssh_user", "root")),
    )
    typer.echo(local_path)


@app.command("test-email")
def test_email_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    r = c.mm_exec.mmctl(["config", "test-email"])
    typer.echo(r.stdout)


@app.command("reload")
def reload_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    r = c.mm_exec.mmctl(["config", "reload"])
    typer.echo(r.stdout)
