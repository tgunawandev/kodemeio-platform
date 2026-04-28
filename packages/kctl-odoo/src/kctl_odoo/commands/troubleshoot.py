"""Troubleshooting, diagnostics, and health check commands."""

from __future__ import annotations

import contextlib
import time
from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError
from kctl_odoo.core.utils import module_state_color

app = typer.Typer(help="Troubleshooting, diagnostics & health checks.")

# Register full diagnostic report as a sub-group: kctl-odoo doctor report
from kctl_odoo.commands.diagnose import app as _diagnose_app  # noqa: E402
from kctl_odoo.commands.readiness import app as _readiness_app  # noqa: E402

app.add_typer(_diagnose_app, name="report")
# Merge readiness commands at top level (kctl-odoo doctor readiness-check)
for cmd in _readiness_app.registered_commands:
    app.registered_commands.append(cmd)


# ---------------------------------------------------------------------------
# Health Check (merged from health.py)
# ---------------------------------------------------------------------------


@app.command("check")
def check(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously monitor")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Watch interval in seconds")] = 10,
) -> None:
    """Check Odoo instance health."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    def _check_once() -> None:
        ok, version = c.check_health()
        if ok:
            try:
                uid = c.authenticate()
                user_count = c.search_count("res.users", [("active", "=", True)])
                module_count = c.search_count("ir.module.module", [("state", "=", "installed")])

                sections = [
                    (
                        "Health",
                        [
                            ("Status", "[green]Healthy[/green]"),
                            ("Version", version),
                            ("Database", c.database),
                            ("UID", str(uid)),
                            ("Active Users", str(user_count)),
                            ("Installed Modules", str(module_count)),
                        ],
                    )
                ]
                out.detail(
                    "Odoo Health",
                    sections,
                    data_for_json={
                        "healthy": True,
                        "version": version,
                        "database": c.database,
                        "uid": uid,
                        "active_users": user_count,
                        "installed_modules": module_count,
                    },
                )
            except Exception:
                out.detail(
                    "Odoo Health",
                    [
                        (
                            "Health",
                            [
                                ("Status", "[green]Reachable[/green]"),
                                ("Version", version),
                                ("Auth", "[yellow]Failed (version check OK)[/yellow]"),
                            ],
                        )
                    ],
                    data_for_json={"healthy": True, "version": version, "auth": False},
                )
        else:
            out.detail(
                "Odoo Health",
                [
                    (
                        "Health",
                        [
                            ("Status", "[red]Unreachable[/red]"),
                            ("Error", version),
                        ],
                    )
                ],
                data_for_json={"healthy": False, "error": version},
            )

    _check_once()

    if watch:
        try:
            while True:
                time.sleep(interval)
                out.header(f"Check at {time.strftime('%H:%M:%S')}")
                _check_once()
        except KeyboardInterrupt:
            out.info("Stopped watching")


# ---------------------------------------------------------------------------
# Troubleshooting Commands
# ---------------------------------------------------------------------------


def _safe_count(client, model: str, domain: list | None = None) -> int | None:
    """Search count that returns None if model doesn't exist."""
    try:
        return client.search_count(model, domain or [])
    except RPCError:
        return None


def _get_param(client, key: str) -> str | None:
    """Get a single ir.config_parameter value, returning None if not found."""
    try:
        result = client.search_read("ir.config_parameter", [("key", "=", key)], fields=["value"])
        return result[0]["value"] if result else None
    except RPCError:
        return None


