"""Agent behavior testing commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.exceptions import GatewayError
from kctl_claw.core.resolve import get_all_agents, resolve_agent

app = typer.Typer(help="Test agent behavior: prompts, replay, regression, benchmarks.")

_GATEWAY_HINT = "Start the gateway first: kctl-claw deploy up"


@app.command("run")
def run(
    ctx: typer.Context,
    agent: Annotated[str, typer.Argument(help="Agent name")],
    prompt: Annotated[str, typer.Argument(help="Test prompt to send")],
) -> None:
    """Send a test prompt to an agent and capture the response."""
    actx: AppContext = ctx.obj
    out = actx.output

    resolve_agent(actx.config_mgr, agent)
    out.info(f"Sending test prompt to agent {agent!r}...")
    out.info(f"Prompt: {prompt[:100]}")

    try:
        data = actx.gateway.post(f"/api/agents/{agent}/message", {"content": prompt, "test": True})
        if isinstance(data, dict):
            sections = [
                (
                    "Response",
                    [
                        ("Agent", agent),
                        ("Status", str(data.get("status", ""))),
                        ("Content", str(data.get("content", ""))[:200]),
                        ("Tokens", str(data.get("tokens", ""))),
                        ("Model", str(data.get("model", ""))),
                    ],
                )
            ]
            out.detail(f"Agent Test: {agent}", sections, data_for_json=data)
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
    """Replay a conversation and diff the output against the original."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info(f"Replaying conversation: {conversation_id!r}...")
    try:
        data = actx.gateway.post(f"/api/conversations/{conversation_id}/replay", {})
        if isinstance(data, dict):
            original = data.get("original", {})
            replayed = data.get("replayed", {})
            diffs = data.get("diffs", [])

            rows = [[str(d.get("turn", "")), str(d.get("field", "")), str(d.get("delta", ""))] for d in diffs]
            out.table(
                f"Replay Diff: {conversation_id} ({len(diffs)} differences)",
                [("Turn", "cyan"), ("Field", ""), ("Delta", "dim")],
                rows,
                data_for_json={
                    "conversation_id": conversation_id,
                    "original": original,
                    "replayed": replayed,
                    "diffs": diffs,
                },
            )
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command()
def regression(
    ctx: typer.Context,
    test_file: Annotated[str, typer.Argument(help="YAML test suite file path")],
) -> None:
    """Run a YAML regression test suite (prompts + expected patterns)."""
    actx: AppContext = ctx.obj
    out = actx.output

    import re
    from pathlib import Path

    test_path = Path(test_file)
    if not test_path.exists():
        out.error(f"Test file not found: {test_file}")
        raise typer.Exit(1)

    try:
        import yaml  # type: ignore[import-untyped]

        suite = yaml.safe_load(test_path.read_text())
    except ImportError as err:
        out.error("PyYAML not installed. Run: uv add pyyaml")
        raise typer.Exit(1) from err
    except Exception as e:
        out.error(f"Failed to parse test file: {e}")
        raise typer.Exit(1) from e

    tests = suite.get("tests", [])
    out.info(f"Running {len(tests)} regression tests from {test_file}...")

    rows = []
    json_data = []
    passed = 0
    failed = 0

    for i, t in enumerate(tests):
        name = t.get("name", f"test_{i}")
        agent = t.get("agent", "")
        prompt = t.get("prompt", "")
        expected_patterns = t.get("expect", [])

        try:
            data = actx.gateway.post(f"/api/agents/{agent}/message", {"content": prompt, "test": True})
            content = str(data.get("content", "") if isinstance(data, dict) else data)

            all_matched = all(re.search(pat, content, re.IGNORECASE) for pat in expected_patterns)
            status = "PASS" if all_matched else "FAIL"
            if all_matched:
                passed += 1
            else:
                failed += 1
            detail = f"{len(expected_patterns)} patterns checked"
        except GatewayError as e:
            status = "ERROR"
            failed += 1
            detail = str(e)[:50]

        rows.append([name, agent, status, detail])
        json_data.append({"name": name, "agent": agent, "status": status, "detail": detail})

    out.table(
        f"Regression Results ({passed} passed, {failed} failed)",
        [("Test", "cyan"), ("Agent", ""), ("Status", ""), ("Detail", "dim")],
        rows,
        data_for_json=json_data,
    )

    if failed:
        out.error(f"{failed} test(s) failed.")
        raise typer.Exit(1)
    else:
        out.success("All regression tests passed.")


