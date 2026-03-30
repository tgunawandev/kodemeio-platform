"""Trading operations commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.exceptions import GatewayError

app = typer.Typer(help="Trading bot operations (JournaltxDevBot).")

_GATEWAY_HINT = "Start the gateway first: kctl-claw deploy up"


@app.command()
def status(ctx: typer.Context) -> None:
    """Show trading bot status (Freqtrade, QuantConnect, Hummingbot)."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Fetching trading status from gateway...")
    try:
        data = actx.gateway.get("/api/trading/status")
        if isinstance(data, dict):
            rows = [[k, str(v)] for k, v in data.items()]
            out.table("Trading Status", [("Key", "cyan"), ("Value", "")], rows)
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command("kill-switch")
def kill_switch(ctx: typer.Context) -> None:
    """Emergency stop all trading bots (requires confirmation)."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.warn("This will immediately stop ALL trading bots.")
    confirmation = typer.prompt("Type 'KILL' to confirm")
    if confirmation != "KILL":
        out.info("Aborted.")
        return

    out.info("Sending kill-switch to gateway...")
    try:
        actx.gateway.post("/api/trading/kill-switch", {"confirm": True})
        out.success("Kill-switch activated — all trading bots stopped.")
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command("risk-limits")
def risk_limits(ctx: typer.Context) -> None:
    """Show risk limits configuration."""
    actx: AppContext = ctx.obj
    out = actx.output
    mgr = actx.config_mgr

    from kctl_claw.core.config_manager import ConfigFile

    data = mgr.read(ConfigFile.OPENCLAW)
    risk = data.get("trading", {}).get("riskLimits", {})

    if risk:
        rows = [[k, str(v)] for k, v in risk.items()]
        out.table(
            "Risk Limits",
            [("Parameter", "cyan"), ("Value", "")],
            rows,
            data_for_json=[{"parameter": k, "value": v} for k, v in risk.items()],
        )
    else:
        out.info("No risk limits configured in openclaw.json.")
        out.info("Configure under: trading.riskLimits")

        # Try gateway as fallback
        try:
            gw_data = actx.gateway.get("/api/trading/risk-limits")
            if isinstance(gw_data, dict):
                rows = [[k, str(v)] for k, v in gw_data.items()]
                out.table("Risk Limits (from gateway)", [("Parameter", "cyan"), ("Value", "")], rows)
        except GatewayError:
            pass


@app.command()
def portfolio(ctx: typer.Context) -> None:
    """Show portfolio overview (positions, P&L, balances)."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Fetching portfolio from gateway...")
    try:
        data = actx.gateway.get("/api/trading/portfolio")
        if isinstance(data, dict):
            rows = [[k, str(v)] for k, v in data.items()]
            out.table("Portfolio", [("Key", "cyan"), ("Value", "")], rows)
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command()
def strategies(ctx: typer.Context) -> None:
    """Show strategy performance summary."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Fetching strategies from gateway...")
    try:
        data = actx.gateway.get("/api/trading/strategies")
        if isinstance(data, list):
            rows = [[str(s.get("name", "")), str(s.get("status", "")), str(s.get("pnl", ""))] for s in data]
            out.table(
                f"Strategies ({len(data)})",
                [("Name", "cyan"), ("Status", ""), ("P&L", "dim")],
                rows,
            )
        elif isinstance(data, dict):
            rows = [[k, str(v)] for k, v in data.items()]
            out.table("Strategies", [("Key", "cyan"), ("Value", "")], rows)
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command()
def backtest(
    ctx: typer.Context,
    strategy: Annotated[str, typer.Argument(help="Strategy name")],
    period: Annotated[str, typer.Option("--period", help="Test period (e.g. 30d, 90d)")] = "30d",
) -> None:
    """Run a historical backtest for a strategy."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info(f"Running backtest for strategy {strategy!r} over {period!r}...")
    try:
        data = actx.gateway.post("/api/trading/backtest", {"strategy": strategy, "period": period})
        if isinstance(data, dict):
            sections = [
                (
                    "Backtest Results",
                    [
                        ("Strategy", strategy),
                        ("Period", period),
                        ("Total Trades", str(data.get("total_trades", ""))),
                        ("Win Rate", str(data.get("win_rate", ""))),
                        ("Total P&L", str(data.get("total_pnl", ""))),
                        ("Max Drawdown", str(data.get("max_drawdown", ""))),
                        ("Sharpe Ratio", str(data.get("sharpe_ratio", ""))),
                    ],
                )
            ]
            out.detail(f"Backtest: {strategy}", sections, data_for_json=data)
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command()
def simulate(
    ctx: typer.Context,
    strategy: Annotated[str, typer.Argument(help="Strategy name for paper trading")],
) -> None:
    """Start paper trading simulation for a strategy."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info(f"Starting paper trading simulation for strategy {strategy!r}...")
    try:
        data = actx.gateway.post("/api/trading/simulate", {"strategy": strategy})
        if isinstance(data, dict):
            out.success(f"Simulation started: {data.get('simulation_id', 'ok')}")
            sections = [("Simulation", [(k, str(v)) for k, v in data.items()])]
            out.detail(f"Paper Trade: {strategy}", sections, data_for_json=data)
        else:
            out.success(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command()
def history(
    ctx: typer.Context,
    count: Annotated[int, typer.Option("--count", help="Number of trades to show")] = 50,
) -> None:
    """Show trade history."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info(f"Fetching trade history (last {count})...")
    try:
        data = actx.gateway.get("/api/trading/history", count=count)
        if isinstance(data, list):
            rows = [
                [
                    str(t.get("id", ""))[:8],
                    str(t.get("strategy", "")),
                    str(t.get("side", "")),
                    str(t.get("pair", "")),
                    str(t.get("pnl", "")),
                    str(t.get("at", "")),
                ]
                for t in data
            ]
            out.table(
                f"Trade History ({len(data)})",
                [("ID", "dim"), ("Strategy", "cyan"), ("Side", ""), ("Pair", ""), ("P&L", ""), ("At", "dim")],
                rows,
                data_for_json=data,
            )
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command()
def compare(
    ctx: typer.Context,
    strategy_a: Annotated[str, typer.Argument(help="First strategy name")],
    strategy_b: Annotated[str, typer.Argument(help="Second strategy name")],
) -> None:
    """Compare performance of two strategies."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info(f"Comparing strategies: {strategy_a!r} vs {strategy_b!r}...")
    try:
        data = actx.gateway.post("/api/trading/compare", {"strategies": [strategy_a, strategy_b]})
        if isinstance(data, list):
            rows = [
                [
                    str(s.get("strategy", "")),
                    str(s.get("total_trades", "")),
                    str(s.get("win_rate", "")),
                    str(s.get("total_pnl", "")),
                    str(s.get("sharpe", "")),
                ]
                for s in data
            ]
            out.table(
                f"Strategy Comparison: {strategy_a} vs {strategy_b}",
                [("Strategy", "cyan"), ("Trades", ""), ("Win Rate", ""), ("P&L", ""), ("Sharpe", "dim")],
                rows,
                data_for_json=data,
            )
        elif isinstance(data, dict):
            rows = [[k, str(v)] for k, v in data.items()]
            out.table("Comparison", [("Metric", "cyan"), ("Value", "")], rows)
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)
