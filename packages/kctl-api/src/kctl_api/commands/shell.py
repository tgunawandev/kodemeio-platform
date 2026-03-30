"""Interactive shell command for kctl-api.

Start a Python REPL with pre-loaded context.
"""

from __future__ import annotations

import typer

from kctl_api.core.callbacks import AppContext

app = typer.Typer(name="shell", help="Interactive Python REPL with API context.", no_args_is_help=False)


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------
@app.command()
def start(ctx: typer.Context) -> None:
    """Start an interactive Python REPL with pre-loaded API client and helpers."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Starting interactive shell ...")
    out.info("Available objects: client, ai_client, actx, out")

    namespace = {
        "actx": actx,
        "client": actx.client,
        "out": actx.output,
    }

    # Try ai_client lazily to avoid connection errors at startup
    try:
        namespace["ai_client"] = actx.ai_client
    except Exception:
        namespace["ai_client"] = None

    try:
        import IPython

        IPython.start_ipython(argv=[], user_ns=namespace)
    except ImportError:
        import code

        code.interact(
            banner="kctl-api shell (use 'client', 'ai_client', 'actx', 'out')",
            local=namespace,
        )


# ---------------------------------------------------------------------------
# db
# ---------------------------------------------------------------------------
@app.command()
def db(ctx: typer.Context) -> None:
    """Start a Python REPL with an async SQLAlchemy DB session pre-loaded."""
    actx: AppContext = ctx.obj
    out = actx.output

    db_url = actx.database_url
    if not db_url:
        out.error("No database_url configured.")
        raise typer.Exit(1)

    out.info("Starting DB shell ...")
    out.info("Available: db (AsyncSession), execute_query, dispose_engine")

    async def _get_session():  # type: ignore[return]
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_async_engine(db_url)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)  # type: ignore[call-overload]
        return async_session()

    import asyncio

    session = asyncio.run(_get_session())

    namespace = {
        "actx": actx,
        "out": out,
        "session": session,
        "db": session,
        "asyncio": asyncio,
    }

    banner = (
        "kctl-api db shell\n"
        "Available: session (AsyncSession), db (alias), asyncio\n"
        "Example:   asyncio.run(session.execute(text('SELECT 1')))"
    )

    try:
        import IPython

        IPython.start_ipython(argv=[], user_ns=namespace)
    except ImportError:
        import code

        code.interact(banner=banner, local=namespace)
    finally:
        asyncio.run(session.close())


# ---------------------------------------------------------------------------
# redis
# ---------------------------------------------------------------------------
@app.command()
def redis(ctx: typer.Context) -> None:
    """Start a Python REPL with a Redis async client pre-loaded."""
    actx: AppContext = ctx.obj
    out = actx.output

    redis_url = actx.redis_url
    if not redis_url:
        out.error("No redis_url configured.")
        raise typer.Exit(1)

    out.info("Starting Redis shell ...")
    out.info("Available: r (Redis client), asyncio")

    from kctl_api.core.redis import get_redis

    r = get_redis(redis_url)

    import asyncio

    namespace = {
        "actx": actx,
        "out": out,
        "r": r,
        "redis": r,
        "asyncio": asyncio,
    }

    banner = "kctl-api redis shell\nAvailable: r (Redis client), asyncio\nExample:   asyncio.run(r.info())"

    try:
        import IPython

        IPython.start_ipython(argv=[], user_ns=namespace)
    except ImportError:
        import code

        code.interact(banner=banner, local=namespace)


# ---------------------------------------------------------------------------
# api
# ---------------------------------------------------------------------------
@app.command()
def api(ctx: typer.Context) -> None:
    """Start a Python REPL with an httpx client pre-loaded for API calls."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Starting API shell ...")
    out.info("Available: client (ApiClient), http (httpx), base_url")

    import httpx

    base_url = actx.client.base_url
    api_key = actx.client.api_key

    http = httpx.Client(
        base_url=base_url,
        headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        timeout=30,
    )

    namespace = {
        "actx": actx,
        "client": actx.client,
        "http": http,
        "httpx": httpx,
        "base_url": base_url,
        "out": out,
    }

    banner = (
        f"kctl-api api shell — connected to {base_url}\n"
        "Available: client (ApiClient), http (httpx.Client), base_url\n"
        "Example:   http.get('/api/v1/health').json()"
    )

    try:
        import IPython

        IPython.start_ipython(argv=[], user_ns=namespace)
    except ImportError:
        import code

        code.interact(banner=banner, local=namespace)
    finally:
        http.close()
