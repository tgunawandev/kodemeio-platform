"""PgBouncer management commands.

PgBouncer exposes an admin console on port 6432 via the virtual 'pgbouncer' database.
We connect through the same SSH tunnel but target port 6432 instead of 5432.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer
from sshtunnel import SSHTunnelForwarder

from kctl_pg.core.callbacks import AppContext
from kctl_pg.core.config import resolve_connection
from kctl_pg.core.exceptions import SSHTunnelError

app = typer.Typer(help="PgBouncer management (admin console).")

# Default PgBouncer port
PGBOUNCER_PORT = 6432


class PgBouncerClient:
    """Lightweight client for PgBouncer admin console via SSH tunnel.

    PgBouncer speaks a limited SQL dialect (SHOW/RELOAD/PAUSE/RESUME).
    We use psycopg with autocommit and simple query mode.
    """

    def __init__(self, actx: AppContext):
        self._actx = actx
        self._tunnel: SSHTunnelForwarder | None = None
        self._conn: Any = None

    def connect(self) -> None:
        """Open SSH tunnel to PgBouncer port and connect."""
        import psycopg
        from psycopg.rows import dict_row

        cfg = resolve_connection(
            profile_name=self._actx.profile,
            host_override=self._actx.host_override,
            port_override=self._actx.port_override,
            user_override=self._actx.user_override,
            password_override=self._actx.password_override,
        )

        ssh_key = str(Path(cfg.ssh_key).expanduser()) if cfg.ssh_key else None

        try:
            self._tunnel = SSHTunnelForwarder(
                (cfg.ssh_host, cfg.ssh_port),
                ssh_username=cfg.ssh_user,
                ssh_pkey=ssh_key,
                remote_bind_address=(cfg.host, PGBOUNCER_PORT),
                local_bind_address=("127.0.0.1",),
            )
            self._tunnel.start()
        except Exception as e:
            raise SSHTunnelError(cfg.ssh_host, e) from e

        local_port = self._tunnel.local_bind_port

        # PgBouncer requires simple query protocol (no extended query).
        # psycopg3 can do this by using autocommit + execute with no params.
        self._conn = psycopg.connect(
            host="127.0.0.1",
            port=local_port,
            user=cfg.user,
            password=cfg.password,
            dbname="pgbouncer",
            row_factory=dict_row,
            autocommit=True,
        )

    def execute(self, sql: str) -> list[dict[str, Any]]:
        """Execute a PgBouncer admin command and return results."""
        assert self._conn is not None, "Not connected"
        cur = self._conn.execute(sql)
        try:
            return cur.fetchall()
        except Exception:
            return []

    def execute_no_result(self, sql: str) -> None:
        """Execute a PgBouncer command that returns no results."""
        assert self._conn is not None, "Not connected"
        self._conn.execute(sql)

    def close(self) -> None:
        """Close connection and tunnel."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
        if self._tunnel is not None:
            try:
                self._tunnel.stop()
            except Exception:
                pass
            self._tunnel = None

    def __enter__(self) -> PgBouncerClient:
        self.connect()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _get_pgb(ctx: typer.Context) -> PgBouncerClient:
    """Create and connect a PgBouncer client from context."""
    actx: AppContext = ctx.obj
    client = PgBouncerClient(actx)
    client.connect()
    return client


