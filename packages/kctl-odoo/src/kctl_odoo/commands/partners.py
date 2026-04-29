"""Partner/contact management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_odoo.commands._credit_limit.command import credit_limit_proposal as _credit_limit_proposal
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.resolve import resolve_id

app = typer.Typer(help="Manage Odoo partners and contacts.")


def _resolve_partner_id(client: object, identifier: str) -> int:
    """Resolve partner ID from numeric ID or name."""
    return resolve_id(client, "res.partner", identifier, ilike=True, label="Partner")  # type: ignore[arg-type]


@app.command("list")
def list_(
    ctx: typer.Context,
    company: Annotated[bool, typer.Option("--company/--no-company", help="Filter companies only")] = False,
    person: Annotated[bool, typer.Option("--person/--no-person", help="Filter persons only")] = False,
    customer: Annotated[bool, typer.Option("--customer/--no-customer", help="Filter customers")] = False,
    supplier: Annotated[bool, typer.Option("--supplier/--no-supplier", help="Filter suppliers")] = False,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 80,
) -> None:
    """List partners/contacts."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = []
    if company:
        domain.append(("is_company", "=", True))
    if person:
        domain.append(("is_company", "=", False))
    if customer:
        domain.append(("customer_rank", ">", 0))
    if supplier:
        domain.append(("supplier_rank", ">", 0))

    partners = c.search_read(
        "res.partner",
        domain=domain,
        fields=["id", "name", "email", "phone", "is_company", "city", "country_id", "customer_rank", "supplier_rank"],
        limit=limit,
        order="name",
    )

    rows = []
    json_data = []
    for p in partners:
        ptype = "Company" if p.get("is_company") else "Person"
        country = p.get("country_id")
        country_name = country[1] if isinstance(country, list) else str(country or "-")
        tags: list[str] = []
        if p.get("customer_rank", 0) > 0:
            tags.append("customer")
        if p.get("supplier_rank", 0) > 0:
            tags.append("supplier")
        tag_str = ", ".join(tags) or "-"

        rows.append(
            [
                str(p["id"]),
                p["name"],
                ptype,
                p.get("email") or "-",
                p.get("city") or "-",
                country_name,
                tag_str,
            ]
        )
        json_data.append(
            {
                "id": p["id"],
                "name": p["name"],
                "type": ptype,
                "email": p.get("email"),
                "phone": p.get("phone"),
                "city": p.get("city"),
                "country": country_name,
                "customer_rank": p.get("customer_rank"),
                "supplier_rank": p.get("supplier_rank"),
            }
        )

    out.table(
        f"Partners ({len(partners)})",
        [
            ("ID", "cyan"),
            ("Name", ""),
            ("Type", ""),
            ("Email", "dim"),
            ("City", "dim"),
            ("Country", "dim"),
            ("Tags", ""),
        ],
        rows,
        data_for_json=json_data,
    )


