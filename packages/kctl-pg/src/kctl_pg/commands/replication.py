"""Replication management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_pg.core.callbacks import AppContext
from kctl_pg.core.exceptions import DatabaseError

app = typer.Typer(help="Replication management (status, lag, slots, publications, subscriptions).")


def _fmt_bytes(b: int | float | None) -> str:
    """Format bytes for human-readable display."""
    if b is None:
        return "-"
    b = float(b)
    if b >= 1_073_741_824:
        return f"{b / 1_073_741_824:.2f} GB"
    if b >= 1_048_576:
        return f"{b / 1_048_576:.2f} MB"
    if b >= 1024:
        return f"{b / 1024:.2f} KB"
    return f"{int(b)} B"


@app.command()
def status(ctx: typer.Context) -> None:
    """Show replication status: primary/standby role and connected replicas."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    is_recovery = c.fetchval("SELECT pg_is_in_recovery()")
    role = "Standby (replica)" if is_recovery else "Primary"

    # Current WAL position
    if is_recovery:
        current_lsn = c.fetchval("SELECT pg_last_wal_receive_lsn()::text")
        replay_lsn = c.fetchval("SELECT pg_last_wal_replay_lsn()::text")
    else:
        current_lsn = c.fetchval("SELECT pg_current_wal_lsn()::text")
        replay_lsn = None

    # WAL level
    wal_level = c.fetchval("SELECT setting FROM pg_settings WHERE name = 'wal_level'")

    sections = [
        (
            "Server Role",
            [
                ("Role", role),
                ("WAL Level", str(wal_level)),
                ("Current LSN", str(current_lsn) if current_lsn else "-"),
            ],
        ),
    ]

    if is_recovery and replay_lsn:
        sections[0][1].append(("Replay LSN", str(replay_lsn)))

    # Connected replicas (only meaningful on primary)
    replicas = c.fetchall("""
        SELECT
            pid,
            usename,
            application_name,
            client_addr::text,
            state,
            sync_state,
            sent_lsn::text,
            write_lsn::text,
            flush_lsn::text,
            replay_lsn::text,
            reply_time::text
        FROM pg_stat_replication
        ORDER BY application_name
    """)

    if replicas:
        sections.append(
            (
                f"Connected Replicas ({len(replicas)})",
                [
                    (
                        r["application_name"] or r["client_addr"] or f"PID {r['pid']}",
                        f"state={r['state']}, sync={r['sync_state']}, "
                        f"sent={r['sent_lsn'] or '-'}, replay={r['replay_lsn'] or '-'}",
                    )
                    for r in replicas
                ],
            )
        )
    else:
        sections.append(("Connected Replicas", [("(none)", "No replicas connected")]))

    json_data = {
        "role": role,
        "is_recovery": is_recovery,
        "wal_level": wal_level,
        "current_lsn": current_lsn,
        "replay_lsn": replay_lsn,
        "replicas": replicas,
    }

    out.detail("Replication Status", sections, data_for_json=json_data)


