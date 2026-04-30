"""kctl-accurate dashboard — composite single-screen overview."""

from __future__ import annotations

import json
from typing import Any

import typer

from kctl_accurate.core.callbacks import AppContext

app = typer.Typer(help="Show a dashboard overview: user, DB info, and module counts.")

# The 5 most-used modules tracked by the dashboard.
_DASHBOARD_MODULES: list[tuple[str, str]] = [
    ("customers", "/accurate/api/customer/list.do"),
    ("vendors", "/accurate/api/vendor/list.do"),
    ("items", "/accurate/api/item/list.do"),
    ("sales-invoices", "/accurate/api/sales-invoice/list.do"),
    ("purchase-invoices", "/accurate/api/purchase-invoice/list.do"),
]


def _count(client_raw: Any, list_path: str) -> int:
    """Cheap row count via list.do?sp.pageSize=1."""
    response = client_raw.get(list_path, params={"sp.pageSize": 1, "sp.page": 1})
    sp = response.get("sp") or {}
    return int(sp.get("rowCount") or 0)


@app.callback(invoke_without_command=True)
def dashboard(
    ctx: typer.Context,
) -> None:
    """Show a dashboard overview: user info, DB info, and module record counts."""
    actx: AppContext = ctx.obj

    # Fetch token info
    info = actx.client.token_info()
    d = info.get("d", {})
    user = d.get("user") or {}
    db = d.get("database") or {}

    # Fetch counts for the 5 key modules
    raw_client = actx.client.raw
    counts: dict[str, int] = {}
    for module_name, list_path in _DASHBOARD_MODULES:
        counts[module_name] = _count(raw_client, list_path)

    if actx.json_mode:
        print(
            json.dumps(
                {"user": user, "database": db, "counts": counts},
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()

    # Build the counts table
    counts_table = Table(show_header=True, header_style="bold cyan", expand=False)
    counts_table.add_column("Module")
    counts_table.add_column("Count", justify="right")
    for module_name, count in counts.items():
        counts_table.add_row(module_name, f"{count:,}")

    # Build the panel content
    header_line = f"[bold]{user.get('name', '—')}[/bold]  [dim]{user.get('email', '—')}[/dim]"
    kv_lines = [
        f"  [dim]DB ID:[/dim] {db.get('id', '—')}",
        f"  [dim]DB Alias:[/dim] {db.get('alias', '—')}",
        f"  [dim]Host:[/dim] {db.get('host', '—')}",
    ]

    console.print()
    console.print(
        Panel(
            header_line + "\n" + "\n".join(kv_lines),
            title="[bold]kctl-accurate dashboard[/bold]",
            border_style="blue",
            expand=False,
        )
    )
    console.print(counts_table)
