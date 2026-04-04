"""Rate limit management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext

app = typer.Typer(help="Manage rate limits.")


@app.command()
def get(
    ctx: typer.Context,
    mailbox: Annotated[str, typer.Argument(help="Mailbox email address")],
) -> None:
    """Get rate limit for a mailbox."""
    c: AppContext = ctx.obj
    data = c.client.mc_get(f"rl-mbox/{mailbox}")

    if isinstance(data, dict):
        item = data
    elif isinstance(data, list) and data:
        item = data[0] if isinstance(data[0], dict) else {"value": data}
    else:
        c.output.info(f"No rate limit set for {mailbox}")
        if c.json_mode:
            c.output.raw_json({})
        return

    sections = [
        (
            "Rate Limit",
            [
                ("Mailbox", mailbox),
                ("Frame", str(item.get("frame", ""))),
                ("Value", str(item.get("value", ""))),
            ],
        )
    ]

    c.output.detail(f"Rate Limit: {mailbox}", sections, data_for_json=item)


@app.command("set")
def set_(
    ctx: typer.Context,
    mailbox: Annotated[str, typer.Argument(help="Mailbox email address")],
    value: Annotated[str, typer.Argument(help="Rate limit value (e.g. '10' for 10 msgs per frame)")],
    frame: Annotated[str, typer.Option("--frame", "-f", help="Time frame (e.g. 's', 'm', 'h', 'd')")] = "h",
) -> None:
    """Set rate limit for a mailbox."""
    c: AppContext = ctx.obj
    payload = {
        "items": [mailbox],
        "attr": {
            "rl_value": value,
            "rl_frame": frame,
        },
    }
    result = c.client.mc_edit("rl-mbox", payload)

    if isinstance(result, list):
        errors = [r for r in result if isinstance(r, dict) and r.get("type") == "danger"]
        if errors:
            for e in errors:
                c.output.error(str(e.get("msg", e)))
            raise typer.Exit(1)

    c.output.success(f"Rate limit for {mailbox} set to {value}/{frame}")
    if c.json_mode:
        c.output.raw_json(result)