@app.command()
def lag(ctx: typer.Context) -> None:
    """Show replication lag for connected replicas (bytes and estimated seconds)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    is_recovery = c.fetchval("SELECT pg_is_in_recovery()")

    if is_recovery:
        # On standby, show lag relative to primary
        row = c.fetchone("""
            SELECT
                pg_last_wal_receive_lsn()::text AS receive_lsn,
                pg_last_wal_replay_lsn()::text AS replay_lsn,
                CASE
                    WHEN pg_last_wal_receive_lsn() IS NOT NULL
                         AND pg_last_wal_replay_lsn() IS NOT NULL
                    THEN pg_wal_lsn_diff(pg_last_wal_receive_lsn(), pg_last_wal_replay_lsn())
                    ELSE NULL
                END AS replay_lag_bytes,
                EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))::numeric(10,2)
                    AS replay_lag_seconds,
                pg_last_xact_replay_timestamp()::text AS last_replay_ts
        """)

        if not row:
            out.error("Could not fetch standby lag info")
            raise typer.Exit(1)

        sections = [
            (
                "Standby Replay Lag",
                [
                    ("Receive LSN", row["receive_lsn"] or "-"),
                    ("Replay LSN", row["replay_lsn"] or "-"),
                    ("Replay Lag (bytes)", _fmt_bytes(row["replay_lag_bytes"])),
                    (
                        "Replay Lag (seconds)",
                        f"{row['replay_lag_seconds']:.2f} s" if row["replay_lag_seconds"] is not None else "-",
                    ),
                    ("Last Replay Timestamp", row["last_replay_ts"] or "-"),
                ],
            ),
        ]

        out.detail("Standby Replication Lag", sections, data_for_json=row)
        return

    # On primary, show lag per replica
    rows_data = c.fetchall("""
        SELECT
            pid,
            application_name,
            client_addr::text,
            state,
            sync_state,
            sent_lsn::text,
            write_lsn::text,
            flush_lsn::text,
            replay_lsn::text,
            pg_wal_lsn_diff(sent_lsn, replay_lsn) AS replay_lag_bytes,
            pg_wal_lsn_diff(sent_lsn, write_lsn) AS write_lag_bytes,
            pg_wal_lsn_diff(sent_lsn, flush_lsn) AS flush_lag_bytes,
            EXTRACT(EPOCH FROM write_lag)::numeric(10,2) AS write_lag_seconds,
            EXTRACT(EPOCH FROM flush_lag)::numeric(10,2) AS flush_lag_seconds,
            EXTRACT(EPOCH FROM replay_lag)::numeric(10,2) AS replay_lag_seconds
        FROM pg_stat_replication
        ORDER BY replay_lag_bytes DESC NULLS LAST
    """)

    if not rows_data:
        out.info("No replicas connected — no lag to report")
        return

    rows = [
        [
            r["application_name"] or "-",
            r["client_addr"] or "-",
            r["state"] or "-",
            r["sync_state"] or "-",
            _fmt_bytes(r["replay_lag_bytes"]),
            f"{r['replay_lag_seconds']:.2f} s" if r["replay_lag_seconds"] is not None else "-",
            _fmt_bytes(r["write_lag_bytes"]),
            _fmt_bytes(r["flush_lag_bytes"]),
        ]
        for r in rows_data
    ]

    out.table(
        f"Replication Lag ({len(rows_data)} replicas)",
        [
            ("Application", "cyan"),
            ("Client", ""),
            ("State", "green"),
            ("Sync", ""),
            ("Replay Lag", "yellow"),
            ("Replay (sec)", "yellow"),
            ("Write Lag", "dim"),
            ("Flush Lag", "dim"),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def slots(ctx: typer.Context) -> None:
    """Show replication slots: name, type, active status, retained WAL."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    rows_data = c.fetchall("""
        SELECT
            slot_name,
            slot_type,
            active,
            active_pid,
            restart_lsn::text,
            confirmed_flush_lsn::text,
            CASE
                WHEN restart_lsn IS NOT NULL AND pg_is_in_recovery() = false
                THEN pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)
                ELSE NULL
            END AS retained_bytes,
            database,
            plugin,
            temporary
        FROM pg_replication_slots
        ORDER BY slot_name
    """)

    if not rows_data:
        out.info("No replication slots configured")
        return

    rows = [
        [
            r["slot_name"],
            r["slot_type"],
            "[green]yes[/green]" if r["active"] else "[red]no[/red]",
            str(r["active_pid"]) if r["active_pid"] else "-",
            r["restart_lsn"] or "-",
            _fmt_bytes(r["retained_bytes"]),
            r["database"] or "-",
            r["plugin"] or "-",
        ]
        for r in rows_data
    ]

    out.table(
        f"Replication Slots ({len(rows_data)})",
        [
            ("Name", "cyan"),
            ("Type", ""),
            ("Active", ""),
            ("PID", "dim"),
            ("Restart LSN", "dim"),
            ("Retained WAL", "yellow"),
            ("Database", ""),
            ("Plugin", "dim"),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command("create-slot")
def slot_create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Replication slot name")],
    logical: Annotated[bool, typer.Option("--logical", help="Create a logical replication slot")] = False,
    plugin: Annotated[str, typer.Option("--plugin", help="Logical decoding plugin (default: pgoutput)")] = "pgoutput",
    physical: Annotated[bool, typer.Option("--physical", help="Create a physical replication slot")] = False,
) -> None:
    """Create a replication slot (physical or logical)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if logical and physical:
        out.error("Cannot specify both --logical and --physical")
        raise typer.Exit(1)

    if not logical and not physical:
        # Default to physical
        physical = True

    if physical:
        try:
            c.fetchone("SELECT pg_create_physical_replication_slot(%s)", (name,))
            out.success(f"Physical replication slot '{name}' created")
        except DatabaseError as e:
            out.error(f"Failed to create physical slot '{name}': {e}")
            raise typer.Exit(1) from e
    else:
        try:
            c.fetchone("SELECT pg_create_logical_replication_slot(%s, %s)", (name, plugin))
            out.success(f"Logical replication slot '{name}' created (plugin: {plugin})")
        except DatabaseError as e:
            out.error(f"Failed to create logical slot '{name}': {e}")
            raise typer.Exit(1) from e


