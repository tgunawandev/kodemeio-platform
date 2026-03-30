"""MCP server testing commands."""

from __future__ import annotations

import json
import time
from typing import Annotated

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.config_manager import ConfigFile
from kctl_claw.core.exceptions import NotFoundError

app = typer.Typer(help="Test MCP servers and tools.")


def _get_servers(actx: AppContext) -> dict:
    data = actx.config_mgr.read(ConfigFile.MCP_REGISTRY)
    return data.get("mcpServers", {})


@app.command()
def tool(
    ctx: typer.Context,
    server: Annotated[str, typer.Argument(help="MCP server name")],
    tool_name: Annotated[str, typer.Argument(help="Tool name to invoke")],
    params: Annotated[str, typer.Option("--params", help="JSON params string")] = "{}",
) -> None:
    """Invoke an MCP tool and validate the response."""
    actx: AppContext = ctx.obj
    out = actx.output

    servers = _get_servers(actx)
    if server not in servers:
        raise NotFoundError("MCP server", server, list(servers.keys()))

    try:
        params_dict = json.loads(params)
    except json.JSONDecodeError as e:
        out.error(f"Invalid JSON params: {e}")
        raise typer.Exit(1) from e

    out.info(f"Invoking tool {tool_name!r} on server {server!r}...")
    out.info(f"Params: {json.dumps(params_dict)}")

    # Simulate JSON-RPC call structure
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": params_dict},
    }

    cfg = servers[server]
    sections = [
        (
            "Request",
            [
                ("Server", server),
                ("Tool", tool_name),
                ("Method", request["method"]),
                ("Params", json.dumps(params_dict)),
            ],
        ),
        (
            "Server Config",
            [
                ("Command", cfg.get("command", "")),
                ("Args", " ".join(str(a) for a in cfg.get("args", []))),
                ("Env Vars", str(len(cfg.get("env", {})))),
            ],
        ),
    ]
    out.detail(
        f"MCP Tool Test: {server}/{tool_name}", sections, data_for_json={"request": request, "server_config": cfg}
    )
    out.warn("Live tool invocation requires a running container. Use gateway API for real calls.")


@app.command()
def server(
    ctx: typer.Context,
    server_name: Annotated[str, typer.Argument(help="MCP server name")],
) -> None:
    """Health check all tools registered for a server."""
    actx: AppContext = ctx.obj
    out = actx.output

    servers = _get_servers(actx)
    if server_name not in servers:
        raise NotFoundError("MCP server", server_name, list(servers.keys()))

    cfg = servers[server_name]
    out.info(f"Checking server: {server_name!r}")

    checks = [
        ("config_present", "OK", "Server entry found in config.json"),
        ("command_set", "OK" if cfg.get("command") else "WARN", cfg.get("command", "MISSING")),
        ("args_present", "OK" if cfg.get("args") else "INFO", f"{len(cfg.get('args', []))} args"),
        ("env_vars", "OK", f"{len(cfg.get('env', {}))} env vars configured"),
    ]

    rows = [[name, status, detail] for name, status, detail in checks]
    json_data = [{"check": name, "status": status, "detail": detail} for name, status, detail in checks]

    out.table(
        f"Server Health: {server_name}",
        [("Check", "cyan"), ("Status", ""), ("Detail", "dim")],
        rows,
        data_for_json=json_data,
    )
    out.warn("Full tool introspection requires a running gateway. Use: kctl-claw health check")


@app.command("all")
def all_(ctx: typer.Context) -> None:
    """Test all tools in all MCP servers."""
    actx: AppContext = ctx.obj
    out = actx.output

    servers = _get_servers(actx)

    rows = []
    json_data = []
    for srv_name, cfg in servers.items():
        command = cfg.get("command", "")
        args = cfg.get("args", [])
        env_count = len(cfg.get("env", {}))
        status = "OK" if command else "WARN"
        detail = f"cmd={command!r}, {len(args)} args, {env_count} env"
        rows.append([srv_name, status, detail])
        json_data.append({"server": srv_name, "status": status, "detail": detail})

    out.table(
        f"All MCP Server Checks ({len(servers)} servers)",
        [("Server", "cyan"), ("Status", ""), ("Detail", "dim")],
        rows,
        data_for_json=json_data,
    )
    out.info("For live tool tests, use: kctl-claw mcp-test tool <server> <tool>")


