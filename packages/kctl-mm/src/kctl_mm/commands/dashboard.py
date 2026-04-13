from __future__ import annotations

import time

import typer

from kctl_mm.core.callbacks import AppContext

app = typer.Typer(help="Operational dashboard.", no_args_is_help=True)


def _c(ctx: typer.Context) -> AppContext:
    return ctx.ensure_object(AppContext)


@app.command("summary")
def summary_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    users = c.client.user_stats()
    teams = c.client.list_teams()
    c.output.raw_json({"users": users.get("total_users_count", 0), "teams": len(teams)})


@app.command("full")
def full_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    c.output.raw_json(
        {
            "ping": c.client.ping_full(),
            "users": c.client.user_stats(),
            "teams": len(c.client.list_teams()),
            "analytics": c.client.analytics(),
        }
    )


@app.command("json")
def json_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    c.output.raw_json(
        {
            "ping": c.client.ping_full(),
            "users": c.client.user_stats(),
            "teams": c.client.list_teams(),
        }
    )


@app.command("activity")
def activity_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    analytics = c.client.analytics()
    rows = [[str(item.get("name", "")), str(item.get("value", ""))] for item in analytics]
    data_for_json = [{"name": item.get("name", ""), "value": item.get("value", "")} for item in analytics]
    c.output.table(
        "Activity",
        [("Name", "cyan"), ("Value", "green")],
        rows,
        data_for_json=data_for_json,
    )


@app.command("watch")
def watch_cmd(ctx: typer.Context, interval: int = 5) -> None:
    c = _c(ctx)
    try:
        while True:
            c.output.raw_json(
                {
                    "users": c.client.user_stats(),
                    "teams": len(c.client.list_teams()),
                }
            )
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
