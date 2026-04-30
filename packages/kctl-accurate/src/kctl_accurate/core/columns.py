"""MODULE_REGISTRY — maps CLI group names to SDK accessor + Pydantic model + curated columns.

Each ``ModuleSpec`` drives the ``build_module_app`` factory in
``commands/modules.py`` to produce a Typer sub-app with ``list``,
``get``, and ``count`` subcommands — no per-module boilerplate required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Type

from pydantic import BaseModel


@dataclass(frozen=True)
class ModuleSpec:
    """Specification for one CLI module group."""

    cli_name: str
    """Typer command group name, e.g. ``"sales-invoices"``."""
    sdk_accessor: str
    """Attribute name on ``AccurateClient``, e.g. ``"sales_invoices"``."""
    model: Type[BaseModel]
    """Pydantic model class for this module."""
    columns: list[str] = field(default_factory=list)
    """Curated field names shown in table / detail views (5–8 fields)."""


def _reg() -> dict[str, ModuleSpec]:
    # Lazy imports so the registry can be imported without an SDK round-trip.
    # JournalVoucher lives in finance.py; client.py has a stale accounting import
    from accurate_sdk.models.finance import BankTransfer, Expense, JournalVoucher, OtherDeposit, OtherPayment
    from accurate_sdk.models.master import (
        Currency,
        Customer,
        Employee,
        GLAccount,
        Item,
        PaymentTerm,
        Tax,
        Unit,
        Vendor,
        Warehouse,
    )
    from accurate_sdk.models.purchase import PurchaseInvoice, PurchaseOrder, PurchasePayment, ReceiveItem
    from accurate_sdk.models.sales import DeliveryOrder, SalesInvoice, SalesOrder, SalesReceipt

    specs: list[ModuleSpec] = [
        # ── Master data ────────────────────────────────────────────────────
        ModuleSpec(
            "customers",
            "customers",
            Customer,
            ["id", "name", "customerNo", "email", "mobilePhone", "npwpNo", "suspended"],
        ),
        ModuleSpec(
            "vendors",
            "vendors",
            Vendor,
            ["id", "name", "vendorNo", "email", "mobilePhone", "npwpNo", "suspended"],
        ),
        ModuleSpec(
            "items",
            "items",
            Item,
            ["id", "no", "name", "unitPrice", "itemType", "suspended"],
        ),
        ModuleSpec(
            "glaccounts",
            "glaccounts",
            GLAccount,
            ["id", "accountNo", "name", "accountType", "lastUpdated"],
        ),
        ModuleSpec(
            "warehouses",
            "warehouses",
            Warehouse,
            ["id", "name", "defaultWarehouse", "lastUpdated"],
        ),
        ModuleSpec(
            "taxes",
            "taxes",
            Tax,
            ["id", "name", "rate", "lastUpdated"],
        ),
        ModuleSpec(
            "units",
            "units",
            Unit,
            ["id", "name", "no", "lastUpdated"],
        ),
        ModuleSpec(
            "currencies",
            "currencies",
            Currency,
            ["id", "name", "code", "symbol", "lastUpdated"],
        ),
        ModuleSpec(
            "payment-terms",
            "payment_terms",
            PaymentTerm,
            ["id", "name", "netDays", "discDays", "discPC", "lastUpdated"],
        ),
        ModuleSpec(
            "employees",
            "employees",
            Employee,
            ["id", "name", "no", "lastUpdated"],
        ),
        # ── Sales ──────────────────────────────────────────────────────────
        ModuleSpec(
            "sales-invoices",
            "sales_invoices",
            SalesInvoice,
            ["id", "number", "transDate", "customerName", "totalAmount", "totalTaxAmount"],
        ),
        ModuleSpec(
            "sales-orders",
            "sales_orders",
            SalesOrder,
            ["id", "number", "transDate", "customerName", "customerId"],
        ),
        ModuleSpec(
            "sales-receipts",
            "sales_receipts",
            SalesReceipt,
            ["id", "number", "transDate", "amount"],
        ),
        ModuleSpec(
            "delivery-orders",
            "delivery_orders",
            DeliveryOrder,
            ["id", "number", "transDate", "lastUpdated"],
        ),
        # ── Purchase ───────────────────────────────────────────────────────
        ModuleSpec(
            "purchase-invoices",
            "purchase_invoices",
            PurchaseInvoice,
            ["id", "number", "transDate", "vendorName", "totalAmount", "totalTaxAmount"],
        ),
        ModuleSpec(
            "purchase-orders",
            "purchase_orders",
            PurchaseOrder,
            ["id", "number", "transDate", "vendorName", "vendorId"],
        ),
        ModuleSpec(
            "purchase-payments",
            "purchase_payments",
            PurchasePayment,
            ["id", "number", "transDate", "amount"],
        ),
        ModuleSpec(
            "receive-items",
            "receive_items",
            ReceiveItem,
            ["id", "number", "transDate", "lastUpdated"],
        ),
        # ── Finance / Accounting ───────────────────────────────────────────
        ModuleSpec(
            "journal-vouchers",
            "journal_vouchers",
            JournalVoucher,
            ["id", "number", "transDate", "lastUpdated"],
        ),
        ModuleSpec(
            "bank-transfers",
            "bank_transfers",
            BankTransfer,
            ["id", "number", "transDate", "amount"],
        ),
        ModuleSpec(
            "other-payments",
            "other_payments",
            OtherPayment,
            ["id", "number", "transDate", "amount"],
        ),
        ModuleSpec(
            "other-deposits",
            "other_deposits",
            OtherDeposit,
            ["id", "number", "transDate", "amount"],
        ),
        ModuleSpec(
            "expenses",
            "expenses",
            Expense,
            ["id", "number", "transDate", "amount"],
        ),
    ]
    return {s.cli_name: s for s in specs}


MODULE_REGISTRY: dict[str, ModuleSpec] = _reg()
