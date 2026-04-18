"""Storage-level admin commands.

Wraps /storage/set-admin-password.
"""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib.exceptions import KctlError

from kctl_dbgate.core.callbacks import AppContext

app = typer.Typer(help="DBGate storage/admin operations.")


@app.command("set-admin-password")
def set_admin_password(
    ctx: typer.Context,
    password: Annotated[str, typer.Option("--password", help="New admin password")],
    yes: Annotated[bool, typer.Option("--yes", help="Skip confirmation")] = False,
) -> None:
    """Rotate the DBGate admin password."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not yes and not typer.confirm("Rotate the DBGate admin password now?"):
        raise typer.Exit(0)

    try:
        actx.client.call("/storage/set-admin-password", {"password": password})
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e
    out.success("Admin password updated")
