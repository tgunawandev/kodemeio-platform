"""Compliance management commands — licenses, certifications, vendor checks."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Regulatory compliance: licenses, certifications, vendor checks.")

_LICENSE_MODEL = "compliance.company.license"
_CERT_MODEL = "compliance.product.certification"
_VENDOR_MODEL = "compliance.vendor.checklist"
_COMPLIANCE_HINT = "Compliance management module (compliance_management) is not installed."


def _m2o_name(val: object) -> str:
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


# ===================================================================
# LICENSES
# ===================================================================


@app.command("licenses")
def licenses(
    ctx: typer.Context,
    expiring_days: Annotated[int, typer.Option("--expiring-days", help="Show licenses expiring within N days")] = 30,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List company licenses and their expiry status.

    Examples:
        kctl-odoo compliance licenses
        kctl-odoo compliance licenses --expiring-days 60 --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _LICENSE_MODEL):
        out.warn(_COMPLIANCE_HINT)
        return

    preferred_fields = ["display_name", "license_type", "date_expiry", "state", "company_id"]
    try:
        records = c.search_read(  # type: ignore[attr-defined]
            _LICENSE_MODEL,
            domain=[],
            fields=preferred_fields,
            limit=limit,
            order="date_expiry asc",
        )
    except RPCError:
        try:
            records = c.search_read(  # type: ignore[attr-defined]
                _LICENSE_MODEL,
                domain=[],
                fields=["display_name", "state", "create_date"],
                limit=limit,
            )
        except RPCError as e:
            out.error(f"Failed to list licenses: {e}")
            raise typer.Exit(1) from e

    if not records:
        out.info("No licenses found.")
        if actx.json_mode:
            out.raw_json([])
        return

    today = datetime.now(tz=UTC).date()
    threshold = today + timedelta(days=expiring_days)

    rows = []
    json_data = []
    for r in records:
        expiry = str(r.get("date_expiry", ""))
        expiry_status = ""
        if expiry:
            try:
                exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
                if exp_date < today:
                    expiry_status = "[red]EXPIRED[/red]"
                elif exp_date <= threshold:
                    expiry_status = "[yellow]EXPIRING[/yellow]"
                else:
                    expiry_status = "[green]OK[/green]"
            except ValueError:
                expiry_status = ""

        rows.append(
            [
                str(r["id"]),
                r.get("display_name", ""),
                str(r.get("license_type", "")),
                _m2o_name(r.get("company_id")),
                expiry,
                expiry_status or str(r.get("state", "")),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "display_name": r.get("display_name"),
                "license_type": r.get("license_type"),
                "company": _m2o_name(r.get("company_id")),
                "date_expiry": expiry,
                "state": r.get("state"),
            }
        )

    out.table(
        f"Company Licenses ({len(records)})",
        [("ID", "dim"), ("Name", "cyan"), ("Type", ""), ("Company", ""), ("Expiry", ""), ("Status", "")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# CERTIFICATIONS
# ===================================================================


@app.command("certifications")
def certifications(
    ctx: typer.Context,
    product: Annotated[str | None, typer.Option("--product", help="Filter by product name (ilike)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List product certifications.

    Examples:
        kctl-odoo compliance certifications
        kctl-odoo compliance certifications --product "Widget A"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _CERT_MODEL):
        out.warn(_COMPLIANCE_HINT)
        return

    domain: list = []
    if product:
        domain.append(("product_id.name", "ilike", product))

    preferred_fields = ["display_name", "product_id", "certification_type", "date_expiry", "state"]
    try:
        records = c.search_read(  # type: ignore[attr-defined]
            _CERT_MODEL,
            domain=domain,
            fields=preferred_fields,
            limit=limit,
            order="date_expiry asc",
        )
    except RPCError:
        try:
            records = c.search_read(  # type: ignore[attr-defined]
                _CERT_MODEL,
                domain=domain,
                fields=["display_name", "state", "create_date"],
                limit=limit,
            )
        except RPCError as e:
            out.error(f"Failed to list certifications: {e}")
            raise typer.Exit(1) from e

    if not records:
        out.info("No certifications found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                str(r["id"]),
                r.get("display_name", ""),
                _m2o_name(r.get("product_id")),
                str(r.get("certification_type", "")),
                str(r.get("date_expiry", "")),
                str(r.get("state", "")),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "display_name": r.get("display_name"),
                "product": _m2o_name(r.get("product_id")),
                "certification_type": r.get("certification_type"),
                "date_expiry": r.get("date_expiry"),
                "state": r.get("state"),
            }
        )

    out.table(
        f"Product Certifications ({len(records)})",
        [("ID", "dim"), ("Name", "cyan"), ("Product", ""), ("Type", ""), ("Expiry", ""), ("State", "")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# VENDOR CHECK
# ===================================================================


@app.command("vendor-check")
def vendor_check(
    ctx: typer.Context,
    partner: Annotated[str, typer.Argument(help="Partner name or ID")],
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List compliance checklists for a vendor/partner.

    Examples:
        kctl-odoo compliance vendor-check "Acme Corp"
        kctl-odoo compliance vendor-check 42
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _VENDOR_MODEL):
        out.warn(_COMPLIANCE_HINT)
        return

    domain: list = []
    if partner.isdigit():
        domain.append(("partner_id", "=", int(partner)))
    else:
        domain.append(("partner_id.name", "ilike", partner))

    preferred_fields = ["display_name", "partner_id", "state", "date_check"]
    try:
        records = c.search_read(  # type: ignore[attr-defined]
            _VENDOR_MODEL,
            domain=domain,
            fields=preferred_fields,
            limit=limit,
            order="date_check desc",
        )
    except RPCError:
        try:
            records = c.search_read(  # type: ignore[attr-defined]
                _VENDOR_MODEL,
                domain=domain,
                fields=["display_name", "state", "create_date"],
                limit=limit,
            )
        except RPCError as e:
            out.error(f"Failed to list vendor checklists: {e}")
            raise typer.Exit(1) from e

    if not records:
        out.info(f"No compliance checklists found for: {partner}")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                str(r["id"]),
                r.get("display_name", ""),
                _m2o_name(r.get("partner_id")),
                str(r.get("state", "")),
                str(r.get("date_check", r.get("create_date", ""))),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "display_name": r.get("display_name"),
                "partner": _m2o_name(r.get("partner_id")),
                "state": r.get("state"),
                "date_check": r.get("date_check"),
            }
        )

    out.table(
        f"Vendor Compliance Checklists ({len(records)})",
        [("ID", "dim"), ("Name", "cyan"), ("Partner", ""), ("State", ""), ("Check Date", "dim")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# EXPIRING
# ===================================================================


@app.command("expiring")
def expiring(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", help="Show items expiring within N days")] = 30,
) -> None:
    """List all licenses and certifications expiring within N days.

    Examples:
        kctl-odoo compliance expiring
        kctl-odoo compliance expiring --days 60
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _LICENSE_MODEL):
        out.warn(_COMPLIANCE_HINT)
        return

    today = datetime.now(tz=UTC).date()
    threshold = (today + timedelta(days=days)).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")

    rows = []
    json_data = []

    # Licenses
    try:
        lic_records = c.search_read(  # type: ignore[attr-defined]
            _LICENSE_MODEL,
            domain=[("date_expiry", ">=", today_str), ("date_expiry", "<=", threshold)],
            fields=["display_name", "license_type", "date_expiry", "company_id"],
            order="date_expiry asc",
        )
        for r in lic_records:
            rows.append(
                ["License", r.get("display_name", ""), str(r.get("date_expiry", "")), _m2o_name(r.get("company_id"))]
            )
            json_data.append(
                {"category": "license", "display_name": r.get("display_name"), "date_expiry": r.get("date_expiry")}
            )
    except RPCError:
        pass

    # Certifications
    if model_available(c, _CERT_MODEL):
        try:
            cert_records = c.search_read(  # type: ignore[attr-defined]
                _CERT_MODEL,
                domain=[("date_expiry", ">=", today_str), ("date_expiry", "<=", threshold)],
                fields=["display_name", "certification_type", "date_expiry", "product_id"],
                order="date_expiry asc",
            )
            for r in cert_records:
                rows.append(
                    [
                        "Certification",
                        r.get("display_name", ""),
                        str(r.get("date_expiry", "")),
                        _m2o_name(r.get("product_id")),
                    ]
                )
                json_data.append(
                    {
                        "category": "certification",
                        "display_name": r.get("display_name"),
                        "date_expiry": r.get("date_expiry"),
                    }
                )
        except RPCError:
            pass

    if not rows:
        out.info(f"No licenses or certifications expiring within {days} days.")
        if actx.json_mode:
            out.raw_json([])
        return

    out.table(
        f"Expiring Items (within {days} days)",
        [("Category", ""), ("Name", "cyan"), ("Expiry", "yellow"), ("Related", "")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# STATS
# ===================================================================


@app.command("stats")
def stats(ctx: typer.Context) -> None:
    """Compliance statistics: licenses and certifications by status.

    Examples:
        kctl-odoo compliance stats
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _LICENSE_MODEL):
        out.warn(_COMPLIANCE_HINT)
        return

    today_str = datetime.now(tz=UTC).date().strftime("%Y-%m-%d")

    try:
        lic_active = c.search_count(_LICENSE_MODEL, [("date_expiry", ">=", today_str)])  # type: ignore[attr-defined]
        lic_expired = c.search_count(_LICENSE_MODEL, [("date_expiry", "<", today_str)])  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to count licenses: {e}")
        raise typer.Exit(1) from e

    cert_valid = cert_expired = 0
    if model_available(c, _CERT_MODEL):
        try:
            cert_valid = c.search_count(_CERT_MODEL, [("date_expiry", ">=", today_str)])  # type: ignore[attr-defined]
            cert_expired = c.search_count(_CERT_MODEL, [("date_expiry", "<", today_str)])  # type: ignore[attr-defined]
        except RPCError:
            pass

    rows = [
        ["Licenses", "Active", str(lic_active)],
        ["Licenses", "Expired", str(lic_expired)],
        ["Certifications", "Valid", str(cert_valid)],
        ["Certifications", "Expired", str(cert_expired)],
    ]
    json_data = {
        "licenses": {"active": lic_active, "expired": lic_expired},
        "certifications": {"valid": cert_valid, "expired": cert_expired},
    }

    out.table(
        "Compliance Statistics",
        [("Category", "cyan"), ("Status", ""), ("Count", "")],
        rows,
        data_for_json=json_data,
    )
