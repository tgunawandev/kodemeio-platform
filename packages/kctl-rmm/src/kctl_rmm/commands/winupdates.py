"""Windows Update management commands."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from kctl_rmm.core.callbacks import AppContext

app = typer.Typer(help="Manage Windows Updates on agents.")


@app.command("list")
def list_(
    ctx: typer.Context,
    agent_id: Annotated[str, typer.Argument(help="Agent ID")],
) -> None:
    """List Windows updates for an agent."""
    c: AppContext = ctx.obj

    data = c.client.get(f"/winupdate/{agent_id}/")

    updates = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []

    if not updates:
        c.output.info(f"No Windows updates found for agent {agent_id}")
        return

    rows: list[list[str]] = []
    for u in updates:
        installed = u.get("installed", False)
        status = "[green]installed[/green]" if installed else "[yellow]available[/yellow]"

        severity = u.get("severity", u.get("categories", "-"))
        if isinstance(severity, list):
            severity = ", ".join(str(s) for s in severity[:2])

        rows.append(
            [
                str(u.get("id", "")),
                str(u.get("title", u.get("kb", "")))[:60],
                u.get("kb", u.get("kb_article_ids", "-")) or "-",
                str(severity),
                status,
                str(u.get("date_installed", u.get("installed_date", "-")))[:10] if installed else "-",
            ]
        )

    c.output.table(
        f"Windows Updates -- {agent_id} ({len(updates)})",
        [("ID", "dim"), ("Title", "cyan"), ("KB", ""), ("Severity", "yellow"), ("Status", ""), ("Installed", "dim")],
        rows,
        data_for_json=updates,
    )


@app.command()
def scan(
    ctx: typer.Context,
    agent_id: Annotated[str, typer.Argument(help="Agent ID")],
) -> None:
    """Trigger a Windows Update scan on an agent."""
    c: AppContext = ctx.obj

    result = c.client.post(f"/winupdate/{agent_id}/scan/")
    c.output.success(f"Windows Update scan triggered on agent {agent_id}")
    if isinstance(result, dict) and c.output.json_mode:
        c.output.raw_json(result)


@app.command()
def install(
    ctx: typer.Context,
    agent_id: Annotated[str, typer.Argument(help="Agent ID")],
    kb: Annotated[Optional[list[str]], typer.Option("--kb", help="KB article ID(s) to install")] = None,
    all_updates: Annotated[bool, typer.Option("--all", help="Install all available updates")] = False,
    reboot: Annotated[bool, typer.Option("--reboot/--no-reboot", help="Allow reboot after install")] = False,
) -> None:
    """Install Windows updates on an agent."""
    c: AppContext = ctx.obj

    if not kb and not all_updates:
        c.output.error("Specify --kb <KB_ID> or --all to install updates")
        raise typer.Exit(1)

    payload: dict = {
        "reboot_after_install": reboot,
    }

    if kb:
        # Install specific KB articles
        payload["kb_article_ids"] = kb
    elif all_updates:
        payload["install_all"] = True

    result = c.client.post(f"/winupdate/{agent_id}/install/", data=payload)
    c.output.success(f"Windows Update install triggered on agent {agent_id}")
    if isinstance(result, dict) and c.output.json_mode:
        c.output.raw_json(result)
