"""Health monitoring, alerting, and metrics export commands."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Health monitoring, alerting, and metrics export.")

# Default thresholds (stored in ir.config_parameter)
_DEFAULTS: dict[str, int] = {
    "mail_failure_rate": 15,  # percent
    "cron_stale_hours": 48,  # hours
    "pending_queue_jobs": 500,  # count
}

_PARAM_PREFIX = "kctl.monitor."


def _get_threshold(c, key: str) -> int:
    """Read a threshold from ir.config_parameter, falling back to defaults."""
    try:
        records = c.search_read(
            "ir.config_parameter",
            domain=[("key", "=", f"{_PARAM_PREFIX}{key}")],
            fields=["value"],
            limit=1,
        )
        if records:
            return int(records[0]["value"])
    except (RPCError, ValueError, KeyError):
        pass
    return _DEFAULTS[key]


@app.command("run")
def run(
    ctx: typer.Context,
    strict: Annotated[bool, typer.Option("--strict", help="Exit 1 on warnings too")] = False,
) -> None:
    """Run all health checks and report status.

    Checks Odoo connectivity, stuck modules, mail failure rate, stale crons,
    and excessive pending queue jobs. Exits 1 if any check fails (or warns
    with --strict).

    Examples:
        kctl-odoo monitor run
        kctl-odoo monitor run --strict
        kctl-odoo monitor run --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    checks: list[dict] = []
    has_fail = False
    has_warn = False

    # ── Check 1: Odoo connectivity ──
    try:
        c.search_read("res.users", domain=[("active", "=", True)], fields=["id"], limit=1)
        checks.append({"name": "odoo_connectivity", "status": "pass", "detail": "Odoo responding"})
    except Exception as e:
        checks.append({"name": "odoo_connectivity", "status": "fail", "detail": str(e)})
        has_fail = True

    # ── Check 2: Stuck modules ──
    try:
        stuck_states = ["to upgrade", "to install", "to remove"]
        stuck_count = c.search_count(
            "ir.module.module",
            [("state", "in", stuck_states)],
        )
        if stuck_count > 0:
            checks.append(
                {
                    "name": "stuck_modules",
                    "status": "fail",
                    "detail": f"{stuck_count} module(s) stuck in upgrade/install/remove state",
                }
            )
            has_fail = True
        else:
            checks.append({"name": "stuck_modules", "status": "pass", "detail": "No stuck modules"})
    except RPCError as e:
        checks.append({"name": "stuck_modules", "status": "warn", "detail": f"Could not check: {e}"})
        has_warn = True

    # ── Check 3: Mail failure rate (last 24h) ──
    try:
        threshold_rate = _get_threshold(c, "mail_failure_rate")
        cutoff_24h = (datetime.now(tz=UTC) - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        sent_24h = c.search_count("mail.mail", [("state", "=", "sent"), ("write_date", ">", cutoff_24h)])
        failed_24h = c.search_count("mail.mail", [("state", "=", "exception"), ("write_date", ">", cutoff_24h)])
        total_24h = sent_24h + failed_24h
        rate = round(failed_24h / total_24h * 100, 1) if total_24h > 0 else 0.0

        if rate >= threshold_rate:
            checks.append(
                {
                    "name": "mail_failure_rate",
                    "status": "fail",
                    "detail": (
                        f"Mail failure rate {rate}% >= threshold {threshold_rate}%"
                        f" (last 24h: {failed_24h} failed / {total_24h} total)"
                    ),
                }
            )
            has_fail = True
        else:
            checks.append(
                {
                    "name": "mail_failure_rate",
                    "status": "pass",
                    "detail": f"Mail failure rate {rate}% < threshold {threshold_rate}% (last 24h)",
                }
            )
    except RPCError as e:
        checks.append({"name": "mail_failure_rate", "status": "warn", "detail": f"Could not check: {e}"})
        has_warn = True

    # ── Check 4: Stale crons ──
    try:
        threshold_hours = _get_threshold(c, "cron_stale_hours")
        stale_cutoff = (datetime.now(tz=UTC) - timedelta(hours=threshold_hours)).strftime("%Y-%m-%d %H:%M:%S")
        stale_count = c.search_count(
            "ir.cron",
            [("active", "=", True), ("nextcall", "<", stale_cutoff)],
        )
        if stale_count > 0:
            checks.append(
                {
                    "name": "stale_crons",
                    "status": "warn",
                    "detail": f"{stale_count} active cron(s) have nextcall older than {threshold_hours}h",
                }
            )
            has_warn = True
        else:
            checks.append(
                {
                    "name": "stale_crons",
                    "status": "pass",
                    "detail": f"No stale crons (threshold: {threshold_hours}h)",
                }
            )
    except RPCError as e:
        checks.append({"name": "stale_crons", "status": "warn", "detail": f"Could not check: {e}"})
        has_warn = True

    # ── Check 5: Pending queue jobs ──
    try:
        threshold_jobs = _get_threshold(c, "pending_queue_jobs")
        pending_count = c.search_count("queue.job", [("state", "=", "pending")])
        if pending_count >= threshold_jobs:
            checks.append(
                {
                    "name": "queue_jobs_pending",
                    "status": "warn",
                    "detail": f"{pending_count} pending queue jobs >= threshold {threshold_jobs}",
                }
            )
            has_warn = True
        else:
            checks.append(
                {
                    "name": "queue_jobs_pending",
                    "status": "pass",
                    "detail": f"{pending_count} pending queue jobs (threshold: {threshold_jobs})",
                }
            )
    except RPCError:
        # queue.job model may not be installed
        checks.append({"name": "queue_jobs_pending", "status": "skip", "detail": "queue.job not available"})

    # ── Output ──
    overall_fail = has_fail or (strict and has_warn)
    overall_status = "fail" if overall_fail else ("warn" if has_warn else "pass")

    if actx.json_mode:
        out.raw_json(
            {
                "status": overall_status,
                "checks": checks,
            }
        )
    else:
        _STATUS_RICH = {
            "pass": "[green]PASS[/green]",
            "fail": "[red]FAIL[/red]",
            "warn": "[yellow]WARN[/yellow]",
            "skip": "[dim]SKIP[/dim]",
        }
        rows = [[c["name"], _STATUS_RICH.get(c["status"], c["status"]), c["detail"]] for c in checks]
        out.table(
            "Health Checks",
            [("Check", ""), ("Status", ""), ("Detail", "dim")],
            rows,
        )
        if overall_fail:
            out.error("Overall status: FAIL")
        elif has_warn:
            out.warn("Overall status: WARN")
        else:
            out.success("Overall status: PASS")

    if overall_fail:
        raise typer.Exit(1)


@app.command("thresholds")
def thresholds(
    ctx: typer.Context,
    set_value: Annotated[
        str | None, typer.Option("--set", help="Set a threshold: KEY=VALUE (e.g. mail_failure_rate=10)")
    ] = None,
) -> None:
    """Show or set alert thresholds.

    Thresholds are stored in ir.config_parameter with prefix kctl.monitor.
    Defaults: mail_failure_rate=15, cron_stale_hours=48, pending_queue_jobs=500.

    Examples:
        kctl-odoo monitor thresholds
        kctl-odoo monitor thresholds --set mail_failure_rate=10
        kctl-odoo monitor thresholds --set cron_stale_hours=24
        kctl-odoo monitor thresholds --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if set_value:
        if "=" not in set_value:
            out.error("Use KEY=VALUE format, e.g. --set mail_failure_rate=10")
            raise typer.Exit(1)
        key, raw_val = set_value.split("=", 1)
        key = key.strip()
        raw_val = raw_val.strip()

        if key not in _DEFAULTS:
            out.error(f"Unknown threshold key '{key}'. Valid keys: {', '.join(_DEFAULTS)}")
            raise typer.Exit(1)

        try:
            int(raw_val)
        except ValueError:
            out.error(f"Value must be an integer, got: {raw_val!r}")
            raise typer.Exit(1) from None

        param_key = f"{_PARAM_PREFIX}{key}"
        try:
            existing = c.search("ir.config_parameter", [("key", "=", param_key)], limit=1)
            if existing:
                c.write("ir.config_parameter", existing, {"value": raw_val})
            else:
                c.create("ir.config_parameter", {"key": param_key, "value": raw_val})
            out.success(f"Set {key} = {raw_val}")
            if actx.json_mode:
                out.raw_json({"key": key, "value": int(raw_val)})
        except RPCError as e:
            out.error(f"Failed to set threshold: {e}")
            raise typer.Exit(1) from e
        return

    # Show all thresholds
    rows = []
    json_data = []
    for key, default in _DEFAULTS.items():
        current = _get_threshold(c, key)
        is_custom = current != default
        src = "[cyan]custom[/cyan]" if is_custom else "[dim]default[/dim]"
        rows.append([key, str(current), str(default), src])
        json_data.append(
            {"key": key, "current": current, "default": default, "source": "custom" if is_custom else "default"}
        )

    out.table(
        "Alert Thresholds",
        [("Key", ""), ("Current", "cyan"), ("Default", "dim"), ("Source", "")],
        rows,
        data_for_json=json_data,
    )


@app.command("prometheus")
def prometheus(
    ctx: typer.Context,
    prefix: Annotated[str, typer.Option("--prefix", help="Metric name prefix")] = "kctl_odoo",
) -> None:
    """Export Prometheus-format metrics.

    Outputs metrics in the Prometheus text exposition format, suitable for
    scraping by a Prometheus server or Pushgateway.

    Examples:
        kctl-odoo monitor prometheus
        kctl-odoo monitor prometheus --prefix myodoo
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    metrics: list[tuple[str, int | float, str]] = []

    # Installed modules count
    try:
        modules_installed = c.search_count("ir.module.module", [("state", "=", "installed")])
        metrics.append((f"{prefix}_modules_installed", modules_installed, "Number of installed Odoo modules"))
    except RPCError:
        pass

    # Failed mail count
    try:
        mail_failed = c.search_count("mail.mail", [("state", "=", "exception")])
        metrics.append((f"{prefix}_mail_failed", mail_failed, "Number of failed emails in queue"))
    except RPCError:
        pass

    # Active crons
    try:
        cron_active = c.search_count("ir.cron", [("active", "=", True)])
        metrics.append((f"{prefix}_cron_active", cron_active, "Number of active scheduled actions"))
    except RPCError:
        pass

    # Pending queue jobs
    try:
        queue_pending = c.search_count("queue.job", [("state", "=", "pending")])
        metrics.append((f"{prefix}_queue_pending", queue_pending, "Number of pending queue jobs"))
    except RPCError:
        queue_pending = 0
        metrics.append((f"{prefix}_queue_pending", 0, "Number of pending queue jobs (model unavailable)"))

    # Active users
    try:
        users_active = c.search_count("res.users", [("active", "=", True), ("share", "=", False)])
        metrics.append((f"{prefix}_users_active", users_active, "Number of active internal users"))
    except RPCError:
        pass

    lines: list[str] = []
    for name, value, help_text in metrics:
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} gauge")
        lines.append(f"{name} {value}")

    output_text = "\n".join(lines)

    if actx.json_mode:
        json_data = [{"metric": name, "value": value, "help": help_text} for name, value, help_text in metrics]
        out.raw_json(json_data)
    else:
        typer.echo(output_text)


