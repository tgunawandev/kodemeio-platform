"""kctl-accurate auth — Accurate Online auth ops."""

from __future__ import annotations

import json

import typer

from kctl_accurate.core.callbacks import AppContext

app = typer.Typer(help="Accurate auth operations: token-info, refresh, logout.")


@app.command("token-info")
def token_info(ctx: typer.Context) -> None:
    """Show current API token info: user, database, host."""
    actx: AppContext = ctx.obj
    out = actx.output
    info = actx.client.token_info()

    if actx.json_mode:
        print(json.dumps(info, indent=2, ensure_ascii=False))
        return

    d = info.get("d", {})
    user = d.get("user") or {}
    db = d.get("database") or {}

    out.header("Accurate Token Info")
    out.kv("User", user.get("name", "[dim]—[/dim]"))
    out.kv("Email", user.get("email", "[dim]—[/dim]"))
    out.kv("DB ID", str(db.get("id", "[dim]—[/dim]")))
    out.kv("DB Alias", db.get("alias", "[dim]—[/dim]"))
    out.kv("Host", db.get("host", "[dim]—[/dim]"))


@app.command()
def refresh(ctx: typer.Context) -> None:
    """Refresh the current API session token."""
    actx: AppContext = ctx.obj
    out = actx.output
    result = actx.client.refresh_token()
    if actx.json_mode:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    out.success("Token refreshed")


@app.command()
def logout(ctx: typer.Context) -> None:
    """Invalidate the current API session."""
    actx: AppContext = ctx.obj
    out = actx.output
    result = actx.client.logout()
    if actx.json_mode:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    out.success("Logged out")
