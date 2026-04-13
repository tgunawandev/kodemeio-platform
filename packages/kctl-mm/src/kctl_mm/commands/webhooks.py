from __future__ import annotations

import typer

from kctl_mm.core.callbacks import AppContext

app = typer.Typer(help="Webhook management.", no_args_is_help=True)


def _c(ctx: typer.Context) -> AppContext:
    return ctx.ensure_object(AppContext)


@app.command("list")
def list_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    c.output.raw_json(
        {
            "incoming": c.client.list_incoming_hooks(),
            "outgoing": c.client.list_outgoing_hooks(),
        }
    )


@app.command("list-incoming")
def list_incoming_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.list_incoming_hooks())


@app.command("list-outgoing")
def list_outgoing_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.list_outgoing_hooks())


@app.command("create-incoming")
def create_incoming_cmd(ctx: typer.Context, channel_id: str, display: str) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.create_incoming_hook(channel_id, display))


@app.command("create-outgoing")
def create_outgoing_cmd(ctx: typer.Context, team_id: str, trigger: str) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.create_outgoing_hook(team_id, [trigger]))


@app.command("delete-incoming")
def delete_incoming_cmd(ctx: typer.Context, hook_id: str) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.delete_incoming_hook(hook_id))


@app.command("delete-outgoing")
def delete_outgoing_cmd(ctx: typer.Context, hook_id: str) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.delete_outgoing_hook(hook_id))
