"""AI cost analytics commands."""

from __future__ import annotations

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.exceptions import GatewayError

app = typer.Typer(help="AI usage and cost analytics.")

_GATEWAY_HINT = "Start the gateway first: kctl-claw deploy up"


@app.command()
def usage(ctx: typer.Context) -> None:
    """Show AI usage summary (tokens, cost, by model)."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Fetching AI usage from gateway...")
    try:
        data = actx.gateway.get("/api/ai/usage")
        if isinstance(data, dict):
            rows = [[k, str(v)] for k, v in data.items()]
            out.table("AI Usage", [("Metric", "cyan"), ("Value", "")], rows)
        elif isinstance(data, list):
            rows = [
                [str(item.get("model", "")), str(item.get("tokens", "")), str(item.get("cost", ""))] for item in data
            ]
            out.table("AI Usage", [("Model", "cyan"), ("Tokens", ""), ("Cost", "dim")], rows)
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command()
def cost(ctx: typer.Context) -> None:
    """Show cost projection (daily/weekly/monthly)."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Fetching cost projection from gateway...")
    try:
        data = actx.gateway.get("/api/ai/cost")
        if isinstance(data, dict):
            rows = [[k, str(v)] for k, v in data.items()]
            out.table("Cost Projection", [("Period", "cyan"), ("Estimated Cost", "")], rows)
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command()
def models(ctx: typer.Context) -> None:
    """Show model breakdown (requests, tokens, latency per model)."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Fetching model breakdown from gateway...")
    try:
        data = actx.gateway.get("/api/ai/models")
        if isinstance(data, list):
            rows = [
                [
                    str(m.get("model", "")),
                    str(m.get("requests", "")),
                    str(m.get("tokens", "")),
                    str(m.get("latency_ms", "")),
                ]
                for m in data
            ]
            out.table(
                f"Model Breakdown ({len(data)})",
                [("Model", "cyan"), ("Requests", ""), ("Tokens", ""), ("Latency (ms)", "dim")],
                rows,
            )
        elif isinstance(data, dict):
            rows = [[k, str(v)] for k, v in data.items()]
            out.table("Model Breakdown", [("Model", "cyan"), ("Value", "")], rows)
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command("top-consumers")
def top_consumers(ctx: typer.Context) -> None:
    """Show top token consumers (by agent, cron job, skill)."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Fetching top consumers from gateway...")
    try:
        data = actx.gateway.get("/api/ai/top-consumers")
        if isinstance(data, list):
            rows = [
                [
                    str(item.get("name", "")),
                    str(item.get("type", "")),
                    str(item.get("tokens", "")),
                ]
                for item in data
            ]
            out.table(
                f"Top Consumers ({len(data)})",
                [("Name", "cyan"), ("Type", ""), ("Tokens", "dim")],
                rows,
            )
        elif isinstance(data, dict):
            rows = [[k, str(v)] for k, v in data.items()]
            out.table("Top Consumers", [("Consumer", "cyan"), ("Tokens", "")], rows)
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)