@app.command("stuck-modules")
def stuck_modules(ctx: typer.Context) -> None:
    """Find modules stuck in transitional states."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    records = c.search_read(
        "ir.module.module",
        domain=[("state", "in", ["to install", "to upgrade", "to remove"])],
        fields=["id", "name", "shortdesc", "state", "installed_version", "latest_version"],
        order="state, name",
    )

    if not records:
        out.success("No stuck modules found.")
        return

    rows = []
    json_data = []
    for m in records:
        state = m.get("state", "")
        state_display = f"[yellow]{state}[/yellow]" if state in ("to install", "to upgrade") else f"[red]{state}[/red]"
        rows.append(
            [
                str(m["id"]),
                m["name"],
                m.get("shortdesc") or "-",
                state_display,
                m.get("installed_version") or "-",
                m.get("latest_version") or "-",
            ]
        )
        json_data.append(
            {
                "id": m["id"],
                "name": m["name"],
                "summary": m.get("shortdesc"),
                "state": state,
                "installed_version": m.get("installed_version"),
                "latest_version": m.get("latest_version"),
            }
        )

    out.table(
        f"Stuck Modules ({len(records)})",
        [("ID", "cyan"), ("Name", ""), ("Summary", ""), ("State", ""), ("Installed Ver", "dim"), ("Latest Ver", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command("fix-stuck")
def fix_stuck(
    ctx: typer.Context,
    module: Annotated[str, typer.Argument(help="Module technical name")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Reset a stuck module to installed/uninstalled state."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    records = c.search_read(
        "ir.module.module",
        domain=[("name", "=", module)],
        fields=["id", "name", "state"],
    )

    if not records:
        out.error(f"Module not found: {module}")
        raise typer.Exit(1)

    m = records[0]
    current_state = m.get("state", "")

    if current_state not in ("to install", "to upgrade", "to remove"):
        out.info(f"Module '{module}' is not stuck (state: {current_state}).")
        return

    # Determine target state
    target_state = "installed" if current_state in ("to upgrade", "to remove") else "uninstalled"

    if not force and not typer.confirm(f"Reset module '{module}' from '{current_state}' to '{target_state}'?"):
        raise typer.Exit(0)

    c.write("ir.module.module", [m["id"]], {"state": target_state})
    out.success(f"Module '{module}' state reset: {current_state} -> {target_state}")


# Moved to dev group: kctl-odoo dev deps-tree
# (Previously: kctl-odoo troubleshoot dependencies)


@app.command("recent-changes")
def recent_changes(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-d", help="Look back N days")] = 7,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 30,
) -> None:
    """Show recently changed modules."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    since = (datetime.now(tz=UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    records = c.search_read(
        "ir.module.module",
        domain=[("write_date", ">=", since)],
        fields=["id", "name", "shortdesc", "state", "installed_version", "write_date"],
        limit=limit,
        order="write_date desc",
    )

    if not records:
        out.info(f"No module changes in the last {days} days.")
        return

    rows = []
    for m in records:
        state_display = module_state_color(m.get("state", ""))
        rows.append(
            [
                str(m["id"]),
                m["name"],
                m.get("shortdesc") or "-",
                state_display,
                m.get("installed_version") or "-",
                str(m.get("write_date") or "-"),
            ]
        )

    out.table(
        f"Recently Changed Modules (last {days} days, {len(records)} results)",
        [("ID", "cyan"), ("Name", ""), ("Summary", ""), ("State", ""), ("Version", "dim"), ("Modified", "dim")],
        rows,
        data_for_json=records,
    )


