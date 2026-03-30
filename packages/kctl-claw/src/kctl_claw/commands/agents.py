"""Agent management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.exceptions import GatewayError
from kctl_claw.core.resolve import get_all_agents, resolve_agent

_GATEWAY_HINT = "Start the gateway first: kctl-claw deploy up"

app = typer.Typer(help="Manage OpenClaw agents.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all configured agents."""
    actx: AppContext = ctx.obj
    out = actx.output
    agents = get_all_agents(actx.config_mgr)

    rows = []
    json_data = []
    for a in agents:
        name = a["name"]
        model = a.get("model", "default")
        profile = a.get("profile", "default")
        thinking = a.get("thinking", "adaptive")
        rows.append([name, model, profile, thinking])
        json_data.append({"name": name, "model": model, "profile": profile, "thinking": thinking})

    out.table(
        f"Agents ({len(agents)})",
        [("Name", "cyan"), ("Model", ""), ("Profile", ""), ("Thinking", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def get(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Agent name")],
) -> None:
    """Get detailed agent info."""
    actx: AppContext = ctx.obj
    out = actx.output
    agent = resolve_agent(actx.config_mgr, name)

    sections = [
        (
            "Config",
            [
                ("Name", agent["name"]),
                ("Model", agent.get("model", "default")),
                ("Profile", agent.get("profile", "default")),
                ("Thinking", agent.get("thinking", "adaptive")),
                ("Sandbox", str(agent.get("sandbox", True))),
            ],
        ),
    ]
    if agent.get("workspace"):
        sections[0][1].append(("Workspace", agent["workspace"]))

    out.detail(f"Agent: {name}", sections, data_for_json=agent)


@app.command("set-model")
def set_model(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Agent name")],
    model: Annotated[str, typer.Argument(help="Model ID (e.g. claude-opus-4-6)")],
) -> None:
    """Change an agent's primary model."""
    actx: AppContext = ctx.obj
    out = actx.output
    mgr = actx.config_mgr

    from kctl_claw.core.config_manager import ConfigFile

    agent = resolve_agent(mgr, name)
    old_model = agent.get("model", "default")

    mgr.backup_before_modify(ConfigFile.OPENCLAW)
    data = mgr.read(ConfigFile.OPENCLAW)
    for a in data["agents"]["list"]:
        if a["name"] == name:
            a["model"] = model
            break
    mgr.write(ConfigFile.OPENCLAW, data)
    out.success(f"{name}: {old_model} -> {model}")

    if actx.live:
        out.info("Reloading gateway...")
        # DockerClient.restart() would go here when available


@app.command("set-profile")
def set_profile(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Agent name")],
    profile: Annotated[str, typer.Argument(help="Tool profile name")],
) -> None:
    """Change an agent's tool profile."""
    actx: AppContext = ctx.obj
    out = actx.output
    mgr = actx.config_mgr

    from kctl_claw.core.config_manager import ConfigFile

    agent = resolve_agent(mgr, name)
    old_profile = agent.get("profile", "default")

    mgr.backup_before_modify(ConfigFile.OPENCLAW)
    data = mgr.read(ConfigFile.OPENCLAW)
    for a in data["agents"]["list"]:
        if a["name"] == name:
            a["profile"] = profile
            break
    mgr.write(ConfigFile.OPENCLAW, data)
    out.success(f"{name}: profile {old_profile} -> {profile}")


@app.command("set-thinking")
def set_thinking(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Agent name")],
    mode: Annotated[str, typer.Argument(help="Thinking mode (adaptive/medium/high/off)")],
) -> None:
    """Change an agent's thinking mode."""
    actx: AppContext = ctx.obj
    out = actx.output
    mgr = actx.config_mgr

    valid_modes = ["adaptive", "medium", "high", "off"]
    if mode not in valid_modes:
        out.error(f"Invalid mode: {mode} (valid: {', '.join(valid_modes)})")
        raise typer.Exit(1)

    from kctl_claw.core.config_manager import ConfigFile

    resolve_agent(mgr, name)

    mgr.backup_before_modify(ConfigFile.OPENCLAW)
    data = mgr.read(ConfigFile.OPENCLAW)
    for a in data["agents"]["list"]:
        if a["name"] == name:
            a["thinking"] = mode
            break
    mgr.write(ConfigFile.OPENCLAW, data)
    out.success(f"{name}: thinking -> {mode}")


@app.command()
def workspace(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Agent name")],
) -> None:
    """Show agent workspace structure."""
    actx: AppContext = ctx.obj
    out = actx.output
    resolve_agent(actx.config_mgr, name)

    root = actx.project_root
    # Main agent uses config/workspace/, others use config/agents/<name>/workspace/
    ws_dir = root / "config" / "workspace" if name == "kodemeiodev" else root / "config" / "agents" / name / "workspace"

    if not ws_dir.exists():
        out.warn(f"Workspace not found: {ws_dir}")
        return

    nodes = []
    for item in sorted(ws_dir.iterdir()):
        if item.is_dir():
            children = [{"name": f.name} for f in sorted(item.iterdir()) if not f.name.startswith(".")]
            nodes.append({"name": f"{item.name}/", "children": children})
        else:
            size = f"{item.stat().st_size:,} bytes"
            nodes.append({"name": item.name, "info": size})

    out.tree(f"Workspace: {name}", nodes)


@app.command()
def test(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Agent name")],
    prompt: Annotated[str, typer.Argument(help="Test prompt to send")],
) -> None:
    """Quick test — send a prompt to an agent and show the response."""
    actx: AppContext = ctx.obj
    out = actx.output

    resolve_agent(actx.config_mgr, name)
    out.info(f"Testing agent {name!r} with: {prompt[:80]!r}")

    try:
        data = actx.gateway.post(f"/api/agents/{name}/message", {"content": prompt, "test": True})
        if isinstance(data, dict):
            sections = [
                (
                    "Response",
                    [
                        ("Agent", name),
                        ("Status", str(data.get("status", ""))),
                        ("Content", str(data.get("content", ""))[:300]),
                        ("Model", str(data.get("model", ""))),
                        ("Tokens", str(data.get("tokens", ""))),
                    ],
                )
            ]
            out.detail(f"Agent Test: {name}", sections, data_for_json=data)
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command()
def replay(
    ctx: typer.Context,
    conversation_id: Annotated[str, typer.Argument(help="Conversation ID to replay")],
) -> None:
    """Quick replay — replay a conversation and diff the output."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info(f"Replaying conversation: {conversation_id!r}...")
    try:
        data = actx.gateway.post(f"/api/conversations/{conversation_id}/replay", {})
        if isinstance(data, dict):
            diffs = data.get("diffs", [])
            rows = [[str(d.get("turn", "")), str(d.get("field", "")), str(d.get("delta", ""))] for d in diffs]
            out.table(
                f"Replay Diff ({len(diffs)} differences)",
                [("Turn", "cyan"), ("Field", ""), ("Delta", "dim")],
                rows,
                data_for_json=data,
            )
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command()
def stats(ctx: typer.Context) -> None:
    """Show per-agent stats: message count, token usage."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Fetching agent stats from gateway...")
    try:
        data = actx.gateway.get("/api/agents/stats")
        if isinstance(data, list):
            rows = [
                [
                    str(s.get("agent", "")),
                    str(s.get("messages", "")),
                    str(s.get("tokens_in", "")),
                    str(s.get("tokens_out", "")),
                    str(s.get("cost_usd", "")),
                ]
                for s in data
            ]
            out.table(
                f"Agent Stats ({len(data)} agents)",
                [("Agent", "cyan"), ("Messages", ""), ("Tokens In", ""), ("Tokens Out", ""), ("Cost USD", "dim")],
                rows,
                data_for_json=data,
            )
        elif isinstance(data, dict):
            rows = [[k, str(v)] for k, v in data.items()]
            out.table("Agent Stats", [("Key", "cyan"), ("Value", "")], rows)
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command("compare-models")
def compare_models(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Agent name")],
) -> None:
    """Compare model performance for a given agent."""
    actx: AppContext = ctx.obj
    out = actx.output

    agent = resolve_agent(actx.config_mgr, name)
    current_model = agent.get("model", "default")

    out.info(f"Model performance comparison for agent {name!r} (current: {current_model!r})")
    try:
        data = actx.gateway.get(f"/api/agents/{name}/model-comparison")
        if isinstance(data, list):
            rows = [
                [
                    str(m.get("model", "")),
                    str(m.get("avg_latency_ms", "")),
                    str(m.get("avg_tokens", "")),
                    str(m.get("avg_cost_usd", "")),
                    str(m.get("success_rate", "")),
                ]
                for m in data
            ]
            out.table(
                f"Model Comparison: {name}",
                [("Model", "cyan"), ("Avg Latency", ""), ("Avg Tokens", ""), ("Avg Cost", ""), ("Success %", "dim")],
                rows,
                data_for_json=data,
            )
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)
