from __future__ import annotations

import typer

from kctl_mm.core.callbacks import AppContext

app = typer.Typer(help="OAuth / LDAP / SAML integrations (mmctl).", no_args_is_help=True)


def _c(ctx: typer.Context) -> AppContext:
    return ctx.ensure_object(AppContext)


@app.command("oauth-list")
def oauth_list_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    c.output.raw_json(c.mm_exec.mmctl_json(["oauth", "list-apps"]))


@app.command("oauth-create")
def oauth_create_cmd(ctx: typer.Context, name: str, callback_url: str) -> None:
    c = _c(ctx)
    r = c.mm_exec.mmctl(["oauth", "create-app", name, callback_url])
    typer.echo(r.stdout)


@app.command("oauth-delete")
def oauth_delete_cmd(ctx: typer.Context, oauth_id: str) -> None:
    c = _c(ctx)
    r = c.mm_exec.mmctl(["oauth", "delete-app", oauth_id])
    typer.echo(r.stdout)


@app.command("ldap-sync")
def ldap_sync_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    r = c.mm_exec.mmctl(["ldap", "sync"])
    typer.echo(r.stdout)


@app.command("ldap-test")
def ldap_test_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    r = c.mm_exec.mmctl(["ldap", "check"])
    typer.echo(r.stdout)
