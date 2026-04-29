"""Tests for the direct-Accurate credit-limit pull layer.

Pure Python — no Odoo, no live Accurate. Uses MagicMock for the
:class:`AccurateClient` so we can exercise field normalisation,
payment-state inference, and customer/invoice grouping.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from kctl_odoo.commands._credit_limit.accurate_command import (
    _read_env_file,
    _resolve_token,
    _slugify,
)
from kctl_odoo.commands._credit_limit.accurate_pull import (
    _build_last_payment_lookup,
    _customer_id_of,
    _infer_payment_state,
    _money,
    _parse_accurate_date,
    pull_customers,
    pull_sales_invoices_and_payments,
)


# ---------------------------------------------------------------------------
# Coercion helpers
# ---------------------------------------------------------------------------


def test_parse_accurate_date_handles_dd_mm_yyyy() -> None:
    assert _parse_accurate_date("15/04/2026") == date(2026, 4, 15)


def test_parse_accurate_date_handles_iso_and_strips_time() -> None:
    assert _parse_accurate_date("2026-01-31") == date(2026, 1, 31)
    assert _parse_accurate_date("15/04/2026 09:30:00") == date(2026, 4, 15)


def test_parse_accurate_date_returns_none_for_invalid() -> None:
    assert _parse_accurate_date(None) is None
    assert _parse_accurate_date("") is None
    assert _parse_accurate_date("not-a-date") is None


def test_money_coerces_strings_and_handles_none() -> None:
    assert _money("1500.5") == 1500.5
    assert _money(None) == 0.0
    assert _money("") == 0.0
    assert _money("garbage") == 0.0
    assert _money(42) == 42.0


def test_customer_id_handles_denormalized_and_nested() -> None:
    assert _customer_id_of({"customerId": 99}) == 99
    assert _customer_id_of({"customer": {"id": 7}}) == 7
    assert _customer_id_of({"customerId": "12"}) == 12
    assert _customer_id_of({}) is None


# ---------------------------------------------------------------------------
# Payment-state inference
# ---------------------------------------------------------------------------


def test_infer_payment_state_paid_status() -> None:
    assert (
        _infer_payment_state(
            amount_total=1000.0,
            amount_residual=0.0,
            status="PAID",
            outstanding_flag=False,
        )
        == "paid"
    )


def test_infer_payment_state_partial() -> None:
    assert (
        _infer_payment_state(
            amount_total=1000.0,
            amount_residual=400.0,
            status="OUTSTANDING",
            outstanding_flag=True,
        )
        == "partial"
    )


def test_infer_payment_state_not_paid() -> None:
    assert (
        _infer_payment_state(
            amount_total=1000.0,
            amount_residual=1000.0,
            status="OUTSTANDING",
            outstanding_flag=True,
        )
        == "not_paid"
    )


def test_infer_payment_state_residual_zero_means_paid() -> None:
    assert (
        _infer_payment_state(
            amount_total=500.0,
            amount_residual=0.0,
            status=None,
            outstanding_flag=None,
        )
        == "paid"
    )


# ---------------------------------------------------------------------------
# Receipt → last-payment lookup
# ---------------------------------------------------------------------------


def test_build_last_payment_lookup_picks_max_date() -> None:
    receipts = [
        {
            "id": 1,
            "transDate": "01/03/2026",
            "detailInvoice": [{"invoice": {"id": 100}, "invoicePayment": 500.0}],
        },
        {
            "id": 2,
            "transDate": "15/04/2026",
            "detailInvoice": [{"invoice": {"id": 100}, "invoicePayment": 500.0}],
        },
        {
            "id": 3,
            "transDate": "10/02/2026",
            "detailInvoice": [{"invoice": {"id": 200}, "paymentAmount": 1200.0}],
        },
    ]
    lookup = _build_last_payment_lookup(receipts)
    assert lookup[100] == date(2026, 4, 15)
    assert lookup[200] == date(2026, 2, 10)


def test_build_last_payment_lookup_skips_zero_payments() -> None:
    receipts = [
        {
            "id": 1,
            "transDate": "01/03/2026",
            "detailInvoice": [{"invoice": {"id": 7}, "invoicePayment": 0.0}],
        }
    ]
    assert _build_last_payment_lookup(receipts) == {}


def test_build_last_payment_lookup_skips_missing_dates() -> None:
    receipts = [
        {
            "id": 1,
            "transDate": None,
            "detailInvoice": [{"invoice": {"id": 7}, "invoicePayment": 100.0}],
        }
    ]
    assert _build_last_payment_lookup(receipts) == {}


# ---------------------------------------------------------------------------
# pull_customers
# ---------------------------------------------------------------------------


def _client_with(customers=None, invoices=None, receipts=None) -> MagicMock:
    """Build a MagicMock AccurateClient pre-loaded with raw responses."""
    client = MagicMock()
    client.customers.list_raw.return_value = customers or []
    client.sales_invoices.list_raw.return_value = invoices or []
    client.sales_receipts.list_raw.return_value = receipts or []
    return client


def test_pull_customers_normalizes_fields() -> None:
    client = _client_with(
        customers=[
            {
                "id": 42,
                "name": "PT Foo",
                "customerNo": "C-001",
                "npwpNo": "01.234.567.8-901.000",
                "creditLimitAmount": 5_000_000,
                "billCity": "Jakarta",
                "billProvince": "DKI",
                "suspended": False,
            }
        ]
    )
    rows = pull_customers(client)
    assert len(rows) == 1
    r = rows[0]
    assert r["id"] == 42
    assert r["name"] == "PT Foo"
    assert r["customer_no"] == "C-001"
    assert r["npwp"] == "01.234.567.8-901.000"
    assert r["current_credit_limit"] == 5_000_000.0
    assert r["billing_city"] == "Jakarta"
    assert r["suspended"] is False


def test_pull_customers_credit_limit_fallback_keys() -> None:
    """``creditLimit`` and ``customerCreditLimit`` should also be honoured."""
    client = _client_with(
        customers=[
            {"id": 1, "name": "A", "creditLimit": 1000},
            {"id": 2, "name": "B", "customerCreditLimit": 2000},
            {"id": 3, "name": "C"},  # no limit at all
        ]
    )
    rows = pull_customers(client)
    by_id = {r["id"]: r for r in rows}
    assert by_id[1]["current_credit_limit"] == 1000.0
    assert by_id[2]["current_credit_limit"] == 2000.0
    assert by_id[3]["current_credit_limit"] == 0.0


def test_pull_customers_drops_rows_without_id() -> None:
    client = _client_with(customers=[{"id": None, "name": "ghost"}, {"id": 1, "name": "A"}])
    rows = pull_customers(client)
    assert [r["id"] for r in rows] == [1]


# ---------------------------------------------------------------------------
# pull_sales_invoices_and_payments — end-to-end shape
# ---------------------------------------------------------------------------


def test_pull_sales_invoices_groups_by_customer_with_dates() -> None:
    invoices = [
        {
            "id": 1001,
            "number": "SI.001",
            "transDate": "01/01/2026",
            "dueDate": "31/01/2026",
            "totalAmount": 1_000_000.0,
            "outstandingAmount": 0.0,
            "status": "PAID",
            "customerId": 42,
            "customer": {"id": 42, "name": "PT Foo", "customerNo": "C-001"},
        },
        {
            "id": 1002,
            "number": "SI.002",
            "transDate": "15/02/2026",
            "dueDate": "15/03/2026",
            "totalAmount": 500_000.0,
            "outstandingAmount": 500_000.0,
            "status": "OUTSTANDING",
            "outstanding": True,
            "customerId": 42,
            "customer": {"id": 42, "name": "PT Foo", "customerNo": "C-001"},
        },
        {
            "id": 1003,
            "number": "SI.003",
            "transDate": "01/03/2026",
            "dueDate": "31/03/2026",
            "totalAmount": 2_000_000.0,
            "outstandingAmount": 0.0,
            "status": "PAID",
            "customer": {"id": 99, "name": "PT Bar", "customerNo": "C-099"},
        },
    ]
    receipts = [
        {
            "id": 5001,
            "transDate": "20/01/2026",
            "detailInvoice": [{"invoice": {"id": 1001}, "invoicePayment": 1_000_000.0}],
        },
        {
            "id": 5002,
            "transDate": "05/03/2026",
            "detailInvoice": [{"invoice": {"id": 1003}, "invoicePayment": 2_000_000.0}],
        },
    ]
    client = _client_with(invoices=invoices, receipts=receipts)
    by_customer = pull_sales_invoices_and_payments(client, today=date(2026, 4, 30))

    assert set(by_customer.keys()) == {42, 99}
    assert len(by_customer[42]) == 2
    assert len(by_customer[99]) == 1

    # Inspect the paid invoice dict
    paid = next(i for i in by_customer[42] if i["id"] == 1001)
    assert paid["invoice_date"] == date(2026, 1, 1)
    assert paid["invoice_date_due"] == date(2026, 1, 31)
    assert paid["amount_total_signed"] == 1_000_000.0
    assert paid["amount_residual"] == 0.0
    assert paid["payment_state"] == "paid"
    assert paid["last_payment_date"] == date(2026, 1, 20)
    assert paid["doc_number"] == "SI.001"

    # Open invoice has no last_payment_date
    open_inv = next(i for i in by_customer[42] if i["id"] == 1002)
    assert open_inv["payment_state"] == "not_paid"
    assert open_inv["amount_residual"] == 500_000.0
    assert open_inv["last_payment_date"] is None


def test_pull_sales_invoices_drops_invoices_without_customer() -> None:
    invoices = [
        {"id": 1, "transDate": "01/01/2026", "totalAmount": 100.0},  # no customer
        {"id": 2, "transDate": "01/01/2026", "totalAmount": 100.0, "customerId": 7},
    ]
    client = _client_with(invoices=invoices)
    by_customer = pull_sales_invoices_and_payments(client)
    assert list(by_customer.keys()) == [7]


def test_pull_sales_invoices_residual_from_paid_amount_fallback() -> None:
    """When ``outstandingAmount`` missing, residual = total - paidAmount."""
    invoices = [
        {
            "id": 1,
            "transDate": "01/01/2026",
            "totalAmount": 1000.0,
            "paidAmount": 600.0,
            "customerId": 5,
        }
    ]
    client = _client_with(invoices=invoices)
    by_customer = pull_sales_invoices_and_payments(client)
    inv = by_customer[5][0]
    assert inv["amount_residual"] == 400.0
    assert inv["payment_state"] == "partial"


# ---------------------------------------------------------------------------
# Token + secret resolution helpers (pure stdlib I/O)
# ---------------------------------------------------------------------------


def test_read_env_file_strips_quotes_and_comments(tmp_path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("# comment\nFOO=bar\nBAZ=\"quoted value\"\nQUX='single quoted'\n\nEMPTY=\n")
    env = _read_env_file(env_path)
    assert env == {"FOO": "bar", "BAZ": "quoted value", "QUX": "single quoted", "EMPTY": ""}


def test_resolve_token_short_key_uses_full_var_prefix(tmp_path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("ACCURATE_TOKEN_TPK=aat.NTA.abc123\n")
    assert _resolve_token("TPK", env_path) == "aat.NTA.abc123"


def test_resolve_token_full_key_works(tmp_path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("ACCURATE_TOKEN_FOO=tok-xyz\n")
    assert _resolve_token("ACCURATE_TOKEN_FOO", env_path) == "tok-xyz"


def test_resolve_token_missing_raises(tmp_path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("OTHER_VAR=value\n")
    with pytest.raises(Exception):  # typer.BadParameter inherits click.UsageError
        _resolve_token("MISSING", env_path)


def test_slugify_handles_company_names() -> None:
    assert _slugify("CV TUNGGAL PANGAN PAKERTI") == "cv-tunggal-pangan-pakerti"
    assert _slugify("PT.  Foo Bar") == "pt-foo-bar"
    assert _slugify("") == "tenant"
