"""Production monitoring commands."""

from __future__ import annotations

import time

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.config_manager import ConfigFile
from kctl_claw.core.exceptions import GatewayError

app = typer.Typer(help="Production monitoring: gateway, agents, MCP servers, alerts.")

_GATEWAY_HINT = "Start the gateway first: kctl-claw deploy up"


@app.command()
def gateway(ctx: typer.Context) -> None:
    """Check gateway health and display status."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Checking gateway health...")
    try:
        start = time.perf_counter()
        data = actx.gateway.health()
        latency_ms = (time.perf_counter() - start) * 1000

        if isinstance(data, dict):
            sections = [
                (
                    "Gateway",
                    [(k, str(v)) for k, v in data.items()] + [("Latency (ms)", f"{latency_ms:.0f}")],
                )
            ]
            out.detail("Gateway Health", sections, data_for_json={**data, "latency_ms": round(latency_ms, 1)})
        else:
            out.success(f"Gateway reachable (latency: {latency_ms:.0f}ms)")
    except GatewayError as e:
        out.warn(f"Gateway unavailable: {e}")
        out.info(_GATEWAY_HINT)


@app.command()
def agents(ctx: typer.Context) -> None:
    """Check per-agent availability via the gateway."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Checking agent availability...")

    # Get configured agents
    try:
        openclaw = actx.config_mgr.read(ConfigFile.OPENCLAW)
        agent_list = openclaw.get("agents", {}).get("list", [])
    except Exception as e:
        out.error(f"Cannot read config: {e}")
        raise typer.Exit(1) from e

    rows = []
    json_data = []
    for agent in agent_list:
        name = agent.get("name", "")
        model = agent.get("model", "default")
        start = time.perf_counter()
        try:
            data = actx.gateway.get(f"/api/agents/{name}/status")
            latency_ms = (time.perf_counter() - start) * 1000
            status = data.get("status", "ok") if isinstance(data, dict) else "ok"
            rows.append([name, model, status, f"{latency_ms:.0f}ms"])
            json_data.append({"agent": name, "model": model, "status": status, "latency_ms": round(latency_ms, 1)})
        except GatewayError as e:
            latency_ms = (time.perf_counter() - start) * 1000
            rows.append([name, model, f"UNAVAIL: {str(e)[:30]}", f"{latency_ms:.0f}ms"])
            json_data.append({"agent": name, "model": model, "status": "unavailable", "error": str(e)})

    if not rows:
        out.warn("No agents configured.")
        return

    out.table(
        f"Agent Availability ({len(rows)} agents)",
        [("Agent", "cyan"), ("Model", ""), ("Status", ""), ("Latency", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command("mcp-health")
def mcp_health(ctx: typer.Context) -> None:
    """Check MCP server health (reads registry + pings gateway endpoint)."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        mcp_data = actx.config_mgr.read(ConfigFile.MCP_REGISTRY)
        servers = mcp_data.get("mcpServers", {})
    except Exception as e:
        out.error(f"Cannot read MCP registry: {e}")
        raise typer.Exit(1) from e

    rows = []
    json_data = []
    for name, cfg in servers.items():
        command = cfg.get("command", "")
        config_ok = "OK" if command else "WARN"

        # Try gateway MCP status endpoint
        start = time.perf_counter()
        try:
            data = actx.gateway.get(f"/api/mcp/servers/{name}/status")
            latency_ms = (time.perf_counter() - start) * 1000
            gw_status = data.get("status", "ok") if isinstance(data, dict) else "ok"
        except GatewayError:
            latency_ms = (time.perf_counter() - start) * 1000
            gw_status = "gateway-offline"

        rows.append([name, config_ok, gw_status, f"{latency_ms:.0f}ms"])
        json_data.append(
            {
                "server": name,
                "config_status": config_ok,
                "gateway_status": gw_status,
                "latency_ms": round(latency_ms, 1),
            }
        )

    out.table(
        f"MCP Server Health ({len(rows)} servers)",
        [("Server", "cyan"), ("Config", ""), ("Gateway Status", ""), ("Latency", "dim")],
        rows,
        data_for_json=json_data,
    )

    failures = [r for r in rows if r[1] != "OK"]
    if failures:
        out.warn(f"{len(failures)} server(s) have config issues.")
    else:
        out.success("All MCP server configs look healthy.")


@app.command()
def alerts(ctx: typer.Context) -> None:
    """Alert on gateway, agent, or MCP failures."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Checking for active alerts...")

    alerts_found: list[tuple[str, str, str]] = []

    # Gateway
    try:
        actx.gateway.health()
    except GatewayError as e:
        alerts_found.append(("CRITICAL", "gateway", f"Gateway unreachable: {e}"))

    # Config validation
    for cfg_name, cfg_file in [
        ("openclaw.json", ConfigFile.OPENCLAW),
        ("config.json", ConfigFile.MCP_REGISTRY),
        ("cron/jobs.json", ConfigFile.CRON_JOBS),
    ]:
        errors = actx.config_mgr.validate_json(cfg_file)
        for err in errors:
            alerts_found.append(("WARN", f"config:{cfg_name}", err))

    # Docker
    try:
        actx.docker.ps()
    except Exception as e:
        alerts_found.append(("CRITICAL", "docker", f"Docker unavailable: {str(e)[:60]}"))

    if not alerts_found:
        out.success("No active alerts — system is healthy.")
        return

    rows = [[level, source, message] for level, source, message in alerts_found]
    json_data = [{"level": level, "source": source, "message": message} for level, source, message in alerts_found]

    out.table(
        f"Active Alerts ({len(alerts_found)})",
        [("Level", "cyan"), ("Source", ""), ("Message", "dim")],
        rows,
        data_for_json=json_data,
    )

    critical = [a for a in alerts_found if a[0] == "CRITICAL"]
    if critical:
        out.error(f"{len(critical)} critical alert(s) require immediate attention.")
        raise typer.Exit(1)
