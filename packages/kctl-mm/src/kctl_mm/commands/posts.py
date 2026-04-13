from __future__ import annotations

import typer

from kctl_mm.core.callbacks import AppContext

app = typer.Typer(help="Post management.", no_args_is_help=True)


def _c(ctx: typer.Context) -> AppContext:
    return ctx.ensure_object(AppContext)


@app.command("create")
def create_cmd(ctx: typer.Context, channel_id: str, message: str) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.create_post(channel_id, message))


@app.command("get")
def get_cmd(ctx: typer.Context, post_id: str) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.get_post(post_id))


@app.command("delete")
def delete_cmd(ctx: typer.Context, post_id: str) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.delete_post(post_id))


@app.command("pin")
def pin_cmd(ctx: typer.Context, post_id: str) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.pin_post(post_id))


@app.command("unpin")
def unpin_cmd(ctx: typer.Context, post_id: str) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.unpin_post(post_id))


@app.command("search")
def search_cmd(ctx: typer.Context, team_id: str, terms: str) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.search_posts(team_id, terms))