@app.command()
def bench(
    ctx: typer.Context,
    server: Annotated[str, typer.Argument(help="MCP server name")],
    tool_name: Annotated[str, typer.Argument(help="Tool name to benchmark")],
    iterations: Annotated[int, typer.Option("--iterations", help="Number of iterations")] = 10,
) -> None:
    """Benchmark latency for an MCP tool invocation."""
    actx: AppContext = ctx.obj
    out = actx.output

    servers = _get_servers(actx)
    if server not in servers:
        raise NotFoundError("MCP server", server, list(servers.keys()))

    out.info(f"Benchmarking {server}/{tool_name} over {iterations} iterations (simulated)...")

    # Simulate benchmark with config read latency
    timings = []
    for _i in range(iterations):
        start = time.perf_counter()
        _ = actx.config_mgr.read(ConfigFile.MCP_REGISTRY)
        elapsed = (time.perf_counter() - start) * 1000
        timings.append(elapsed)

    avg = sum(timings) / len(timings)
    min_t = min(timings)
    max_t = max(timings)
    p95 = sorted(timings)[int(len(timings) * 0.95)]

    sections = [
        (
            "Benchmark Results",
            [
                ("Server", server),
                ("Tool", tool_name),
                ("Iterations", str(iterations)),
                ("Avg (ms)", f"{avg:.2f}"),
                ("Min (ms)", f"{min_t:.2f}"),
                ("Max (ms)", f"{max_t:.2f}"),
                ("P95 (ms)", f"{p95:.2f}"),
            ],
        )
    ]
    out.detail(
        f"Benchmark: {server}/{tool_name}",
        sections,
        data_for_json={
            "server": server,
            "tool": tool_name,
            "iterations": iterations,
            "avg_ms": round(avg, 2),
            "min_ms": round(min_t, 2),
            "max_ms": round(max_t, 2),
            "p95_ms": round(p95, 2),
        },
    )
    out.warn("Note: timings reflect config I/O only. Live tool latency requires a running gateway.")


@app.command()
def protocol(
    ctx: typer.Context,
    server: Annotated[str, typer.Argument(help="MCP server name")],
    duration: Annotated[int, typer.Option("--duration", help="Capture duration in seconds")] = 30,
) -> None:
    """Capture JSON-RPC messages for a server (protocol trace)."""
    actx: AppContext = ctx.obj
    out = actx.output

    servers = _get_servers(actx)
    if server not in servers:
        raise NotFoundError("MCP server", server, list(servers.keys()))

    cfg = servers[server]
    out.info(f"Protocol trace for {server!r} (duration: {duration}s)")
    out.info(f"Command: {cfg.get('command', '')} {' '.join(str(a) for a in cfg.get('args', []))}")

    # Show example JSON-RPC messages for documentation purposes
    example_messages = [
        {
            "direction": "client->server",
            "message": {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
        },
        {
            "direction": "server->client",
            "message": {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"protocolVersion": "2024-11-05", "serverInfo": {"name": server}},
            },
        },
        {
            "direction": "client->server",
            "message": {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        },
    ]

    rows = [[m["direction"], json.dumps(m["message"])[:80]] for m in example_messages]
    out.table(
        f"Protocol Trace: {server} (example messages)",
        [("Direction", "cyan"), ("Message (preview)", "dim")],
        rows,
        data_for_json=example_messages,
    )
    out.warn(f"Live protocol capture (duration={duration}s) requires a running container.")
    out.info("Use: kctl-claw deploy up then check container logs for real JSON-RPC traffic.")
