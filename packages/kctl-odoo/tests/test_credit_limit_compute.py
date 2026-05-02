"""Tests for credit-limit compute helpers (pure Python, no Odoo)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta

from kctl_odoo.commands._credit_limit.compute import (
    Params,
    ProposalRow,
    _compute_avg_dso,
    _compute_avg_monthly_sales,
    _compute_months_active,
    _compute_review_flag,
    _has_overdue_120d,
    _label_dso,
    _oldest_overdue_days,
    compute_group,
    compute_per_pair,
)


# ---------------------------------------------------------------------------
# Task 2 — Params + ProposalRow dataclasses
# ---------------------------------------------------------------------------


def test_params_defaults() -> None:
    p = Params()
    assert p.coverage == 1.5
    assert p.insufficient_min_invoices == 3
    assert p.overdue_review_days == 120
    assert p.today == date.today()


def test_proposal_row_dict_roundtrip() -> None:
    row = ProposalRow(partner_id=42, partner_name="X", trading_companies="CSP")
    d = asdict(row)
    assert d["partner_id"] == 42
    assert d["proposed_limit"] is None
    assert d["payment_behavior"] == "Unknown"


# ---------------------------------------------------------------------------
# Task 3 — _compute_avg_monthly_sales + _compute_months_active
# ---------------------------------------------------------------------------


def test_months_active_floors_at_one() -> None:
    today = date(2026, 4, 29)
    assert _compute_months_active(date(2026, 4, 24), today) == 1.0


def test_months_active_typical() -> None:
    today = date(2026, 4, 29)
    first = today - timedelta(days=274)
    assert round(_compute_months_active(first, today), 1) == 9.0


def test_months_active_empty_invoices_returns_one() -> None:
    today = date(2026, 4, 29)
    assert _compute_months_active(None, today) == 1.0


def test_avg_monthly_sales_basic() -> None:
    today = date(2026, 4, 29)
    invoices = [
        {"invoice_date": date(2026, 1, 1), "amount_total_signed": 1_000_000.0},
        {"invoice_date": date(2026, 2, 1), "amount_total_signed": 2_000_000.0},
        {"invoice_date": date(2026, 3, 1), "amount_total_signed": 3_000_000.0},
        {"invoice_date": date(2026, 4, 1), "amount_total_signed": 4_000_000.0},
    ]
    result = _compute_avg_monthly_sales(invoices, today)
    assert 2_000_000 < result < 3_000_000


def test_avg_monthly_sales_includes_negative_refund() -> None:
    today = date(2026, 4, 29)
    invoices = [
        {"invoice_date": date(2026, 1, 1), "amount_total_signed": 1_000_000.0},
        {"invoice_date": date(2026, 2, 1), "amount_total_signed": -300_000.0},
    ]
    result = _compute_avg_monthly_sales(invoices, today)
    assert result > 0
    assert result < 700_000


# ---------------------------------------------------------------------------
# Task 4 — _compute_avg_dso + _label_dso
# ---------------------------------------------------------------------------


def test_compute_avg_dso_returns_none_when_no_settled() -> None:
    invoices = [
        {"payment_state": "not_paid", "invoice_date": date(2026, 1, 1), "last_payment_date": None},
    ]
    assert _compute_avg_dso(invoices) is None


def test_compute_avg_dso_excludes_unsettled() -> None:
    invoices = [
        {"payment_state": "paid", "invoice_date": date(2026, 1, 1), "last_payment_date": date(2026, 1, 25)},
        {"payment_state": "not_paid", "invoice_date": date(2026, 2, 1), "last_payment_date": None},
        {"payment_state": "in_payment", "invoice_date": date(2026, 3, 1), "last_payment_date": date(2026, 4, 5)},
    ]
    avg = _compute_avg_dso(invoices)
    assert avg is not None
    assert round(avg, 1) == 29.5


def test_label_dso_good() -> None:
    assert _label_dso(0) == "Good"
    assert _label_dso(7.0) == "Good"
    assert _label_dso(14.0) == "Good"


def test_label_dso_slow() -> None:
    assert _label_dso(14.1) == "Slow"
    assert _label_dso(22.0) == "Slow"
    assert _label_dso(30.0) == "Slow"


def test_label_dso_bad() -> None:
    assert _label_dso(30.1) == "Bad"
    assert _label_dso(60.0) == "Bad"
    assert _label_dso(180.0) == "Bad"


def test_label_dso_unknown_when_none() -> None:
    assert _label_dso(None) == "Unknown"


# ---------------------------------------------------------------------------
# Task 5 — _has_overdue_120d + _oldest_overdue_days + _compute_review_flag
# ---------------------------------------------------------------------------


def test_has_overdue_120d_false_when_residual_zero() -> None:
    today = date(2026, 4, 29)
    invoices = [{"invoice_date_due": date(2025, 1, 1), "amount_residual": 0.0}]
    assert _has_overdue_120d(invoices, today, threshold=120) is False


def test_has_overdue_120d_true_when_open_and_old() -> None:
    today = date(2026, 4, 29)
    invoices = [{"invoice_date_due": date(2025, 1, 1), "amount_residual": 500_000.0}]
    assert _has_overdue_120d(invoices, today, threshold=120) is True


def test_has_overdue_120d_false_when_below_threshold() -> None:
    today = date(2026, 4, 29)
    invoices = [{"invoice_date_due": date(2026, 1, 1), "amount_residual": 500_000.0}]
    assert _has_overdue_120d(invoices, today, threshold=120) is False


def test_oldest_overdue_days_zero_when_no_overdue() -> None:
    today = date(2026, 4, 29)
    invoices = [{"invoice_date_due": date(2026, 5, 1), "amount_residual": 100.0}]
    assert _oldest_overdue_days(invoices, today) == 0


def test_oldest_overdue_days_returns_max_lateness() -> None:
    today = date(2026, 4, 29)
    invoices = [
        {"invoice_date_due": date(2026, 1, 1), "amount_residual": 100.0},
        {"invoice_date_due": date(2025, 1, 1), "amount_residual": 100.0},
    ]
    assert _oldest_overdue_days(invoices, today) == 483


def test_review_flag_set_for_bad_payer() -> None:
    assert _compute_review_flag(behavior="Bad", has_overdue_120d=False) == "REVIEW_REQUIRED"


def test_review_flag_set_for_overdue_120d() -> None:
    assert _compute_review_flag(behavior="Good", has_overdue_120d=True) == "REVIEW_REQUIRED"


def test_review_flag_blank_for_good_payer_no_overdue() -> None:
    assert _compute_review_flag(behavior="Good", has_overdue_120d=False) == ""


# ---------------------------------------------------------------------------
# Task 6 — compute_per_pair (the main per-(customer × company) function)
# ---------------------------------------------------------------------------


def _make_invoice(
    *,
    invoice_date: date,
    invoice_date_due: date | None = None,
    amount: float = 1_000_000.0,
    payment_state: str = "paid",
    paid_after_days: int | None = 14,
    residual: float = 0.0,
) -> dict:
    inv: dict = {
        "invoice_date": invoice_date,
        "invoice_date_due": invoice_date_due or invoice_date,
        "amount_total_signed": amount,
        "amount_residual": residual,
        "payment_state": payment_state,
    }
    if paid_after_days is not None and payment_state in ("paid", "in_payment"):
        inv["last_payment_date"] = invoice_date + timedelta(days=paid_after_days)
    else:
        inv["last_payment_date"] = None
    return inv


def test_compute_per_pair_insufficient_data_returns_marker() -> None:
    p = Params(today=date(2026, 4, 29))
    invoices = [
        _make_invoice(invoice_date=date(2026, 4, 1)),
        _make_invoice(invoice_date=date(2026, 4, 5)),
    ]
    row = compute_per_pair(
        invoices,
        current_limit=10_000_000.0,
        partner_id=1,
        partner_name="X",
        trading_companies="CSP",
        params=p,
    )
    assert row.proposed_limit == "INSUFFICIENT_DATA"
    assert row.current_limit_sum_idr == 10_000_000.0


def test_compute_per_pair_happy_path() -> None:
    p = Params(today=date(2026, 4, 29))
    invoices = [
        _make_invoice(invoice_date=date(2026, 1, 1), amount=1_000_000.0),
        _make_invoice(invoice_date=date(2026, 2, 1), amount=2_000_000.0),
        _make_invoice(invoice_date=date(2026, 3, 1), amount=3_000_000.0),
    ]
    row = compute_per_pair(
        invoices,
        current_limit=10_000_000.0,
        partner_id=1,
        partner_name="X",
        trading_companies="CSP",
        params=p,
    )
    assert isinstance(row.proposed_limit, float)
    assert row.proposed_limit > 0
    assert row.payment_behavior == "Good"
    assert row.review_flag == ""
    assert row.has_overdue_120d is False


def test_compute_per_pair_negative_sales() -> None:
    p = Params(today=date(2026, 4, 29))
    invoices = [
        _make_invoice(invoice_date=date(2026, 1, 1), amount=1_000_000.0),
        _make_invoice(invoice_date=date(2026, 2, 1), amount=-3_000_000.0),
        _make_invoice(invoice_date=date(2026, 3, 1), amount=500_000.0),
    ]
    row = compute_per_pair(
        invoices,
        current_limit=5_000_000.0,
        partner_id=1,
        partner_name="X",
        trading_companies="CSP",
        params=p,
    )
    assert row.proposed_limit == 0.0
    assert row.review_flag == "REVIEW_REQUIRED"
    assert "negative" in row.note.lower()


def test_compute_per_pair_bad_payer_keeps_proposal_but_flags_review() -> None:
    p = Params(today=date(2026, 4, 29))
    invoices = [
        _make_invoice(invoice_date=date(2026, 1, 1), amount=1_000_000.0, paid_after_days=120),
        _make_invoice(invoice_date=date(2026, 2, 1), amount=1_000_000.0, paid_after_days=130),
        _make_invoice(invoice_date=date(2026, 3, 1), amount=1_000_000.0, paid_after_days=110),
    ]
    row = compute_per_pair(
        invoices,
        current_limit=5_000_000.0,
        partner_id=1,
        partner_name="X",
        trading_companies="CSP",
        params=p,
    )
    assert isinstance(row.proposed_limit, float)
    assert row.proposed_limit > 0
    assert row.payment_behavior == "Bad"
    assert row.review_flag == "REVIEW_REQUIRED"


# ---------------------------------------------------------------------------
# Task 7 — compute_group (cross-company aggregation per customer)
# ---------------------------------------------------------------------------


def test_compute_group_aggregates_across_companies() -> None:
    p = Params(today=date(2026, 4, 29))
    invoices_per_company = {
        "CSP": [
            _make_invoice(invoice_date=date(2026, 1, 1), amount=1_000_000.0),
            _make_invoice(invoice_date=date(2026, 2, 1), amount=2_000_000.0),
        ],
        "TPRP": [
            _make_invoice(invoice_date=date(2026, 1, 15), amount=500_000.0),
            _make_invoice(invoice_date=date(2026, 3, 1), amount=1_500_000.0),
        ],
    }
    current_limits = {"CSP": 5_000_000.0, "TPRP": 3_000_000.0}
    row = compute_group(
        invoices_per_company,
        current_limits=current_limits,
        partner_id=1,
        partner_name="X",
        params=p,
        excluded_companies="",
    )
    assert row.invoice_count == 4
    assert row.total_sales_idr == 5_000_000.0
    assert row.current_limit_sum_idr == 8_000_000.0
    assert "CSP" in row.trading_companies
    assert "TPRP" in row.trading_companies


def test_compute_group_carries_excluded_companies() -> None:
    p = Params(today=date(2026, 4, 29))
    invoices_per_company = {
        "CSP": [
            _make_invoice(invoice_date=date(2026, 1, 1), amount=1_000_000.0),
            _make_invoice(invoice_date=date(2026, 2, 1), amount=1_000_000.0),
            _make_invoice(invoice_date=date(2026, 3, 1), amount=1_000_000.0),
        ],
    }
    current_limits = {"CSP": 5_000_000.0}
    row = compute_group(
        invoices_per_company,
        current_limits=current_limits,
        partner_id=1,
        partner_name="X",
        params=p,
        excluded_companies="MPJ,LFI",
    )
    assert row.excluded_companies == "MPJ,LFI"
