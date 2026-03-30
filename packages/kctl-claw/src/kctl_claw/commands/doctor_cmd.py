"""Environment validation commands (doctor)."""

from __future__ import annotations

import shutil
from datetime import UTC

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.config_manager import ConfigFile
from kctl_claw.core.exceptions import DockerError, GatewayError

app = typer.Typer(help="Environment validation: check, fix, and report.")


def _run_all_checks(actx: AppContext) -> list[tuple[str, str, str]]:
    """Run all doctor checks. Returns list of (check_name, status, detail)."""
    results: list[tuple[str, str, str]] = []
    out = actx.output

    # 1. Docker availability
    try:
        actx.docker.ps()
        results.append(("docker", "OK", "Docker is running"))
    except DockerError as e:
        results.append(("docker", "FAIL", f"Docker unavailable: {str(e)[:60]}"))
    except Exception as e:
        results.append(("docker", "WARN", f"Docker check failed: {str(e)[:60]}"))

    # 2. Node.js
    node_path = shutil.which("node")
    if node_path:
        import subprocess

        try:
            r = subprocess.run(["node", "--version"], capture_output=True, text=True, check=False, timeout=5)
            version = r.stdout.strip()
            results.append(("node.js", "OK", f"{version} at {node_path}"))
        except Exception:
            results.append(("node.js", "WARN", "node found but version check failed"))
    else:
        results.append(("node.js", "FAIL", "node not found in PATH"))

    # 3. Gateway health
    try:
        actx.gateway.health()
        results.append(("gateway", "OK", "Gateway reachable"))
    except GatewayError as e:
        results.append(("gateway", "WARN", f"Gateway unavailable: {str(e)[:60]}"))
    except Exception as e:
        results.append(("gateway", "WARN", f"Gateway check failed: {str(e)[:60]}"))

    # 4. Config files
    for cfg_name, cfg_file in [
        ("openclaw.json", ConfigFile.OPENCLAW),
        ("config.json (MCP)", ConfigFile.MCP_REGISTRY),
        ("cron/jobs.json", ConfigFile.CRON_JOBS),
    ]:
        try:
            actx.config_mgr.read(cfg_file)
            results.append((f"config:{cfg_name}", "OK", "Readable"))
        except FileNotFoundError:
            results.append((f"config:{cfg_name}", "FAIL", "File not found"))
        except Exception as e:
            results.append((f"config:{cfg_name}", "FAIL", str(e)[:60]))

    # 5. MCP servers config
    try:
        mcp_data = actx.config_mgr.read(ConfigFile.MCP_REGISTRY)
        servers = mcp_data.get("mcpServers", {})
        results.append(("mcp:registry", "OK", f"{len(servers)} servers registered"))
    except Exception as e:
        results.append(("mcp:registry", "FAIL", str(e)[:60]))

    # 6. Telegram bots config
    try:
        data = actx.config_mgr.read(ConfigFile.OPENCLAW)
        accounts = data.get("channels", {}).get("telegram", {}).get("accounts", [])
        results.append(("telegram:bots", "OK", f"{len(accounts)} bot(s) configured"))
    except Exception as e:
        results.append(("telegram:bots", "WARN", str(e)[:60]))

    # 7. Webhook check (gateway-dependent)
    try:
        wh_data = actx.gateway.get("/api/telegram/webhooks")
        if isinstance(wh_data, list):
            ok_count = sum(1 for w in wh_data if w.get("status") == "ok")
            results.append(("telegram:webhooks", "OK", f"{ok_count}/{len(wh_data)} webhooks active"))
        else:
            results.append(("telegram:webhooks", "INFO", "Webhook status unavailable"))
    except GatewayError:
        results.append(("telegram:webhooks", "WARN", "Gateway unavailable — cannot check webhooks"))
    except Exception as e:
        results.append(("telegram:webhooks", "WARN", str(e)[:60]))

    _ = out  # suppress unused warning
    return results


