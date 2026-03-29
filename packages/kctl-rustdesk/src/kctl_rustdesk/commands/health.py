"""Health check commands."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from kctl_common.exceptions import CommandError
from kctl_rustdesk.core.callbacks import AppContext
from kctl_rustdesk.core.executor import RustDeskExecutor

app = typer.Typer(help="Health checks for RustDesk server.")


def _run_checks(ex: RustDeskExecutor) -> list[dict[str, str]]:
    """Run all health checks, return list of {name, status, message}."""
    checks: list[dict[str, str]] = []

    for svc in ("hbbs", "hbbr"):
        running = ex.container_running(svc)
        checks.append(
            {
                "name": f"container:{svc}",
                "status": "pass" if running else "fail",
                "message": "running" if running else "not running",
            }
        )

    for path_name, path in [("public key", ex.KEY_PUB_PATH), ("private key", ex.KEY_PRIV_PATH)]:
        exists = ex.file_exists("hbbs", path)
        checks.append(
            {
                "name": f"key:{path_name}",
                "status": "pass" if exists else "fail",
                "message": "exists" if exists else "missing",
            }
        )

    try:
        count = ex.query_db_scalar("SELECT count(*) FROM peer;")
        checks.append(
            {
                "name": "database",
                "status": "pass",
                "message": f"accessible, {count} peers",
            }
        )
    except (CommandError, Exception) as e:
        checks.append(
            {
                "name": "database",
                "status": "fail",
                "message": str(e),
            }
        )

    try:
        output = ex.exec_hbbs(["netstat", "-tlnp"], check=False)
        for port in ("21115", "21116", "21117", "21118"):
            listening = port in output
            checks.append(
                {
                    "name": f"port:{port}",
                    "status": "pass" if listening else "warn",
                    "message": "listening" if listening else "not detected",
                }
            )
    except (CommandError, Exception):
        checks.append(
            {
                "name": "port:check",
                "status": "warn",
                "message": "netstat not available in container",
            }
        )

    return checks


@app.command("check")
def check(
    ctx: typer.Context,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Run health checks on RustDesk server."""
    c: AppContext = ctx.obj
    out = c.output
    ex = c.executor

    checks = _run_checks(ex)

    if as_json or c.json_mode:
        passed = sum(1 for ch in checks if ch["status"] in ("pass", "warn"))
        total = len(checks)
        score = round(passed / total * 100) if total else 0
        print(json.dumps({"score": score, "checks": checks}, indent=2))
        return

    out.header("RustDesk Health Check")

    passed = 0
    total = len(checks)
    for ch in checks:
        status = ch["status"]
        name = ch["name"]
        message = ch["message"]
        if status == "pass":
            out.text(f"  [green]PASS[/green] {name}: {message}")
            passed += 1
        elif status == "warn":
            out.text(f"  [yellow]WARN[/yellow] {name}: {message}")
            passed += 1
        else:
            out.text(f"  [red]FAIL[/red] {name}: {message}")

    score = round(passed / total * 100) if total else 0
    out.text("")
    if score >= 80:
        out.success(f"Health score: {score}% ({passed}/{total})")
    elif score >= 50:
        out.warn(f"Health score: {score}% ({passed}/{total})")
    else:
        out.error(f"Health score: {score}% ({passed}/{total})")
