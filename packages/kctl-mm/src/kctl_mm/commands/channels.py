from __future__ import annotations

import typer

from kctl_mm.core.callbacks import AppContext

app = typer.Typer(help="Channel management.", no_args_is_help=True)


def _c(ctx: typer.Context) -> AppContext:
    return ctx.ensure_object(AppContext)


@app.command("list")
def list_cmd(ctx: typer.Context, team_name: str) -> None:
    c = _c(ctx)
    team = c.client.get_team_by_name(team_name)
    channels = c.client.list_channels_for_team(team["id"])
    rows = [[ch.get("id", ""), ch.get("name", ""), ch.get("display_name", ""), ch.get("type", "")] for ch in channels]
    c.output.table(
        "Channels",
        [("ID", "dim"), ("Name", "cyan"), ("Display", "green"), ("Type", "yellow")],
        rows,
        data_for_json=channels,
    )


@app.command("get")
def get_cmd(ctx: typer.Context, team_name: str, channel_name: str) -> None:
    c = _c(ctx)
    team = c.client.get_team_by_name(team_name)
    c.output.raw_json(c.client.get_channel_by_name(team["id"], channel_name))


@app.command("create")
def create_cmd(
    ctx: typer.Context,
    team_name: str,
    channel_name: str,
    display: str,
    private: bool = typer.Option(False, "--private"),
) -> None:
    c = _c(ctx)
    team = c.client.get_team_by_name(team_name)
    c.output.raw_json(c.client.create_channel(team["id"], channel_name, display, private=private))


@app.command("archive")
def archive_cmd(ctx: typer.Context, team_name: str, channel_name: str) -> None:
    r = _c(ctx).mm_exec.mmctl(["channel", "archive", f"{team_name}:{channel_name}"])
    typer.echo(r.stdout)


@app.command("members")
def members_cmd(ctx: typer.Context, team_name: str, channel_name: str) -> None:
    c = _c(ctx)
    team = c.client.get_team_by_name(team_name)
    channel = c.client.get_channel_by_name(team["id"], channel_name)
    c.output.raw_json(c.client.list_channel_members(channel["id"]))


@app.command("add")
def add_cmd(ctx: typer.Context, team_name: str, channel_name: str, user: str) -> None:
    r = _c(ctx).mm_exec.mmctl(["channel", "users", "add", f"{team_name}:{channel_name}", user])
    typer.echo(r.stdout)


@app.command("remove")
def remove_cmd(ctx: typer.Context, team_name: str, channel_name: str, user: str) -> None:
    r = _c(ctx).mm_exec.mmctl(["channel", "users", "remove", f"{team_name}:{channel_name}", user])
    typer.echo(r.stdout)


@app.command("rename")
def rename_cmd(ctx: typer.Context, team_name: str, channel_name: str, new_display: str) -> None:
    c = _c(ctx)
    team = c.client.get_team_by_name(team_name)
    channel = c.client.get_channel_by_name(team["id"], channel_name)
    c.output.raw_json(c.client.rename_channel(channel["id"], new_display))