@app.command()
def check(ctx: typer.Context) -> None:
    """Check Docker, Node.js, gateway health, MCP servers, and Telegram webhooks."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Running environment checks...")
    results = _run_all_checks(actx)

    rows = [[name, status, detail] for name, status, detail in results]
    json_data = [{"check": name, "status": status, "detail": detail} for name, status, detail in results]

    failures = [r for r in results if r[1] == "FAIL"]
    warnings = [r for r in results if r[1] == "WARN"]

    out.table(
        f"Doctor Check ({len(results)} checks, {len(failures)} failed, {len(warnings)} warnings)",
        [("Check", "cyan"), ("Status", ""), ("Detail", "dim")],
        rows,
        data_for_json=json_data,
    )

    if failures:
        out.error(f"{len(failures)} check(s) failed. Run 'kctl-claw doctor fix' to attempt auto-fix.")
        raise typer.Exit(1)
    elif warnings:
        out.warn(f"{len(warnings)} warning(s) — some services may be offline.")
    else:
        out.success("All environment checks passed.")


@app.command()
def fix(ctx: typer.Context) -> None:
    """Auto-fix environment issues: rebuild container, sync config."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Running doctor checks to identify issues...")
    results = _run_all_checks(actx)
    failures = [r for r in results if r[1] == "FAIL"]
    warnings = [r for r in results if r[1] == "WARN"]

    if not failures and not warnings:
        out.success("No issues found — nothing to fix.")
        return

    out.info(f"Found {len(failures)} failure(s) and {len(warnings)} warning(s). Attempting fixes...")

    fixed = []
    for name, status, detail in failures + warnings:
        if name == "gateway" or name == "docker":
            out.info("Attempting to restart gateway...")
            try:
                actx.docker.restart()
                fixed.append(name)
                out.success("Restarted gateway/docker services.")
            except DockerError as e:
                out.warn(f"Could not restart: {e}")
        elif name.startswith("config:"):
            out.warn(f"Config issue {name!r}: manual fix required — {detail}")
        else:
            out.info(f"Skipping {name!r} ({status}): {detail}")

    if fixed:
        out.success(f"Fixed: {', '.join(fixed)}")
        out.info("Re-run 'kctl-claw doctor check' to verify.")
    else:
        out.warn("Auto-fix could not resolve all issues. Manual intervention may be required.")


@app.command()
def report(ctx: typer.Context) -> None:
    """Generate a full diagnostic report."""
    actx: AppContext = ctx.obj
    out = actx.output

    import json as json_mod
    from datetime import datetime

    out.info("Generating full diagnostic report...")
    results = _run_all_checks(actx)

    # Gather additional info
    report_data = {
        "generated_at": datetime.now(UTC).isoformat(),
        "checks": [{"check": n, "status": s, "detail": d} for n, s, d in results],
        "summary": {
            "total": len(results),
            "ok": sum(1 for r in results if r[1] == "OK"),
            "warn": sum(1 for r in results if r[1] == "WARN"),
            "fail": sum(1 for r in results if r[1] == "FAIL"),
        },
    }

    try:
        mcp_data = actx.config_mgr.read(ConfigFile.MCP_REGISTRY)
        report_data["mcp_servers"] = list(mcp_data.get("mcpServers", {}).keys())
    except Exception:
        report_data["mcp_servers"] = []

    try:
        openclaw = actx.config_mgr.read(ConfigFile.OPENCLAW)
        agents = [a.get("name") for a in openclaw.get("agents", {}).get("list", [])]
        report_data["agents"] = agents
        report_data["version"] = openclaw.get("version", "unknown")
    except Exception:
        report_data["agents"] = []

    rows = [[r["check"], r["status"], r["detail"]] for r in report_data["checks"]]
    out.table(
        "Diagnostic Report",
        [("Check", "cyan"), ("Status", ""), ("Detail", "dim")],
        rows,
        data_for_json=report_data,
    )

    summary = report_data["summary"]
    out.info(f"Summary: {summary['ok']} OK, {summary['warn']} warnings, {summary['fail']} failures")
    out.info(f"Report generated at: {report_data['generated_at']}")

    if out.json_mode or out.format == "json":
        typer.echo(json_mod.dumps(report_data, indent=2))
