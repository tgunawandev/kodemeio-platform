"""Raw Redis command execution for kctl-redis."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_redis.core.callbacks import AppContext

app = typer.Typer(help="Execute raw Redis commands.", no_args_is_help=True)


@app.command(name="exec")
def exec_cmd(
    ctx: typer.Context,
    command: Annotated[list[str], typer.Argument(help="Redis command and arguments")],
) -> None:
    """Execute a raw Redis command.

    Example: kctl-redis query exec SET mykey myvalue
    Example: kctl-redis query exec GET mykey
    """
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    result = c.execute(*command)

    if app_ctx.json_mode:
        out.json({"command": " ".join(command), "result": result})
    else:
        if isinstance(result, list):
            for i, item in enumerate(result):
                out.text(f"{i + 1}) {item}")
        elif isinstance(result, dict):
            for k, v in result.items():
                out.kv(str(k), str(v))
        else:
            out.text(str(result))

    app_ctx.close()
