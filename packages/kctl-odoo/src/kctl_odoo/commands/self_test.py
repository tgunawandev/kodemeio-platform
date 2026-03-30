"""CLI self-test and smoke test."""

from __future__ import annotations

import subprocess
import sys
import time
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext

app = typer.Typer(help="CLI self-test and smoke test.", invoke_without_command=True)

# Each entry: group name -> command string (or None to skip).
# Commands must be read-only operations safe to run against any instance.
SMOKE_TESTS: dict[str, str | None] = {
    # Infrastructure & health
    "health": "doctor check",
    "doctor": "doctor version-info",
    "dashboard": "dashboard info",
    "deploy": "deploy status",
    "workers": "workers status",
    "performance": "performance modules-count",
    # Config & server
    "server": "server params --search web.base",
    "server-mail": "server mail-outgoing",
    "config": None,  # interactive
    # Users & partners
    "users": "users list --limit 1",
    "companies": "companies list",
    "partners": "partners list --limit 1",
    # Modules & bundles
    "modules": "modules list --state installed --limit 1",
    "bundles": "bundles list",
    # Communication
    "mail": "mail status",
    "sessions": "sessions stats",
    "integration": "integration webhooks",
    # Jobs & cron
    "cron": "cron list --active --limit 1",
    "jobs": "jobs stats",
    # Security & storage
    "security": "security groups --limit 1",
    "storage": "storage filestore-stats",
    # Master data & setup
    "master-data": "master-data settings",
    "setup": "setup quickstart",
    # Business operations
    "accounting": "accounting invoices --limit 1",
    "sales": "sales orders --limit 1",
    "purchasing": "purchasing orders --limit 1",
    "inventory": "inventory warehouses",
    "hr": "hr departments",
    "mrp": "mrp orders --limit 1",
    "tax": "tax accounts",
    "pos": "pos configs",
    "project": "project list --limit 1",
    # Reports & backup
    "report": "report list --limit 1",
    "backup": "backup list",
    "tenants": "tenants list",
    # Dev tools
    "fastapi": "fastapi health tpm",
    "dev-mode": "dev-mode status",
    "pipeline": "pipeline metrics",
    "lint": "lint xml base_management",
    # SP4 new groups
    "views": "views validate base_management",
    "manifest": "manifest validate base_management",
    "orm": "orm fields-unused base_management",
    "record-rules": "record-rules audit",
    "traceback": "traceback recent --count 1",
    "translations": "translations validate base_management",
    "website": "website pages --limit 1",
    "monitor": "monitor thresholds",
    "auto-maintain": "auto-maintain report",
    "currency": "currency rates --limit 1",
    "sequences": "sequences list --limit 1",
    "fleet": "fleet vehicles --limit 1",
    "helpdesk": "helpdesk tickets --limit 1",
    "events": "events list --limit 1",
    "approvals": "approvals pending --limit 1",
    "data-quality": "data-quality report",
    "automation": "automation rules --limit 1",
    # Operations command groups
    "products": "products list --limit 1",
    "crm": "crm pipeline",
    "delivery": "delivery list --limit 1",
    # Foundation ops groups
    "audit": "audit rules",
    "forms": "forms types",
    "compliance": "compliance stats",
    "dunning": "dunning stats",
    "budget": "budget list --limit 1",
    "quality": "quality stats",
    "support": "support tickets --limit 1",
    "kpi": "kpi list",
    "periods": "periods list --limit 1",
    "statements": "statements overdue --limit 1",
    "assets": "assets summary",
    "payment-gateways": "payment-gateways status",
    "bank": "bank status",
    # Docker-dependent
    "local": "local status",
    "logs": "logs errors --days 1 --limit 1",
    # Data operations
    "export": "export records res.partner --fields name --limit 1",
    "import": "import guide",
    # Interactive / special setup — always skip
    "shell": None,
    "scaffold": None,
    "generate": None,
    "repl": None,
    "test": None,
    "diff": None,
    "migrate": None,
    "clean": None,
    "history": None,
    "skill": None,
}

# Patterns in stderr that indicate a non-fatal skip rather than a real failure.
_SKIP_PATTERNS = (
    "not installed",
    "not available",
    "no module named",
    "module not found",
    "not configured",
)


def _is_skip(stderr: str) -> bool:
    """Return True if stderr indicates the command is not applicable."""
    lower = stderr.lower()
    return any(p in lower for p in _SKIP_PATTERNS)


def _run_smoke(
    group: str,
    cmd_str: str,
    profile: str | None,
    json_mode: bool,
) -> dict:
    """Run a single smoke-test command and return the result dict."""
    cmd: list[str] = ["kctl-odoo"]
    if profile:
        cmd.extend(["-p", profile])
    if json_mode:
        cmd.append("--json")
    cmd.extend(cmd_str.split())

    start = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        elapsed = round(time.monotonic() - start, 2)

        stderr = result.stderr.strip()
        stdout = result.stdout.strip()

        # Determine status
        if result.returncode == 0:
            status = "PASS"
            notes = ""
        elif _is_skip(stderr):
            status = "SKIP"
            notes = "Not available"
        elif "Traceback" in stderr:
            status = "FAIL"
            notes = "Traceback detected"
        else:
            status = "FAIL"
            notes = stderr[:120] if stderr else f"exit {result.returncode}"

        return {
            "group": group,
            "command": cmd_str,
            "status": status,
            "time_s": elapsed,
            "notes": notes,
            "exit_code": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }

    except subprocess.TimeoutExpired:
        elapsed = round(time.monotonic() - start, 2)
        return {
            "group": group,
            "command": cmd_str,
            "status": "FAIL",
            "time_s": elapsed,
            "notes": "Timeout (30s)",
            "exit_code": -1,
            "stdout": "",
            "stderr": "Timed out after 30s",
        }
    except FileNotFoundError:
        return {
            "group": group,
            "command": cmd_str,
            "status": "FAIL",
            "time_s": 0.0,
            "notes": "Command not found",
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command not found: {sys.executable}",
        }