@app.command("check-xml-ids")
def check_xml_ids(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """Check for potentially broken XML IDs (ir.model.data with missing references)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Look for noupdate records that reference non-existent models
    # or records with orphaned references
    data_records = c.search_read(
        "ir.model.data",
        domain=[("res_id", "!=", 0)],
        fields=["id", "module", "name", "model", "res_id"],
        limit=200,
        order="id desc",
    )

    checked_models: dict[str, set[int]] = {}
    for d in data_records:
        model = d.get("model")
        res_id = d.get("res_id")
        if not model or not res_id:
            continue

        # Batch check: collect IDs per model
        if model not in checked_models:
            checked_models[model] = set()
        checked_models[model].add(res_id)

    # Check each model for missing records
    missing_refs: list[dict] = []
    for model, res_ids in checked_models.items():
        try:
            existing = c.search(model, [("id", "in", list(res_ids))])
            existing_set = set(existing)
            for rid in res_ids:
                if rid not in existing_set:
                    # Find the ir.model.data record for this
                    for d in data_records:
                        if d.get("model") == model and d.get("res_id") == rid:
                            missing_refs.append(d)
                            if len(missing_refs) >= limit:
                                break
            if len(missing_refs) >= limit:
                break
        except Exception:
            # Model might not exist anymore
            for d in data_records:
                if d.get("model") == model:
                    missing_refs.append(d)
                    if len(missing_refs) >= limit:
                        break
            if len(missing_refs) >= limit:
                break

    if not missing_refs:
        out.success("No broken XML ID references found.")
        return

    rows = []
    json_data = []
    for d in missing_refs:
        xml_id = f"{d.get('module')}.{d.get('name')}"
        rows.append([str(d["id"]), xml_id, d.get("model") or "-", str(d.get("res_id") or "-")])
        json_data.append(
            {
                "id": d["id"],
                "xml_id": xml_id,
                "model": d.get("model"),
                "res_id": d.get("res_id"),
            }
        )

    out.table(
        f"Broken XML IDs ({len(missing_refs)})",
        [("ID", "cyan"), ("XML ID", ""), ("Model", ""), ("Res ID", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command("mail-diagnostics")
def mail_diagnostics(ctx: typer.Context) -> None:
    """Check mail server configuration and queue status."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Outgoing mail servers
    try:
        outgoing = c.search_read(
            "ir.mail_server",
            domain=[],
            fields=["id", "name", "smtp_host", "smtp_port", "smtp_encryption", "active"],
        )
    except Exception:
        outgoing = []

    # Incoming mail servers (fetchmail)
    fetchmail = []
    with contextlib.suppress(Exception):
        fetchmail = c.search_read(
            "fetchmail.server",
            domain=[],
            fields=["id", "name", "server", "server_type", "state", "active"],
        )

    # Mail queue status
    mail_queue: dict[str, int] = {}
    try:
        for state in ["outgoing", "sent", "exception", "cancel"]:
            count = c.search_count("mail.mail", [("state", "=", state)])
            mail_queue[state] = count
    except Exception:
        pass

    # Failed messages count
    failed_count = 0
    with contextlib.suppress(Exception):
        failed_count = c.search_count("mail.mail", [("state", "=", "exception")])

    outgoing_lines = []
    for srv in outgoing:
        status = "[green]active[/green]" if srv.get("active") else "[red]inactive[/red]"
        outgoing_lines.append(
            (srv["name"], f"{srv.get('smtp_host')}:{srv.get('smtp_port')} ({srv.get('smtp_encryption', '-')}) {status}")
        )

    fetchmail_lines = []
    for srv in fetchmail:
        status = "[green]active[/green]" if srv.get("active") else "[red]inactive[/red]"
        state = srv.get("state", "")
        fetchmail_lines.append(
            (srv["name"], f"{srv.get('server')} ({srv.get('server_type', '-')}) state={state} {status}")
        )

    queue_lines = [(state, str(count)) for state, count in mail_queue.items()]

    json_out = {
        "outgoing_servers": outgoing,
        "fetchmail_servers": fetchmail,
        "mail_queue": mail_queue,
        "failed_count": failed_count,
    }

    sections = [
        ("Outgoing Mail Servers", outgoing_lines if outgoing_lines else [("(none)", "No servers configured")]),
        (
            "Incoming Mail (Fetchmail)",
            fetchmail_lines if fetchmail_lines else [("(none)", "Not configured or module not installed")],
        ),
        ("Mail Queue", queue_lines if queue_lines else [("(empty)", "No mail in queue")]),
        (
            "Issues",
            [
                ("Failed Messages", f"[red]{failed_count}[/red]" if failed_count > 0 else "[green]0[/green]"),
            ],
        ),
    ]

    out.detail("Mail Diagnostics", sections, data_for_json=json_out)


# Moved to cron group: kctl-odoo cron diagnose
# (Previously: kctl-odoo troubleshoot cron-diagnostics)


@app.command("module-conflicts")
def module_conflicts(ctx: typer.Context) -> None:
    """Find modules with overlapping model inheritance that may conflict."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Find installed modules
    installed = c.search_read(
        "ir.module.module",
        domain=[("state", "=", "installed")],
        fields=["id", "name"],
    )
    {m["id"]: m["name"] for m in installed}

    # Get model data to find overlapping inheritances
    # ir.model records with modules that inherit the same model
    models = c.search_read(
        "ir.model",
        domain=[],
        fields=["id", "model", "name", "modules"],
        limit=500,
        order="model",
    )

    # Find models touched by multiple modules
    conflicts = []
    for m in models:
        modules_str = m.get("modules") or ""
        module_list = [mod.strip() for mod in modules_str.split(",") if mod.strip()]
        # Only flag if more than 2 modules touch the same model (base + 1 is normal)
        if len(module_list) > 3:
            conflicts.append(
                {
                    "model": m["model"],
                    "model_name": m.get("name") or m["model"],
                    "modules": module_list,
                    "module_count": len(module_list),
                }
            )

    if not conflicts:
        out.success("No significant model inheritance overlaps found.")
        return

    # Sort by number of modules descending
    conflicts.sort(key=lambda x: x["module_count"], reverse=True)

    rows = []
    for con in conflicts[:50]:
        mods = ", ".join(con["modules"][:5])
        if len(con["modules"]) > 5:
            mods += f" (+{len(con['modules']) - 5} more)"
        rows.append([con["model"], con["model_name"], str(con["module_count"]), mods])

    out.table(
        f"Model Inheritance Overlaps ({len(conflicts)})",
        [("Model", "cyan"), ("Name", ""), ("Modules", ""), ("Module List", "dim")],
        rows,
        data_for_json=conflicts,
    )


@app.command("check-config")
def check_config(ctx: typer.Context) -> None:
    """Validate Odoo instance configuration against best practices.

    Checks critical settings and shows PASS/FAIL for each item:
    web.base.url, mail catchall, SMTP, database UUID, lock dates,
    warehouses, and default taxes.

    Examples:
        kctl-odoo troubleshoot check-config
        kctl-odoo troubleshoot check-config --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    checks: list[tuple[str, bool, str]] = []  # (name, passed, detail)

    # 1. web.base.url not localhost
    base_url = _get_param(c, "web.base.url") or ""
    is_localhost = "localhost" in base_url or "127.0.0.1" in base_url
    if base_url and not is_localhost:
        checks.append(("web.base.url", True, base_url))
    elif not base_url:
        checks.append(("web.base.url", False, "Not set"))
    else:
        checks.append(("web.base.url", False, f"Points to localhost: {base_url}"))

    # 2. mail.catchall.domain set
    catchall = _get_param(c, "mail.catchall.domain")
    checks.append(("mail.catchall.domain", bool(catchall), catchall or "Not set"))

    # 3. SMTP configured
    try:
        smtp_count = c.search_count("ir.mail_server", [("active", "=", True)])
        checks.append(("SMTP Server", smtp_count > 0, f"{smtp_count} active server(s)"))
    except RPCError:
        checks.append(("SMTP Server", False, "Could not query"))

    # 4. database.uuid exists
    db_uuid = _get_param(c, "database.uuid")
    checks.append(("database.uuid", bool(db_uuid), db_uuid or "Not set"))

    # 5. Lock dates set (fiscal year lock)
    try:
        companies = c.search_read("res.company", [], fields=["id", "name", "fiscalyear_lock_date"])
        if companies:
            lock = companies[0].get("fiscalyear_lock_date")
            checks.append(("Fiscal Lock Date", bool(lock), str(lock) if lock else "Not set"))
        else:
            checks.append(("Fiscal Lock Date", False, "No company found"))
    except RPCError:
        checks.append(("Fiscal Lock Date", False, "Could not query"))

    # 6. Warehouse exists
    wh_count = _safe_count(c, "stock.warehouse", [])
    if wh_count is not None:
        checks.append(("Warehouse", wh_count > 0, f"{wh_count} warehouse(s)"))
    else:
        checks.append(("Warehouse", True, "stock module not installed (optional)"))

    # 7. Default taxes configured
    try:
        sale_taxes = c.search_count("account.tax", [("type_tax_use", "=", "sale")])
        purchase_taxes = c.search_count("account.tax", [("type_tax_use", "=", "purchase")])
        has_taxes = sale_taxes > 0 and purchase_taxes > 0
        checks.append(("Default Taxes", has_taxes, f"Sale: {sale_taxes}, Purchase: {purchase_taxes}"))
    except RPCError:
        checks.append(("Default Taxes", True, "account module not installed (optional)"))

    # Build output
    passed = sum(1 for _, p, _ in checks if p)
    total = len(checks)
    score_pct = round(passed / total * 100) if total else 0

    rows = []
    json_checks = []
    for name, ok, detail in checks:
        status = "[green]PASS[/green]" if ok else "[red]FAIL[/red]"
        rows.append([name, status, detail])
        json_checks.append({"check": name, "passed": ok, "detail": detail})

    rows.append(["", "", ""])
    rows.append(["[bold]Score[/bold]", f"[bold]{passed}/{total}[/bold]", f"[bold]{score_pct}%[/bold]"])

    out.table(
        "Configuration Check",
        [("Check", "cyan"), ("Status", ""), ("Detail", "dim")],
        rows,
        data_for_json=json_checks,
    )


@app.command("version-info")
def version_info(ctx: typer.Context) -> None:
    """Show Odoo version, database, CLI version, and module statistics.

    Examples:
        kctl-odoo troubleshoot version-info
        kctl-odoo troubleshoot version-info --json
    """
    from kctl_odoo import __version__ as cli_version

    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    sections: list[tuple[str, list[tuple[str, str]]]] = []
    json_data: dict = {}

    # ── Odoo Version ──
    info = c.version_info()
    server_version = info.get("server_version", "unknown")
    server_serie = info.get("server_serie", "unknown")

    sections.append(
        (
            "Odoo",
            [
                ("Server Version", server_version),
                ("Server Serie", server_serie),
            ],
        )
    )
    json_data["odoo_version"] = server_version
    json_data["odoo_serie"] = server_serie

    # ── Database ──
    db_uuid = _get_param(c, "database.uuid") or "unknown"
    db_create = _get_param(c, "database.create_date") or "unknown"
    sections.append(
        (
            "Database",
            [
                ("Name", c.database),
                ("UUID", db_uuid),
                ("Created", db_create),
            ],
        )
    )
    json_data["database"] = {"name": c.database, "uuid": db_uuid, "create_date": db_create}

    # ── CLI ──
    profile = actx.profile if hasattr(actx, "profile") else "default"
    sections.append(
        (
            "CLI",
            [
                ("kctl-odoo Version", cli_version),
                ("Active Profile", str(profile)),
            ],
        )
    )
    json_data["cli_version"] = cli_version
    json_data["profile"] = str(profile)

    # ── Module Counts by Origin ──
    try:
        all_installed = c.search_read(
            "ir.module.module",
            [("state", "=", "installed")],
            ["name", "author"],
            limit=0,
        )
        private_count = 0
        oca_count = 0
        for m in all_installed:
            author = (m.get("author") or "").lower()
            if "kodemeio" in author or "kodeme" in author:
                private_count += 1
            elif "oca" in author or "odoo community" in author:
                oca_count += 1
        core_count = len(all_installed) - private_count - oca_count

        sections.append(
            (
                "Modules by Origin",
                [
                    ("Total Installed", str(len(all_installed))),
                    ("Core (Odoo SA)", str(core_count)),
                    ("OCA", str(oca_count)),
                    ("Private (Kodemeio)", str(private_count)),
                ],
            )
        )
        json_data["modules"] = {
            "total": len(all_installed),
            "core": core_count,
            "oca": oca_count,
            "private": private_count,
        }
    except RPCError:
        pass

    out.detail("Version Information", sections, data_for_json=json_data)


@app.command("unused-modules")
def unused_modules(
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

    modules = c.search_read(
        "ir.module.module",
        domain=[("state", "=", "installed")],
        fields=["name", "shortdesc"],
        limit=500,
    )

    candidates = []
    for mod in modules:
        mod_name = mod["name"]
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
                with contextlib.suppress(Exception):
                    total_records += c.search_count(mi["model"], [])

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
