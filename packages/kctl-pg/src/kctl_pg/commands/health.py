"""Health check commands."""

from __future__ import annotations

import typer

from kctl_pg.core.callbacks import AppContext
from kctl_pg.core.exceptions import KctlError

app = typer.Typer(help="Check PostgreSQL server health.")


@app.callback(invoke_without_command=True)
def health(ctx: typer.Context) -> None:
    """Check PostgreSQL health: connectivity, version, uptime, connections."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        c = actx.client
    except KctlError as e:
        out.error(f"Cannot connect: {e}")
        raise typer.Exit(1) from e

    version = c.short_version

    uptime = c.fetchone("SELECT now() - pg_postmaster_start_time() AS uptime")
    uptime_str = str(uptime["uptime"]) if uptime else "unknown"

    conns = c.fetchone("""
        SELECT
            count(*) AS total,
            count(*) FILTER (WHERE state = 'active') AS active,
            count(*) FILTER (WHERE state = 'idle') AS idle,
            count(*) FILTER (WHERE state = 'idle in transaction') AS idle_in_tx,
            (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') AS max_conns
        FROM pg_stat_activity
        WHERE backend_type = 'client backend'
    """)

    is_in_recovery = c.fetchval("SELECT pg_is_in_recovery()")

    sections = [
        (
            "Server",
            [
                ("Status", "[green]UP[/green]"),
                ("Version", version),
                ("Uptime", uptime_str),
                ("Role", "Standby (read replica)" if is_in_recovery else "Primary"),
            ],
        ),
        (
            "Connections",
            [
                ("Total", f"{conns['total']} / {conns['max_conns']}" if conns else "unknown"),
                ("Active", str(conns["active"]) if conns else "0"),
                ("Idle", str(conns["idle"]) if conns else "0"),
                ("Idle in TX", str(conns["idle_in_tx"]) if conns else "0"),
            ],
        ),
    ]

    # Check replication if primary
    if not is_in_recovery:
        replicas = c.fetchall("""
            SELECT client_addr, state, sent_lsn, replay_lsn
            FROM pg_stat_replication
        """)
        if replicas:
            sections.append(
                (
                    "Replication",
                    [
                        (str(r["client_addr"]), f"state={r['state']} sent={r['sent_lsn']} replay={r['replay_lsn']}")
                        for r in replicas
                    ],
                )
            )

    out.detail(
        "PostgreSQL Health",
        sections,
        data_for_json={
            "status": "up",
            "version": version,
            "uptime": uptime_str,
            "is_replica": is_in_recovery,
            "connections": dict(conns) if conns else {},
        },
    )
