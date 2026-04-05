"""Server configuration and management commands for kctl-redis."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_redis.core.callbacks import AppContext

app = typer.Typer(help="Redis server management.", no_args_is_help=True)


@app.command(name="config-get")
def config_get(
    ctx: typer.Context,
    pattern: Annotated[str, typer.Argument(help="Config parameter pattern")] = "*",
) -> None:
    """Get Redis configuration parameters."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    r = app_ctx.client.r

    config = r.config_get(pattern)
    if app_ctx.json_mode:
        out.json(config)
    else:
        rows = [{"parameter": k, "value": str(v)} for k, v in sorted(config.items())]
        out.table(rows, columns=["parameter", "value"], title="Redis Configuration")

    app_ctx.close()


@app.command(name="config-set")
def config_set(
    ctx: typer.Context,
    parameter: Annotated[str, typer.Argument(help="Config parameter name")],
    value: Annotated[str, typer.Argument(help="Config parameter value")],
) -> None:
    """Set a Redis configuration parameter at runtime."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    r = app_ctx.client.r

    r.config_set(parameter, value)
    out.success(f"Set {parameter} = {value}")
    app_ctx.close()


@app.command()
def acl(
    ctx: typer.Context,
    user: Annotated[str | None, typer.Option(help="Show details for a specific user")] = None,
) -> None:
    """List ACL users or show user details."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    if user:
        result = c.execute("ACL", "GETUSER", user)
        if app_ctx.json_mode:
            out.json({"user": user, "details": result})
        else:
            out.kv("User", user)
            if isinstance(result, list):
                for i in range(0, len(result), 2):
                    out.kv(f"  {result[i]}", str(result[i + 1]))
    else:
        result = c.execute("ACL", "LIST")
        if app_ctx.json_mode:
            out.json({"acl_rules": result})
        else:
            if isinstance(result, list):
                for rule in result:
                    out.text(str(rule))
            else:
                out.text(str(result))

    app_ctx.close()


@app.command(name="info")
def info_cmd(
    ctx: typer.Context,
    section: Annotated[str | None, typer.Argument(help="INFO section (server, clients, memory, stats, etc.)")] = None,
) -> None:
    """Show Redis INFO output."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    data = c.info(section)
    if app_ctx.json_mode:
        out.json(data)
    else:
        rows = [{"key": k, "value": str(v)} for k, v in data.items()]
        title = f"INFO {section}" if section else "INFO"
        out.table(rows, columns=["key", "value"], title=title)

    app_ctx.close()
