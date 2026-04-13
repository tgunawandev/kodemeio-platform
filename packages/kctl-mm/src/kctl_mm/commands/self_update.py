"""Self-update command for kctl-mm."""

from __future__ import annotations

import typer

from kctl_mm import __version__
from kctl_mm.core.callbacks import AppContext

app = typer.Typer(help="Check for updates and upgrade kctl-mm.", no_args_is_help=False, invoke_without_command=True)


@app.callback(invoke_without_command=True)
def self_update(ctx: typer.Context) -> None:
    """Check PyPI for updates and upgrade kctl-mm via uv tool."""
    if ctx.invoked_subcommand is not None:
        return
    actx: AppContext = ctx.obj
    out = actx.output

    from kctl_lib.self_update import check_update
    from kctl_lib.self_update import update as do_update

    latest = check_update("kctl-mm", __version__)
    if latest:
        out.info(f"Updating to {latest}...")
        do_update("kctl-mm")
        out.success(f"Updated to {latest}")
    else:
        out.success("Already up to date")
