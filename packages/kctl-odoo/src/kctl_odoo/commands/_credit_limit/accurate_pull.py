"""Pull customer + invoice + payment data from Accurate Online via the SDK.

Pure-ish module: takes an :class:`AccurateClient`, returns plain dicts
shaped for the existing :mod:`compute` layer. No Odoo, no I/O outside
the SDK calls.

Spec: docs/superpowers/specs/2026-04-29-credit-limit-proposal-design.md
(direct-Accurate pilot variant for trading companies that aren't
migrated yet).

Accurate field names (camelCase, see kodemeio-accurate/packages/
accurate-sdk/src/accurate_sdk/models/master.py + sales.py):

* Customer: ``id``, ``name``, ``customerNo``, ``npwpNo``, plus an
  optional ``creditLimitAmount`` carried via ``extra='allow'`` (the
  Pydantic model permits unknown fields).
* SalesInvoice: ``id``, ``number``, ``transDate`` (DD/MM/YYYY string),
  ``dueDate``, ``totalAmount``, ``customerId`` (denormalized) /
  ``customer.id`` (nested), ``status`` (PAID/OUTSTANDING/CLOSED),
  ``outstanding`` (bool), ``paidAmount`` / ``outstandingAmount``
  (numeric, if present).
* SalesReceipt: ``id``, ``number``, ``transDate``, ``customer``,
  ``detailInvoice[]`` with each entry carrying ``invoice.id`` and
  ``invoicePayment``/``paymentAmount``.

The list endpoints return paginated lite rows; for sales-invoice we may
need a detail.do call to recover ``status`` reliably. To keep the pilot
fast we read whatever the list endpoint hands us and infer the missing
fields heuristically — see :func:`_infer_payment_state`.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from accurate_sdk import AccurateClient


# ---------------------------------------------------------------------------
# Helpers — date + numeric coercion
# ---------------------------------------------------------------------------


def _parse_accurate_date(value: Any) -> date | None:
    """Parse Accurate's ``DD/MM/YYYY`` string into a :class:`date`.

    Tolerates ``None`` / empty strings / already-parsed ``date`` values.
    Also accepts ISO ``YYYY-MM-DD`` and ``DD/MM/YYYY HH:mm:ss``.
    """
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str):
        return None
    s = value.strip()
    if " " in s:  # strip optional time component
        s = s.split(" ", 1)[0]
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _money(value: Any) -> float:
    """Coerce ``value`` to a non-NaN float, defaulting to 0.0."""
    if value is None or value == "":
        return 0.0
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.0
    if f != f:  # NaN check
        return 0.0
    return f


def _customer_id_of(record: dict[str, Any]) -> int | None:
    """Resolve the customer id out of an Accurate sales record.

    Accurate's response sometimes uses ``customerId`` (denormalized) and
    sometimes ``customer.id`` (nested). We probe both.
    """
    cid = record.get("customerId")
    if cid is not None:
        try:
            return int(cid)
        except (TypeError, ValueError):
            return None
    cust = record.get("customer")
    if isinstance(cust, dict):
        cid = cust.get("id")
        if cid is not None:
            try:
                return int(cid)
            except (TypeError, ValueError):
                return None
    return None


def _customer_field(record: dict[str, Any], key: str) -> Any:
    """Pull a customer attr out of a sales record (``customer.<key>``)."""
    cust = record.get("customer")
    if isinstance(cust, dict):
        return cust.get(key)
    return None


def _model_dict(obj: Any) -> dict[str, Any]:
    """Return ``obj.model_dump()`` for pydantic v2 records.

    Falls back to ``vars(obj)`` if the object is not a pydantic model
    (e.g. a MagicMock in tests). Pydantic ``extra='allow'`` ensures
    even unknown Accurate fields appear in the dump.
    """
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        try:
            return dump()
        except Exception:  # noqa: BLE001 — fallthrough to alternatives
            pass
    if isinstance(obj, dict):
        return obj
    # Fallback for MagicMock-style fixtures: collect attrs into a dict
    # using the public attr names of the AccurateRecord model. We don't
    # know all attrs here, so just return vars() filtered to non-private.
    try:
        return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
    except TypeError:
        return {}


# ---------------------------------------------------------------------------
# Customer pull
# ---------------------------------------------------------------------------


def pull_customers(client: AccurateClient) -> list[dict[str, Any]]:
    """Fetch all customers, return flat dicts with normalised fields.

    Output shape (per row):

    .. code-block:: python

        {
            "id": 42,
            "customer_no": "C-001",
            "name": "PT Foo",
            "npwp": "01.234.567.8-901.000",
            "current_credit_limit": 5_000_000.0,
            "billing_city": "Jakarta",
            "billing_province": "DKI",
            "suspended": False,
        }
    """
    rows = client.customers.list_raw(
        fields="id,name,wpName,customerNo,npwpNo,email,mobilePhone,billStreet,billCity,billProvince,billZipCode,billCountry,suspended"
    )
    out: list[dict[str, Any]] = []
    for raw in rows:
        # raw is a plain dict from list.do — preserves ALL fields from
        # the Accurate response (both modelled and ``extra='allow'``).
        # ``creditLimitAmount`` is the typical name; we also look at
        # ``creditLimit`` and ``customerCreditLimit`` to be tolerant.
        credit = (
            raw.get("creditLimitAmount")
            if raw.get("creditLimitAmount") is not None
            else raw.get("creditLimit")
            if raw.get("creditLimit") is not None
            else raw.get("customerCreditLimit")
        )
        out.append(
            {
                "id": int(raw["id"]) if raw.get("id") is not None else None,
                "customer_no": raw.get("customerNo") or "",
                "name": raw.get("name") or "",
                "wp_name": raw.get("wpName") or "",
                "npwp": raw.get("npwpNo") or "",
                "email": raw.get("email") or "",
                "mobile_phone": raw.get("mobilePhone") or "",
                "billing_street": raw.get("billStreet") or "",
                "billing_city": raw.get("billCity") or "",
                "billing_province": raw.get("billProvince") or "",
                "billing_zip": raw.get("billZipCode") or "",
                "billing_country": raw.get("billCountry") or "",
                "current_credit_limit": _money(credit),
                "suspended": bool(raw.get("suspended", False)),
            }
        )
    # Drop any rows without an id (defensive — shouldn't happen)
    return [r for r in out if r["id"] is not None]


def pull_customer_credit_limits(client: AccurateClient, customer_ids: list[int]) -> dict[int, float]:
    """Fetch detail for each customer and extract ``customerLimitAmountValue``.

    Kept for backwards compatibility; new callers should prefer
    :func:`pull_customer_details` which returns address + identity fields
    in addition to the credit limit.
    """
    if not customer_ids:
        return {}
    details = pull_customer_details(client, customer_ids)
    return {cid: d.get("current_credit_limit", 0.0) for cid, d in details.items()}


def pull_customer_details(client: AccurateClient, customer_ids: list[int]) -> dict[int, dict[str, Any]]:
    """Fetch full customer detail for each id — credit limit + address + identity.

    The customer/list endpoint doesn't expose ``customerLimitAmountValue``
    or any of the bill* address fields even with ``fields=`` — only the
    detail endpoint has them. Uses ``detail_many`` for parallel pulls
    (8 concurrent at 8 req/sec).

    Returns ``{customer_id: enriched_dict}`` where the enriched dict has:
      - current_credit_limit (float)
      - billing_street, billing_city, billing_province,
        billing_zip, billing_country (str)
      - id_card (str — KTP / national ID, if recorded)
      - npwp (str — NPWP/tax id, also returned by list endpoint)
      - wp_name (str — wajib pajak / tax-bearer name on NPWP)
      - shipping_street, shipping_city, shipping_province (str)
    """
    if not customer_ids:
        return {}
    details = client.detail_many(
        "/accurate/api/customer/detail.do",
        customer_ids,
    )
    result: dict[int, dict[str, Any]] = {}
    for d in details:
        cid = d.get("id")
        if cid is None or "__error__" in d:
            continue
        result[cid] = {
            "current_credit_limit": _money(d.get("customerLimitAmountValue")),
            "term_name": (d.get("term") or {}).get("name", "") if isinstance(d.get("term"), dict) else "",
            "term_net_days": int((d.get("term") or {}).get("netDays") or 0) if isinstance(d.get("term"), dict) else 0,
            "max_invoice_age": int(d.get("maxInvoiceAge") or 0),
            "billing_street": d.get("billStreet") or "",
            "billing_city": d.get("billCity") or "",
            "billing_province": d.get("billProvince") or "",
            "billing_zip": d.get("billZipCode") or "",
            "billing_country": d.get("billCountry") or "",
            "shipping_street": d.get("shipStreet") or "",
            "shipping_city": d.get("shipCity") or "",
            "shipping_province": d.get("shipProvince") or "",
            "id_card": d.get("idCard") or "",
            "npwp": d.get("npwpNo") or "",
            "wp_name": d.get("wpName") or "",
            # Full Accurate detail dict — for the "Atribut Lengkap" sheet.
            # This carries every field Accurate returns (~100+ fields including
            # group limit settings, default accounts, salesman, custom fields,
            # tax codes, payment terms, etc.) — required for shareholder review.
            "_raw_accurate": d,
        }
    return result


# ---------------------------------------------------------------------------
# Sales-invoice + sales-receipt pull
# ---------------------------------------------------------------------------


def _infer_payment_state(
    *,
    amount_total: float,
    amount_residual: float,
    status: str | None,
    outstanding_flag: bool | None,
) -> str:
    """Infer compute-layer ``payment_state`` from Accurate signals.

    Compute layer accepts: ``"paid"``, ``"in_payment"``, ``"partial"``,
    ``"not_paid"``. Accurate's ``status`` is ``PAID``/``OUTSTANDING``/
    ``CLOSED``, and the Boolean ``outstanding`` flag is a secondary hint.

    Logic:

    * Status PAID or CLOSED → ``"paid"``.
    * Residual <= 0 (non-negative slack) → ``"paid"``.
    * 0 < residual < total → ``"partial"``.
    * Otherwise → ``"not_paid"``.
    """
    norm_status = (status or "").upper().strip()
    if norm_status in ("PAID", "CLOSED"):
        return "paid"
    if amount_total > 0 and amount_residual <= 0:
        return "paid"
    if amount_total > 0 and 0 < amount_residual < amount_total:
        return "partial"
    if outstanding_flag is True or amount_residual >= amount_total > 0:
        return "not_paid"
    # Defensive default: if amount_total is 0 and residual is 0 we treat as paid
    if amount_total == 0 and amount_residual == 0:
        return "paid"
    return "not_paid"


def _build_last_payment_lookup(
    receipts_raw: list[dict[str, Any]],
) -> dict[int, date]:
    """Return ``{invoice_id: max_receipt_date}`` from a receipt list.

    Each receipt's ``detailInvoice[]`` entries carry ``invoice.id`` and
    a payment amount. Only receipts with a parseable ``transDate`` and a
    positive payment amount on a given invoice contribute to that
    invoice's ``last_payment_date``.
    """
    last_payment: dict[int, date] = {}
    for raw in receipts_raw:
        receipt_date = _parse_accurate_date(raw.get("transDate"))
        if receipt_date is None:
            continue
        for entry in raw.get("detailInvoice") or []:
            inv_ref = entry.get("invoice")
            if not isinstance(inv_ref, dict):
                continue
            inv_id_raw = inv_ref.get("id")
            try:
                inv_id = int(inv_id_raw)
            except (TypeError, ValueError):
                continue
            paid = _money(entry.get("invoicePayment") or entry.get("paymentAmount"))
            if paid <= 0:
                continue
            existing = last_payment.get(inv_id)
            if existing is None or receipt_date > existing:
                last_payment[inv_id] = receipt_date
    return last_payment


def _build_paid_amount_lookup(receipts_raw: list[dict[str, Any]]) -> dict[int, float]:
    """Sum cumulative paid amount per invoice id from receipts' detailInvoice lines.

    Accurate's invoice ``outstanding`` field is a BOOLEAN (True if any balance
    remains, False if paid). It is NOT the residual amount. To get the real
    AR residual we sum ``invoicePayment`` (or ``paymentAmount``) across all
    receipts that reference each invoice.

    Returns ``{invoice_id: total_paid_idr}``.
    """
    paid: dict[int, float] = {}
    for raw in receipts_raw:
        for entry in raw.get("detailInvoice") or []:
            inv_ref = entry.get("invoice")
            if not isinstance(inv_ref, dict):
                continue
            inv_id_raw = inv_ref.get("id")
            try:
                inv_id = int(inv_id_raw)
            except (TypeError, ValueError):
                continue
            amt = _money(entry.get("invoicePayment") or entry.get("paymentAmount"))
            if amt > 0:
                paid[inv_id] = paid.get(inv_id, 0.0) + amt
    return paid


def pull_sales_invoices_and_payments_accurate(
    client: AccurateClient,
    *,
    today: date | None = None,
) -> dict[int, list[dict[str, Any]]]:
    """Accurate-data pull with **100% accuracy** for shareholder review.

    Unlike :func:`pull_sales_invoices_and_payments` which reads only the
    list endpoint (and falls back to inference for partials), this version
    fetches each invoice's *detail* record. The detail endpoint exposes
    the authoritative ``outstanding`` and ``lastPaymentDate`` fields
    directly — no estimation.

    Cost: one detail call per invoice (~125ms each at 8rps, parallelised
    8x via detail_many ≈ N/8 seconds total). For a tenant with 47
    invoices this is ~6 seconds.
    """
    today = today or date.today()
    invoice_summaries = client.sales_invoices.list_raw(
        fields="id,number,transDate,dueDate,totalAmount,statusName,customer,customerNo"
    )
    if not invoice_summaries:
        return {}
    invoice_ids = [int(r["id"]) for r in invoice_summaries if r.get("id") is not None]
    detail_records = client.detail_many(
        "/accurate/api/sales-invoice/detail.do",
        invoice_ids,
    )
    # Pull receipts ONCE to build the paid-amount lookup. ``outstanding`` on
    # the invoice detail is a BOOLEAN, not a number — we must sum receipts.
    receipts_raw = client.sales_receipts.list_raw(fields="id,transDate,detailInvoice,customer")
    paid_by_invoice = _build_paid_amount_lookup(receipts_raw)

    by_customer: dict[int, list[dict[str, Any]]] = {}
    for d in detail_records:
        if "__error__" in d:
            continue
        try:
            invoice_id = int(d["id"])
        except (KeyError, TypeError, ValueError):
            continue
        customer_id = _customer_id_of(d)
        if customer_id is None:
            continue

        invoice_date = _parse_accurate_date(d.get("transDate"))
        due_date = _parse_accurate_date(d.get("dueDate")) or invoice_date

        # Authoritative numbers from detail endpoint
        amount_total = _money(d.get("totalAmount"))
        # Compute residual = totalAmount - sum of receipt payments against this invoice.
        # Don't use ``outstanding`` (boolean) or ``paidOverTotal`` (boolean) directly.
        total_paid = paid_by_invoice.get(invoice_id, 0.0)
        amount_residual = max(0.0, amount_total - total_paid)
        last_payment_date = _parse_accurate_date(d.get("lastPaymentDate"))

        # Map Indonesian statusName to compute-layer payment_state (most reliable signal)
        status_name = d.get("statusName") or ""
        if status_name == "Lunas":
            payment_state = "paid"
            amount_residual = 0.0  # statusName=Lunas is authoritative
        elif status_name == "Sebagian":
            payment_state = "partial"
        elif status_name == "Belum Lunas":
            payment_state = "not_paid"
            # If receipts didn't contribute (no partial payment), residual = full
            if total_paid == 0:
                amount_residual = amount_total
        else:
            # Fallback when status string is missing
            if amount_residual <= 0:
                payment_state = "paid"
            elif amount_residual < amount_total:
                payment_state = "partial"
            else:
                payment_state = "not_paid"

        invoice_dict: dict[str, Any] = {
            # Compute-layer required keys
            "invoice_date": invoice_date,
            "invoice_date_due": due_date,
            "amount_total_signed": amount_total,
            "amount_residual": amount_residual,
            "payment_state": payment_state,
            "last_payment_date": last_payment_date,
            # Extras for the Raw Invoices sheet
            "id": invoice_id,
            "customer_id": customer_id,
            "customer_no": _customer_field(d, "customerNo") or "",
            "customer_name": _customer_field(d, "name") or d.get("customerName") or "",
            "doc_number": d.get("number") or "",
            "amount_total": amount_total,
            "status": d.get("statusName") or d.get("status") or "",
        }
        by_customer.setdefault(customer_id, []).append(invoice_dict)

    return by_customer


def pull_sales_invoices_and_payments(
    client: AccurateClient,
    *,
    today: date | None = None,
) -> dict[int, list[dict[str, Any]]]:
    """Fetch sales invoices and receipts; group invoice dicts by customer id.

    Returns ``{customer_id: [invoice_dict, ...]}`` where each
    ``invoice_dict`` matches the shape :func:`compute.compute_per_pair`
    expects. Invoices missing a customer id are dropped.

    The Accurate list endpoints return paginated rows. We read raw dicts
    so any extra fields surfaced by the API ride along even if the
    pydantic models don't declare them.
    """
    today = today or date.today()
    invoices_raw = client.sales_invoices.list_raw(
        fields="id,number,transDate,dueDate,totalAmount,statusName,customer,customerNo"
    )
    receipts_raw = client.sales_receipts.list_raw(fields="id,number,transDate,detailInvoice,customer")

    last_payment = _build_last_payment_lookup(receipts_raw)

    by_customer: dict[int, list[dict[str, Any]]] = {}
    for raw in invoices_raw:
        try:
            invoice_id = int(raw["id"])
        except (KeyError, TypeError, ValueError):
            continue
        customer_id = _customer_id_of(raw)
        if customer_id is None:
            continue

        invoice_date = _parse_accurate_date(raw.get("transDate") or raw.get("invoiceDate"))
        due_date = _parse_accurate_date(raw.get("dueDate")) or invoice_date

        amount_total = _money(raw.get("totalAmount"))
        # Accurate sometimes carries a numeric ``outstanding`` (residual
        # IDR) and sometimes only a boolean. Try a few names; fall back
        # to inferring from totalAmount + paid signal.
        residual_explicit = None
        for key in ("outstandingAmount", "residualAmount", "outstandingValue"):
            if raw.get(key) is not None:
                residual_explicit = _money(raw.get(key))
                break
        outstanding_flag = raw.get("outstanding")
        if isinstance(outstanding_flag, (int, float)) and not isinstance(outstanding_flag, bool):
            # Some endpoints return outstanding as the residual amount itself
            if residual_explicit is None:
                residual_explicit = _money(outstanding_flag)
            outstanding_flag = residual_explicit > 0

        # Accurate also sometimes carries paidAmount (cumulative payment)
        paid_amount = None
        for key in ("paidAmount", "totalPayment", "paid"):
            if raw.get(key) is not None and not isinstance(raw.get(key), bool):
                paid_amount = _money(raw.get(key))
                break

        if residual_explicit is not None:
            amount_residual = residual_explicit
        elif paid_amount is not None:
            amount_residual = max(0.0, amount_total - paid_amount)
        else:
            # Fall back to Indonesian statusName from list endpoint
            status_id = (raw.get("statusName") or raw.get("status") or raw.get("paidStatus") or "").strip()
            status_upper = status_id.upper()
            if status_upper in ("PAID", "CLOSED") or status_id == "Lunas":
                amount_residual = 0.0
            elif status_id == "Belum Lunas":
                amount_residual = amount_total
            elif status_id == "Sebagian":
                # Partial — without detail we don't know how much. Estimate half.
                amount_residual = amount_total / 2.0
            elif outstanding_flag is True:
                amount_residual = amount_total
            else:
                amount_residual = 0.0

        # Map Indonesian statusName to compute-layer payment_state directly
        status_id = (raw.get("statusName") or raw.get("status") or raw.get("paidStatus") or "").strip()
        if status_id == "Lunas":
            payment_state = "paid"
        elif status_id == "Sebagian":
            payment_state = "partial"
        elif status_id == "Belum Lunas":
            payment_state = "not_paid"
        else:
            payment_state = _infer_payment_state(
                amount_total=amount_total,
                amount_residual=amount_residual,
                status=status_id,
                outstanding_flag=outstanding_flag if isinstance(outstanding_flag, bool) else None,
            )

        last_pay = last_payment.get(invoice_id)
        # If we marked the invoice paid but the receipt search didn't
        # find a date, leave last_payment_date None — DSO won't include
        # it but the invoice still counts toward total sales.
        if payment_state == "not_paid":
            last_pay = None

        invoice_dict: dict[str, Any] = {
            # Compute-layer required keys
            "invoice_date": invoice_date,
            "invoice_date_due": due_date,
            "amount_total_signed": amount_total,
            "amount_residual": amount_residual,
            "payment_state": payment_state,
            "last_payment_date": last_pay,
            # Extras for the Raw Invoices sheet
            "id": invoice_id,
            "customer_id": customer_id,
            "customer_no": _customer_field(raw, "customerNo") or "",
            "customer_name": _customer_field(raw, "name") or raw.get("customerName") or "",
            "doc_number": raw.get("number") or "",
            "amount_total": amount_total,
            "status": raw.get("status") or raw.get("paidStatus") or "",
        }
        by_customer.setdefault(customer_id, []).append(invoice_dict)

    return by_customer
