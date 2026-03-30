"""Shared helpers for biz sub-commands."""

from __future__ import annotations

from datetime import UTC, datetime

from kctl_odoo.core.exceptions import RPCError


def model_available(client: object, model: str) -> bool:
    """Return True if *model* exists in the Odoo instance."""
    try:
        client.search_count(model, [("id", "=", 0)])  # type: ignore[attr-defined]
        return True
    except RPCError:
        return False


def module_hint(model: str) -> str:
    """Return a helpful install hint for a missing model."""
    mapping: dict[str, str] = {
        "sale.order": "sale",
        "purchase.order": "purchase",
        "stock.quant": "stock",
        "stock.picking": "stock",
        "account.move": "account",
        "mrp.production": "mrp",
        "crm.lead": "crm",
        "hr.employee": "hr",
        "hr.leave": "hr_holidays",
        "hr.expense.sheet": "hr_expense",
        "mail.mail": "mail",
    }
    module = mapping.get(model, model.split(".")[0])
    return f"Module for '{model}' not installed. Install with: kctl-odoo modules install {module}"


def period_domain(field: str, period: str) -> list:
    """Build a date-range domain filter for *field* based on period name."""
    now = datetime.now(tz=UTC)
    if period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "quarter":
        q_month = ((now.month - 1) // 3) * 3 + 1
        start = now.replace(month=q_month, day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "year":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        return []
    return [(field, ">=", start.strftime("%Y-%m-%d %H:%M:%S"))]


def fmt_amount(amount: float) -> str:
    """Format a monetary amount with thousands separator."""
    if amount >= 0:
        return f"{amount:,.2f}"
    return f"-{abs(amount):,.2f}"


def parse_ids(ids_str: str | None) -> list[int]:
    """Parse a comma-separated string of IDs."""
    if not ids_str:
        return []
    return [int(x.strip()) for x in ids_str.split(",") if x.strip().isdigit()]
