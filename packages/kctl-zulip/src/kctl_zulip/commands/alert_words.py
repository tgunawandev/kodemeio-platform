"""Alert words management commands."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from kctl_zulip.core.callbacks import AppContext

app = typer.Typer(help="Alert words management.")


@app.command("list")
def list_(
    ctx: typer.Context,
) -> None:
    """List your alert words."""
    c: AppContext = ctx.obj
    data = c.client.get("users/me/alert_words")
    words = data.get("alert_words", [])

    rows = [[w] for w in words]

    c.output.table(
        f"Alert Words ({len(words)})",
        [("Word", "cyan")],
        rows,
        data_for_json=words,
    )


@app.command()
def add(
    ctx: typer.Context,
    words: Annotated[list[str], typer.Argument(help="Words to add as alert words")],
) -> None:
    """Add alert words."""
    c: AppContext = ctx.obj
    result = c.client.post("users/me/alert_words", data={"alert_words": json.dumps(words)})
    all_words = result.get("alert_words", [])
    c.output.success(f"Alert words added. Total: {len(all_words)}")


@app.command()
def remove(
    ctx: typer.Context,
    words: Annotated[list[str], typer.Argument(help="Words to remove from alert words")],
) -> None:
    """Remove alert words."""
    c: AppContext = ctx.obj
    c.client.request("DELETE", "users/me/alert_words", data={"alert_words": json.dumps(words)})
    c.output.success(f"Alert words removed: {', '.join(words)}")
