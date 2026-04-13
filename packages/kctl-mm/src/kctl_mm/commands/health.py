from __future__ import annotations

import typer

from kctl_mm.core.callbacks import AppContext

app = typer.Typer(help="Health checks.", no_args_is_help=True)


def _c(ctx: typer.Context) -> AppContext:
    return ctx.ensure_object(AppContext)


@app.command("status")
def status_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.ping())


@app.command("quick")
def quick_cmd(ctx: typer.Context) -> None:
    r = _c(ctx).client.ping()
    typer.echo("OK" if r.get("status") == "OK" else "FAIL")


@app.command("json")
def json_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.ping_full())


@app.command("components")
def components_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    r = c.client.ping_full()
    rows = [
        [key.replace("_status", ""), str(r.get(key, "UNKNOWN"))]
        for key in ("database_status", "filestore_status", "search_status")
    ]
    data_for_json = [{"component": row[0], "status": row[1]} for row in rows]
    c.output.table(
        "Components",
        [("Component", "cyan"), ("Status", "green")],
        rows,
        data_for_json=data_for_json,
    )


@app.command("metrics")
def metrics_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.user_stats())
