"""Dashboard command -- system overview."""

from __future__ import annotations

import time

import typer
from typing import Annotated

from kctl_mailcow.core.callbacks import AppContext

app = typer.Typer(help="System overview dashboard.")


def _fetch_dashboard(ctx: AppContext) -> dict:
    """Collect all dashboard data."""
    c = ctx.client

    # Domains count
    domains = []
    try:
        data = c.mc_get("domain/all")
        domains = data if isinstance(data, list) else []
    except Exception:
        pass

    # Mailboxes count
    mailboxes = []
    try:
        data = c.mc_get("mailbox/all")
        mailboxes = data if isinstance(data, list) else []
    except Exception:
        pass

    # Aliases count
    aliases = []
    try:
        data = c.mc_get("alias/all")
        aliases = data if isinstance(data, list) else []
    except Exception:
        pass

    # Queue
    queue = []
    try:
        data = c.mc_get("mailq/all")
        queue = data if isinstance(data, list) else []
    except Exception:
        pass

    # Container status
    containers = {}
    try:
        data = c.mc_get("status/containers")
        if isinstance(data, dict):
            containers = data
    except Exception:
        pass

    return {
        "domains": len(domains),
        "mailboxes": len(mailboxes),
        "aliases": len(aliases),
        "queue": len(queue),
        "containers": containers,
        "domains_list": domains,
        "mailboxes_list": mailboxes,
    }


def _display_dashboard(ctx: AppContext, data: dict) -> None:
    out = ctx.output

    if ctx.json_mode:
        out.raw_json(data)
        return

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    # Resource counts
    sections.append(
        (
            "Resources",
            [
                ("Domains", str(data.get("domains", 0))),
                ("Mailboxes", str(data.get("mailboxes", 0))),
                ("Aliases", str(data.get("aliases", 0))),
                ("Queue", str(data.get("queue", 0))),
            ],
        )
    )

    # Container health
    containers = data.get("containers", {})
    if containers:
        running = sum(
            1 for v in containers.values() if (isinstance(v, dict) and v.get("state") == "running") or v == "running"
        )
        total = len(containers)
        color = "green" if running == total else ("yellow" if running > total // 2 else "red")
        sections.append(
            (
                "Containers",
                [
                    ("Running", f"[{color}]{running}/{total}[/{color}]"),
                ],
            )
        )

    # Top mailboxes by usage
    mailboxes = data.get("mailboxes_list", [])
    if mailboxes:
        sorted_mboxes = sorted(mailboxes, key=lambda m: m.get("quota_used", 0), reverse=True)[:5]
        mbox_kvs = []
        for m in sorted_mboxes:
            used = m.get("quota_used", 0)
            total_q = m.get("quota", 1)
            pct = int(used / total_q * 100) if total_q else 0
            color = "red" if pct > 90 else ("yellow" if pct > 70 else "green")
            mbox_kvs.append((m.get("username", ""), f"[{color}]{pct}% quota used[/{color}]"))
        sections.append(("Top Mailboxes by Quota", mbox_kvs))

    out.detail("Mailcow Dashboard", sections, data_for_json=data)


@app.callback(invoke_without_command=True)
def dashboard(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously refresh.")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Refresh interval in seconds.")] = 10,
) -> None:
    """Show system overview dashboard."""
    actx: AppContext = ctx.obj

    if watch:
        try:
            while True:
                data = _fetch_dashboard(actx)
                actx.output.console.clear()
                _display_dashboard(actx, data)
                actx.output.text(f"\n[dim]Refreshing every {interval}s. Press Ctrl+C to stop.[/dim]")
                time.sleep(interval)
        except KeyboardInterrupt:
            actx.output.info("Stopped watching.")
    else:
        data = _fetch_dashboard(actx)
        _display_dashboard(actx, data)
