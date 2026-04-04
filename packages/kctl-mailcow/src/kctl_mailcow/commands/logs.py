"""Log viewing commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext

app = typer.Typer(help="View Mailcow service logs.")


@app.command("list")
def list_(
    ctx: typer.Context,
    log_type: Annotated[
        str,
        typer.Argument(
            help="Log type: dovecot, postfix, sogo, netfilter, autodiscover, rspamd-history, acme, watchdog, api"
        ),
    ] = "postfix",
    count: Annotated[int, typer.Option("--count", "-n", help="Number of log entries")] = 50,
) -> None:
    """View logs for a service."""
    c: AppContext = ctx.obj

    valid_types = [
        "dovecot",
        "postfix",
        "sogo",
        "netfilter",
        "autodiscover",
        "rspamd-history",
        "acme",
        "watchdog",
        "api",
    ]
    if log_type not in valid_types:
        c.output.error(f"Invalid log type: {log_type}")
        c.output.info(f"Valid types: {', '.join(valid_types)}")
        raise typer.Exit(1)

    data = c.client.mc_get(f"logs/{log_type}/{count}")
    items = data if isinstance(data, list) else []

    if c.json_mode:
        c.output.raw_json(items)
        return

    if not items:
        c.output.info(f"No {log_type} log entries found")
        return

    c.output.header(f"{log_type.title()} Logs (last {count})")
    for entry in items:
        if isinstance(entry, dict):
            time_str = entry.get("time", "")
            message = entry.get("message", entry.get("msg", str(entry)))
            priority = entry.get("priority", "")
            prefix = f"[dim]{time_str}[/dim] " if time_str else ""
            if priority in ("err", "crit", "alert", "emerg"):
                c.output.text(f"{prefix}[red]{message}[/red]")
            elif priority == "warning":
                c.output.text(f"{prefix}[yellow]{message}[/yellow]")
            else:
                c.output.text(f"{prefix}{message}")
        else:
            c.output.text(str(entry))
