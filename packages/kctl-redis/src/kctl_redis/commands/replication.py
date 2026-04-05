"""Replication management commands for kctl-redis."""

from __future__ import annotations

import typer

from kctl_redis.core.callbacks import AppContext

app = typer.Typer(help="Redis replication management.", no_args_is_help=True)


@app.command()
def info(ctx: typer.Context) -> None:
    """Show replication info."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    repl = c.info("replication")
    if app_ctx.json_mode:
        out.json(repl)
    else:
        out.kv("Role", repl.get("role", "?"))
        out.kv("Connected slaves", str(repl.get("connected_slaves", 0)))
        out.kv("Repl backlog size", str(repl.get("repl_backlog_size", 0)))

        for key, val in repl.items():
            if key.startswith("slave") and isinstance(val, str):
                out.kv(f"  {key}", val)

    app_ctx.close()


@app.command()
def lag(ctx: typer.Context) -> None:
    """Show replication lag for replicas."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    repl = c.info("replication")
    role = repl.get("role", "unknown")

    if role == "slave":
        out.kv("Role", "replica")
        out.kv("Master link status", repl.get("master_link_status", "?"))
        out.kv("Replication offset", str(repl.get("master_repl_offset", "?")))
        out.kv("Last I/O seconds ago", str(repl.get("master_last_io_seconds_ago", "?")))
        if repl.get("master_link_status") == "down":
            out.kv("Link down since (seconds)", str(repl.get("master_link_down_since_seconds", "?")))
    elif role == "master":
        slave_count = repl.get("connected_slaves", 0)
        if slave_count == 0:
            out.info("No replicas connected")
        else:
            rows = []
            for i in range(slave_count):
                slave_info = repl.get(f"slave{i}", "")
                rows.append({"replica": f"slave{i}", "info": str(slave_info)})
            out.table(rows, columns=["replica", "info"], title="Replica Lag")
    else:
        out.info(f"Role: {role}")

    app_ctx.close()


@app.command()
def promote(ctx: typer.Context) -> None:
    """Promote this replica to master (REPLICAOF NO ONE)."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    repl = c.info("replication")
    if repl.get("role") != "slave":
        out.error("This instance is not a replica")
        raise typer.Exit(1)

    typer.confirm("Promote this replica to master?", abort=True)
    c.execute("REPLICAOF", "NO", "ONE")
    out.success("Promoted to master (REPLICAOF NO ONE)")
    app_ctx.close()