@app.command("gatus-export")
def gatus_export(
    ctx: typer.Context,
) -> None:
    """Generate a Gatus endpoints YAML config for monitoring this instance.

    Outputs a Gatus-compatible YAML configuration with health checks for
    the Odoo web server, login page, and JSON-RPC endpoint.

    Examples:
        kctl-odoo monitor gatus-export
        kctl-odoo monitor gatus-export > gatus-odoo.yaml
    """
    actx: AppContext = ctx.obj
    out = actx.output

    # Try to get base URL from client config
    try:
        base_url = actx.client._url.rstrip("/")
    except Exception:
        base_url = "https://your-odoo-instance.example.com"

    yaml_content = f"""# Gatus monitoring configuration for Odoo
# Generated by kctl-odoo monitor gatus-export
# Integrate into your gatus config.yaml under the 'endpoints' key.

endpoints:
  - name: odoo-web
    url: {base_url}/web/health
    interval: 1m
    conditions:
      - "[STATUS] == 200"
    alerts:
      - type: slack
        failure-threshold: 2
        success-threshold: 2

  - name: odoo-login
    url: {base_url}/web/login
    interval: 5m
    conditions:
      - "[STATUS] == 200"
      - "[BODY] contains 'login'"

  - name: odoo-jsonrpc
    url: {base_url}/web/dataset/call_kw
    method: POST
    headers:
      Content-Type: application/json
    body: |
      {{"jsonrpc":"2.0","method":"call","id":1,"params":{{"service":"common","method":"version","args":[]}}}}
    interval: 2m
    conditions:
      - "[STATUS] == 200"
      - "[BODY] contains 'server_version'"
"""

    if actx.json_mode:
        out.raw_json({"yaml": yaml_content, "base_url": base_url})
    else:
        typer.echo(yaml_content)


