"""Tests for migration-readiness checks (pure Python, no Odoo)."""

from __future__ import annotations

from datetime import date

from kctl_odoo.commands._credit_limit.readiness import (
    CheckResult,
    ReadinessReport,
    assemble_readiness_report,
    check_accurate_live,
    check_ar_aging_parity,
    check_customer_count_nonzero,
    check_no_long_partial_payments,
    check_no_partnerless_invoices,
    check_no_stale_drafts,
)


def test_check_result_passed() -> None:
    r = CheckResult(name="state_live", passed=True, reason=None)
    assert r.passed
    assert r.reason is None


def test_readiness_report_overall_ready_when_all_pass() -> None:
    rep = ReadinessReport(
        company_id=42,
        company_code="CSP",
        company_name="X",
        sub_group="TPP1",
        accurate_state="live",
        last_sync_at=None,
        checks=[CheckResult(name=f"c{i}", passed=True, reason=None) for i in range(1, 7)],
    )
    assert rep.overall == "READY"
    assert rep.failure_reasons == ""


def test_readiness_report_not_ready_when_any_fails() -> None:
    rep = ReadinessReport(
        company_id=42,
        company_code="CSP",
        company_name="X",
        sub_group="TPP1",
        accurate_state="in_progress",
        last_sync_at=None,
        checks=[
            CheckResult(name="c1", passed=True, reason=None),
            CheckResult(name="c2", passed=False, reason="AR aging diff Rp 5M"),
            CheckResult(name="c3", passed=True, reason=None),
        ],
    )
    assert rep.overall == "NOT_READY"
    assert "AR aging diff Rp 5M" in rep.failure_reasons


def test_check_accurate_live_passes_when_state_is_live() -> None:
    accurate_company = {"state": "live"}
    r = check_accurate_live(accurate_company)
    assert r.passed
    assert r.reason is None


def test_check_accurate_live_fails_when_state_is_in_progress() -> None:
    accurate_company = {"state": "in_progress"}
    r = check_accurate_live(accurate_company)
    assert not r.passed
    assert "in_progress" in r.reason


def test_check_accurate_live_fails_when_not_registered() -> None:
    r = check_accurate_live(None)
    assert not r.passed
    assert "not registered" in r.reason.lower()


def test_check_customer_count_passes_when_positive() -> None:
    r = check_customer_count_nonzero(customer_count=42)
    assert r.passed


def test_check_customer_count_fails_when_zero() -> None:
    r = check_customer_count_nonzero(customer_count=0)
    assert not r.passed
    assert "no customer" in r.reason.lower()


def test_ar_aging_parity_passes_when_within_tolerance() -> None:
    parity_line = {
        "line_type": "ar_aging",
        "accurate_amount": 100_000_000.0,
        "odoo_amount": 100_050_000.0,
        "status": "green",
    }
    r = check_ar_aging_parity(parity_line, abs_tolerance=100_000.0, rel_tolerance=0.001)
    assert r.passed


def test_ar_aging_parity_fails_when_abs_too_large() -> None:
    parity_line = {
        "line_type": "ar_aging",
        "accurate_amount": 100_000_000.0,
        "odoo_amount": 99_500_000.0,
        "status": "amber",
    }
    r = check_ar_aging_parity(parity_line, abs_tolerance=100_000.0, rel_tolerance=0.001)
    assert not r.passed
    assert "Rp" in r.reason or "abs" in r.reason


def test_ar_aging_parity_fails_when_rel_too_large() -> None:
    parity_line = {
        "line_type": "ar_aging",
        "accurate_amount": 1_000_000.0,
        "odoo_amount": 1_002_000.0,
        "status": "amber",
    }
    r = check_ar_aging_parity(parity_line, abs_tolerance=100_000.0, rel_tolerance=0.001)
    assert not r.passed


def test_ar_aging_parity_fails_when_no_report_found() -> None:
    r = check_ar_aging_parity(None, abs_tolerance=100_000.0, rel_tolerance=0.001)
    assert not r.passed
    assert "no ar_aging" in r.reason.lower() or "missing" in r.reason.lower()


def test_check_no_partnerless_passes_when_zero() -> None:
    r = check_no_partnerless_invoices(partnerless_count=0)
    assert r.passed


def test_check_no_partnerless_fails_when_nonzero() -> None:
    r = check_no_partnerless_invoices(partnerless_count=3)
    assert not r.passed
    assert "3" in r.reason


def test_check_no_stale_drafts_passes_when_zero() -> None:
    r = check_no_stale_drafts(stale_draft_count=0)
    assert r.passed


def test_check_no_stale_drafts_fails_when_nonzero() -> None:
    r = check_no_stale_drafts(stale_draft_count=2)
    assert not r.passed


def test_check_no_long_partials_passes_when_zero() -> None:
    r = check_no_long_partial_payments(long_partial_count=0)
    assert r.passed


def test_check_no_long_partials_fails_when_nonzero() -> None:
    r = check_no_long_partial_payments(long_partial_count=5)
    assert not r.passed


def test_assemble_readiness_report_all_pass() -> None:
    rep = assemble_readiness_report(
        company={
            "id": 42,
            "code": "CSP",
            "name": "X",
            "sub_group": "TPP1",
        },
        accurate_company={"state": "live", "last_sync_at": None},
        ar_aging_parity_line={
            "accurate_amount": 100_000_000.0,
            "odoo_amount": 100_000_000.0,
            "line_type": "ar_aging",
        },
        partnerless_count=0,
        stale_draft_count=0,
        long_partial_count=0,
        customer_count=15,
        ar_abs_tolerance=100_000.0,
        ar_rel_tolerance=0.001,
    )
    assert rep.overall == "READY"
    assert rep.company_code == "CSP"
    assert len(rep.checks) == 6


def test_assemble_readiness_report_one_fail_marks_not_ready() -> None:
    rep = assemble_readiness_report(
        company={"id": 42, "code": "CSP", "name": "X", "sub_group": "TPP1"},
        accurate_company={"state": "in_progress", "last_sync_at": None},
        ar_aging_parity_line={
            "accurate_amount": 100_000_000.0,
            "odoo_amount": 100_000_000.0,
            "line_type": "ar_aging",
        },
        partnerless_count=0,
        stale_draft_count=0,
        long_partial_count=0,
        customer_count=15,
        ar_abs_tolerance=100_000.0,
        ar_rel_tolerance=0.001,
    )
    assert rep.overall == "NOT_READY"
    assert "in_progress" in rep.failure_reasons
