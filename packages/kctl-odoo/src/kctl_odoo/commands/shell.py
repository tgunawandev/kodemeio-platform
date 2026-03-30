"""Shell command — execute arbitrary ORM calls."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext

app = typer.Typer(help="Execute ORM method calls.")


@app.command()
def call(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Model name (e.g. res.partner)")],
    method: Annotated[str, typer.Argument(help="Method name (e.g. search_read)")],
    args: Annotated[str | None, typer.Argument(help="JSON-encoded positional args")] = None,
    kwargs: Annotated[str | None, typer.Option("--kwargs", "-k", help="JSON-encoded keyword args")] = None,
) -> None:
    """Execute an ORM method on a model.

    Examples:
      kctl-odoo shell call res.partner search_read '[[["is_company","=",true]]]' -k '{"fields":["name"],"limit":5}'
      kctl-odoo shell call res.users search_count '[[]]'
      kctl-odoo shell call ir.module.module fields_get '[]' -k '{"attributes":["string","type"]}'
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    parsed_args: list = []
    if args:
        try:
            parsed_args = json.loads(args)
        except json.JSONDecodeError as e:
            out.error(f"Invalid JSON for args: {e}")
            raise typer.Exit(1) from e

    parsed_kwargs: dict = {}
    if kwargs:
        try:
            parsed_kwargs = json.loads(kwargs)
        except json.JSONDecodeError as e:
            out.error(f"Invalid JSON for kwargs: {e}")
            raise typer.Exit(1) from e

    result = c.execute_kw(model, method, parsed_args, parsed_kwargs)
    out.raw_json(result)
