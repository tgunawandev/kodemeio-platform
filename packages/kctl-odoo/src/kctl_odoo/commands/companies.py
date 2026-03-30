"""Company management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.resolve import resolve_id

app = typer.Typer(help="Manage Odoo companies.")


def _resolve_company_id(client: object, identifier: str) -> int:
    """Resolve company ID from numeric ID or name."""
    return resolve_id(client, "res.company", identifier, ilike=True, label="Company")  # type: ignore[arg-type]


@app.command("list")
def list_(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 80,
) -> None:
    """List companies."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    companies = c.search_read(
        "res.company",
        domain=[],
        fields=["id", "name", "email", "phone", "currency_id", "parent_id"],
        limit=limit,
        order="id",
    )

    rows = []
    json_data = []
    for co in companies:
        currency = co.get("currency_id")
        currency_name = currency[1] if isinstance(currency, list) else str(currency or "-")
        parent = co.get("parent_id")
        parent_name = parent[1] if isinstance(parent, list) else str(parent or "-") if parent else "-"

        rows.append(
            [
                str(co["id"]),
                co["name"],
                co.get("email") or "-",
                co.get("phone") or "-",
                currency_name,
                parent_name,
            ]
        )
        json_data.append(
            {
                "id": co["id"],
                "name": co["name"],
                "email": co.get("email"),
                "phone": co.get("phone"),
                "currency": currency_name,
                "parent": parent_name,
            }
        )

    out.table(
        f"Companies ({len(companies)})",
        [("ID", "cyan"), ("Name", ""), ("Email", "dim"), ("Phone", "dim"), ("Currency", ""), ("Parent", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def get(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Company ID or name")],
) -> None:
    """Get company details."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    company_id = _resolve_company_id(c, identifier)
    records = c.read(
        "res.company",
        [company_id],
        fields=[
            "id",
            "name",
            "email",
            "phone",
            "website",
            "vat",
            "currency_id",
            "parent_id",
            "child_ids",
            "street",
            "city",
            "zip",
            "country_id",
            "create_date",
            "write_date",
        ],
    )

    if not records:
        out.error(f"Company not found: {identifier}")
        raise typer.Exit(1)

    co = records[0]
    currency = co.get("currency_id")
    currency_name = currency[1] if isinstance(currency, list) else str(currency or "-")
    parent = co.get("parent_id")
    parent_name = parent[1] if isinstance(parent, list) else "-" if not parent else str(parent)
    country = co.get("country_id")
    country_name = country[1] if isinstance(country, list) else str(country or "-")

    sections = [
        (
            "Company Info",
            [
                ("ID", str(co["id"])),
                ("Name", co["name"]),
                ("Email", co.get("email") or "-"),
                ("Phone", co.get("phone") or "-"),
                ("Website", co.get("website") or "-"),
                ("VAT", co.get("vat") or "-"),
                ("Currency", currency_name),
                ("Parent", parent_name),
                ("Children", str(len(co.get("child_ids", [])))),
            ],
        ),
        (
            "Address",
            [
                ("Street", co.get("street") or "-"),
                ("City", co.get("city") or "-"),
                ("ZIP", co.get("zip") or "-"),
                ("Country", country_name),
            ],
        ),
        (
            "Dates",
            [
                ("Created", str(co.get("create_date", ""))),
                ("Updated", str(co.get("write_date", ""))),
            ],
        ),
    ]

    out.detail(f"Company: {co['name']}", sections, data_for_json=co)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Company name")],
    email: Annotated[str | None, typer.Option("--email", help="Email")] = None,
    currency: Annotated[str | None, typer.Option("--currency", help="Currency code (e.g. USD, EUR)")] = None,
    parent: Annotated[str | None, typer.Option("--parent", help="Parent company ID or name")] = None,
) -> None:
    """Create a new company."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    vals: dict = {"name": name}
    if email:
        vals["email"] = email
    if currency:
        currency_ids = c.search("res.currency", [("name", "=", currency.upper())])
        if not currency_ids:
            out.error(f"Currency not found: {currency}")
            raise typer.Exit(1)
        vals["currency_id"] = currency_ids[0]
    if parent:
        vals["parent_id"] = _resolve_company_id(c, parent)

    company_id = c.create("res.company", vals)
    out.success(f"Created company '{name}' (ID: {company_id})")


@app.command()
def update(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Company ID or name")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="New name")] = None,
    email: Annotated[str | None, typer.Option("--email", help="Email")] = None,
    phone: Annotated[str | None, typer.Option("--phone", help="Phone")] = None,
    website: Annotated[str | None, typer.Option("--website", help="Website")] = None,
) -> None:
    """Update a company."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    company_id = _resolve_company_id(c, identifier)
    vals: dict = {}
    if name is not None:
        vals["name"] = name
    if email is not None:
        vals["email"] = email
    if phone is not None:
        vals["phone"] = phone
    if website is not None:
        vals["website"] = website

    if not vals:
        out.warn("No fields to update")
        return

    c.write("res.company", [company_id], vals)
    out.success(f"Updated company {identifier} (ID: {company_id})")


@app.command()
def users(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Company ID or name")],
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 80,
) -> None:
    """List users belonging to a company."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    company_id = _resolve_company_id(c, identifier)
    company_data = c.read("res.company", [company_id], fields=["name"])
    company_name = company_data[0]["name"] if company_data else str(company_id)

    user_records = c.search_read(
        "res.users",
        domain=[("company_ids", "in", [company_id])],
        fields=["id", "login", "name", "email", "active", "company_id"],
        limit=limit,
        order="login",
    )

    rows = []
    json_data = []
    for u in user_records:
        current_co = u.get("company_id")
        is_current = current_co[0] == company_id if isinstance(current_co, list) else False
        status = "[green]active[/green]" if u.get("active") else "[red]inactive[/red]"
        current_label = "[cyan]current[/cyan]" if is_current else ""

        rows.append([str(u["id"]), u["login"], u["name"], u.get("email") or "-", status, current_label])
        json_data.append(
            {
                "id": u["id"],
                "login": u["login"],
                "name": u["name"],
                "email": u.get("email"),
                "active": u.get("active"),
                "is_current_company": is_current,
            }
        )

    out.table(
        f"Users in '{company_name}' ({len(user_records)})",
        [("ID", "cyan"), ("Login", ""), ("Name", ""), ("Email", "dim"), ("Status", ""), ("Current Co.", "")],
        rows,
        data_for_json=json_data,
    )


@app.command("switch")
def switch_company(
    ctx: typer.Context,
    user_id: Annotated[int, typer.Argument(help="User ID")],
    company_id: Annotated[int, typer.Argument(help="Target company ID")],
) -> None:
    """Switch a user's current company."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Verify user exists
    user_data = c.read("res.users", [user_id], fields=["login", "company_ids"])
    if not user_data:
        out.error(f"User not found: {user_id}")
        raise typer.Exit(1)

    # Verify company is in user's allowed companies
    allowed = user_data[0].get("company_ids", [])
    if company_id not in allowed:
        out.error(f"Company {company_id} is not in user's allowed companies: {allowed}")
        raise typer.Exit(1)

    c.write("res.users", [user_id], {"company_id": company_id})
    out.success(f"Switched user {user_data[0]['login']} (ID: {user_id}) to company ID {company_id}")
