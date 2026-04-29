"""Migration-readiness checks for the credit-limit-proposal command.

All check functions are pure: they take plain dicts (the data the pull
layer fetches via search_read) and return CheckResult instances. No
Odoo client, no I/O.

Spec: docs/superpowers/specs/2026-04-29-credit-limit-proposal-design.md §5 Stage 2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CheckResult:
    """Result of one readiness check."""

    name: str
    passed: bool
    reason: str | None = None


@dataclass
class ReadinessReport:
    """All 6 check results for one trading company."""

    company_id: int
    company_code: str
    company_name: str
    sub_group: str
    accurate_state: str
    last_sync_at: datetime | None
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def overall(self) -> str:
        return "READY" if all(c.passed for c in self.checks) else "NOT_READY"

    @property
    def failure_reasons(self) -> str:
        return ", ".join(c.reason for c in self.checks if not c.passed and c.reason)


def check_accurate_live(accurate_company: dict[str, Any] | None) -> CheckResult:
    """Check 1: accurate.company.state == 'live' (means cutover completed)."""
    if accurate_company is None:
        return CheckResult(
            name="state_live",
            passed=False,
            reason="company not registered in accurate.company",
        )
    state = accurate_company.get("state", "unknown")
    if state == "live":
        return CheckResult(name="state_live", passed=True, reason=None)
    return CheckResult(
        name="state_live",
        passed=False,
        reason=f"accurate.company state='{state}' (need 'live')",
    )


def check_customer_count_nonzero(customer_count: int) -> CheckResult:
    """Check 6: at least one partner has a posted out_invoice in this company."""
    if customer_count > 0:
        return CheckResult(name="customer_count_nonzero", passed=True, reason=None)
    return CheckResult(
        name="customer_count_nonzero",
        passed=False,
        reason="no customers with posted invoices in this company",
    )


def check_ar_aging_parity(
    parity_line: dict[str, Any] | None,
    *,
    abs_tolerance: float,
    rel_tolerance: float,
) -> CheckResult:
    """Check 2: latest accurate.parity.report ar_aging line is within tolerance."""
    if parity_line is None:
        return CheckResult(
            name="ar_aging_parity",
            passed=False,
            reason="no ar_aging parity report on file for this company",
        )
    accurate_amt = parity_line.get("accurate_amount", 0.0)
    odoo_amt = parity_line.get("odoo_amount", 0.0)
    abs_diff = abs(accurate_amt - odoo_amt)
    rel_diff = abs_diff / abs(accurate_amt) if accurate_amt else float("inf")
    if abs_diff <= abs_tolerance and rel_diff <= rel_tolerance:
        return CheckResult(name="ar_aging_parity", passed=True, reason=None)
    return CheckResult(
        name="ar_aging_parity",
        passed=False,
        reason=(f"ar_aging parity diff Rp {abs_diff:,.0f} ({rel_diff * 100:.3f}%) exceeds tolerance"),
    )


def check_no_partnerless_invoices(partnerless_count: int) -> CheckResult:
    """Check 3: zero posted out_invoices with partner_id IS NULL."""
    if partnerless_count == 0:
        return CheckResult(name="no_partnerless_invoices", passed=True, reason=None)
    return CheckResult(
        name="no_partnerless_invoices",
        passed=False,
        reason=f"{partnerless_count} posted out_invoice rows with partner_id NULL",
    )


def check_no_stale_drafts(stale_draft_count: int) -> CheckResult:
    """Check 4: zero out_invoice drafts older than 30 days."""
    if stale_draft_count == 0:
        return CheckResult(name="no_stale_drafts", passed=True, reason=None)
    return CheckResult(
        name="no_stale_drafts",
        passed=False,
        reason=f"{stale_draft_count} out_invoice drafts >30d old (suggests data import gap)",
    )


def check_no_long_partial_payments(long_partial_count: int) -> CheckResult:
    """Check 5: zero out_invoices with payment_state='partial' aged > 90 days."""
    if long_partial_count == 0:
        return CheckResult(name="no_long_partial_payments", passed=True, reason=None)
    return CheckResult(
        name="no_long_partial_payments",
        passed=False,
        reason=(
            f"{long_partial_count} out_invoice rows with payment_state='partial' >90d (suggests un-reconciled payments)"
        ),
    )


def assemble_readiness_report(
    *,
    company: dict[str, Any],
    accurate_company: dict[str, Any] | None,
    ar_aging_parity_line: dict[str, Any] | None,
    partnerless_count: int,
    stale_draft_count: int,
    long_partial_count: int,
    customer_count: int,
    ar_abs_tolerance: float,
    ar_rel_tolerance: float,
) -> ReadinessReport:
    """Run all 6 checks for one trading company and return a ReadinessReport."""
    checks = [
        check_accurate_live(accurate_company),
        check_ar_aging_parity(
            ar_aging_parity_line,
            abs_tolerance=ar_abs_tolerance,
            rel_tolerance=ar_rel_tolerance,
        ),
        check_no_partnerless_invoices(partnerless_count),
        check_no_stale_drafts(stale_draft_count),
        check_no_long_partial_payments(long_partial_count),
        check_customer_count_nonzero(customer_count),
    ]
    return ReadinessReport(
        company_id=company["id"],
        company_code=company.get("code", ""),
        company_name=company.get("name", ""),
        sub_group=company.get("sub_group", ""),
        accurate_state=(accurate_company or {}).get("state", "not_registered"),
        last_sync_at=(accurate_company or {}).get("last_sync_at"),
        checks=checks,
    )
