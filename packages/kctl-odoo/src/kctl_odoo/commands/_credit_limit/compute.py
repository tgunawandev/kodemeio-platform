"""Pure-python compute helpers for credit-limit proposals.

These functions take plain Python dicts/lists and return ProposalRow
instances. No Odoo client, no I/O, no global state — fully unit-testable.

Spec: docs/superpowers/specs/2026-04-29-credit-limit-proposal-design.md §7
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from statistics import mean
from typing import Any


@dataclass
class Params:
    """Tunable parameters for the proposal computation."""

    coverage: float = 1.5
    insufficient_min_invoices: int = 3
    overdue_review_days: int = 120
    today: date = field(default_factory=date.today)


@dataclass
class ProposalRow:
    """One row of the Proposal sheets (group or per-pair)."""

    partner_id: int
    partner_name: str
    trading_companies: str = ""
    excluded_companies: str = ""
    first_invoice_date: date | None = None
    months_active: float = 0.0
    invoice_count: int = 0
    settled_invoice_count: int = 0
    total_sales_idr: float = 0.0
    avg_monthly_sales_idr: float = 0.0
    proposed_limit: float | str | None = None  # "INSUFFICIENT_DATA" | float | None
    current_limit_sum_idr: float = 0.0
    delta_idr: float = 0.0
    delta_pct: float = 0.0
    avg_DSO_days: float | None = None
    payment_behavior: str = "Unknown"
    has_overdue_120d: bool = False
    oldest_overdue_days: int = 0
    total_open_AR_idr: float = 0.0
    review_flag: str = ""
    note: str = ""


def _compute_months_active(first_invoice_date: date | None, today: date) -> float:
    """Months between first invoice and today, floored at 1.0."""
    if first_invoice_date is None:
        return 1.0
    days = max(0, (today - first_invoice_date).days)
    return max(1.0, days / 30.44)


def _compute_avg_monthly_sales(invoices: list[dict[str, Any]], today: date) -> float:
    """Net sales / months_active. Refunds are included as negative."""
    if not invoices:
        return 0.0
    first = min(i["invoice_date"] for i in invoices)
    months = _compute_months_active(first, today)
    total = sum(i["amount_total_signed"] for i in invoices)
    return total / months


def _compute_avg_dso(invoices: list[dict[str, Any]]) -> float | None:
    """Mean of (last_payment_date - invoice_date).days across settled invoices.

    Returns None if no settled invoices exist.
    """
    settled = [i for i in invoices if i["payment_state"] in ("paid", "in_payment") and i.get("last_payment_date")]
    if not settled:
        return None
    days = [(i["last_payment_date"] - i["invoice_date"]).days for i in settled]
    return mean(days)


def _label_dso(avg_dso: float | None) -> str:
    """Bucket label tuned for Indonesian fresh-produce credit (typical net-7 to net-14).

    Good   if avg_DSO ≤ 14.0    (Bagus — pays within 2 weeks)
    Slow   if 14.0 < avg_DSO ≤ 30.0   (Lambat — within 1 month)
    Bad    if avg_DSO > 30.0    (Buruk — beyond 1 month)
    Unknown if avg_DSO is None
    """
    if avg_dso is None:
        return "Unknown"
    if avg_dso <= 14.0:
        return "Good"
    if avg_dso <= 30.0:
        return "Slow"
    return "Bad"


def _has_overdue_120d(invoices: list[dict[str, Any]], today: date, threshold: int) -> bool:
    """True if any invoice has amount_residual > 0 AND days-past-due > threshold."""
    for i in invoices:
        if i["amount_residual"] <= 0 or not i.get("invoice_date_due"):
            continue
        days_late = (today - i["invoice_date_due"]).days
        if days_late > threshold:
            return True
    return False


def _oldest_overdue_days(invoices: list[dict[str, Any]], today: date) -> int:
    """Days past due of the most overdue OPEN invoice (residual > 0). 0 if none overdue."""
    overdue_days = [
        (today - i["invoice_date_due"]).days
        for i in invoices
        if i["amount_residual"] > 0 and i.get("invoice_date_due") and i["invoice_date_due"] < today
    ]
    return max(overdue_days) if overdue_days else 0


def _compute_review_flag(behavior: str, has_overdue_120d: bool) -> str:
    """Return 'REVIEW_REQUIRED' if Bad payer or has open invoice >120d overdue, else ''."""
    if behavior == "Bad" or has_overdue_120d:
        return "REVIEW_REQUIRED"
    return ""


def compute_per_pair(
    invoices: list[dict[str, Any]],
    *,
    current_limit: float,
    partner_id: int,
    partner_name: str,
    trading_companies: str,
    params: Params,
    excluded_companies: str = "",
) -> ProposalRow:
    """Compute one ProposalRow from a list of invoice dicts for a (partner, scope).

    `scope` is either a single (partner × company) pair or a partner's full set
    of READY-company invoices (used by compute_group via this same function).
    """
    settled = [i for i in invoices if i["payment_state"] in ("paid", "in_payment") and i.get("last_payment_date")]
    invoice_count = len(invoices)
    settled_count = len(settled)
    total_sales = sum(i["amount_total_signed"] for i in invoices)
    total_open_ar = sum(i["amount_residual"] for i in invoices)
    first_invoice_date = min((i["invoice_date"] for i in invoices), default=None)
    months_active = _compute_months_active(first_invoice_date, params.today)
    avg_monthly = total_sales / months_active if months_active > 0 else 0.0
    avg_dso = _compute_avg_dso(invoices)
    behavior = _label_dso(avg_dso)
    has_120 = _has_overdue_120d(invoices, params.today, params.overdue_review_days)
    oldest_overdue = _oldest_overdue_days(invoices, params.today)
    review_flag = _compute_review_flag(behavior=behavior, has_overdue_120d=has_120)
    note = ""

    proposed: float | str
    # Gate on total invoice count, not settled — the formula is avg-sales-based
    # (payment_state is informational). A customer with 5 unpaid invoices still
    # has a real sales pattern; we just flag them via review_flag/has_overdue_120d.
    if invoice_count < params.insufficient_min_invoices:
        proposed = "INSUFFICIENT_DATA"
    elif avg_monthly < 0:
        proposed = 0.0
        review_flag = "REVIEW_REQUIRED"
        note = "net negative sales — verify refund pattern"
    else:
        proposed = avg_monthly * params.coverage

    if isinstance(proposed, float):
        delta = proposed - current_limit
        delta_pct = (delta / current_limit * 100.0) if current_limit else 0.0
    else:
        delta = 0.0
        delta_pct = 0.0

    return ProposalRow(
        partner_id=partner_id,
        partner_name=partner_name,
        trading_companies=trading_companies,
        excluded_companies=excluded_companies,
        first_invoice_date=first_invoice_date,
        months_active=round(months_active, 1),
        invoice_count=invoice_count,
        settled_invoice_count=settled_count,
        total_sales_idr=total_sales,
        avg_monthly_sales_idr=avg_monthly,
        proposed_limit=proposed,
        current_limit_sum_idr=current_limit,
        delta_idr=delta,
        delta_pct=round(delta_pct, 2),
        avg_DSO_days=round(avg_dso, 1) if avg_dso is not None else None,
        payment_behavior=behavior,
        has_overdue_120d=has_120,
        oldest_overdue_days=oldest_overdue,
        total_open_AR_idr=total_open_ar,
        review_flag=review_flag,
        note=note,
    )


def compute_group(
    invoices_per_company: dict[str, list[dict[str, Any]]],
    *,
    current_limits: dict[str, float],
    partner_id: int,
    partner_name: str,
    params: Params,
    excluded_companies: str = "",
) -> ProposalRow:
    """Aggregate a customer's invoices across READY companies into one group row.

    invoices_per_company:  {company_code: [invoice_dict, ...]}
    current_limits:        {company_code: float}
    """
    all_invoices: list[dict[str, Any]] = []
    for invoices in invoices_per_company.values():
        all_invoices.extend(invoices)
    trading_companies = ",".join(sorted(invoices_per_company.keys()))
    current_limit_sum = sum(current_limits.values())

    return compute_per_pair(
        all_invoices,
        current_limit=current_limit_sum,
        partner_id=partner_id,
        partner_name=partner_name,
        trading_companies=trading_companies,
        params=params,
        excluded_companies=excluded_companies,
    )