@app.command()
def get(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Partner ID or name")],
) -> None:
    """Get partner details."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    partner_id = _resolve_partner_id(c, identifier)
    records = c.read(
        "res.partner",
        [partner_id],
        fields=[
            "id",
            "name",
            "email",
            "phone",
            "mobile",
            "is_company",
            "company_name",
            "street",
            "street2",
            "city",
            "zip",
            "country_id",
            "state_id",
            "website",
            "vat",
            "lang",
            "customer_rank",
            "supplier_rank",
            "parent_id",
            "child_ids",
            "user_ids",
            "company_id",
            "create_date",
            "write_date",
        ],
    )

    if not records:
        out.error(f"Partner not found: {identifier}")
        raise typer.Exit(1)

    p = records[0]
    country = p.get("country_id")
    country_name = country[1] if isinstance(country, list) else str(country or "-")
    state = p.get("state_id")
    state_name = state[1] if isinstance(state, list) else str(state or "-")
    parent = p.get("parent_id")
    parent_name = parent[1] if isinstance(parent, list) else "-" if not parent else str(parent)
    co = p.get("company_id")
    co_name = co[1] if isinstance(co, list) else str(co or "-")

    sections = [
        (
            "Contact",
            [
                ("ID", str(p["id"])),
                ("Name", p["name"]),
                ("Type", "Company" if p.get("is_company") else "Person"),
                ("Email", p.get("email") or "-"),
                ("Phone", p.get("phone") or "-"),
                ("Mobile", p.get("mobile") or "-"),
                ("Website", p.get("website") or "-"),
                ("VAT", p.get("vat") or "-"),
                ("Language", p.get("lang") or "-"),
            ],
        ),
        (
            "Address",
            [
                ("Street", p.get("street") or "-"),
                ("Street2", p.get("street2") or "-"),
                ("City", p.get("city") or "-"),
                ("ZIP", p.get("zip") or "-"),
                ("State", state_name),
                ("Country", country_name),
            ],
        ),
        (
            "Relations",
            [
                ("Parent", parent_name),
                ("Company", co_name),
                ("Children", str(len(p.get("child_ids", [])))),
                ("Linked Users", str(len(p.get("user_ids", [])))),
                ("Customer Rank", str(p.get("customer_rank", 0))),
                ("Supplier Rank", str(p.get("supplier_rank", 0))),
            ],
        ),
        (
            "Dates",
            [
                ("Created", str(p.get("create_date", ""))),
                ("Updated", str(p.get("write_date", ""))),
            ],
        ),
    ]

    out.detail(f"Partner: {p['name']}", sections, data_for_json=p)


@app.command()
def search(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Search term (name or email)")],
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 20,
) -> None:
    """Search partners by name or email."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain = ["|", ("name", "ilike", query), ("email", "ilike", query)]
    partners = c.search_read(
        "res.partner",
        domain=domain,
        fields=["id", "name", "email", "phone", "is_company", "city"],
        limit=limit,
        order="name",
    )

    rows = []
    for p in partners:
        ptype = "Company" if p.get("is_company") else "Person"
        rows.append(
            [str(p["id"]), p["name"], ptype, p.get("email") or "-", p.get("phone") or "-", p.get("city") or "-"]
        )

    out.table(
        f"Search: '{query}' ({len(partners)} results)",
        [("ID", "cyan"), ("Name", ""), ("Type", ""), ("Email", "dim"), ("Phone", "dim"), ("City", "dim")],
        rows,
        data_for_json=partners,
    )


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Partner name")],
    email: Annotated[str | None, typer.Option("--email", help="Email")] = None,
    phone: Annotated[str | None, typer.Option("--phone", help="Phone")] = None,
    is_company: Annotated[bool, typer.Option("--company/--person", help="Company or person")] = False,
    parent_id: Annotated[int | None, typer.Option("--parent", help="Parent partner ID")] = None,
) -> None:
    """Create a new partner/contact."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    vals: dict = {"name": name, "is_company": is_company}
    if email:
        vals["email"] = email
    if phone:
        vals["phone"] = phone
    if parent_id is not None:
        vals["parent_id"] = parent_id

    pid = c.create("res.partner", vals)
    label = "company" if is_company else "contact"
    out.success(f"Created {label} '{name}' (ID: {pid})")


@app.command()
def update(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Partner ID or name")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="Name")] = None,
    email: Annotated[str | None, typer.Option("--email", help="Email")] = None,
    phone: Annotated[str | None, typer.Option("--phone", help="Phone")] = None,
    city: Annotated[str | None, typer.Option("--city", help="City")] = None,
) -> None:
    """Update a partner/contact."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    partner_id = _resolve_partner_id(c, identifier)

    vals: dict = {}
    if name is not None:
        vals["name"] = name
    if email is not None:
        vals["email"] = email
    if phone is not None:
        vals["phone"] = phone
    if city is not None:
        vals["city"] = city

    if not vals:
        out.warn("No fields to update")
        return

    c.write("res.partner", [partner_id], vals)
    out.success(f"Updated partner {identifier} (ID: {partner_id})")


