"""Rate limit management commands for kctl-api.

Inspect tier config, test rate limits, and check Redis state.
"""

from __future__ import annotations

import asyncio
import time
from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext

app = typer.Typer(name="rate-limit", help="Rate limit — tiers, test, status, simulate.", no_args_is_help=True)

# Default tier config matches kctl-lib RateTier + DEFAULT_TIERS
_DEFAULT_TIERS: dict[str, int] = {
    "free": 30,
    "user": 100,
    "premium": 300,
    "admin": 600,
}
_WINDOW_SECONDS = 60


# ---------------------------------------------------------------------------
# tiers
# ---------------------------------------------------------------------------
@app.command()
def tiers(ctx: typer.Context) -> None:
    """Show tier rate limit configuration (requests per minute)."""
    actx: AppContext = ctx.obj
    out = actx.output

    rows = [
        [tier, str(rpm), str(round(rpm / _WINDOW_SECONDS, 2)), f"~{round(_WINDOW_SECONDS / rpm * 1000)}ms min interval"]
        for tier, rpm in _DEFAULT_TIERS.items()
    ]

    out.table(
        title="Rate Limit Tiers (requests per 60s window)",
        columns=[
            ("Tier", "bold"),
            ("Req/min", ""),
            ("Req/sec", ""),
            ("Note", ""),
        ],
        rows=rows,
        data_for_json=[{"tier": t, "rpm": r, "window_seconds": _WINDOW_SECONDS} for t, r in _DEFAULT_TIERS.items()],
    )


# ---------------------------------------------------------------------------
# test
# ---------------------------------------------------------------------------
@app.command()
def test(
    ctx: typer.Context,
    endpoint: Annotated[str, typer.Argument(help="Endpoint path to test (e.g. /api/v1/health).")],
    tier: Annotated[str, typer.Option("--tier", help="Tier to simulate.")] = "user",
    count: Annotated[int, typer.Option("--count", help="Number of requests to send.")] = 50,
) -> None:
    """Send sequential requests to test rate limit behavior."""
    actx: AppContext = ctx.obj
    out = actx.output

    limit = _DEFAULT_TIERS.get(tier, 100)
    out.info(f"Testing rate limit — {count} requests to {endpoint} (tier={tier}, limit={limit}/min)")

    results: list[dict] = []
    rate_limited_at: int | None = None

    for i in range(1, count + 1):
        try:
            start = time.monotonic()
            response = actx.client.get_raw(endpoint)
            elapsed_ms = round((time.monotonic() - start) * 1000)
            status = response.status_code

            results.append({"request": i, "status": status, "latency_ms": elapsed_ms})

            if status == 429 and rate_limited_at is None:
                rate_limited_at = i
                out.warn(f"Rate limited at request #{i} (HTTP 429)")
                break
            elif status >= 500:
                out.warn(f"Request #{i} returned {status}")

        except Exception as e:
            results.append({"request": i, "status": "error", "error": str(e)})
            out.warn(f"Request #{i} failed: {e}")

    success_count = sum(1 for r in results if isinstance(r.get("status"), int) and r["status"] < 400)
    limited_count = sum(1 for r in results if r.get("status") == 429)
    avg_latency = round(sum(r.get("latency_ms", 0) for r in results if "latency_ms" in r) / max(len(results), 1))

    out.text("")
    out.text(f"  Sent:          {len(results)}")
    out.text(f"  Success (2xx): [green]{success_count}[/green]")
    out.text(f"  Rate limited:  [yellow]{limited_count}[/yellow]")
    out.text(f"  Avg latency:   {avg_latency}ms")
    if rate_limited_at:
        out.text(f"  Limited at:    request #{rate_limited_at}")

    if actx.json_mode:
        out.raw_json(
            {
                "endpoint": endpoint,
                "tier": tier,
                "sent": len(results),
                "success": success_count,
                "rate_limited": limited_count,
                "rate_limited_at": rate_limited_at,
                "avg_latency_ms": avg_latency,
                "results": results,
            }
        )


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------
@app.command()
def status(ctx: typer.Context) -> None:
    """Inspect Redis rate limit keys (rl: prefix)."""
    actx: AppContext = ctx.obj
    out = actx.output

    redis_url = actx.redis_url
    if not redis_url:
        out.error("No redis_url configured.")
        raise typer.Exit(1)

    async def _run() -> list[dict]:
        from kctl_api.core.redis import close_redis, get_redis

        try:
            client = get_redis(redis_url)
            keys: list[str] = []
            async for key in client.scan_iter(match="rl:*", count=200):
                keys.append(key)

            if not keys:
                return []

            results = []
            for key in keys[:100]:  # cap at 100 for display
                try:
                    val = await client.get(key)
                    ttl = await client.ttl(key)
                    results.append(
                        {
                            "key": key,
                            "count": int(val) if val else 0,
                            "ttl_seconds": ttl,
                        }
                    )
                except Exception:
                    pass
            return sorted(results, key=lambda x: -x.get("count", 0))
        finally:
            await close_redis()

    try:
        entries = asyncio.run(_run())
    except Exception as e:
        out.error(f"Redis error: {e}")
        raise typer.Exit(1) from None

    if not entries:
        out.info("No active rate limit keys found (prefix: rl:*).")
        return

    rows = [[e["key"], str(e["count"]), str(e["ttl_seconds"])] for e in entries]
    out.table(
        title=f"Active Rate Limit Keys ({len(entries)})",
        columns=[("Key", ""), ("Requests", "bold"), ("TTL (s)", "")],
        rows=rows,
        data_for_json=entries,
    )


# ---------------------------------------------------------------------------
# simulate
# ---------------------------------------------------------------------------
@app.command()
def simulate(
    ctx: typer.Context,
    tier: Annotated[str, typer.Argument(help="Tier to simulate: free, user, premium, admin.")],
) -> None:
    """Show expected rate limit behavior for a tier."""
    actx: AppContext = ctx.obj
    out = actx.output

    if tier not in _DEFAULT_TIERS:
        out.error(f"Unknown tier '{tier}'. Choose from: {', '.join(_DEFAULT_TIERS)}")
        raise typer.Exit(1)

    limit = _DEFAULT_TIERS[tier]
    interval_ms = round(_WINDOW_SECONDS / limit * 1000)
    burst_warning = limit

    sections = [
        (
            f"Tier: {tier}",
            [
                ("Max requests", f"{limit} per {_WINDOW_SECONDS}s window"),
                ("Min interval", f"{interval_ms}ms between requests"),
                ("Burst (window)", f"Up to {burst_warning} requests before 429"),
                ("Response on limit", "HTTP 429 Too Many Requests"),
                ("Reset", f"Counter resets after {_WINDOW_SECONDS}s TTL"),
                ("Header", "X-RateLimit-Remaining, X-RateLimit-Reset (if configured)"),
            ],
        )
    ]

    out.detail(
        title=f"Rate Limit Simulation: {tier}",
        sections=sections,
        data_for_json={"tier": tier, "limit": limit, "window": _WINDOW_SECONDS, "interval_ms": interval_ms},
    )
