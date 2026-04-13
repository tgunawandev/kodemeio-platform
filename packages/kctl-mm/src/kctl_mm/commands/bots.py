from __future__ import annotations

import typer

from kctl_mm.core.callbacks import AppContext

app = typer.Typer(help="Bot management.", no_args_is_help=True)


def _c(ctx: typer.Context) -> AppContext:
    return ctx.ensure_object(AppContext)


@app.command("list")
def list_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    bots = c.client.list_bots()
    rows = [[b.get("user_id", ""), b.get("username", ""), b.get("display_name", "")] for b in bots]
    c.output.table(
        "Bots",
        [("ID", "dim"), ("Username", "cyan"), ("Display", "green")],
        rows,
        data_for_json=bots,
    )


@app.command("create")
def create_cmd(ctx: typer.Context, username: str, display: str) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.create_bot(username, display))


@app.command("enable")
def enable_cmd(ctx: typer.Context, bot_id: str) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.enable_bot(bot_id))


@app.command("disable")
def disable_cmd(ctx: typer.Context, bot_id: str) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.disable_bot(bot_id))


@app.command("delete")
def delete_cmd(ctx: typer.Context, bot_id: str) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.delete_bot(bot_id))