@app.command()
def delete(
    ctx: typer.Context,
    partner_id: Annotated[int, typer.Argument(help="Partner ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a partner/contact."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Verify partner exists
    records = c.read("res.partner", [partner_id], fields=["id", "name"])
    if not records:
        out.error(f"Partner not found: {partner_id}")
        raise typer.Exit(1)

    partner_name = records[0]["name"]
    if not force and not typer.confirm(f"Delete partner '{partner_name}' (ID: {partner_id})? This cannot be undone."):
        raise typer.Exit(0)

    c.unlink("res.partner", [partner_id])
    out.success(f"Deleted partner '{partner_name}' (ID: {partner_id})")


@app.command()
def duplicates(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results per check")] = 50,
) -> None:
    """Find potential duplicate partners (same email)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Find partners with duplicate emails
    partners = c.search_read(
        "res.partner",
        domain=[("email", "!=", False), ("email", "!=", "")],
        fields=["id", "name", "email", "is_company", "active"],
        limit=500,
        order="email, name",
    )

    # Group by email
    email_groups: dict[str, list[dict]] = {}
    for p in partners:
        email = (p.get("email") or "").strip().lower()
        if email:
            email_groups.setdefault(email, []).append(p)

    # Find duplicates
    rows = []
    json_data = []
    count = 0
    for email, group in sorted(email_groups.items()):
        if len(group) < 2:
            continue
        if count >= limit:
            break
        for p in group:
            ptype = "Company" if p.get("is_company") else "Person"
            status = "[green]active[/green]" if p.get("active") else "[red]inactive[/red]"
            rows.append([str(p["id"]), p["name"], email, ptype, status])
            json_data.append(
                {
                    "id": p["id"],
                    "name": p["name"],
                    "email": email,
                    "type": ptype,
                    "active": p.get("active"),
                }
            )
        count += 1

    if not rows:
        out.info("No duplicate partners found.")
        return

    out.table(
        f"Potential Duplicates ({count} groups)",
        [("ID", "cyan"), ("Name", ""), ("Email", ""), ("Type", "dim"), ("Status", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def stats(ctx: typer.Context) -> None:
    """Show partner statistics."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    total = c.search_count("res.partner", [])
    companies = c.search_count("res.partner", [("is_company", "=", True)])
    persons = c.search_count("res.partner", [("is_company", "=", False)])
    customers = c.search_count("res.partner", [("customer_rank", ">", 0)])
    suppliers = c.search_count("res.partner", [("supplier_rank", ">", 0)])
    active = c.search_count("res.partner", [("active", "=", True)])
    inactive = c.search_count("res.partner", [("active", "=", False)])
    with_email = c.search_count("res.partner", [("email", "!=", False), ("email", "!=", "")])
    no_email = total - with_email

    # Top countries
    top_partners = c.search_read(
        "res.partner",
        domain=[("country_id", "!=", False)],
        fields=["country_id"],
        limit=500,
    )
    country_counts: dict[str, int] = {}
    for p in top_partners:
        country = p.get("country_id")
        name = country[1] if isinstance(country, list) else str(country or "Unknown")
        country_counts[name] = country_counts.get(name, 0) + 1

    top_countries = sorted(country_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    country_lines = [(name, str(cnt)) for name, cnt in top_countries]

    json_out = {
        "total": total,
        "companies": companies,
        "persons": persons,
        "customers": customers,
        "suppliers": suppliers,
        "active": active,
        "inactive": inactive,
        "with_email": with_email,
        "no_email": no_email,
        "top_countries": dict(top_countries),
    }

    sections = [
        (
            "Overview",
            [
                ("Total", str(total)),
                ("Companies", str(companies)),
                ("Persons", str(persons)),
                ("Active", str(active)),
                ("Inactive", str(inactive)),
            ],
        ),
        (
            "Roles",
            [
                ("Customers", str(customers)),
                ("Suppliers", str(suppliers)),
            ],
        ),
        (
            "Contact Info",
            [
                ("With Email", str(with_email)),
                ("No Email", str(no_email)),
            ],
        ),
        ("Top Countries", country_lines if country_lines else [("(none)", "-")]),
    ]

    out.detail("Partner Statistics", sections, data_for_json=json_out)


app.command("credit-limit-proposal")(_credit_limit_proposal)
