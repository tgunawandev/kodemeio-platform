"""Health check commands."""

from __future__ import annotations

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.config_manager import ConfigFile
from kctl_claw.core.exceptions import GatewayError

app = typer.Typer(help="Deep health checks for gateway, configs, and Docker.")


@app.command()
def check(ctx: typer.Context) -> None:
    """Full health check: config validation, Docker status, gateway ping."""
    actx: AppContext = ctx.obj
    out = actx.output
    mgr = actx.config_mgr

    results: list[tuple[str, str, str]] = []

    # Config file checks
    for cfg_name, cfg_file in [
        ("openclaw.json", ConfigFile.OPENCLAW),
        ("config.json", ConfigFile.MCP_REGISTRY),
        ("cron/jobs.json", ConfigFile.CRON_JOBS),
    ]:
        try:
            mgr.read(cfg_file)
            results.append((cfg_name, "OK", "readable"))
        except Exception as e:
            results.append((cfg_name, "FAIL", str(e)[:60]))

    # Gateway check
    try:
        actx.gateway.health()
        results.append(("gateway", "OK", "reachable"))
    except GatewayError as e:
        results.append(("gateway", "WARN", f"unavailable: {str(e)[:50]}"))
    except Exception as e:
        results.append(("gateway", "WARN", str(e)[:50]))

    # Docker check
    try:
        actx.docker.ps()
        results.append(("docker", "OK", "reachable"))
    except Exception as e:
        results.append(("docker", "WARN", f"unavailable: {str(e)[:50]}"))

    rows = [[name, status, detail] for name, status, detail in results]
    json_data = [{"check": name, "status": status, "detail": detail} for name, status, detail in results]

    failures = [r for r in results if r[1] == "FAIL"]
    warnings = [r for r in results if r[1] == "WARN"]

    out.table(
        f"Health Check ({len(results)} checks, {len(failures)} failed, {len(warnings)} warnings)",
        [("Check", "cyan"), ("Status", ""), ("Detail", "dim")],
        rows,
        data_for_json=json_data,
    )

    if failures:
        out.error(f"{len(failures)} check(s) failed.")
        raise typer.Exit(1)
    elif warnings:
        out.warn(f"{len(warnings)} warning(s) — gateway/docker may be offline.")
    else:
        out.success("All checks passed.")


@app.command()
def gateway(ctx: typer.Context) -> None:
    """Check gateway health: uptime, version, active connections."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Pinging gateway...")
    try:
        data = actx.gateway.health()
        if isinstance(data, dict):
            sections = [
                (
                    "Gateway",
                    [(k, str(v)) for k, v in data.items()],
                )
            ]
            out.detail("Gateway Health", sections, data_for_json=data)
        else:
            out.success(f"Gateway reachable: {data}")
    except GatewayError as e:
        out.warn(f"Gateway unavailable: {e}")
        out.info("Start the gateway: kctl-claw deploy up")