@app.command("drop-slot")
def slot_drop(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Replication slot name")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Drop even if active (terminates walsender)")] = False,
) -> None:
    """Drop a replication slot."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Check if slot exists
    existing = c.fetchone(
        "SELECT slot_name, active, active_pid FROM pg_replication_slots WHERE slot_name = %s",
        (name,),
    )

    if not existing:
        out.error(f"Replication slot '{name}' not found")
        raise typer.Exit(1)

    if existing["active"] and not force:
        out.error(
            f"Slot '{name}' is active (PID {existing['active_pid']}). Use --force to terminate the walsender and drop."
        )
        raise typer.Exit(1)

    if existing["active"] and force:
        # Terminate the walsender process first
        c.execute(
            "SELECT pg_terminate_backend(active_pid) FROM pg_replication_slots WHERE slot_name = %s",
            (name,),
        )
        out.info(f"Terminated walsender for slot '{name}'")

    try:
        c.execute("SELECT pg_drop_replication_slot(%s)", (name,))
        out.success(f"Replication slot '{name}' dropped")
    except DatabaseError as e:
        out.error(f"Failed to drop slot '{name}': {e}")
        raise typer.Exit(1) from e


@app.command()
def publications(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Database name (default: current)")] = None,
) -> None:
    """Show publications and their tables."""
    actx: AppContext = ctx.obj
    out = actx.output

    if database:
        c = actx.get_client(database)
    else:
        c = actx.client

    try:
        rows_data = c.fetchall("""
            SELECT
                p.pubname AS name,
                p.puballtables AS all_tables,
                p.pubinsert AS insert,
                p.pubupdate AS update,
                p.pubdelete AS delete,
                p.pubtruncate AS truncate,
                pg_catalog.pg_get_userbyid(p.pubowner) AS owner
            FROM pg_publication p
            ORDER BY p.pubname
        """)

        if not rows_data:
            out.info("No publications found")
            if database:
                c.close()
            return

        # Get tables for each publication
        for pub in rows_data:
            tables = c.fetchall(
                """
                SELECT schemaname, tablename
                FROM pg_publication_tables
                WHERE pubname = %s
                ORDER BY schemaname, tablename
                """,
                (pub["name"],),
            )
            pub["tables"] = [f"{t['schemaname']}.{t['tablename']}" for t in tables]
            pub["table_count"] = len(tables)

        rows = [
            [
                r["name"],
                r["owner"],
                "[green]yes[/green]" if r["all_tables"] else "[dim]no[/dim]",
                str(r["table_count"]),
                "I" if r["insert"] else "",
                "U" if r["update"] else "",
                "D" if r["delete"] else "",
                "T" if r["truncate"] else "",
            ]
            for r in rows_data
        ]

        out.table(
            f"Publications ({len(rows_data)})",
            [
                ("Name", "cyan"),
                ("Owner", ""),
                ("All Tables", ""),
                ("# Tables", ""),
                ("Ins", "dim"),
                ("Upd", "dim"),
                ("Del", "dim"),
                ("Trunc", "dim"),
            ],
            rows,
            data_for_json=rows_data,
        )
    finally:
        if database:
            c.close()


@app.command()
def subscriptions(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Database name (default: current)")] = None,
) -> None:
    """Show subscriptions and their status."""
    actx: AppContext = ctx.obj
    out = actx.output

    if database:
        c = actx.get_client(database)
    else:
        c = actx.client

    try:
        rows_data = c.fetchall("""
            SELECT
                s.subname AS name,
                pg_catalog.pg_get_userbyid(s.subowner) AS owner,
                s.subenabled AS enabled,
                s.subconninfo AS conninfo,
                s.subslotname AS slot_name,
                s.subpublications AS publications
            FROM pg_subscription s
            ORDER BY s.subname
        """)

        if not rows_data:
            out.info("No subscriptions found")
            if database:
                c.close()
            return

        # Get subscription stats if available
        try:
            sub_stats = c.fetchall("""
                SELECT
                    subname,
                    last_msg_send_time::text,
                    last_msg_receipt_time::text,
                    latest_end_lsn::text
                FROM pg_stat_subscription
                WHERE subname IS NOT NULL
            """)
            stats_map = {s["subname"]: s for s in sub_stats}
        except DatabaseError:
            stats_map = {}

        for sub in rows_data:
            stat = stats_map.get(sub["name"], {})
            sub["last_msg_send_time"] = stat.get("last_msg_send_time", "-")
            sub["latest_end_lsn"] = stat.get("latest_end_lsn", "-")
            # Sanitize conninfo to hide password
            conninfo = sub.get("conninfo", "")
            if conninfo:
                parts = []
                for part in conninfo.split():
                    if part.startswith("password="):
                        parts.append("password=***")
                    else:
                        parts.append(part)
                sub["conninfo_safe"] = " ".join(parts)
            else:
                sub["conninfo_safe"] = "-"

        rows = [
            [
                r["name"],
                r["owner"],
                "[green]yes[/green]" if r["enabled"] else "[red]no[/red]",
                r["slot_name"] or "-",
                ", ".join(r["publications"]) if r["publications"] else "-",
                r.get("latest_end_lsn", "-") or "-",
                r.get("conninfo_safe", "-"),
            ]
            for r in rows_data
        ]

        out.table(
            f"Subscriptions ({len(rows_data)})",
            [
                ("Name", "cyan"),
                ("Owner", ""),
                ("Enabled", ""),
                ("Slot", ""),
                ("Publications", ""),
                ("End LSN", "dim"),
                ("Connection", "dim"),
            ],
            rows,
            data_for_json=rows_data,
        )
    finally:
        if database:
            c.close()


@app.command()
def promote(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation prompt")] = False,
) -> None:
    """Promote standby to primary (pg_promote)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    is_recovery = c.fetchval("SELECT pg_is_in_recovery()")

    if not is_recovery:
        out.error("This server is already a primary — cannot promote")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm("Are you sure you want to promote this standby to primary? This is irreversible.")
        if not confirm:
            out.info("Promotion cancelled")
            raise typer.Exit(0)

    try:
        result = c.fetchval("SELECT pg_promote()")
        if result:
            out.success("Server promoted to primary successfully")
        else:
            out.error("pg_promote() returned false — promotion may have failed")
            raise typer.Exit(1)
    except DatabaseError as e:
        out.error(f"Failed to promote: {e}")
        raise typer.Exit(1) from e