@app.command()
def benchmark(
    ctx: typer.Context,
    agent: Annotated[str, typer.Argument(help="Agent name")],
    prompt: Annotated[str, typer.Argument(help="Test prompt")],
    models: Annotated[str, typer.Option("--models", help="Comma-separated model list")] = "",
) -> None:
    """Compare quality, cost, and latency across multiple models for an agent."""
    actx: AppContext = ctx.obj
    out = actx.output

    resolve_agent(actx.config_mgr, agent)
    model_list = [m.strip() for m in models.split(",") if m.strip()] if models else ["default"]

    out.info(f"Benchmarking agent {agent!r} across {len(model_list)} model(s)...")

    rows = []
    json_data = []
    for model in model_list:
        import time

        start = time.perf_counter()
        try:
            data = actx.gateway.post(
                f"/api/agents/{agent}/message",
                {"content": prompt, "test": True, "model": model},
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            tokens = data.get("tokens", 0) if isinstance(data, dict) else 0
            cost = data.get("cost_usd", "N/A") if isinstance(data, dict) else "N/A"
            status = "OK"
        except GatewayError as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            tokens = 0
            cost = "N/A"
            status = f"ERR: {str(e)[:30]}"

        rows.append([model, status, f"{elapsed_ms:.0f}ms", str(tokens), str(cost)])
        json_data.append(
            {"model": model, "status": status, "latency_ms": round(elapsed_ms, 1), "tokens": tokens, "cost_usd": cost}
        )

    out.table(
        f"Benchmark: {agent}",
        [("Model", "cyan"), ("Status", ""), ("Latency", ""), ("Tokens", ""), ("Cost", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def compare(
    ctx: typer.Context,
    prompt: Annotated[str, typer.Argument(help="Test prompt")],
    model_a: Annotated[str, typer.Option("--a", help="First model ID")] = "claude-opus-4-6",
    model_b: Annotated[str, typer.Option("--b", help="Second model ID")] = "claude-sonnet-4",
) -> None:
    """Side-by-side model comparison for a given prompt."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info(f"Comparing {model_a!r} vs {model_b!r}...")

    results = {}
    for model in [model_a, model_b]:
        import time

        start = time.perf_counter()
        try:
            data = actx.gateway.post("/api/agents/compare", {"content": prompt, "model": model})
            elapsed_ms = (time.perf_counter() - start) * 1000
            results[model] = {
                "status": "OK",
                "content": str(data.get("content", ""))[:200] if isinstance(data, dict) else str(data)[:200],
                "latency_ms": round(elapsed_ms, 1),
                "tokens": data.get("tokens", "N/A") if isinstance(data, dict) else "N/A",
            }
        except GatewayError as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            results[model] = {"status": f"ERR: {e}", "content": "", "latency_ms": round(elapsed_ms, 1), "tokens": "N/A"}

    rows = [
        [model_a, results[model_a]["status"], f"{results[model_a]['latency_ms']}ms", results[model_a]["content"][:60]],
        [model_b, results[model_b]["status"], f"{results[model_b]['latency_ms']}ms", results[model_b]["content"][:60]],
    ]
    out.table(
        "Model Comparison",
        [("Model", "cyan"), ("Status", ""), ("Latency", ""), ("Response Preview", "dim")],
        rows,
        data_for_json=results,
    )
    if results[model_a]["status"] == "OK" or results[model_b]["status"] == "OK":
        out.info("Full responses available via gateway API.")
    else:
        out.warn(_GATEWAY_HINT)


def _get_all_agents(actx: AppContext) -> list[dict]:
    return get_all_agents(actx.config_mgr)
