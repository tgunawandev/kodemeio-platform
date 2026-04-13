from __future__ import annotations

import typer

from kctl_mm.core.callbacks import AppContext

app = typer.Typer(help="Team management.", no_args_is_help=True)


def _c(ctx: typer.Context) -> AppContext:
    return ctx.ensure_object(AppContext)


@app.command("list")
def list_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    teams = c.client.list_teams()
    rows = [[t.get("id", ""), t.get("name", ""), t.get("display_name", ""), t.get("type", "")] for t in teams]
    c.output.table(
        "Teams",
        [("ID", "dim"), ("Name", "cyan"), ("Display", "green"), ("Type", "yellow")],
        rows,
        data_for_json=teams,
    )


@app.command("get")
def get_cmd(ctx: typer.Context, team_name: str) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.get_team_by_name(team_name))


@app.command("create")
def create_cmd(ctx: typer.Context, name: str, display: str) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.create_team(name, display))


@app.command("archive")
def archive_cmd(ctx: typer.Context, team_name: str) -> None:
    r = _c(ctx).mm_exec.mmctl(["team", "archive", team_name])
    typer.echo(r.stdout)


@app.command("members")
def members_cmd(ctx: typer.Context, team_name: str) -> None:
    c = _c(ctx)
    team = c.client.get_team_by_name(team_name)
    c.output.raw_json(c.client.list_team_members(team["id"]))


@app.command("add")
def add_cmd(ctx: typer.Context, team_name: str, user: str) -> None:
    r = _c(ctx).mm_exec.mmctl(["team", "users", "add", team_name, user])
    typer.echo(r.stdout)


@app.command("remove")
def remove_cmd(ctx: typer.Context, team_name: str, user: str) -> None:
    r = _c(ctx).mm_exec.mmctl(["team", "users", "remove", team_name, user])
    typer.echo(r.stdout)


@app.command("delete")
def delete_cmd(
    ctx: typer.Context,
    team_name: str,
    confirm: bool = typer.Option(False, "--confirm"),
) -> None:
    if not confirm:
        typer.echo("--confirm is required to delete a team")
        raise typer.Exit(code=1)
    r = _c(ctx).mm_exec.mmctl(["team", "delete", team_name, "--confirm"])
    typer.echo(r.stdout)
