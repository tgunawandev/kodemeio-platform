"""Health check commands for kctl-api.

Check connectivity to api-main, ai-main, database, and Redis.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.utils import service_status_color

app = typer.Typer(name="health", help="Health checks for API services, database, and Redis.", no_args_is_help=True)

# Default watch interval in seconds
_DEFAULT_INTERVAL = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_api(actx: AppContext) -> dict:
    """Check api-main health via HTTP client."""
    try:
        healthy, details = actx.client.health_check()
        return {"service": "api-main", "healthy": healthy, "status": details.get("status", "unknown"), **details}
    except Exception as e:
        return {"service": "api-main", "healthy": False, "status": "error", "error": str(e)}


def _check_ai(actx: AppContext) -> dict:
    """Check ai-main health via HTTP client."""
    try:
        data = actx.ai_client.get("/api/v1/ai/health")
        healthy = data.get("status") == "ok" if data else False
        return {"service": "ai-main", "healthy": healthy, "status": data.get("status", "unknown"), **(data or {})}
    except Exception as e:
        return {"service": "ai-main", "healthy": False, "status": "error", "error": str(e)}


async def _check_db_async(actx: AppContext) -> dict:
    """Check database connectivity with SELECT 1."""
    from kctl_api.core.db import dispose_engine, execute_query

    db_url = actx.database_url
    if not db_url:
        return {"service": "database", "healthy": False, "status": "error", "error": "No database_url configured."}

    try:
        rows = await execute_query(db_url, "SELECT 1 AS ping")
        await dispose_engine()
        ok = len(rows) > 0 and rows[0].get("ping") == 1
        return {"service": "database", "healthy": ok, "status": "ok" if ok else "error"}
    except ImportError as e:
        return {"service": "database", "healthy": False, "status": "error", "error": str(e)}
    except Exception as e:
        with contextlib.suppress(Exception):
            await dispose_engine()
        return {"service": "database", "healthy": False, "status": "error", "error": str(e)}


async def _check_redis_async(actx: AppContext) -> dict:
    """Check Redis connectivity with PING."""
    from kctl_api.core.redis import close_redis, get_redis

    redis_url = actx.redis_url
    if not redis_url:
        return {"service": "redis", "healthy": False, "status": "error", "error": "No redis_url configured."}

    try:
        client = get_redis(redis_url)
        pong = await client.ping()
        await close_redis()
        return {"service": "redis", "healthy": bool(pong), "status": "ok" if pong else "error"}
    except ImportError as e:
        return {"service": "redis", "healthy": False, "status": "error", "error": str(e)}
    except Exception as e:
        with contextlib.suppress(Exception):
            await close_redis()
        return {"service": "redis", "healthy": False, "status": "error", "error": str(e)}


def _display_single_check(actx: AppContext, result: dict) -> None:
    """Display a single health check result."""
    out = actx.output
    service = result["service"]
    healthy = result["healthy"]
    status = result.get("status", "unknown")

    if actx.json_mode:
        out.raw_json(result)
        return

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            service,
            [
                ("Status", service_status_color(status)),
                ("Healthy", "[green]yes[/green]" if healthy else "[red]no[/red]"),
            ],
        ),
    ]
    # Add extra details
    error = result.get("error")
    if error:
        sections[0][1].append(("Error", f"[red]{error}[/red]"))

    # Include version/uptime if present
    for extra_key in ("version", "uptime", "database", "redis", "workers"):
        val = result.get(extra_key)
        if val is not None:
            sections[0][1].append((extra_key.title(), str(val)))

    out.detail(title=f"Health: {service}", sections=sections, data_for_json=result)


def _display_all_results(actx: AppContext, results: list[dict]) -> None:
    """Display aggregated health check results as a table."""
    out = actx.output

    if actx.json_mode:
        out.raw_json(results)
        return

    rows: list[list[str]] = []
    for r in results:
        status = r.get("status", "unknown")
        healthy = r["healthy"]
        error = r.get("error", "")
        rows.append(
            [
                r["service"],
                service_status_color(status),
                "[green]yes[/green]" if healthy else "[red]no[/red]",
                error if error else "",
            ]
        )

    out.table(
        title="Health Check Summary",
        columns=[
            ("Service", "bold"),
            ("Status", ""),
            ("Healthy", ""),
            ("Error", "red"),
        ],
        rows=rows,
        data_for_json=results,
    )

    # Summary line
    total = len(results)
    healthy_count = sum(1 for r in results if r["healthy"])
    if healthy_count == total:
        out.success(f"All {total} services healthy.")
    else:
        out.warn(f"{healthy_count}/{total} services healthy.")


def _run_watch(
    check_fn: object,
    actx: AppContext,
    interval: int,
    *,
    is_async: bool = False,
    display_fn: object | None = None,
) -> None:
    """Run a check function in a watch loop with console clearing."""
    import datetime as dt

    console = actx.output.console
    disp = display_fn or _display_single_check

    try:
        while True:
            console.clear()
            actx.output.info(f"Watch mode (every {interval}s) — {dt.datetime.now(tz=dt.UTC).strftime('%H:%M:%S UTC')}")
            result = (  # type: ignore[operator]
                asyncio.run(check_fn(actx)) if is_async else check_fn(actx)  # type: ignore[operator]
            )
            disp(actx, result)  # type: ignore[operator]
            time.sleep(interval)
    except KeyboardInterrupt:
        actx.output.info("Watch stopped.")


# ---------------------------------------------------------------------------
# api
# ---------------------------------------------------------------------------
@app.command()
def api(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously poll.")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Watch interval in seconds.")] = _DEFAULT_INTERVAL,
) -> None:
    """Check api-main health (GET /api/v1/health)."""
    actx: AppContext = ctx.obj

    if watch:
        _run_watch(_check_api, actx, interval)
        return

    result = _check_api(actx)
    _display_single_check(actx, result)
    if not result["healthy"]:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# db
# ---------------------------------------------------------------------------
@app.command()
def db(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously poll.")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Watch interval in seconds.")] = _DEFAULT_INTERVAL,
) -> None:
    """Check database connectivity (async SELECT 1)."""
    actx: AppContext = ctx.obj

    if watch:
        _run_watch(_check_db_async, actx, interval, is_async=True)
        return

    result = asyncio.run(_check_db_async(actx))
    _display_single_check(actx, result)
    if not result["healthy"]:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# redis
# ---------------------------------------------------------------------------
@app.command()
def redis(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously poll.")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Watch interval in seconds.")] = _DEFAULT_INTERVAL,
) -> None:
    """Check Redis connectivity (async PING)."""
    actx: AppContext = ctx.obj

    if watch:
        _run_watch(_check_redis_async, actx, interval, is_async=True)
        return

    result = asyncio.run(_check_redis_async(actx))
    _display_single_check(actx, result)
    if not result["healthy"]:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# ai
# ---------------------------------------------------------------------------
@app.command()
def ai(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously poll.")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Watch interval in seconds.")] = _DEFAULT_INTERVAL,
) -> None:
    """Check ai-main health (GET /api/v1/ai/health)."""
    actx: AppContext = ctx.obj

    if watch:
        _run_watch(_check_ai, actx, interval)
        return

    result = _check_ai(actx)
    _display_single_check(actx, result)
    if not result["healthy"]:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# all
# ---------------------------------------------------------------------------
@app.command(name="all")
def all_checks(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously poll.")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Watch interval in seconds.")] = _DEFAULT_INTERVAL,
) -> None:
    """Run all health checks and display aggregated results."""
    actx: AppContext = ctx.obj

    def _run_all(actx: AppContext) -> list[dict]:
        results: list[dict] = []
        # Synchronous HTTP checks
        results.append(_check_api(actx))
        results.append(_check_ai(actx))
        # Async infrastructure checks
        results.append(asyncio.run(_check_db_async(actx)))
        results.append(asyncio.run(_check_redis_async(actx)))
        return results

    if watch:
        import datetime as dt

        console = actx.output.console
        try:
            while True:
                console.clear()
                actx.output.info(
                    f"Watch mode (every {interval}s) — {dt.datetime.now(tz=dt.UTC).strftime('%H:%M:%S UTC')}"
                )
                results = _run_all(actx)
                _display_all_results(actx, results)
                time.sleep(interval)
        except KeyboardInterrupt:
            actx.output.info("Watch stopped.")
        return

    results = _run_all(actx)
    _display_all_results(actx, results)

    # Exit with error code if any check failed
    if not all(r["healthy"] for r in results):
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# deep
# ---------------------------------------------------------------------------
@app.command()
def deep(ctx: typer.Context) -> None:
    """Deep health check — DB, Redis, all external service dependencies."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Running deep health check ...")
    results: list[dict] = []

    # Standard checks
    results.append(_check_api(actx))
    results.append(_check_ai(actx))
    results.append(asyncio.run(_check_db_async(actx)))
    results.append(asyncio.run(_check_redis_async(actx)))

    # Deep DB check — verify schema exists
    async def _deep_db() -> dict:
        from kctl_api.core.db import dispose_engine, execute_query

        db_url = actx.database_url
        if not db_url:
            return {"service": "db-schema", "healthy": False, "status": "error", "error": "No database_url"}
        try:
            rows = await execute_query(
                db_url,
                "SELECT COUNT(*) AS cnt FROM information_schema.tables WHERE table_schema = 'public'",
            )
            await dispose_engine()
            cnt = rows[0].get("cnt", 0) if rows else 0
            return {
                "service": "db-schema",
                "healthy": cnt > 0,
                "status": "ok" if cnt > 0 else "empty",
                "tables": cnt,
            }
        except Exception as e:
            return {"service": "db-schema", "healthy": False, "status": "error", "error": str(e)}

    results.append(asyncio.run(_deep_db()))

    # Deep Redis check — verify can write/read
    async def _deep_redis() -> dict:
        from kctl_api.core.redis import close_redis, get_redis

        redis_url = actx.redis_url
        if not redis_url:
            return {"service": "redis-rw", "healthy": False, "status": "error", "error": "No redis_url"}
        try:
            import time

            client = get_redis(redis_url)
            test_key = f"kctl:healthcheck:{int(time.time())}"
            await client.set(test_key, "1", ex=10)
            val = await client.get(test_key)
            await client.delete(test_key)
            await close_redis()
            ok = val == "1"
            return {"service": "redis-rw", "healthy": ok, "status": "ok" if ok else "error"}
        except Exception as e:
            return {"service": "redis-rw", "healthy": False, "status": "error", "error": str(e)}

    results.append(asyncio.run(_deep_redis()))

    _display_all_results(actx, results)

    if not all(r["healthy"] for r in results):
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# deps-check
# ---------------------------------------------------------------------------
@app.command(name="deps-check")
def deps_check(ctx: typer.Context) -> None:
    """Verify external service dependencies are reachable."""
    actx: AppContext = ctx.obj
    out = actx.output

    import httpx

    # Read external deps from env or config
    deps_to_check: list[dict] = []

    # API itself
    url = actx.client.base_url.rstrip("/")
    deps_to_check.append({"name": "api-main", "url": f"{url}/api/v1/health"})

    # Check AI URL if configured
    try:
        ai_url = actx.ai_client.base_url.rstrip("/")
        deps_to_check.append({"name": "ai-main", "url": f"{ai_url}/api/v1/ai/health"})
    except Exception:
        pass

    # Check any ODOO_URL from env
    import os

    odoo_url = os.environ.get("ODOO_URL")
    if odoo_url:
        deps_to_check.append({"name": "odoo", "url": f"{odoo_url.rstrip('/')}/web/dataset/call_kw"})

    results: list[dict] = []
    for dep in deps_to_check:
        try:
            response = httpx.get(dep["url"], timeout=5, follow_redirects=True)
            healthy = response.status_code < 500
            results.append(
                {
                    "service": dep["name"],
                    "healthy": healthy,
                    "status": str(response.status_code),
                    "url": dep["url"],
                }
            )
        except Exception as e:
            results.append(
                {
                    "service": dep["name"],
                    "healthy": False,
                    "status": "unreachable",
                    "error": str(e)[:60],
                    "url": dep["url"],
                }
            )

    rows = [
        [
            r["service"],
            r.get("url", ""),
            "[green]ok[/green]" if r["healthy"] else "[red]fail[/red]",
            r.get("status", ""),
            r.get("error", ""),
        ]
        for r in results
    ]
    out.table(
        title="External Dependency Check",
        columns=[("Service", "bold"), ("URL", "dim"), ("Status", ""), ("Code", ""), ("Error", "red")],
        rows=rows,
        data_for_json=results,
    )

    failed = [r for r in results if not r["healthy"]]
    if failed:
        out.warn(f"{len(failed)} dependency/ies unreachable.")
        raise typer.Exit(1)
    else:
        out.success(f"All {len(results)} dependencies reachable.")
