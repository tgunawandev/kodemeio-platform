"""kctl-accurate db — database/company management commands."""

from __future__ import annotations

import json

import typer

from kctl_accurate.core.callbacks import AppContext

app = typer.Typer(help="Accurate database/company operations: list-companies, open, info.")


@app.command("list-companies")
def list_companies(ctx: typer.Context) -> None:
    """List all Accurate companies accessible with this token."""
    actx: AppContext = ctx.obj
    companies = actx.client.db_list()

    if actx.json_mode:
        print(json.dumps(companies, indent=2, ensure_ascii=False))
        return

    from rich.console import Console
    from rich.table import Table

    table = Table(title="Accurate Companies", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim")
    table.add_column("Alias")
    table.add_column("Host")

    for company in companies:
        table.add_row(
            str(company.get("id", "")),
            str(company.get("alias", "")),
            str(company.get("host", "")),
        )

    console = Console()
    console.print(table)


@app.command("open")
def open_db(
    ctx: typer.Context,
    db_id: int = typer.Argument(help="Accurate company/database ID to open."),
) -> None:
    """Open a database session and print session info."""
    actx: AppContext = ctx.obj
    session = actx.client.open_db(db_id)

    if actx.json_mode:
        print(json.dumps(session, indent=2, ensure_ascii=False))
        return

    from rich.console import Console
    from rich.panel import Panel

    lines = [f"  [dim]{k}:[/dim] {v}" for k, v in session.items()]
    content = "\n".join(lines)
    Console().print(Panel(content, title=f"[bold]DB Session — {db_id}[/bold]", border_style="blue", expand=False))


@app.command("info")
def db_info(ctx: typer.Context) -> None:
    """Show current profile's database info (user, DB ID, alias, host)."""
    actx: AppContext = ctx.obj
    info = actx.client.token_info()

    if actx.json_mode:
        print(json.dumps(info, indent=2, ensure_ascii=False))
        return

    from rich.console import Console
    from rich.panel import Panel

    d = info.get("d", {})
    user = d.get("user") or {}
    db = d.get("database") or {}

    lines = [
        f"  [dim]User:[/dim] {user.get('name', '[dim]—[/dim]')}",
        f"  [dim]User Email:[/dim] {user.get('email', '[dim]—[/dim]')}",
        f"  [dim]DB ID:[/dim] {db.get('id', '[dim]—[/dim]')}",
        f"  [dim]DB Alias:[/dim] {db.get('alias', '[dim]—[/dim]')}",
        f"  [dim]Host:[/dim] {db.get('host', '[dim]—[/dim]')}",
    ]
    content = "\n".join(lines)
    Console().print(Panel(content, title="[bold]Current Database Info[/bold]", border_style="blue", expand=False))
