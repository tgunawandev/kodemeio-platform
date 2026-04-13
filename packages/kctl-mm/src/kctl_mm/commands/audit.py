from __future__ import annotations

import typer

from kctl_mm.core.callbacks import AppContext

app = typer.Typer(help="Audit & compliance reports.", no_args_is_help=True)


def _c(ctx: typer.Context) -> AppContext:
    return ctx.ensure_object(AppContext)


@app.command("login")
def login_cmd(ctx: typer.Context, username: str) -> None:
    c = _c(ctx)
    user = c.client.get_user_by_username(username)
    user_id = user["id"] if isinstance(user, dict) else user
    c.output.raw_json(c.client.list_user_audits(user_id))


@app.command("security")
def security_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.list_compliance_reports())


@app.command("compliance")
def compliance_cmd(
    ctx: typer.Context,
    report_id: str,
    out: str = typer.Option(..., "--out", help="Local path to save report."),
) -> None:
    c = _c(ctx)
    path = c.client.download_compliance_report(report_id, out)
    typer.echo(path)
