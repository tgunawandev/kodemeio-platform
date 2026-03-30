"""Policy management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_ak.core.callbacks import AppContext

app = typer.Typer(help="Policy management (expression, password, reputation, etc.).")

POLICY_TYPE_ENDPOINTS = {
    "expression": "policies/expression/",
    "password": "policies/password/",
    "reputation": "policies/reputation/",
    "event_matcher": "policies/event_matcher/",
    "geoip": "policies/geoip/",
    "password_expiry": "policies/password_expiry/",
}


@app.command("list")
def list_(
    ctx: typer.Context,
    type_: Annotated[
        str | None,
        typer.Option(
            "--type", help="Filter by type: expression, password, reputation, event_matcher, geoip, password_expiry"
        ),
    ] = None,
) -> None:
    """List all policies."""
    c: AppContext = ctx.obj
    params: dict = {}
    if type_:
        params["type"] = type_

    policies = c.client.get_all("policies/all/", params=params)

    rows = []
    for p in policies:
        rows.append(
            [
                str(p.get("pk", "")),
                p.get("verbose_name", p.get("object_type", "")),
                p.get("name", ""),
                str(p.get("bound_to", 0)),
            ]
        )

    c.output.table(
        "Policies",
        [("ID", "cyan"), ("Type", "yellow"), ("Name", ""), ("Bound To", "dim")],
        rows,
        data_for_json=policies,
    )


@app.command()
def get(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Policy UUID")],
) -> None:
    """Get policy details."""
    c: AppContext = ctx.obj
    p = c.client.get(f"policies/all/{id_}/")

    c.output.detail(
        p.get("name", str(id_)),
        [
            (
                "Policy",
                [
                    ("ID", str(p.get("pk", ""))),
                    ("Name", p.get("name", "")),
                    ("Type", p.get("verbose_name", p.get("object_type", ""))),
                    ("Execution Logging", str(p.get("execution_logging", False))),
                ],
            ),
        ],
        data_for_json=p,
    )


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Policy name")],
    type_: Annotated[
        str,
        typer.Option(
            "--type", help="Policy type: expression, password, reputation, event_matcher, geoip, password_expiry"
        ),
    ] = "expression",
    expression: Annotated[
        str | None, typer.Option("--expression", help="Python expression (for expression policies)")
    ] = None,
    execution_logging: Annotated[bool, typer.Option("--execution-logging", help="Enable execution logging")] = False,
) -> None:
    """Create a policy."""
    c: AppContext = ctx.obj
    endpoint = POLICY_TYPE_ENDPOINTS.get(type_)
    if not endpoint:
        c.output.error(f"Unknown policy type: {type_}. Valid: {', '.join(POLICY_TYPE_ENDPOINTS)}")
        raise typer.Exit(1)

    payload: dict = {
        "name": name,
        "execution_logging": execution_logging,
    }
    if expression is not None:
        payload["expression"] = expression

    result = c.client.post(endpoint, data=payload)
    c.output.success(f"Created {type_} policy '{result.get('name', name)}' (ID: {result.get('pk', '?')})")


@app.command()
def update(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Policy UUID")],
    name: Annotated[str | None, typer.Option("--name", help="New name")] = None,
    expression: Annotated[str | None, typer.Option("--expression", help="New expression")] = None,
    execution_logging: Annotated[
        bool | None, typer.Option("--execution-logging/--no-execution-logging", help="Toggle execution logging")
    ] = None,
) -> None:
    """Update a policy."""
    c: AppContext = ctx.obj
    payload: dict = {}
    if name is not None:
        payload["name"] = name
    if expression is not None:
        payload["expression"] = expression
    if execution_logging is not None:
        payload["execution_logging"] = execution_logging

    if not payload:
        c.output.error("No fields to update. Use --name, --expression, or --execution-logging.")
        raise typer.Exit(1)

    result = c.client.put(f"policies/all/{id_}/", data=payload)
    c.output.success(f"Updated policy '{result.get('name', id_)}'")


@app.command()
def delete(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Policy UUID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a policy."""
    if not force:
        typer.confirm(f"Delete policy {id_}?", abort=True)
    c: AppContext = ctx.obj
    c.client.delete(f"policies/all/{id_}/")
    c.output.success(f"Deleted policy {id_}")


@app.command()
def bindings(ctx: typer.Context) -> None:
    """List all policy bindings."""
    c: AppContext = ctx.obj
    data = c.client.get_all("policies/bindings/")

    rows = []
    for b in data:
        policy_obj = b.get("policy_obj", {}) or {}
        rows.append(
            [
                str(b.get("pk", "")),
                policy_obj.get("name", "") if policy_obj else str(b.get("policy", "-")),
                str(b.get("target", "-")),
                str(b.get("order", 0)),
                str(b.get("enabled", True)),
                str(b.get("negate", False)),
            ]
        )

    c.output.table(
        "Policy Bindings",
        [("ID", "cyan"), ("Policy", ""), ("Target", "dim"), ("Order", ""), ("Enabled", ""), ("Negate", "dim")],
        rows,
        data_for_json=data,
    )


@app.command()
def bind(
    ctx: typer.Context,
    policy_id: Annotated[str, typer.Argument(help="Policy UUID to bind")],
    target: Annotated[str, typer.Option("--target", help="Target UUID (flow, application, etc.)")],
    order: Annotated[int, typer.Option("--order", help="Binding order")] = 0,
    enabled: Annotated[bool, typer.Option("--enabled/--disabled", help="Enable binding")] = True,
    negate: Annotated[bool, typer.Option("--negate", help="Negate policy result")] = False,
) -> None:
    """Create a policy binding."""
    c: AppContext = ctx.obj
    payload = {
        "policy": policy_id,
        "target": target,
        "order": order,
        "enabled": enabled,
        "negate": negate,
    }
    result = c.client.post("policies/bindings/", data=payload)
    c.output.success(f"Created binding (ID: {result.get('pk', '?')})")


@app.command()
def unbind(
    ctx: typer.Context,
    binding_id: Annotated[str, typer.Argument(help="Binding UUID to remove")],
) -> None:
    """Delete a policy binding."""
    c: AppContext = ctx.obj
    c.client.delete(f"policies/bindings/{binding_id}/")
    c.output.success(f"Deleted binding {binding_id}")


@app.command()
def test(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Policy UUID")],
    user: Annotated[int, typer.Option("--user", help="User PK to test against")],
) -> None:
    """Test a policy against a user."""
    c: AppContext = ctx.obj
    result = c.client.post(f"policies/all/{id_}/test/", data={"user": user})

    passing = result.get("passing", False)
    messages = result.get("messages", [])

    status = "[green]PASS[/green]" if passing else "[red]FAIL[/red]"
    sections = [
        (
            "Result",
            [
                ("Policy", str(id_)),
                ("User", str(user)),
                ("Result", status),
                ("Messages", ", ".join(messages) if messages else "(none)"),
            ],
        ),
    ]
    if result.get("log_messages"):
        log_kvs = [(str(i + 1), msg) for i, msg in enumerate(result["log_messages"])]
        sections.append(("Log", log_kvs))

    c.output.detail("Policy Test", sections, data_for_json=result)
