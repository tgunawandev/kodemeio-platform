"""Global password policy management."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage global password policy.")


@app.command()
def get(ctx: typer.Context) -> None:
    """Show current password policy."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("passwordpolicy")
    item = data if isinstance(data, dict) else {}

    sections = [
        (
            "Password Policy",
            [
                ("Min Length", str(item.get("min_length", ""))),
                ("Min Uppercase", str(item.get("min_upper", ""))),
                ("Min Lowercase", str(item.get("min_lower", ""))),
                ("Min Digits", str(item.get("min_num", ""))),
                ("Min Special", str(item.get("min_special", ""))),
            ],
        )
    ]
    c.output.detail("Password Policy", sections, data_for_json=item)


@app.command("set")
def set_(
    ctx: typer.Context,
    min_length: Annotated[int | None, typer.Option("--min-length", help="Minimum password length")] = None,
    min_upper: Annotated[int | None, typer.Option("--min-upper", help="Minimum uppercase characters")] = None,
    min_lower: Annotated[int | None, typer.Option("--min-lower", help="Minimum lowercase characters")] = None,
    min_num: Annotated[int | None, typer.Option("--min-num", help="Minimum digits")] = None,
    min_special: Annotated[int | None, typer.Option("--min-special", help="Minimum special characters")] = None,
) -> None:
    """Set password policy rules."""
    c: AppContext = ctx.obj
    attr: dict = {}
    if min_length is not None:
        attr["min_length"] = min_length
    if min_upper is not None:
        attr["min_upper"] = min_upper
    if min_lower is not None:
        attr["min_lower"] = min_lower
    if min_num is not None:
        attr["min_num"] = min_num
    if min_special is not None:
        attr["min_special"] = min_special

    if not attr:
        c.output.warn("No fields to update")
        raise typer.Exit(0)

    # passwordpolicy is a singleton endpoint — no items key needed
    result = c.client.mc_edit("passwordpolicy", {"attr": attr})
    handle_result(c, result, "Password policy updated")
