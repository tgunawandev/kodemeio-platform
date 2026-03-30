"""Full instance diagnostic report with health scoring.

Runs 10 independent diagnostic sections, scores each 0-100, and produces
an overall weighted health score.  Outputs to terminal, JSON, Markdown, or
HTML.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Instance diagnostics and health reporting.")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    severity: str  # critical, high, medium, low, info
    area: str
    title: str
    detail: str
    fix_command: str | None = None


@dataclass
class SectionResult:
    name: str
    score: int  # 0-100
    findings: list[Finding] = field(default_factory=list)
    duration_ms: int = 0


@dataclass
class DiagnosticReport:
    profile: str
    url: str
    version: str
    database: str
    timestamp: datetime
    sections: list[SectionResult]
    overall_score: int
    duration_seconds: float

    # -- serialisation helpers ------------------------------------------------

    def to_dict(self) -> dict:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)

    def to_markdown(self) -> str:
        lines = [
            "# Diagnostic Report",
            "",
            f"**Profile:** {self.profile}  ",
            f"**URL:** {self.url}  ",
            f"**Database:** {self.database}  ",
            f"**Version:** {self.version}  ",
            f"**Timestamp:** {self.timestamp.isoformat()}  ",
            f"**Overall Score:** {self.overall_score}/100  ",
            f"**Duration:** {self.duration_seconds:.1f}s  ",
            "",
            "## Section Scores",
            "",
            "| Section | Score | Duration |",
            "|---------|------:|----------:|",
        ]
        for s in self.sections:
            lines.append(f"| {s.name} | {s.score} | {s.duration_ms}ms |")

        critical = [f for s in self.sections for f in s.findings if f.severity in ("critical", "high")]
        if critical:
            lines += ["", "## Critical / High Findings", ""]
            for f in critical:
                cmd = f"  - Fix: `{f.fix_command}`" if f.fix_command else ""
                lines.append(f"- **[{f.severity.upper()}]** {f.area} / {f.title}: {f.detail}{cmd}")

        medium = [f for s in self.sections for f in s.findings if f.severity == "medium"]
        if medium:
            lines += ["", "## Medium Findings", ""]
            for f in medium:
                lines.append(f"- {f.area} / {f.title}: {f.detail}")

        lines.append("")
        return "\n".join(lines)

    def to_html(self) -> str:
        score_color = "#22c55e" if self.overall_score >= 75 else "#eab308" if self.overall_score >= 50 else "#ef4444"
        rows_html = ""
        for s in self.sections:
            sc = "#22c55e" if s.score >= 75 else "#eab308" if s.score >= 50 else "#ef4444"
            rows_html += (
                f"<tr><td>{s.name}</td>"
                f"<td style='color:{sc};font-weight:bold'>{s.score}</td>"
                f"<td>{s.duration_ms}ms</td></tr>\n"
            )

        findings_html = ""
        for s in self.sections:
            for f in s.findings:
                if f.severity in ("critical", "high", "medium"):
                    sev_col = "#ef4444" if f.severity in ("critical", "high") else "#eab308"
                    fix = f"<br><code>{f.fix_command}</code>" if f.fix_command else ""
                    findings_html += (
                        f"<tr><td style='color:{sev_col}'>{f.severity.upper()}</td>"
                        f"<td>{f.area}</td><td>{f.title}</td><td>{f.detail}{fix}</td></tr>\n"
                    )

        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Diagnostic Report</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#1e293b}}
h1{{border-bottom:2px solid #3b82f6;padding-bottom:.5rem}}
table{{border-collapse:collapse;width:100%;margin:1rem 0}}
th,td{{border:1px solid #e2e8f0;padding:.5rem .75rem;text-align:left}}
th{{background:#f1f5f9}}
.score{{font-size:3rem;font-weight:bold;color:{score_color};text-align:center;margin:1rem 0}}
.meta{{color:#64748b;font-size:.9rem}}
code{{background:#f1f5f9;padding:.1rem .3rem;border-radius:3px;font-size:.85rem}}
</style></head><body>
<h1>Odoo Diagnostic Report</h1>
<div class="meta">Profile: {self.profile} | Database: {self.database} | Version: {self.version}<br>
{self.timestamp.isoformat()} | Duration: {self.duration_seconds:.1f}s</div>
<div class="score">{self.overall_score}/100</div>
<h2>Section Scores</h2>
<table><tr><th>Section</th><th>Score</th><th>Duration</th></tr>
{rows_html}</table>
<h2>Findings</h2>
<table><tr><th>Severity</th><th>Area</th><th>Title</th><th>Detail</th></tr>
{findings_html}</table>
</body></html>"""


