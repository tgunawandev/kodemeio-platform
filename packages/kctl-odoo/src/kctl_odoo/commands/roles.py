"""kctl-odoo roles — declarative role management.

See kodemeio-docs/superpowers/specs/2026-04-19-role-standardization-design.md
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from kctl_odoo.core.callbacks import AppContext

app = typer.Typer(help="Declarative role management via install/roles.yaml")
console = Console()


def _get_client(ctx: typer.Context):
    """Return the Odoo client from typer context (indirection for test mocking)."""
    app_ctx: AppContext = ctx.obj
    return app_ctx.client


@app.command("list")
def list_cmd(ctx: typer.Context) -> None:
    """List roles currently in the DB with user counts."""
    client = _get_client(ctx)
    roles = client.execute("res.users.role", "search_read", [], ["id", "name", "implied_ids"])
    if not roles:
        console.print("[yellow]No roles configured in this DB.[/yellow]")
        return

    table = Table(title=f"Roles ({len(roles)})")
    table.add_column("ID", justify="right")
    table.add_column("Name")
    table.add_column("Groups", justify="right")
    table.add_column("Users", justify="right")

    for role in roles:
        lines = client.execute(
            "res.users.role.line",
            "search_read",
            [("role_id", "=", role["id"])],
            ["user_id"],
        )
        table.add_row(
            str(role["id"]),
            role["name"],
            str(len(role["implied_ids"])),
            str(len(lines)),
        )
    console.print(table)


@app.command("show")
def show_cmd(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Role name (case-sensitive)"),
) -> None:
    """Show role detail: groups, implied groups, assigned users."""
    client = _get_client(ctx)
    roles = client.execute(
        "res.users.role",
        "search_read",
        [("name", "=", name)],
        ["id", "name", "implied_ids"],
    )
    if not roles:
        console.print(f"[red]Role '{name}' not found.[/red]")
        raise typer.Exit(1)

    role = roles[0]
    console.print(f"[bold]Role:[/bold] {role['name']} (id={role['id']})")

    if role["implied_ids"]:
        groups = client.execute("res.groups", "read", role["implied_ids"], ["name", "full_name"])
        group_table = Table(title="Groups")
        group_table.add_column("ID", justify="right")
        group_table.add_column("Full Name")
        for g in groups:
            group_table.add_row(str(g["id"]), g.get("full_name") or g["name"])
        console.print(group_table)
    else:
        console.print("[dim]No groups.[/dim]")

    user_lines = client.execute(
        "res.users.role.line",
        "search_read",
        [("role_id", "=", role["id"])],
        ["user_id"],
    )
    if user_lines:
        users_str = ", ".join(line["user_id"][1] for line in user_lines if line.get("user_id"))
        console.print(f"[bold]Users ({len(user_lines)}):[/bold] {users_str}")
    else:
        console.print("[dim]No users assigned.[/dim]")
