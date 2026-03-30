"""Record rule debugging and access simulation commands."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

app = typer.Typer(help="Debug and audit Odoo record rules and access control.")
console = Console()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("simulate")
def simulate_rules(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Model technical name (e.g. sale.order)")],
    user_id: Annotated[int, typer.Argument(help="User ID to simulate access for")],
    record_id: Annotated[int, typer.Argument(help="Record ID to test access on")],
) -> None:
    """Evaluate record rules for a given user and record combination."""
    from kctl_odoo.core.callbacks import AppContext
    from kctl_odoo.core.exceptions import RPCError

    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        # Get user info
        users = c.read("res.users", [user_id], ["name", "login", "groups_id"])
        if not users:
            out.error(f"User {user_id} not found")
            raise typer.Exit(1)
        user = users[0]

        # Get record info
        records = c.read(model, [record_id], ["display_name"])
        if not records:
            out.error(f"Record {record_id} not found in {model}")
            raise typer.Exit(1)
        record = records[0]

        # Get applicable rules
        rules = c.search_read(
            "ir.rule",
            domain=[("model_id.model", "=", model), ("active", "=", True)],
            fields=["id", "name", "domain_force", "groups", "perm_read", "perm_write", "perm_create", "perm_unlink"],
        )

        console.print("\n[bold]Rule Simulation[/bold]")
        console.print(f"  Model:  [cyan]{model}[/cyan]")
        console.print(f"  User:   [cyan]{user.get('login')} (ID={user_id})[/cyan]")
        console.print(f"  Record: [cyan]{record.get('display_name', '')} (ID={record_id})[/cyan]")
        console.print(f"\n[bold]{len(rules)} rule(s) found:[/bold]\n")

        if not rules:
            console.print(
                "  [dim]No record rules defined for this model — all access governed by ir.model.access[/dim]"
            )
            return

        for rule in rules:
            group_names = [g[1] if isinstance(g, list) else str(g) for g in rule.get("groups", [])]
            groups_str = ", ".join(group_names) if group_names else "[dim]global (all users)[/dim]"
            perms = []
            if rule.get("perm_read"):
                perms.append("read")
            if rule.get("perm_write"):
                perms.append("write")
            if rule.get("perm_create"):
                perms.append("create")
            if rule.get("perm_unlink"):
                perms.append("unlink")

            console.print(f"  [cyan]{rule.get('name')}[/cyan] (ID={rule['id']})")
            console.print(f"    Groups:  {groups_str}")
            console.print(f"    Perms:   {', '.join(perms) or 'none'}")
            console.print(f"    Domain:  [dim]{rule.get('domain_force', '[]')}[/dim]")

    except RPCError as e:
        out.error(f"RPC error: {e.detail}")
        raise typer.Exit(1) from e


@app.command("explain")
def explain_rules(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Model technical name (e.g. sale.order)")],
    user_id: Annotated[int, typer.Argument(help="User ID to show rules for")],
) -> None:
    """Show the full record rule chain for a model and user."""
    from kctl_odoo.core.callbacks import AppContext
    from kctl_odoo.core.exceptions import RPCError

    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        # Get user info
        users = c.read("res.users", [user_id], ["name", "login", "groups_id"])
        if not users:
            out.error(f"User {user_id} not found")
            raise typer.Exit(1)
        user = users[0]

        # Get user's group IDs
        group_ids = user.get("groups_id", [])

        # Get all rules for this model
        all_rules = c.search_read(
            "ir.rule",
            domain=[("model_id.model", "=", model), ("active", "=", True)],
            fields=[
                "id",
                "name",
                "domain_force",
                "groups",
                "perm_read",
                "perm_write",
                "perm_create",
                "perm_unlink",
                "global",
            ],
        )

        # Filter: global rules apply to all users; group rules apply if user is in group
        applicable = []
        for rule in all_rules:
            rule_groups = rule.get("groups", [])
            rule_group_ids = [g[0] if isinstance(g, list) else g for g in rule_groups]
            is_global = rule.get("global", False) or not rule_groups
            in_group = any(gid in group_ids for gid in rule_group_ids)
            if is_global or in_group:
                applicable.append(rule)

        console.print(f"\n[bold]Rule Chain:[/bold] {model} for user '{user.get('login')}' (ID={user_id})")
        console.print(f"  Total rules: {len(all_rules)}, Applicable: [cyan]{len(applicable)}[/cyan]\n")

        if not applicable:
            console.print("  [dim]No applicable record rules — access controlled by ir.model.access only[/dim]")
            return

        for rule in applicable:
            perms = []
            if rule.get("perm_read"):
                perms.append("read")
            if rule.get("perm_write"):
                perms.append("write")
            if rule.get("perm_create"):
                perms.append("create")
            if rule.get("perm_unlink"):
                perms.append("unlink")
            scope = "[dim]global[/dim]" if rule.get("global") else "[yellow]group[/yellow]"
            console.print(f"  [{scope}] [cyan]{rule.get('name')}[/cyan]")
            console.print(f"    Perms:  {', '.join(perms) or 'none'}")
            console.print(f"    Domain: [dim]{rule.get('domain_force', '[]')}[/dim]")

    except RPCError as e:
        out.error(f"RPC error: {e.detail}")
        raise typer.Exit(1) from e


@app.command("audit")
def audit_rules(ctx: typer.Context) -> None:
    """Audit: models without record rules, overly permissive rules."""
    from kctl_odoo.core.callbacks import AppContext
    from kctl_odoo.core.exceptions import RPCError

    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        # Get all models with access control
        all_rules = c.search_read(
            "ir.rule",
            domain=[("active", "=", True)],
            fields=["name", "model_id", "domain_force", "groups", "global"],
            limit=500,
        )

        # Models with rules
        models_with_rules: set[str] = set()
        permissive_rules = []

        for rule in all_rules:
            model_name = rule.get("model_id", [None, ""])[1] if isinstance(rule.get("model_id"), list) else ""
            models_with_rules.add(model_name)

            # Overly permissive: global rule with domain=[] or domain=[(1,'=',1)]
            domain = (rule.get("domain_force") or "[]").strip()
            is_global = rule.get("global", False) or not rule.get("groups")
            if is_global and domain in ("[]", "[(1, '=', 1)]", "[(1,'=',1)]"):
                permissive_rules.append(rule)

        console.print("\n[bold]Record Rule Audit[/bold]\n")
        console.print(f"  Total active rules: [cyan]{len(all_rules)}[/cyan]")
        console.print(f"  Models with rules:  [cyan]{len(models_with_rules)}[/cyan]")

        if permissive_rules:
            console.print("\n  [yellow]Permissive global rules (domain=[] or always-true):[/yellow]")
            for rule in permissive_rules[:20]:
                model_name = rule.get("model_id", [None, "?"])[1] if isinstance(rule.get("model_id"), list) else "?"
                console.print(f"    - [cyan]{rule.get('name')}[/cyan] on {model_name}")
        else:
            console.print("\n  [green]No overly permissive global rules found.[/green]")

    except RPCError as e:
        out.error(f"RPC error: {e.detail}")
        raise typer.Exit(1) from e


@app.command("test")
def test_rules(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Model technical name")],
    limit: Annotated[int, typer.Option("--limit", help="Max records to test against")] = 5,
) -> None:
    """Test record rules against sample data by checking which records are visible."""
    from kctl_odoo.core.callbacks import AppContext
    from kctl_odoo.core.exceptions import RPCError

    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        # Read sample records (as the current user)
        records = c.search_read(
            model,
            domain=[],
            fields=["id", "display_name"],
            limit=limit,
        )

        # Count total without restrictions
        total = c.search_count(model, [])

        console.print(f"\n[bold]Record Rule Test:[/bold] {model}")
        console.print(f"  Visible records (as current user): [cyan]{len(records)}[/cyan] of {total} total\n")

        if records:
            for rec in records:
                console.print(f"  [green]visible[/green] ID={rec['id']} — {rec.get('display_name', '')}")
        else:
            console.print("  [red]No records visible — record rules may be blocking all access[/red]")

        # Get rule count
        rule_count = c.search_count("ir.rule", [("model_id.model", "=", model), ("active", "=", True)])
        console.print(f"\n  Active rules for this model: [cyan]{rule_count}[/cyan]")

    except RPCError as e:
        out.error(f"RPC error: {e.detail}")
        raise typer.Exit(1) from e
