"""MCP server management commands."""

from __future__ import annotations

import time
from typing import Annotated, Any

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.config_manager import ConfigFile
from kctl_claw.core.exceptions import GatewayError, NotFoundError

app = typer.Typer(help="Manage MCP server registry and tool profiles.")


def _get_servers(actx: AppContext) -> dict[str, Any]:
    """Read mcpServers from config.json."""
    from typing import cast

    data = actx.config_mgr.read(ConfigFile.MCP_REGISTRY)
    return cast(dict[str, Any], data.get("mcpServers", {}))


def _get_profiles(actx: AppContext) -> dict[str, Any]:
    """Read tool profiles from openclaw.json."""
    from typing import cast

    data = actx.config_mgr.read(ConfigFile.OPENCLAW)
    return cast(dict[str, Any], data.get("tools", {}).get("profiles", {}))


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all MCP servers."""
    actx: AppContext = ctx.obj
    out = actx.output

    servers = _get_servers(actx)

    rows = []
    json_data = []
    for name, cfg in servers.items():
        command = cfg.get("command", "")
        env_count = len(cfg.get("env", {}))
        args = cfg.get("args", [])
        rows.append([name, command, str(env_count), str(len(args))])
        json_data.append({"name": name, "command": command, "env_count": env_count, "args_count": len(args)})

    out.table(
        f"MCP Servers ({len(servers)})",
        [("Name", "cyan"), ("Command", ""), ("Env Vars", ""), ("Args", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def get(
    ctx: typer.Context,
    server: Annotated[str, typer.Argument(help="MCP server name")],
) -> None:
    """Show MCP server config detail."""
    actx: AppContext = ctx.obj
    out = actx.output

    servers = _get_servers(actx)
    if server not in servers:
        raise NotFoundError("MCP server", server, list(servers.keys()))

    cfg = servers[server]
    command = cfg.get("command", "")
    args = cfg.get("args", [])
    env = cfg.get("env", {})

    sections = [
        (
            "Config",
            [
                ("Name", server),
                ("Command", command),
                ("Args", " ".join(str(a) for a in args)),
            ],
        ),
    ]
    if env:
        env_pairs = [(k, v) for k, v in env.items()]
        sections.append(("Environment", env_pairs))

    out.detail(f"MCP Server: {server}", sections, data_for_json={"name": server, **cfg})


@app.command()
def tools(
    ctx: typer.Context,
    server: Annotated[str, typer.Argument(help="MCP server name")],
) -> None:
    """Show tools for an MCP server (placeholder — needs running container for full introspection)."""
    actx: AppContext = ctx.obj
    out = actx.output

    servers = _get_servers(actx)
    if server not in servers:
        raise NotFoundError("MCP server", server, list(servers.keys()))

    cfg = servers[server]
    args = cfg.get("args", [])

    out.info(f"Server: {server}")
    out.info(f"Command: {cfg.get('command', '')} {' '.join(str(a) for a in args)}")
    out.warn("Full tool introspection requires a running container. Use: kctl-claw mcp test <server>")


@app.command()
def profiles(ctx: typer.Context) -> None:
    """Show tool profile assignments."""
    actx: AppContext = ctx.obj
    out = actx.output

    profs = _get_profiles(actx)

    rows = []
    json_data = []
    for name, cfg in profs.items():
        servers = cfg.get("servers", [])
        denied = cfg.get("denied_tools", [])
        rows.append(
            [name, str(len(servers)), ", ".join(servers[:3]) + ("..." if len(servers) > 3 else ""), str(len(denied))]
        )
        json_data.append(
            {"profile": name, "server_count": len(servers), "servers": servers, "denied_tool_count": len(denied)}
        )

    out.table(
        f"Tool Profiles ({len(profs)})",
        [("Profile", "cyan"), ("# Servers", ""), ("Servers (preview)", ""), ("Denied Tools", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command("add-to-profile")
def add_to_profile(
    ctx: typer.Context,
    server: Annotated[str, typer.Argument(help="MCP server name")],
    profile: Annotated[str, typer.Argument(help="Tool profile name")],
) -> None:
    """Add an MCP server to a tool profile."""
    actx: AppContext = ctx.obj
    out = actx.output
    mgr = actx.config_mgr

    # Validate server exists
    servers = _get_servers(actx)
    if server not in servers:
        raise NotFoundError("MCP server", server, list(servers.keys()))

    mgr.backup_before_modify(ConfigFile.OPENCLAW)
    data = mgr.read(ConfigFile.OPENCLAW)

    profs = data.get("tools", {}).get("profiles", {})
    if profile not in profs:
        out.error(f"Profile not found: {profile!r}. Valid: {', '.join(profs)}")
        raise typer.Exit(1)

    prof_servers: list[str] = profs[profile].setdefault("servers", [])
    if server in prof_servers:
        out.warn(f"{server!r} is already in profile {profile!r}")
        return

    prof_servers.append(server)
    mgr.write(ConfigFile.OPENCLAW, data)
    out.success(f"Added {server!r} to profile {profile!r}")


@app.command("remove-from-profile")
def remove_from_profile(
    ctx: typer.Context,
    server: Annotated[str, typer.Argument(help="MCP server name")],
    profile: Annotated[str, typer.Argument(help="Tool profile name")],
) -> None:
    """Remove an MCP server from a tool profile."""
    actx: AppContext = ctx.obj
    out = actx.output
    mgr = actx.config_mgr

    mgr.backup_before_modify(ConfigFile.OPENCLAW)
    data = mgr.read(ConfigFile.OPENCLAW)

    profs = data.get("tools", {}).get("profiles", {})
    if profile not in profs:
        out.error(f"Profile not found: {profile!r}. Valid: {', '.join(profs)}")
        raise typer.Exit(1)

    prof_servers: list[str] = profs[profile].get("servers", [])
    if server not in prof_servers:
        out.warn(f"{server!r} is not in profile {profile!r}")
        return

    prof_servers.remove(server)
    mgr.write(ConfigFile.OPENCLAW, data)
    out.success(f"Removed {server!r} from profile {profile!r}")


@app.command()
def debug(
    ctx: typer.Context,
    server: Annotated[str, typer.Argument(help="MCP server name")],
) -> None:
    """Start an MCP server with JSON-RPC logging enabled."""
    actx: AppContext = ctx.obj
    out = actx.output

    servers = _get_servers(actx)
    if server not in servers:
        raise NotFoundError("MCP server", server, list(servers.keys()))

    cfg = servers[server]
    out.info(f"Debug mode for server {server!r}")
    out.info(f"Command: {cfg.get('command', '')} {' '.join(str(a) for a in cfg.get('args', []))}")
    out.info("Set MCP_DEBUG=1 env var to enable JSON-RPC logging in the container.")
    out.info("Use: kctl-claw deploy up, then check logs with: kctl-claw docker logs openclaw")

    try:
        data = actx.gateway.post(f"/api/mcp/servers/{server}/debug", {"enabled": True})
        if isinstance(data, dict):
            out.success(f"Debug logging enabled for {server!r}: {data}")
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info("Start the gateway first: kctl-claw deploy up")


@app.command()
def restart(
    ctx: typer.Context,
    server: Annotated[str, typer.Argument(help="MCP server name")],
) -> None:
    """Restart a specific MCP server via the gateway."""
    actx: AppContext = ctx.obj
    out = actx.output

    servers = _get_servers(actx)
    if server not in servers:
        raise NotFoundError("MCP server", server, list(servers.keys()))

    out.info(f"Restarting MCP server {server!r}...")
    try:
        data = actx.gateway.post(f"/api/mcp/servers/{server}/restart", {})
        if isinstance(data, dict):
            out.success(f"Server {server!r} restarted: {data.get('status', 'ok')}")
        else:
            out.success(f"Restart request sent for {server!r}.")
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info("Use 'kctl-claw deploy restart' to restart the full container.")


@app.command("test-tool")
def test_tool(
    ctx: typer.Context,
    server: Annotated[str, typer.Argument(help="MCP server name")],
    tool_name: Annotated[str, typer.Argument(help="Tool name to test")],
) -> None:
    """Quick alias for mcp-test tool — invoke a tool and show the result."""
    actx: AppContext = ctx.obj
    out = actx.output

    servers = _get_servers(actx)
    if server not in servers:
        raise NotFoundError("MCP server", server, list(servers.keys()))

    out.info(f"Testing tool {tool_name!r} on server {server!r}...")
    try:
        data = actx.gateway.post(f"/api/mcp/servers/{server}/tools/{tool_name}/call", {"arguments": {}})
        if isinstance(data, dict):
            sections = [("Result", [(k, str(v)[:100]) for k, v in data.items()])]
            out.detail(f"Tool Test: {server}/{tool_name}", sections, data_for_json=data)
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info("Use 'kctl-claw mcp-test tool <server> <tool>' for full offline testing.")


@app.command()
def latency(ctx: typer.Context) -> None:
    """Show per-tool latency report from the gateway."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Fetching tool latency report...")
    try:
        data = actx.gateway.get("/api/mcp/latency")
        if isinstance(data, list):
            rows = [
                [
                    str(d.get("server", "")),
                    str(d.get("tool", "")),
                    str(d.get("avg_ms", "")),
                    str(d.get("p95_ms", "")),
                    str(d.get("calls", "")),
                ]
                for d in data
            ]
            out.table(
                f"Tool Latency ({len(data)} tools)",
                [("Server", "cyan"), ("Tool", ""), ("Avg (ms)", ""), ("P95 (ms)", ""), ("Calls", "dim")],
                rows,
                data_for_json=data,
            )
        elif isinstance(data, dict):
            rows = [[k, str(v)] for k, v in data.items()]
            out.table("Tool Latency", [("Key", "cyan"), ("Value", "")], rows)
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info("Start the gateway first: kctl-claw deploy up")
        # Show config-based fallback
        servers = _get_servers(actx)
        out.info(f"({len(servers)} MCP servers configured locally)")
        _ = time  # ensure import is used
