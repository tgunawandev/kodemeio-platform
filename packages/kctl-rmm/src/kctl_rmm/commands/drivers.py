"""Project-specific driver management (POS58 thermal printer)."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_rmm.core.callbacks import AppContext

app = typer.Typer(help="Driver management (POS58 thermal printer).")

# Known script IDs from Tactical RMM
SCRIPT_CHECK_PRINTER = 135  # RPP02 - Check System Info
SCRIPT_INSTALL_POS58 = 136  # RPP02 - Install POS58 Driver


@app.command("install-pos58")
def install_pos58(
    ctx: typer.Context,
    agent_id: Annotated[str, typer.Argument(help="Agent ID")],
    timeout: Annotated[int, typer.Option("--timeout", "-t", help="Script timeout")] = 300,
) -> None:
    """Install POS58 thermal printer driver on an agent (script 136)."""
    c: AppContext = ctx.obj
    c.output.info(f"Running POS58 driver install script (ID: {SCRIPT_INSTALL_POS58}) on {agent_id}")

    c.client.post(f"/agents/{agent_id}/runscript/", data={
        "script": SCRIPT_INSTALL_POS58,
        "output": "forget",
        "timeout": timeout,
    })
    c.output.success(f"POS58 driver install dispatched to {agent_id} (fire-and-forget)")
    c.output.info("Check script history for results: kctl-rmm scripts history --agent " + agent_id)


@app.command("check-printer")
def check_printer(
    ctx: typer.Context,
    agent_id: Annotated[str, typer.Argument(help="Agent ID")],
    timeout: Annotated[int, typer.Option("--timeout", "-t", help="Script timeout")] = 120,
) -> None:
    """Check printer/USB info on an agent (script 135)."""
    c: AppContext = ctx.obj
    c.output.info(f"Running printer check script (ID: {SCRIPT_CHECK_PRINTER}) on {agent_id}")

    c.client.post(f"/agents/{agent_id}/runscript/", data={
        "script": SCRIPT_CHECK_PRINTER,
        "output": "forget",
        "timeout": timeout,
    })
    c.output.success(f"Printer check dispatched to {agent_id} (fire-and-forget)")
    c.output.info("Check script history for results: kctl-rmm scripts history --agent " + agent_id)