@app.command()
def status(ctx: typer.Context) -> None:
    """Show PgBouncer version and pool summary."""
    actx: AppContext = ctx.obj
    out = actx.output

    pgb = _get_pgb(ctx)
    try:
        # Get version
        version_rows = pgb.execute("SHOW VERSION;")
        version = version_rows[0].get("version", "unknown") if version_rows else "unknown"

        # Get pools
        pools = pgb.execute("SHOW POOLS;")
    finally:
        pgb.close()

    sections = [
        (
            "PgBouncer",
            [
                ("Version", str(version)),
                ("Port", str(PGBOUNCER_PORT)),
            ],
        ),
    ]

    if pools:
        total_cl_active = sum(int(p.get("cl_active", 0)) for p in pools)
        total_cl_waiting = sum(int(p.get("cl_waiting", 0)) for p in pools)
        total_sv_active = sum(int(p.get("sv_active", 0)) for p in pools)
        total_sv_idle = sum(int(p.get("sv_idle", 0)) for p in pools)

        sections.append(
            (
                "Pool Summary",
                [
                    ("Client Active", str(total_cl_active)),
                    ("Client Waiting", str(total_cl_waiting)),
                    ("Server Active", str(total_sv_active)),
                    ("Server Idle", str(total_sv_idle)),
                    ("Total Pools", str(len(pools))),
                ],
            )
        )

    json_data = {
        "version": str(version),
        "port": PGBOUNCER_PORT,
        "pools": pools,
    }

    out.detail("PgBouncer Status", sections, data_for_json=json_data)