@app.callback()
def self_test(
    ctx: typer.Context,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show stdout/stderr for each test")] = False,
    group_filter: Annotated[
        str | None, typer.Option("--group", "-g", help="Only test these groups (comma-separated)")
    ] = None,
) -> None:
    """Run one read-only command from each command group and report PASS/FAIL/SKIP.

    Exercises every kctl-odoo command group with a lightweight, read-only
    operation to verify connectivity and basic functionality.

    Examples:
        kctl-odoo self-test
        kctl-odoo self-test --verbose
        kctl-odoo self-test --group health,modules,users
        kctl-odoo --profile staging self-test
        kctl-odoo self-test --json
    """
    if ctx.invoked_subcommand is not None:
        return

    actx: AppContext = ctx.obj
    out = actx.output

    # Determine which groups to test
    if group_filter:
        selected = {g.strip() for g in group_filter.split(",")}
        unknown = selected - set(SMOKE_TESTS.keys())
        if unknown:
            out.warn(f"Unknown group(s): {', '.join(sorted(unknown))}")
        tests = {k: v for k, v in SMOKE_TESTS.items() if k in selected}
    else:
        tests = dict(SMOKE_TESTS)

    if not tests:
        out.error("No tests to run.")
        raise typer.Exit(1)

    out.info(f"Running self-test for {len(tests)} command group(s)...")

    results: list[dict] = []
    total_start = time.monotonic()

    import concurrent.futures

    # Separate skip entries from runnable entries
    skip_entries = {g: c for g, c in tests.items() if c is None}
    run_entries = {g: c for g, c in tests.items() if c is not None}

    # Add skip results immediately
    for group in skip_entries:
        results.append(
            {
                "group": group,
                "command": "",
                "status": "SKIP",
                "time_s": 0.0,
                "notes": "Requires Docker/repo",
                "exit_code": -1,
                "stdout": "",
                "stderr": "",
            }
        )

    # Run all non-skip tests in parallel
    max_workers = min(8, len(run_entries)) if run_entries else 1
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_run_smoke, group, cmd_str, actx.profile, actx.json_mode): group
            for group, cmd_str in run_entries.items()
        }
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            # Verbose: show output inline
            if verbose and not actx.json_mode:
                status_color = {
                    "PASS": "[green]PASS[/green]",
                    "FAIL": "[red]FAIL[/red]",
                    "SKIP": "[yellow]SKIP[/yellow]",
                }
                out.info(
                    f"  {result['group']}: {status_color.get(result['status'], result['status'])} ({result['time_s']}s)"
                )
                if result["stdout"]:
                    for line in result["stdout"].splitlines()[:5]:
                        out.info(f"    stdout: {line}")
                if result["stderr"]:
                    for line in result["stderr"].splitlines()[:3]:
                        out.info(f"    stderr: {line}")

    # Sort results by group name for consistent output
    results.sort(key=lambda r: r["group"])

    total_elapsed = round(time.monotonic() - total_start, 2)

    # Tally
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    skip_count = sum(1 for r in results if r["status"] == "SKIP")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")

    if actx.json_mode:
        out.raw_json(
            {
                "total": len(results),
                "pass": pass_count,
                "skip": skip_count,
                "fail": fail_count,
                "total_time_s": total_elapsed,
                "results": results,
            }
        )
        return

    # Table output
    _STATUS_RICH = {
        "PASS": "[green]PASS[/green]",
        "FAIL": "[red]FAIL[/red]",
        "SKIP": "[yellow]SKIP[/yellow]",
    }

    rows = []
    for r in results:
        rows.append(
            [
                r["group"],
                _STATUS_RICH.get(r["status"], r["status"]),
                f"{r['time_s']}s" if r["time_s"] > 0 else "-",
                r.get("notes", ""),
            ]
        )

    out.table(
        f"Self-Test Results ({len(results)} groups, {total_elapsed}s)",
        [("Group", ""), ("Status", ""), ("Time", "dim"), ("Notes", "dim")],
        rows,
    )

    # Summary
    summary = f"{pass_count} PASS, {skip_count} SKIP, {fail_count} FAIL"
    if fail_count > 0:
        out.error(f"Summary: {summary}")
    else:
        out.success(f"Summary: {summary}")

    # Show failure details
    if fail_count > 0 and not verbose:
        out.info("Failed groups (use --verbose for full output):")
        for r in results:
            if r["status"] == "FAIL":
                detail = r.get("notes", "") or r.get("stderr", "")[:120]
                out.error(f"  {r['group']}: {detail}")

    if fail_count > 0:
        raise typer.Exit(1)
