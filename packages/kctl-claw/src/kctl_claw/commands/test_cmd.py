"""Test runner commands."""

from __future__ import annotations

import subprocess
from pathlib import Path

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.config_manager import ConfigFile
from kctl_claw.core.exceptions import GatewayError

app = typer.Typer(help="Run unit, integration, and smoke tests.")

_GATEWAY_HINT = "Start the gateway first: kctl-claw deploy up"


@app.command()
def unit(ctx: typer.Context) -> None:
    """Run MCP server unit tests if test files exist."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = actx.project_root
    test_patterns = ["test/", "tests/", "*.test.mjs", "*.spec.mjs", "*.test.js"]
    found_tests: list[Path] = []

    for pattern in test_patterns:
        found_tests.extend(root.glob(pattern))

    if not found_tests:
        out.warn("No test files found. Expected: test/, tests/, *.test.mjs")
        out.info("MCP server tests should be placed in mcp-servers/test/ or tests/")
        return

    out.info(f"Found {len(found_tests)} test file(s)/director(ies). Running...")

    # Try node test runner
    node_path = __import__("shutil").which("node")
    if not node_path:
        out.error("node not found in PATH — cannot run MCP server tests.")
        raise typer.Exit(1)

    results = []
    for test_path in sorted(found_tests)[:10]:
        if test_path.is_file() and test_path.suffix in (".mjs", ".js"):
            try:
                result = subprocess.run(
                    ["node", "--test", str(test_path)],
                    capture_output=True,
                    text=True,
                    cwd=str(root),
                    timeout=30,
                    check=False,
                )
                status = "PASS" if result.returncode == 0 else "FAIL"
                detail = result.stdout.strip()[:80] or result.stderr.strip()[:80]
                results.append([str(test_path.relative_to(root)), status, detail])
            except subprocess.TimeoutExpired:
                results.append([str(test_path.relative_to(root)), "TIMEOUT", "exceeded 30s"])

    if results:
        out.table(
            f"Unit Tests ({len(results)} files)",
            [("File", "cyan"), ("Status", ""), ("Detail", "dim")],
            results,
            data_for_json=[{"file": r[0], "status": r[1], "detail": r[2]} for r in results],
        )
        failed = [r for r in results if r[1] != "PASS"]
        if failed:
            out.error(f"{len(failed)} test file(s) failed.")
            raise typer.Exit(1)
        else:
            out.success("All unit tests passed.")
    else:
        out.info("No runnable .mjs/.js test files found.")


@app.command()
def integration(ctx: typer.Context) -> None:
    """Test MCP server communication (requires running container)."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Running integration tests...")

    results: list[tuple[str, str, str]] = []

    # 1. Config files are readable
    for cfg_name, cfg_file in [
        ("openclaw.json", ConfigFile.OPENCLAW),
        ("config.json", ConfigFile.MCP_REGISTRY),
        ("cron/jobs.json", ConfigFile.CRON_JOBS),
    ]:
        try:
            actx.config_mgr.read(cfg_file)
            results.append((f"config:{cfg_name}", "PASS", "Readable"))
        except Exception as e:
            results.append((f"config:{cfg_name}", "FAIL", str(e)[:60]))

    # 2. MCP server registry has entries
    try:
        mcp_data = actx.config_mgr.read(ConfigFile.MCP_REGISTRY)
        servers = mcp_data.get("mcpServers", {})
        if servers:
            results.append(("mcp:registry", "PASS", f"{len(servers)} servers configured"))
        else:
            results.append(("mcp:registry", "FAIL", "No MCP servers defined"))
    except Exception as e:
        results.append(("mcp:registry", "FAIL", str(e)[:60]))

    # 3. Gateway MCP endpoint
    try:
        data = actx.gateway.get("/api/mcp/servers")
        if isinstance(data, (list, dict)):
            count = len(data) if isinstance(data, list) else len(data.get("servers", []))
            results.append(("gateway:mcp", "PASS", f"{count} servers reported by gateway"))
        else:
            results.append(("gateway:mcp", "PASS", "MCP endpoint reachable"))
    except GatewayError as e:
        results.append(("gateway:mcp", "SKIP", f"Gateway unavailable: {str(e)[:50]}"))

    # 4. Agents configured
    try:
        openclaw = actx.config_mgr.read(ConfigFile.OPENCLAW)
        agents = openclaw.get("agents", {}).get("list", [])
        if agents:
            results.append(("agents:config", "PASS", f"{len(agents)} agents configured"))
        else:
            results.append(("agents:config", "FAIL", "No agents defined"))
    except Exception as e:
        results.append(("agents:config", "FAIL", str(e)[:60]))

    rows = [[name, status, detail] for name, status, detail in results]
    json_data = [{"test": name, "status": status, "detail": detail} for name, status, detail in results]

    failures = [r for r in results if r[1] == "FAIL"]
    out.table(
        f"Integration Tests ({len(results)} tests, {len(failures)} failed)",
        [("Test", "cyan"), ("Status", ""), ("Detail", "dim")],
        rows,
        data_for_json=json_data,
    )

    if failures:
        out.error(f"{len(failures)} integration test(s) failed.")
        raise typer.Exit(1)
    else:
        out.success("All integration tests passed.")


@app.command()
def smoke(ctx: typer.Context) -> None:
    """Gateway health + agent response smoke test."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Running smoke tests...")
    results: list[tuple[str, str, str]] = []

    # 1. Gateway health
    try:
        data = actx.gateway.health()
        status_val = data.get("status", "unknown") if isinstance(data, dict) else "ok"
        results.append(("gateway:health", "PASS", f"status={status_val}"))
    except GatewayError as e:
        results.append(("gateway:health", "FAIL", str(e)[:60]))

    # 2. Agents list via gateway
    try:
        data = actx.gateway.get("/api/agents")
        count = len(data) if isinstance(data, list) else 1
        results.append(("gateway:agents", "PASS", f"{count} agent(s) responding"))
    except GatewayError as e:
        results.append(("gateway:agents", "SKIP", str(e)[:60]))

    # 3. Agent response (first configured agent)
    try:
        openclaw = actx.config_mgr.read(ConfigFile.OPENCLAW)
        agents = openclaw.get("agents", {}).get("list", [])
        if agents:
            first_agent = agents[0]["name"]
            try:
                actx.gateway.post(
                    f"/api/agents/{first_agent}/message",
                    {"content": "ping", "test": True},
                )
                results.append(("agent:response", "PASS", f"{first_agent} responded"))
            except GatewayError as e:
                results.append(("agent:response", "SKIP", f"Gateway unavailable: {str(e)[:40]}"))
        else:
            results.append(("agent:response", "SKIP", "No agents configured"))
    except Exception as e:
        results.append(("agent:response", "SKIP", str(e)[:60]))

    rows = [[name, status, detail] for name, status, detail in results]
    json_data = [{"test": name, "status": status, "detail": detail} for name, status, detail in results]

    failures = [r for r in results if r[1] == "FAIL"]
    out.table(
        f"Smoke Tests ({len(results)} tests, {len(failures)} failed)",
        [("Test", "cyan"), ("Status", ""), ("Detail", "dim")],
        rows,
        data_for_json=json_data,
    )

    if failures:
        out.error(f"{len(failures)} smoke test(s) failed.")
        out.info(_GATEWAY_HINT)
        raise typer.Exit(1)
    else:
        out.success("Smoke tests passed.")
