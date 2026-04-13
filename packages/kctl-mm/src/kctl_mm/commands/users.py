from __future__ import annotations

import typer

from kctl_mm.core.callbacks import AppContext

app = typer.Typer(help="User management.", no_args_is_help=True)


def _c(ctx: typer.Context) -> AppContext:
    return ctx.ensure_object(AppContext)


@app.command("list")
def list_cmd(
    ctx: typer.Context,
    page: int = typer.Option(0, "--page"),
    per_page: int = typer.Option(60, "--per-page"),
) -> None:
    c = _c(ctx)
    users = c.client.list_users(page, per_page)
    rows = [
        [
            u.get("id", ""),
            u.get("username", ""),
            u.get("email", ""),
            u.get("roles", ""),
        ]
        for u in users
    ]
    c.output.table(
        "Users",
        [("ID", "dim"), ("Username", "cyan"), ("Email", "green"), ("Roles", "yellow")],
        rows,
        data_for_json=users,
    )


@app.command("get")
def get_cmd(ctx: typer.Context, username: str) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.get_user_by_username(username))


@app.command("create")
def create_cmd(
    ctx: typer.Context,
    email: str,
    username: str,
    password: str = typer.Option(..., "--password", prompt=True, hide_input=True),
) -> None:
    c = _c(ctx)
    result = c.client.create_user({"email": email, "username": username, "password": password})
    c.output.raw_json(result)


@app.command("activate")
def activate_cmd(ctx: typer.Context, username: str) -> None:
    c = _c(ctx)
    user = c.client.get_user_by_username(username)
    c.output.raw_json(c.client.update_user_active(user["id"], True))


@app.command("deactivate")
def deactivate_cmd(ctx: typer.Context, username: str) -> None:
    c = _c(ctx)
    user = c.client.get_user_by_username(username)
    c.output.raw_json(c.client.update_user_active(user["id"], False))


@app.command("reset-pwd")
def reset_pwd_cmd(ctx: typer.Context, username: str) -> None:
    r = _c(ctx).mm_exec.mmctl(["user", "reset-password", username])
    typer.echo(r.stdout)


@app.command("promote")
def promote_cmd(ctx: typer.Context, username: str) -> None:
    r = _c(ctx).mm_exec.mmctl(["user", "roles", "system_admin", username])
    typer.echo(r.stdout)


@app.command("demote")
def demote_cmd(ctx: typer.Context, username: str) -> None:
    r = _c(ctx).mm_exec.mmctl(["user", "roles", "system_user", username])
    typer.echo(r.stdout)


@app.command("search")
def search_cmd(ctx: typer.Context, query: str) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.post("/users/search", json={"term": query}))


@app.command("invite")
def invite_cmd(ctx: typer.Context, email: str, team: str) -> None:
    r = _c(ctx).mm_exec.mmctl(["user", "invite", email, team])
    typer.echo(r.stdout)
