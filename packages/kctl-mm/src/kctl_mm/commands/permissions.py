from __future__ import annotations

import typer

from kctl_mm.core.callbacks import AppContext

app = typer.Typer(help="Permissions & role management (mmctl).", no_args_is_help=True)

# Well-known Mattermost built-in roles. `mmctl` does not expose a
# `permissions list` subcommand in modern versions, so we surface this
# curated list for discoverability.
WELL_KNOWN_ROLES = [
    "system_admin",
    "system_user",
    "team_admin",
    "team_user",
    "channel_admin",
    "channel_user",
]


def _c(ctx: typer.Context) -> AppContext:
    return ctx.ensure_object(AppContext)


@app.command("list")
def list_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    c.output.raw_json(WELL_KNOWN_ROLES)


@app.command("get")
def get_cmd(ctx: typer.Context, role: str) -> None:
    c = _c(ctx)
    c.output.raw_json(c.mm_exec.mmctl_json(["roles", "show", role]))


@app.command("add")
def add_cmd(ctx: typer.Context, role: str, perm: str) -> None:
    c = _c(ctx)
    r = c.mm_exec.mmctl(["permissions", "add", role, perm])
    typer.echo(r.stdout)


@app.command("remove")
def remove_cmd(ctx: typer.Context, role: str, perm: str) -> None:
    c = _c(ctx)
    r = c.mm_exec.mmctl(["permissions", "remove", role, perm])
    typer.echo(r.stdout)


@app.command("assign")
def assign_cmd(ctx: typer.Context, role: str, user: str) -> None:
    c = _c(ctx)
    r = c.mm_exec.mmctl(["permissions", "role-assign", role, user])
    typer.echo(r.stdout)
