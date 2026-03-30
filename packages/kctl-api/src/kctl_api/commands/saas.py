"""SaaS management commands for kctl-api.

Create tenants, check status, and manage plans.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.exceptions import APIError, AuthenticationError
from kctl_api.core.exceptions import ConnectionError as KctlConnectionError

app = typer.Typer(name="saas", help="SaaS tenant management — create, status, plans.", no_args_is_help=True)

_BASE = "/api/v1/saas"


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------
@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Tenant name.")],
    plan: Annotated[str, typer.Option("--plan", "-p", help="Plan ID or slug.")] = "free",
) -> None:
    """Create a new SaaS tenant via POST /api/v1/saas/tenants."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        result = actx.client.post(f"{_BASE}/tenants", json={"name": name, "plan": plan})
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"Tenant created: {name}")
    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------
@app.command()
def status(
    ctx: typer.Context,
    tenant_id: Annotated[str, typer.Argument(help="Tenant ID.")],
) -> None:
    """Get tenant provisioning status via GET /api/v1/saas/tenants/{slug}/status."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        data = actx.client.get(f"{_BASE}/tenants/{tenant_id}/status")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    if not data:
        out.error(f"Tenant not found: {tenant_id}")
        raise typer.Exit(1)

    out.detail(
        title=f"Tenant: {data.get('name', tenant_id)}",
        sections=[
            ("Details", [(k, str(v)) for k, v in data.items()]),
        ],
        data_for_json=data,
    )


# ---------------------------------------------------------------------------
# select-plan
# ---------------------------------------------------------------------------
@app.command(name="select-plan")
def select_plan(
    ctx: typer.Context,
    tenant_id: Annotated[str, typer.Argument(help="Tenant ID.")],
    plan: Annotated[str, typer.Argument(help="Plan ID or slug to switch to.")],
) -> None:
    """Change tenant plan via POST /api/v1/saas/tenants/{slug}/select-plan."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        result = actx.client.post(f"{_BASE}/tenants/{tenant_id}/select-plan", json={"plan": plan})
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"Tenant {tenant_id} plan changed to {plan}.")
    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------
@app.command(name="list")
def list_tenants(
    ctx: typer.Context,
    page: Annotated[int, typer.Option("--page", "-p", help="Page number.")] = 1,
    per_page: Annotated[int, typer.Option("--per-page", "-n", help="Items per page.")] = 20,
) -> None:
    """List SaaS tenants via GET /api/v1/saas/tenants."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        data = actx.client.get(f"{_BASE}/tenants", params={"page": page, "per_page": per_page})
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    items = data.get("items", []) if isinstance(data, dict) else []
    total = data.get("total", len(items)) if isinstance(data, dict) else len(items)

    rows: list[list[str]] = []
    for t in items:
        rows.append(
            [
                str(t.get("id", "")),
                t.get("name", ""),
                t.get("plan", ""),
                t.get("status", ""),
                str(t.get("created_at", "")),
            ]
        )

    out.table(
        title=f"SaaS Tenants (page {page}, {total} total)",
        columns=[
            ("ID", "bold"),
            ("Name", ""),
            ("Plan", ""),
            ("Status", ""),
            ("Created", "dim"),
        ],
        rows=rows,
        data_for_json=items,
    )
