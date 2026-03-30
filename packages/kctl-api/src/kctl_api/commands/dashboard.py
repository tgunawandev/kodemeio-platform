"""Dashboard and overview commands for kctl-api.

Aggregate health, job, and service information.
"""

from __future__ import annotations

import asyncio
import contextlib

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.utils import service_status_color

app = typer.Typer(name="dashboard", help="Dashboard — overview, live monitoring.", no_args_is_help=True)


# ---------------------------------------------------------------------------
# overview
# ---------------------------------------------------------------------------
@app.command()
def overview(ctx: typer.Context) -> None:
    """Show a combined overview: health + jobs + recent activity."""
    actx: AppContext = ctx.obj
    out = actx.output

    # Gather health checks
    health_results: list[dict] = []

    # API health
    try:
        healthy, details = actx.client.health_check()
        health_results.append({"service": "api-main", "healthy": healthy, "status": details.get("status", "unknown")})
    except Exception as e:
        health_results.append({"service": "api-main", "healthy": False, "status": "error", "error": str(e)})

    # AI health
    try:
        ai_data = actx.ai_client.get("/api/v1/ai/health")
        ai_ok = ai_data.get("status") == "ok" if ai_data else False
        health_results.append({"service": "ai-main", "healthy": ai_ok, "status": ai_data.get("status", "unknown")})
    except Exception as e:
        health_results.append({"service": "ai-main", "healthy": False, "status": "error", "error": str(e)})

    # DB health
    db_url = actx.database_url
    if db_url:

        async def _check_db() -> dict:
            from kctl_api.core.db import dispose_engine, execute_query

            try:
                rows = await execute_query(db_url, "SELECT 1 AS ping")
                await dispose_engine()
                ok = len(rows) > 0 and rows[0].get("ping") == 1
                return {"service": "database", "healthy": ok, "status": "ok" if ok else "error"}
            except Exception as e:
                with contextlib.suppress(Exception):
                    await dispose_engine()
                return {"service": "database", "healthy": False, "status": "error", "error": str(e)}

        health_results.append(asyncio.run(_check_db()))

    # Redis health
    redis_url = actx.redis_url
    if redis_url:

        async def _check_redis() -> dict:
            from kctl_api.core.redis import close_redis, get_redis

            try:
                client = get_redis(redis_url)
                pong = await client.ping()
                await close_redis()
                return {"service": "redis", "healthy": bool(pong), "status": "ok" if pong else "error"}
            except Exception as e:
                with contextlib.suppress(Exception):
                    await close_redis()
                return {"service": "redis", "healthy": False, "status": "error", "error": str(e)}

        health_results.append(asyncio.run(_check_redis()))

    # Display health table
    health_rows: list[list[str]] = []
    for r in health_results:
        health_rows.append(
            [
                r["service"],
                service_status_color(r.get("status", "unknown")),
                "[green]yes[/green]" if r["healthy"] else "[red]no[/red]",
            ]
        )

    out.table(
        title="Service Health",
        columns=[
            ("Service", "bold"),
            ("Status", ""),
            ("Healthy", ""),
        ],
        rows=health_rows,
        data_for_json=health_results,
    )

    # Try to show job overview
    try:
        jobs_data = actx.client.get("/api/v1/jobs/queues/overview")
        if jobs_data:
            out.header("Job Queues")
            if isinstance(jobs_data, list):
                for q in jobs_data:
                    out.kv(q.get("name", "queue"), f"queued={q.get('queued', 0)} active={q.get('active', 0)}")
            elif isinstance(jobs_data, dict):
                for k, v in jobs_data.items():
                    out.kv(k, str(v))
    except Exception:
        pass

    # Summary
    total = len(health_results)
    healthy_count = sum(1 for r in health_results if r["healthy"])
    if healthy_count == total:
        out.success(f"All {total} services healthy.")
    else:
        out.warn(f"{healthy_count}/{total} services healthy.")


# ---------------------------------------------------------------------------
# live
# ---------------------------------------------------------------------------
@app.command()
def live(
    ctx: typer.Context,
) -> None:
    """Live dashboard with auto-refresh (not yet implemented)."""
    actx: AppContext = ctx.obj
    out = actx.output
    out.info("Not yet implemented. Will show a live Rich dashboard with auto-refresh.")