@app.command()
def pools(ctx: typer.Context) -> None:
    """Show PgBouncer connection pools."""
    actx: AppContext = ctx.obj
    out = actx.output

    pgb = _get_pgb(ctx)
    try:
        rows_data = pgb.execute("SHOW POOLS;")
    finally:
        pgb.close()

    if not rows_data:
        out.info("No pools found")
        return

    rows = [
        [
            str(r.get("database", "")),
            str(r.get("user", "")),
            str(r.get("cl_active", 0)),
            str(r.get("cl_waiting", 0)),
            str(r.get("sv_active", 0)),
            str(r.get("sv_idle", 0)),
            str(r.get("sv_used", 0)),
            str(r.get("sv_tested", 0)),
            str(r.get("sv_login", 0)),
            str(r.get("maxwait", 0)),
            str(r.get("pool_mode", "")),
        ]
        for r in rows_data
    ]

    out.table(
        "PgBouncer Pools",
        [
            ("Database", "cyan"),
            ("User", ""),
            ("Cl Active", "green"),
            ("Cl Waiting", "yellow"),
            ("Sv Active", "green"),
            ("Sv Idle", "dim"),
            ("Sv Used", "dim"),
            ("Sv Tested", "dim"),
            ("Sv Login", "dim"),
            ("Max Wait", "red"),
            ("Mode", ""),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def clients(ctx: typer.Context) -> None:
    """Show PgBouncer client connections."""
    actx: AppContext = ctx.obj
    out = actx.output

    pgb = _get_pgb(ctx)
    try:
        rows_data = pgb.execute("SHOW CLIENTS;")
    finally:
        pgb.close()

    if not rows_data:
        out.info("No client connections")
        return

    rows = [
        [
            str(r.get("type", "")),
            str(r.get("user", "")),
            str(r.get("database", "")),
            str(r.get("state", "")),
            str(r.get("addr", "")),
            str(r.get("port", "")),
            str(r.get("connect_time", "")),
            str(r.get("request_time", "")),
        ]
        for r in rows_data
    ]

    out.table(
        f"PgBouncer Clients ({len(rows_data)})",
        [
            ("Type", ""),
            ("User", ""),
            ("Database", "cyan"),
            ("State", "green"),
            ("Address", "dim"),
            ("Port", "dim"),
            ("Connected", "dim"),
            ("Last Request", "dim"),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def servers(ctx: typer.Context) -> None:
    """Show PgBouncer server (backend) connections."""
    actx: AppContext = ctx.obj
    out = actx.output

    pgb = _get_pgb(ctx)
    try:
        rows_data = pgb.execute("SHOW SERVERS;")
    finally:
        pgb.close()

    if not rows_data:
        out.info("No server connections")
        return

    rows = [
        [
            str(r.get("type", "")),
            str(r.get("user", "")),
            str(r.get("database", "")),
            str(r.get("state", "")),
            str(r.get("addr", "")),
            str(r.get("port", "")),
            str(r.get("connect_time", "")),
            str(r.get("request_time", "")),
        ]
        for r in rows_data
    ]

    out.table(
        f"PgBouncer Servers ({len(rows_data)})",
        [
            ("Type", ""),
            ("User", ""),
            ("Database", "cyan"),
            ("State", "green"),
            ("Address", "dim"),
            ("Port", "dim"),
            ("Connected", "dim"),
            ("Last Request", "dim"),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def databases(ctx: typer.Context) -> None:
    """Show PgBouncer database configurations."""
    actx: AppContext = ctx.obj
    out = actx.output

    pgb = _get_pgb(ctx)
    try:
        rows_data = pgb.execute("SHOW DATABASES;")
    finally:
        pgb.close()

    if not rows_data:
        out.info("No databases configured")
        return

    rows = [
        [
            str(r.get("name", "")),
            str(r.get("host", "")),
            str(r.get("port", "")),
            str(r.get("database", "")),
            str(r.get("force_user", "") or "-"),
            str(r.get("pool_size", "")),
            str(r.get("pool_mode", "")),
            str(r.get("current_connections", 0)),
        ]
        for r in rows_data
    ]

    out.table(
        "PgBouncer Databases",
        [
            ("Name", "cyan"),
            ("Host", ""),
            ("Port", "dim"),
            ("Database", ""),
            ("Force User", "dim"),
            ("Pool Size", ""),
            ("Pool Mode", ""),
            ("Connections", "green"),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def stats(ctx: typer.Context) -> None:
    """Show PgBouncer statistics."""
    actx: AppContext = ctx.obj
    out = actx.output

    pgb = _get_pgb(ctx)
    try:
        rows_data = pgb.execute("SHOW STATS;")
    finally:
        pgb.close()

    if not rows_data:
        out.info("No statistics available")
        return

    rows = [
        [
            str(r.get("database", "")),
            str(r.get("total_xact_count", r.get("total_requests", 0))),
            str(r.get("total_query_count", r.get("total_received", 0))),
            str(r.get("total_received", 0)),
            str(r.get("total_sent", 0)),
            str(r.get("total_xact_time", r.get("total_query_time", 0))),
            str(r.get("total_query_time", 0)),
            str(r.get("avg_xact_time", r.get("avg_query", 0))),
            str(r.get("avg_query_time", r.get("avg_query", 0))),
        ]
        for r in rows_data
    ]

    out.table(
        "PgBouncer Statistics",
        [
            ("Database", "cyan"),
            ("Total Xact", ""),
            ("Total Query", ""),
            ("Received", "dim"),
            ("Sent", "dim"),
            ("Xact Time", ""),
            ("Query Time", ""),
            ("Avg Xact", "yellow"),
            ("Avg Query", "yellow"),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def reload(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Reload PgBouncer configuration."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not force:
        if not typer.confirm("Reload PgBouncer configuration?"):
            raise typer.Exit(0)

    pgb = _get_pgb(ctx)
    try:
        pgb.execute_no_result("RELOAD;")
    finally:
        pgb.close()

    out.success("PgBouncer configuration reloaded")


@app.command()
def pause(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Database to pause (all if omitted)")] = None,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Pause PgBouncer database (or all databases)."""
    actx: AppContext = ctx.obj
    out = actx.output

    target = database or "all databases"
    if not force:
        if not typer.confirm(f"Pause {target}? New queries will be queued"):
            raise typer.Exit(0)

    pgb = _get_pgb(ctx)
    try:
        cmd = f"PAUSE {database};" if database else "PAUSE;"
        pgb.execute_no_result(cmd)
    finally:
        pgb.close()

    out.success(f"Paused {target}")


@app.command()
def resume(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Database to resume (all if omitted)")] = None,
) -> None:
    """Resume PgBouncer database (or all databases)."""
    actx: AppContext = ctx.obj
    out = actx.output

    target = database or "all databases"

    pgb = _get_pgb(ctx)
    try:
        cmd = f"RESUME {database};" if database else "RESUME;"
        pgb.execute_no_result(cmd)
    finally:
        pgb.close()

    out.success(f"Resumed {target}")