@app.command("glitchtip-export")
def glitchtip_export(
    ctx: typer.Context,
) -> None:
    """Show GlitchTip/Sentry DSN configuration for Odoo error tracking.

    Reads the Sentry DSN from ir.config_parameter (key: sentry.dsn) if set,
    and prints setup instructions for integrating Odoo with GlitchTip/Sentry.

    Examples:
        kctl-odoo monitor glitchtip-export
        kctl-odoo monitor glitchtip-export --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    dsn = None
    dsn_set = False
    try:
        records = c.search_read(
            "ir.config_parameter",
            domain=[("key", "=", "sentry.dsn")],
            fields=["value"],
            limit=1,
        )
        if records and records[0].get("value"):
            dsn = records[0]["value"]
            dsn_set = True
    except RPCError:
        pass

    if actx.json_mode:
        out.raw_json(
            {
                "dsn_configured": dsn_set,
                "dsn": dsn if dsn_set else None,
            }
        )
        return

    if dsn_set:
        out.success(f"Sentry DSN configured: {dsn}")
    else:
        out.warn("Sentry DSN not configured in ir.config_parameter (key: sentry.dsn)")

    out.info("")
    out.info("GlitchTip / Sentry Setup Instructions:")
    out.info("")
    out.info("1. Install the OCA sentry module (or odoo-sentry PyPI package):")
    out.info("   pip install odoo-sentry  # or add to requirements.txt")
    out.info("")
    out.info("2. Add to odoo.conf (or set via environment variable):")
    out.info("   sentry_dsn = https://<key>@glitchtip.yourdomain.com/<project-id>")
    out.info("   sentry_environment = production")
    out.info("   sentry_release = 18.0")
    out.info("")
    out.info("3. Or set DSN via kctl-odoo:")
    out.info("   kctl-odoo server params --set sentry.dsn=https://<key>@...")
    out.info("")
    out.info("4. Verify via ir.config_parameter in Odoo Settings > Technical.")
    out.info("")
    out.info("Environment variable alternative (ODOO_SERVER_WIDE_MODULES must include sentry):")
    out.info("   SENTRY_DSN=https://<key>@glitchtip.yourdomain.com/<project-id>")


@app.command("history")
def history(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-d", help="Number of days to look back")] = 7,
) -> None:
    """Show health check history.

    Health check history is available via the kctl-odoo history command group.
    Use 'kctl-odoo history health' to see past health check runs stored in the
    local history database.

    Examples:
        kctl-odoo monitor history
        kctl-odoo monitor history --days 14
    """
    actx: AppContext = ctx.obj
    out = actx.output

    out.info(f"Health check history (last {days} days):")
    out.info("")
    out.info("History tracking is available via the history command group:")
    out.info("  kctl-odoo history health")
    out.info("")
    out.info("To run a health check and record results, use:")
    out.info("  kctl-odoo monitor run")
    out.info("")
    out.info("For full audit trail and event history, see:")
    out.info("  kctl-odoo history list --days " + str(days))

    if actx.json_mode:
        out.raw_json(
            {
                "message": "History available via 'kctl-odoo history health'",
                "days": days,
            }
        )
