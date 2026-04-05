"""Health check commands for kctl-redis."""

from __future__ import annotations

import time
from typing import Annotated

import typer

from kctl_redis.core.callbacks import AppContext

app = typer.Typer(help="Redis health checks.", no_args_is_help=True)


@app.command()
def ping(ctx: typer.Context) -> None:
    """Ping Redis and measure latency."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    start = time.monotonic()
    c.r.ping()
    latency_ms = (time.monotonic() - start) * 1000

    out.success(f"PONG ({latency_ms:.1f}ms)")
    app_ctx.close()


@app.command()
def info(ctx: typer.Context) -> None:
    """Show Redis server info summary."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    server = c.info("server")
    rows = [
        {"key": "version", "value": server.get("redis_version", "?")},
        {"key": "mode", "value": server.get("redis_mode", "?")},
        {"key": "os", "value": server.get("os", "?")},
        {"key": "uptime_days", "value": str(server.get("uptime_in_days", "?"))},
        {"key": "tcp_port", "value": str(server.get("tcp_port", "?"))},
        {"key": "config_file", "value": server.get("config_file", "?")},
    ]
    out.table(rows, columns=["key", "value"], title="Redis Server Info")
    app_ctx.close()


@app.command()
def check(
    ctx: typer.Context,
    memory_warn: Annotated[int, typer.Option(help="Memory usage warning threshold %")] = 80,
    memory_crit: Annotated[int, typer.Option(help="Memory usage critical threshold %")] = 90,
    clients_warn: Annotated[int, typer.Option(help="Connected clients warning threshold")] = 500,
) -> None:
    """Run health threshold checks."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    all_info = c.info()
    score = 100
    issues: list[str] = []

    used = all_info.get("used_memory", 0)
    maxmem = all_info.get("maxmemory", 0)
    if maxmem > 0:
        pct = used * 100 / maxmem
        if pct >= memory_crit:
            score -= 20
            issues.append(f"Memory CRITICAL: {pct:.0f}% used")
        elif pct >= memory_warn:
            score -= 10
            issues.append(f"Memory WARNING: {pct:.0f}% used")

    clients = all_info.get("connected_clients", 0)
    if clients >= clients_warn:
        score -= 10
        issues.append(f"High client count: {clients}")

    rejected = all_info.get("rejected_connections", 0)
    if rejected > 0:
        score -= 15
        issues.append(f"Rejected connections: {rejected}")

    frag = all_info.get("mem_fragmentation_ratio", 1.0)
    if frag >= 2.0:
        score -= 10
        issues.append(f"High fragmentation: {frag:.2f}")

    hits = all_info.get("keyspace_hits", 0)
    misses = all_info.get("keyspace_misses", 0)
    total = hits + misses
    hit_ratio = (hits / total * 100) if total > 0 else 100.0
    if hit_ratio < 50 and total > 100:
        score -= 10
        issues.append(f"Low hit ratio: {hit_ratio:.1f}%")

    if score >= 80:
        status = "healthy"
    elif score >= 60:
        status = "warning"
    else:
        status = "critical"

    if app_ctx.json_mode:
        out.json(
            {
                "status": status,
                "score": score,
                "hit_ratio": round(hit_ratio, 1),
                "memory_used": used,
                "maxmemory": maxmem,
                "connected_clients": clients,
                "fragmentation": frag,
                "issues": issues,
            }
        )
    else:
        out.kv("Status", f"{status} (score: {score}/100)")
        out.kv("Hit ratio", f"{hit_ratio:.1f}%")
        out.kv("Memory", f"{used} / {maxmem} bytes")
        out.kv("Clients", str(clients))
        out.kv("Fragmentation", f"{frag:.2f}")
        if issues:
            out.warn("Issues:")
            for issue in issues:
                out.text(f"  - {issue}")
        else:
            out.success("No issues detected")

    app_ctx.close()