# ---------------------------------------------------------------------------
# Weights for overall score
# ---------------------------------------------------------------------------

WEIGHTS: dict[str, int] = {
    "server_health": 10,
    "configuration": 10,
    "security": 15,
    "data_integrity": 15,
    "financial_health": 15,
    "inventory_health": 10,
    "kpis": 10,
    "mail": 5,
    "storage": 5,
    "dr": 5,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_count(c: object, model: str, domain: list | None = None) -> int | None:
    """search_count returning None when the model does not exist."""
    try:
        return c.search_count(model, domain or [])  # type: ignore[attr-defined]
    except RPCError:
        return None


def _timed(fn, *args, **kwargs) -> tuple:
    """Run *fn* and return (result, elapsed_ms)."""
    t0 = time.monotonic()
    result = fn(*args, **kwargs)
    return result, round((time.monotonic() - t0) * 1000)


def _deduct(base: int, penalty: int, count: int, *, cap: int = 100) -> int:
    """Subtract *penalty* per *count*, floor at 0, cap at *cap*."""
    return max(0, min(cap, base - penalty * count))


# ---------------------------------------------------------------------------
# Section check functions
# ---------------------------------------------------------------------------


def _check_server_health(c: object, *, quick: bool = False) -> SectionResult:
    """1. Server health — version info + RPC latency."""
    findings: list[Finding] = []
    try:
        t0 = time.monotonic()
        ver = c.version_info()  # type: ignore[attr-defined]
        latency_ms = round((time.monotonic() - t0) * 1000)

        version = ver.get("server_version", "unknown")
        findings.append(Finding("info", "server", "Odoo version", version))

        # Latency scoring
        if latency_ms > 2000:
            findings.append(Finding("high", "server", "High RPC latency", f"{latency_ms}ms (>2000ms)"))
            score = 40
        elif latency_ms > 1000:
            findings.append(Finding("medium", "server", "Elevated RPC latency", f"{latency_ms}ms"))
            score = 70
        else:
            score = 100

        # Benchmark: 3 additional calls if not quick
        if not quick:
            latencies = [latency_ms]
            for _ in range(3):
                t1 = time.monotonic()
                c.version_info()  # type: ignore[attr-defined]
                latencies.append(round((time.monotonic() - t1) * 1000))
            avg = sum(latencies) // len(latencies)
            findings.append(Finding("info", "server", "Avg RPC latency (4 calls)", f"{avg}ms"))
            if avg > 2000:
                score = min(score, 40)

        return SectionResult("server_health", score, findings)
    except Exception as exc:
        return SectionResult("server_health", 0, [Finding("critical", "server", "Server unreachable", str(exc))])


def _check_configuration(c: object, **_kw) -> SectionResult:
    """2. Configuration — web.base.url, SMTP, UUID, lock dates, etc."""
    findings: list[Finding] = []
    score = 100
    try:

        def _param(key: str) -> str | None:
            rows = c.search_read(  # type: ignore[attr-defined]
                "ir.config_parameter", [("key", "=", key)], ["value"], limit=1
            )
            return rows[0]["value"] if rows else None

        # web.base.url
        base_url = _param("web.base.url") or ""
        if not base_url:
            findings.append(Finding("high", "config", "web.base.url not set", "Set web.base.url in System Parameters"))
            score -= 15
        elif base_url == "http://localhost:8069":
            findings.append(Finding("medium", "config", "web.base.url is default", base_url))
            score -= 5

        # UUID
        db_uuid = _param("database.uuid")
        if not db_uuid:
            findings.append(Finding("medium", "config", "Database UUID missing", "No database.uuid parameter"))
            score -= 5

        # SMTP
        smtp_count = _safe_count(c, "ir.mail_server", [("active", "=", True)])
        if smtp_count is not None and smtp_count == 0:
            findings.append(
                Finding(
                    "high",
                    "config",
                    "No active SMTP server",
                    "Configure outgoing mail",
                    fix_command="kctl-odoo server mail-outgoing",
                )
            )
            score -= 15

        # Lock dates
        try:
            companies = c.search_read("res.company", [], ["fiscalyear_lock_date", "period_lock_date"], limit=5)  # type: ignore[attr-defined]
            no_lock = [co for co in companies if not co.get("fiscalyear_lock_date") and not co.get("period_lock_date")]
            if no_lock:
                findings.append(
                    Finding("medium", "config", "No lock dates set", f"{len(no_lock)} company(ies) without lock dates")
                )
                score -= 5
        except RPCError:
            pass

        return SectionResult("configuration", max(0, score), findings)
    except Exception as exc:
        return SectionResult("configuration", 0, [Finding("critical", "config", "Config check failed", str(exc))])


def _check_security(c: object, **_kw) -> SectionResult:
    """3. Security — admin count, stale users, ACL gaps, HTTPS, passwords."""
    findings: list[Finding] = []
    score = 100
    try:
        # Admin count
        try:
            admin_groups = c.search_read(  # type: ignore[attr-defined]
                "res.groups",
                [("category_id.name", "=", "Administration"), ("name", "ilike", "Settings")],
                ["users"],
                limit=1,
            )
            admin_count = len(admin_groups[0]["users"]) if admin_groups else 0
            if admin_count > 5:
                findings.append(Finding("high", "security", "Too many admins", f"{admin_count} admin users"))
                score -= 15
            elif admin_count > 3:
                findings.append(Finding("medium", "security", "Many admins", f"{admin_count} admin users"))
                score -= 5
        except RPCError:
            pass

        # Stale users (90d)
        cutoff_90d = (datetime.now(tz=UTC) - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")
        stale = _safe_count(
            c,
            "res.users",
            [
                ("active", "=", True),
                ("share", "=", False),
                "|",
                ("login_date", "=", False),
                ("login_date", "<", cutoff_90d),
            ],
        )
        if stale and stale > 0:
            findings.append(
                Finding(
                    "medium",
                    "security",
                    "Stale users",
                    f"{stale} users inactive >90d",
                    fix_command="kctl-odoo security compliance",
                )
            )
            score -= min(10, stale * 2)

        # HTTPS
        try:
            url_rows = c.search_read(  # type: ignore[attr-defined]
                "ir.config_parameter", [("key", "=", "web.base.url")], ["value"], limit=1
            )
            base_url = url_rows[0]["value"] if url_rows else ""
            if base_url and not base_url.startswith("https://") and "localhost" not in base_url:
                findings.append(Finding("high", "security", "No HTTPS", base_url))
                score -= 15
        except RPCError:
            pass

        # Signup scope
        try:
            sp = c.search_read(  # type: ignore[attr-defined]
                "ir.config_parameter", [("key", "=", "auth_signup.invitation_scope")], ["value"], limit=1
            )
            scope = sp[0]["value"] if sp else "b2b"
            if scope == "b2c":
                findings.append(
                    Finding("medium", "security", "Public signup enabled", "auth_signup.invitation_scope=b2c")
                )
                score -= 5
        except RPCError:
            pass

        return SectionResult("security", max(0, score), findings)
    except Exception as exc:
        return SectionResult("security", 0, [Finding("critical", "security", "Security check failed", str(exc))])


def _check_data_integrity(c: object, *, quick: bool = False, **_kw) -> SectionResult:
    """4. Data integrity — draft entries, unreconciled items, negative stock."""
    findings: list[Finding] = []
    score = 100
    try:
        now = datetime.now(tz=UTC)

        # Draft journal entries
        draft_entries = _safe_count(c, "account.move", [("state", "=", "draft")])
        if draft_entries is not None and draft_entries > 50:
            findings.append(Finding("medium", "data", "Many draft entries", f"{draft_entries} draft journal entries"))
            score -= 10

        # Overdue AR
        overdue = _safe_count(
            c,
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("payment_state", "in", ["not_paid", "partial"]),
                ("invoice_date_due", "<", now.strftime("%Y-%m-%d")),
            ],
        )
        if overdue is not None and overdue > 0:
            sev = "high" if overdue > 20 else "medium"
            findings.append(Finding(sev, "data", "Overdue AR invoices", f"{overdue} overdue"))
            score -= min(20, overdue)

        # Overdue AP
        overdue_ap = _safe_count(
            c,
            "account.move",
            [
                ("move_type", "=", "in_invoice"),
                ("state", "=", "posted"),
                ("payment_state", "in", ["not_paid", "partial"]),
                ("invoice_date_due", "<", now.strftime("%Y-%m-%d")),
            ],
        )
        if overdue_ap is not None and overdue_ap > 0:
            findings.append(Finding("medium", "data", "Overdue AP bills", f"{overdue_ap} overdue"))
            score -= min(10, overdue_ap // 2)

        # Negative stock (quick check)
        neg_stock = _safe_count(c, "stock.quant", [("quantity", "<", 0), ("location_id.usage", "=", "internal")])
        if neg_stock is not None and neg_stock > 0:
            findings.append(
                Finding(
                    "high",
                    "data",
                    "Negative stock",
                    f"{neg_stock} quants with negative qty",
                    fix_command="kctl-odoo maintenance inventory-close",
                )
            )
            score -= min(20, neg_stock * 5)

        return SectionResult("data_integrity", max(0, score), findings)
    except Exception as exc:
        return SectionResult("data_integrity", 0, [Finding("critical", "data", "Integrity check failed", str(exc))])


def _check_financial_health(c: object, *, quick: bool = False, **_kw) -> SectionResult:
    """5. Financial health — trial balance, draft invoices, bank recon, suspense."""
    findings: list[Finding] = []
    score = 100
    try:
        now = datetime.now(tz=UTC)
        year_start = f"{now.year}-01-01"

        # Trial balance check (current year posted lines)
        if not quick:
            try:
                lines = c.search_read(  # type: ignore[attr-defined]
                    "account.move.line",
                    [("parent_state", "=", "posted"), ("date", ">=", year_start)],
                    ["debit", "credit"],
                    limit=0,
                )
                total_d = sum(line.get("debit", 0) for line in lines)
                total_c = sum(line.get("credit", 0) for line in lines)
                diff = abs(total_d - total_c)
                if diff > 0.01:
                    findings.append(
                        Finding("critical", "finance", "Trial balance mismatch", f"Debit-Credit diff: {diff:,.2f}")
                    )
                    score -= 30
            except RPCError:
                pass

        # Draft invoices
        draft_inv = _safe_count(
            c,
            "account.move",
            [
                ("state", "=", "draft"),
                ("move_type", "in", ["out_invoice", "in_invoice", "out_refund", "in_refund"]),
            ],
        )
        if draft_inv is not None and draft_inv > 20:
            findings.append(Finding("medium", "finance", "Many draft invoices", f"{draft_inv} draft invoices/bills"))
            score -= 10

        # Bank reconciliation
        unrecon = _safe_count(c, "account.bank.statement.line", [("is_reconciled", "=", False)])
        if unrecon is not None and unrecon > 0:
            sev = "high" if unrecon > 50 else "medium"
            findings.append(Finding(sev, "finance", "Unreconciled bank lines", f"{unrecon} lines"))
            score -= min(20, unrecon // 5)

        # Suspense accounts
        try:
            suspense = c.search_read(  # type: ignore[attr-defined]
                "account.account", [("name", "ilike", "suspense")], ["id", "name"], limit=5
            )
            for sa in suspense:
                sa_lines = c.search_read(  # type: ignore[attr-defined]
                    "account.move.line",
                    [("account_id", "=", sa["id"]), ("parent_state", "=", "posted")],
                    ["debit", "credit"],
                    limit=0,
                )
                bal = sum(line.get("debit", 0) - line.get("credit", 0) for line in sa_lines)
                if abs(bal) > 0.01:
                    findings.append(
                        Finding("high", "finance", f"Suspense balance: {sa['name']}", f"Balance: {bal:,.2f}")
                    )
                    score -= 10
        except RPCError:
            pass

        return SectionResult("financial_health", max(0, score), findings)
    except Exception as exc:
        return SectionResult("financial_health", 0, [Finding("critical", "finance", "Finance check failed", str(exc))])


def _check_inventory_health(c: object, *, quick: bool = False, **_kw) -> SectionResult:
    """6. Inventory health — negative stock, stuck transfers, valuation."""
    findings: list[Finding] = []
    score = 100
    try:
        now = datetime.now(tz=UTC)

        # Negative stock
        neg = _safe_count(c, "stock.quant", [("quantity", "<", 0), ("location_id.usage", "=", "internal")])
        if neg is None:
            # stock module not installed
            return SectionResult(
                "inventory_health", 100, [Finding("info", "inventory", "Stock not installed", "Skipped")]
            )
        if neg > 0:
            findings.append(Finding("high", "inventory", "Negative stock", f"{neg} quants"))
            score -= min(25, neg * 5)

        # Stuck transfers (>7d)
        cutoff_7d = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        stuck = _safe_count(
            c,
            "stock.picking",
            [
                ("state", "in", ["waiting", "confirmed"]),
                ("scheduled_date", "<", cutoff_7d),
            ],
        )
        if stuck and stuck > 0:
            findings.append(Finding("medium", "inventory", "Stuck transfers", f"{stuck} transfers >7d old"))
            score -= min(15, stuck * 3)

        # Valuation mismatch (skip in quick mode)
        if not quick:
            try:
                layers = c.search_read(  # type: ignore[attr-defined]
                    "stock.valuation.layer", [("company_id", "!=", False)], ["value"], limit=0
                )
                layer_total = sum(line.get("value", 0) for line in layers)
                stock_accts = c.search_read(  # type: ignore[attr-defined]
                    "account.account",
                    [("account_type", "=", "asset_current"), ("name", "ilike", "stock valuation")],
                    ["id"],
                    limit=5,
                )
                gl_total = 0.0
                for sa in stock_accts:
                    gl_lines = c.search_read(  # type: ignore[attr-defined]
                        "account.move.line",
                        [("account_id", "=", sa["id"]), ("parent_state", "=", "posted")],
                        ["debit", "credit"],
                        limit=0,
                    )
                    gl_total += sum(line.get("debit", 0) - line.get("credit", 0) for line in gl_lines)
                diff = abs(layer_total - gl_total)
                if diff > 1.0:
                    findings.append(
                        Finding(
                            "high",
                            "inventory",
                            "Valuation vs GL mismatch",
                            f"Layer: {layer_total:,.2f}, GL: {gl_total:,.2f}, Diff: {diff:,.2f}",
                        )
                    )
                    score -= 20
            except RPCError:
                pass

        return SectionResult("inventory_health", max(0, score), findings)
    except Exception as exc:
        return SectionResult(
            "inventory_health", 0, [Finding("critical", "inventory", "Inventory check failed", str(exc))]
        )


def _check_kpis(c: object, **_kw) -> SectionResult:
    """7. KPIs — fulfillment, AR aging, email health, data quality."""
    findings: list[Finding] = []
    score = 100
    kpi_count = 0
    kpi_pass = 0
    try:
        now = datetime.now(tz=UTC)

        # Order fulfillment
        confirmed_so = _safe_count(c, "sale.order", [("state", "=", "sale")])
        if confirmed_so is not None and confirmed_so > 0:
            kpi_count += 1
            so_done = _safe_count(c, "sale.order", [("state", "=", "sale"), ("picking_ids.state", "=", "done")]) or 0
            rate = (so_done / confirmed_so) * 100
            if rate >= 80:
                kpi_pass += 1
            else:
                findings.append(Finding("medium", "kpi", "Low order fulfillment", f"{rate:.0f}%"))

        # AR aging >30d
        total_recv = _safe_count(
            c,
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("payment_state", "in", ["not_paid", "partial"]),
            ],
        )
        if total_recv is not None and total_recv > 0:
            kpi_count += 1
            cutoff_30d = (now - timedelta(days=30)).strftime("%Y-%m-%d")
            overdue = (
                _safe_count(
                    c,
                    "account.move",
                    [
                        ("move_type", "=", "out_invoice"),
                        ("state", "=", "posted"),
                        ("payment_state", "in", ["not_paid", "partial"]),
                        ("invoice_date_due", "<", cutoff_30d),
                    ],
                )
                or 0
            )
            ar_pct = (overdue / total_recv) * 100
            if ar_pct <= 20:
                kpi_pass += 1
            else:
                findings.append(Finding("medium", "kpi", "High AR aging", f"{ar_pct:.0f}% receivables >30d"))

        # Email health (24h)
        total_mail_24h = _safe_count(
            c, "mail.mail", [("create_date", ">=", (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S"))]
        )
        if total_mail_24h is not None and total_mail_24h > 0:
            kpi_count += 1
            failed_mail = (
                _safe_count(
                    c,
                    "mail.mail",
                    [
                        ("create_date", ">=", (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")),
                        ("state", "=", "exception"),
                    ],
                )
                or 0
            )
            fail_rate = (failed_mail / total_mail_24h) * 100
            if fail_rate <= 5:
                kpi_pass += 1
            else:
                findings.append(Finding("medium", "kpi", "Email failure rate", f"{fail_rate:.0f}%"))

        # Data quality
        total_prods = _safe_count(c, "product.template", [("sale_ok", "=", True)])
        if total_prods is not None and total_prods > 0:
            kpi_count += 1
            with_ref = (
                _safe_count(
                    c,
                    "product.template",
                    [
                        ("sale_ok", "=", True),
                        ("default_code", "!=", False),
                        ("default_code", "!=", ""),
                    ],
                )
                or 0
            )
            dq = (with_ref / total_prods) * 100
            if dq >= 80:
                kpi_pass += 1
            else:
                findings.append(Finding("low", "kpi", "Low product data quality", f"{dq:.0f}% have internal ref"))

        score = (kpi_pass * 100) // kpi_count if kpi_count > 0 else 100

        return SectionResult("kpis", score, findings)
    except Exception as exc:
        return SectionResult("kpis", 0, [Finding("critical", "kpi", "KPI check failed", str(exc))])


def _check_mail(c: object, **_kw) -> SectionResult:
    """8. Mail — SMTP servers, queue depth, failure rate."""
    findings: list[Finding] = []
    score = 100
    try:
        smtp = _safe_count(c, "ir.mail_server", [("active", "=", True)])
        if smtp is not None and smtp == 0:
            findings.append(Finding("high", "mail", "No SMTP server", "No active outgoing mail server"))
            score -= 30

        outgoing = _safe_count(c, "mail.mail", [("state", "=", "outgoing")])
        if outgoing is not None and outgoing > 100:
            findings.append(Finding("medium", "mail", "Large mail queue", f"{outgoing} outgoing"))
            score -= 10

        failed = _safe_count(c, "mail.mail", [("state", "=", "exception")])
        if failed is not None and failed > 0:
            sev = "high" if failed > 50 else "medium"
            findings.append(
                Finding(
                    sev,
                    "mail",
                    "Failed emails",
                    f"{failed} in exception state",
                    fix_command="kctl-odoo mail retry-failed",
                )
            )
            score -= min(30, failed)

        return SectionResult("mail", max(0, score), findings)
    except Exception as exc:
        return SectionResult("mail", 0, [Finding("critical", "mail", "Mail check failed", str(exc))])


def _check_storage(c: object, **_kw) -> SectionResult:
    """9. Storage — attachment count, mail messages, logging records."""
    findings: list[Finding] = []
    score = 100
    try:
        attachments = _safe_count(c, "ir.attachment", [])
        if attachments is not None:
            findings.append(Finding("info", "storage", "Attachments", f"{attachments:,}"))
            if attachments > 100_000:
                findings.append(
                    Finding(
                        "medium",
                        "storage",
                        "Large attachment count",
                        f"{attachments:,} attachments — consider cleanup",
                        fix_command="kctl-odoo storage cleanup",
                    )
                )
                score -= 10

        mail_messages = _safe_count(c, "mail.message", [])
        if mail_messages is not None:
            findings.append(Finding("info", "storage", "Mail messages", f"{mail_messages:,}"))
            if mail_messages > 500_000:
                findings.append(Finding("medium", "storage", "Large message count", f"{mail_messages:,}"))
                score -= 10

        log_count = _safe_count(c, "ir.logging", [])
        if log_count is not None and log_count > 50_000:
            findings.append(Finding("low", "storage", "Large log table", f"{log_count:,} ir.logging records"))
            score -= 5

        return SectionResult("storage", max(0, score), findings)
    except Exception as exc:
        return SectionResult("storage", 0, [Finding("critical", "storage", "Storage check failed", str(exc))])


def _check_dr(c: object, **_kw) -> SectionResult:
    """10. Disaster recovery — backup cron, RPO compliance."""
    findings: list[Finding] = []
    score = 100
    try:
        # Look for backup cron
        backup_cron = _safe_count(
            c,
            "ir.cron",
            [
                ("active", "=", True),
                "|",
                ("name", "ilike", "backup"),
                ("name", "ilike", "auto_backup"),
            ],
        )
        if backup_cron is not None and backup_cron == 0:
            findings.append(
                Finding(
                    "high",
                    "dr",
                    "No backup cron",
                    "No automated backup scheduled action found",
                    fix_command="kctl-odoo backup schedule",
                )
            )
            score -= 40

        # Check if auto_backup module installed
        auto_backup = _safe_count(
            c,
            "ir.module.module",
            [
                ("name", "in", ["auto_backup", "db_auto_backup"]),
                ("state", "=", "installed"),
            ],
        )
        if auto_backup is not None and auto_backup == 0:
            findings.append(
                Finding("medium", "dr", "auto_backup not installed", "Consider installing auto_backup OCA module")
            )
            score -= 20

        return SectionResult("dr", max(0, score), findings)
    except Exception as exc:
        return SectionResult("dr", 0, [Finding("critical", "dr", "DR check failed", str(exc))])


# ---------------------------------------------------------------------------
# Section registry
# ---------------------------------------------------------------------------

SECTION_CHECKS: list[tuple[str, callable]] = [
    ("server_health", _check_server_health),
    ("configuration", _check_configuration),
    ("security", _check_security),
    ("data_integrity", _check_data_integrity),
    ("financial_health", _check_financial_health),
    ("inventory_health", _check_inventory_health),
    ("kpis", _check_kpis),
    ("mail", _check_mail),
    ("storage", _check_storage),
    ("dr", _check_dr),
]


# ---------------------------------------------------------------------------
# Main command
# ---------------------------------------------------------------------------


@app.callback(invoke_without_command=True)
def diagnose(
    ctx: typer.Context,
    output: Annotated[str | None, typer.Option("--output", "-o", help="Write report to file (json/md/html)")] = None,
    quick: Annotated[
        bool, typer.Option("--quick", help="Skip slow checks (benchmark, valuation, trial balance)")
    ] = False,
    section_filter: Annotated[str | None, typer.Option("--section", help="Comma-separated sections to run")] = None,
) -> None:
    """Run full instance diagnostic and generate a health report.

    Runs 10 diagnostic sections, scores each 0-100, and computes a weighted
    overall health score.

    Examples:
        kctl-odoo diagnose
        kctl-odoo diagnose --quick
        kctl-odoo diagnose --section security,mail
        kctl-odoo diagnose --output report.html
    """
    run_diagnose_core(ctx, output=output, quick=quick, section_filter=section_filter)


def run_diagnose_core(
    ctx: typer.Context,
    output: str | None = None,
    quick: bool = False,
    section_filter: str | None = None,
) -> None:
    """Core diagnose logic — callable from both `diagnose` and `report generate`."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Determine which sections to run
    allowed: set[str] | None = None
    if section_filter:
        allowed = {s.strip() for s in section_filter.split(",")}

    # Gather basic info
    start_time = time.monotonic()
    ver = c.version_info()
    version = ver.get("server_version", "unknown")
    profile = actx.profile or "default"

    out.info(f"Running diagnostics on {c.database} ({version})...")

    # Run each section
    sections: list[SectionResult] = []
    for name, check_fn in SECTION_CHECKS:
        if allowed and name not in allowed:
            continue

        out.info(f"  Checking {name}...")
        t0 = time.monotonic()
        kwargs: dict = {}
        if name in ("server_health", "data_integrity", "financial_health", "inventory_health"):
            kwargs["quick"] = quick
        result = check_fn(c, **kwargs)
        result.duration_ms = round((time.monotonic() - t0) * 1000)
        sections.append(result)

    # Compute overall score (weighted)
    active_weights = {s.name: WEIGHTS.get(s.name, 5) for s in sections}
    total_weight = sum(active_weights.values())
    overall = sum(s.score * active_weights[s.name] for s in sections) // total_weight if total_weight else 0

    duration = time.monotonic() - start_time

    report = DiagnosticReport(
        profile=profile,
        url=getattr(c, "base_url", ""),
        version=version,
        database=c.database,
        timestamp=datetime.now(tz=UTC),
        sections=sections,
        overall_score=overall,
        duration_seconds=round(duration, 1),
    )

    # -- File output --
    if output:
        ext = output.rsplit(".", 1)[-1].lower() if "." in output else "json"
        if ext == "json":
            content = report.to_json()
        elif ext == "md":
            content = report.to_markdown()
        elif ext == "html":
            content = report.to_html()
        else:
            content = report.to_json()

        with open(output, "w") as fh:
            fh.write(content)
        out.success(f"Report written to {output}")
        return

    # -- JSON mode --
    if out.json_mode or out.format == "json":
        out.raw_json(report.to_dict())
        return

    # -- Terminal output --
    score_color = "green" if overall >= 75 else "yellow" if overall >= 50 else "red"

    # Header with score
    detail_sections: list[tuple[str, list[tuple[str, str]]]] = []
    detail_sections.append(
        (
            "Instance",
            [
                ("Profile", profile),
                ("Database", c.database),
                ("Version", version),
                ("Overall Score", f"[{score_color}]{overall}/100[/{score_color}]"),
                ("Duration", f"{duration:.1f}s"),
            ],
        )
    )

    # Section scores table
    score_rows: list[list[str]] = []
    for s in sections:
        sc = "green" if s.score >= 75 else "yellow" if s.score >= 50 else "red"
        finding_count = len([f for f in s.findings if f.severity not in ("info",)])
        score_rows.append(
            [
                s.name.replace("_", " ").title(),
                f"[{sc}]{s.score}[/{sc}]",
                f"{s.duration_ms}ms",
                str(finding_count) if finding_count else "-",
            ]
        )

    out.detail(
        f"Diagnostic Report -- [{score_color}]{overall}/100[/{score_color}]",
        detail_sections,
        data_for_json=report.to_dict(),
    )

    out.table(
        "Section Scores",
        [("Section", ""), ("Score", ""), ("Duration", "dim"), ("Findings", "")],
        score_rows,
    )

    # Critical and high findings
    critical = [f for s in sections for f in s.findings if f.severity in ("critical", "high")]
    if critical:
        out.header("Critical / High Findings")
        for f in critical:
            fix_hint = f" -- Fix: {f.fix_command}" if f.fix_command else ""
            out.error(f"[{f.severity.upper()}] {f.area} / {f.title}: {f.detail}{fix_hint}")

    # Medium findings
    medium = [f for s in sections for f in s.findings if f.severity == "medium"]
    if medium:
        out.header("Medium Findings")
        for f in medium:
            fix_hint = f" -- Fix: {f.fix_command}" if f.fix_command else ""
            out.warn(f"{f.area} / {f.title}: {f.detail}{fix_hint}")

    if not critical and not medium:
        out.success("No critical or medium findings detected.")


@app.command("auto-fix-modules")
def auto_fix_modules(
    ctx: typer.Context,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be fixed without acting")] = False,
) -> None:
    """Detect and fix column-mismatch errors by updating affected modules.

    Tries a basic res.users query. If it fails with UndefinedColumn,
    parses the missing column and suggests which module to update.

    Examples:
        kctl-odoo doctor auto-fix-modules --dry-run
        kctl-odoo doctor auto-fix-modules
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Probe for column errors
    try:
        c.search_read("res.users", domain=[("id", "=", 1)], fields=["id", "login"], limit=1)
        out.success("No column-mismatch errors detected.")
        return
    except Exception as e:
        error_msg = str(e)

    # Parse the error
    import re

    match = re.search(r"column (\w+)\.(\w+) does not exist", error_msg)
    if not match:
        out.error(f"Unexpected error (not a column mismatch): {error_msg[:200]}")
        raise typer.Exit(1)

    table_name = match.group(1)
    column_name = match.group(2)
    out.warn(f"Missing column: {table_name}.{column_name}")

    # Try to find which module defines this field
    try:
        fields = c.search_read(
            "ir.model.fields",
            domain=[("name", "=", column_name)],
            fields=["model_id", "module"],
            limit=5,
        )
    except Exception:
        fields = []

    if fields:
        modules = list({f.get("module", "unknown") for f in fields if f.get("module")})
        out.info(f"Field defined by module(s): {', '.join(modules)}")

        if dry_run:
            out.info(f"DRY RUN: would update module(s): {', '.join(modules)}")
        else:
            for mod in modules:
                out.info(f"Updating module: {mod}")
                import subprocess

                result = subprocess.run(
                    ["kctl-odoo", "local", "update", mod],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode == 0:
                    out.success(f"  {mod}: updated successfully")
                else:
                    out.error(f"  {mod}: update failed — {result.stderr[:100]}")
    else:
        out.warn(f"Could not determine which module defines {column_name}.")
        out.info("Try manually: kctl-odoo local update <module_name>")


# unused-modules moved to troubleshoot.py (registered under 'doctor' group)


def _unused_modules_placeholder(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """Find installed modules with zero records in their custom models.

    Modules that are installed but have no data may be unused and
    candidates for uninstallation to reduce complexity.

    Examples:
        kctl-odoo doctor unused-modules
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Get all installed modules
    modules = c.search_read(
        "ir.module.module",
        domain=[("state", "=", "installed")],
        fields=["name", "shortdesc"],
        limit=500,
    )

    # For each module, find its custom models and check record counts
    candidates = []
    for mod in modules:
        mod_name = mod["name"]
        # Skip core/OCA modules — only check private
        if mod_name.startswith(
            (
                "base",
                "web",
                "mail",
                "bus",
                "auth_",
                "account",
                "sale",
                "stock",
                "purchase",
                "hr",
                "mrp",
                "crm",
                "project",
                "delivery",
                "payment",
                "l10n_",
                "board",
                "digest",
                "calendar",
                "contacts",
                "portal",
                "product",
                "uom",
                "barcodes",
                "resource",
                "phone_",
                "sms",
            )
        ):
            continue

        # Find models owned by this module
        try:
            models = c.search_read(
                "ir.model.data",
                domain=[("module", "=", mod_name), ("model", "=", "ir.model")],
                fields=["res_id"],
                limit=50,
            )
            if not models:
                continue

            model_ids = [m["res_id"] for m in models]
            model_info = c.search_read(
                "ir.model",
                domain=[("id", "in", model_ids), ("transient", "=", False)],
                fields=["model"],
                limit=50,
            )

            total_records = 0
            model_count = len(model_info)
            for mi in model_info:
                try:
                    count = c.search_count(mi["model"], [])
                    total_records += count
                except Exception:
                    pass

            if total_records == 0 and model_count > 0:
                candidates.append(
                    [
                        mod_name,
                        mod.get("shortdesc", ""),
                        str(model_count),
                        "0",
                    ]
                )
        except Exception:
            pass

    if not candidates:
        out.success("No unused modules detected.")
        return

    out.table(
        f"Potentially Unused Modules ({len(candidates)})",
        [("Module", ""), ("Description", ""), ("Models", ""), ("Records", "")],
        candidates[:limit],
    )
    out.warn("These modules have 0 records. Consider uninstalling if not needed.")
