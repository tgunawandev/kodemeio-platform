"""CLI self-test and smoke test."""

from __future__ import annotations

import shlex
import subprocess
import time
from typing import Annotated

import typer

from kctl_hz.core.callbacks import AppContext

app = typer.Typer(help="CLI self-test and smoke test.", invoke_without_command=True)

# Each entry: group name -> command string (or None to skip).
# Commands must be read-only operations safe to run against any instance.
SMOKE_TESTS: dict[str, str | None] = {
    "health": "health check",
    "status": "status show",
    "servers": "servers list",
    "volumes": "volumes list",
    "firewalls": "firewalls list",
    "networks": "networks list",
    "ssh-keys": "ssh-keys list",
    "ips": "ips list",
    "snapshots": "snapshots list",
    "load-balancers": "load-balancers list",
    "placement-groups": "placement-groups list",
    "images": "images list",
    "server-types": "server-types list",
    "locations": "locations list",
    "costs": "costs estimate",
    "labels": None,  # Requires resource type + ID args
    "dns": "dns zones",
    "rdns": None,  # Requires a specific IP — skip
    "s3": "s3 buckets",
    "storage-boxes": "storage-boxes list",
    "config": "config show",
}

# Patterns in stderr that indicate a non-fatal skip rather than a real failure.
_SKIP_PATTERNS = (
    "not configured",
    "not available",
    "no token",
    "no dns",
    "no s3",
    "no cloud api token",
    "no dns api token",
    "auth error",
    "connection error",
    "s3 credentials not configured",
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
    cmd: list[str] = ["kctl-hz"]
    if profile:
        cmd.extend(["-p", profile])
    if json_mode:
        cmd.append("--json")
    cmd.extend(shlex.split(cmd_str))

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
            "stderr": f"Command not found: {cmd[0]}",
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

    Exercises every kctl-hz command group with a lightweight, read-only
    operation to verify connectivity and basic functionality.

    Examples:
        kctl-hz self-test
        kctl-hz self-test --verbose
        kctl-hz self-test --group health,servers,volumes
        kctl-hz --profile staging self-test
        kctl-hz self-test --json
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

    for group, cmd_str in tests.items():
        if cmd_str is None:
            results.append(
                {
                    "group": group,
                    "command": "",
                    "status": "SKIP",
                    "time_s": 0.0,
                    "notes": "Requires specific resource",
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": "",
                }
            )
            continue

        result = _run_smoke(group, cmd_str, actx.profile, actx.json_mode)
        results.append(result)

        # Verbose: show output inline
        if verbose and not actx.json_mode:
            status_color = {
                "PASS": "[green]PASS[/green]",
                "FAIL": "[red]FAIL[/red]",
                "SKIP": "[yellow]SKIP[/yellow]",
            }
            out.info(f"  {group}: {status_color.get(result['status'], result['status'])} ({result['time_s']}s)")
            if result["stdout"]:
                for line in result["stdout"].splitlines()[:5]:
                    out.info(f"    stdout: {line}")
            if result["stderr"]:
                for line in result["stderr"].splitlines()[:3]:
                    out.info(f"    stderr: {line}")

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
    status_rich = {
        "PASS": "[green]PASS[/green]",
        "FAIL": "[red]FAIL[/red]",
        "SKIP": "[yellow]SKIP[/yellow]",
    }

    rows = []
    for r in results:
        rows.append(
            [
                r["group"],
                status_rich.get(r["status"], r["status"]),
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