@app.command("senders")
def wal_senders(ctx: typer.Context) -> None:
    """Show detailed WAL sender information for all connected replicas."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    rows_data = c.fetchall("""
        SELECT
            pid,
            usename,
            application_name,
            client_addr::text,
            client_hostname,
            client_port,
            backend_start::text,
            state,
            sent_lsn::text,
            write_lsn::text,
            flush_lsn::text,
            replay_lsn::text,
            write_lag::text,
            flush_lag::text,
            replay_lag::text,
            sync_priority,
            sync_state,
            reply_time::text
        FROM pg_stat_replication
        ORDER BY application_name
    """)

    if not rows_data:
        out.info("No WAL senders active — no replicas connected")
        return

    rows = [
        [
            str(r["pid"]),
            r["application_name"] or "-",
            r["client_addr"] or "-",
            r["state"] or "-",
            r["sent_lsn"] or "-",
            r["write_lsn"] or "-",
            r["flush_lsn"] or "-",
            r["replay_lsn"] or "-",
            r["sync_state"] or "-",
            (r["replay_lag"] or "-").split(".")[0] if r["replay_lag"] else "-",
        ]
        for r in rows_data
    ]

    out.table(
        f"WAL Senders ({len(rows_data)})",
        [
            ("PID", ""),
            ("Application", "cyan"),
            ("Client", ""),
            ("State", "green"),
            ("Sent LSN", "dim"),
            ("Write LSN", "dim"),
            ("Flush LSN", "dim"),
            ("Replay LSN", "dim"),
            ("Sync", "yellow"),
            ("Replay Lag", "red"),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command("receiver")
def wal_receiver(ctx: typer.Context) -> None:
    """Show WAL receiver status (only on standby servers)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    is_recovery = c.fetchval("SELECT pg_is_in_recovery()")

    if not is_recovery:
        out.info("This server is a primary — no WAL receiver running")
        return

    row = c.fetchone("""
        SELECT
            pid,
            status,
            receive_start_lsn::text,
            receive_start_tli,
            written_lsn::text,
            flushed_lsn::text,
            received_tli,
            last_msg_send_time::text,
            last_msg_receipt_time::text,
            latest_end_lsn::text,
            latest_end_time::text,
            slot_name,
            sender_host,
            sender_port,
            conninfo
        FROM pg_stat_wal_receiver
    """)

    if not row:
        out.warn("No WAL receiver process found — replication may be down")
        return

    # Sanitize conninfo
    conninfo = row.get("conninfo", "")
    if conninfo:
        parts = []
        for part in conninfo.split():
            if part.startswith("password="):
                parts.append("password=***")
            else:
                parts.append(part)
        conninfo_safe = " ".join(parts)
    else:
        conninfo_safe = "-"

    sections = [
        (
            "WAL Receiver",
            [
                ("PID", str(row["pid"])),
                ("Status", str(row["status"])),
                ("Sender", f"{row['sender_host'] or '-'}:{row['sender_port'] or '-'}"),
                ("Slot Name", row["slot_name"] or "-"),
            ],
        ),
        (
            "LSN Positions",
            [
                ("Receive Start LSN", row["receive_start_lsn"] or "-"),
                ("Written LSN", row["written_lsn"] or "-"),
                ("Flushed LSN", row["flushed_lsn"] or "-"),
                ("Latest End LSN", row["latest_end_lsn"] or "-"),
            ],
        ),
        (
            "Timing",
            [
                ("Last Msg Sent", (row["last_msg_send_time"] or "-")[:19]),
                ("Last Msg Received", (row["last_msg_receipt_time"] or "-")[:19]),
                ("Latest End Time", (row["latest_end_time"] or "-")[:19]),
            ],
        ),
        (
            "Connection",
            [
                ("Connection Info", conninfo_safe),
            ],
        ),
    ]

    out.detail("WAL Receiver Status", sections, data_for_json=row)
