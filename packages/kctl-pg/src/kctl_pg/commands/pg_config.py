"""PostgreSQL configuration management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_pg.core.callbacks import AppContext

app = typer.Typer(help="Manage PostgreSQL configuration (pg_settings).")


@app.command()
def show(
    ctx: typer.Context,
    filter: Annotated[str | None, typer.Option("--filter", "-f", help="Filter settings by name pattern")] = None,
) -> None:
    """Show PostgreSQL settings (optionally filtered by name pattern)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    sql = """
        SELECT name, setting, unit, category, short_desc, source, boot_val
        FROM pg_settings
    """
    params: list = []

    if filter:
        sql += " WHERE name LIKE %s"
        params.append(f"%{filter}%")

    sql += " ORDER BY name"

    rows_data = c.fetchall(sql, tuple(params) if params else None)

    rows = [
        [
            r["name"],
            str(r["setting"]),
            r["unit"] or "-",
            r["source"],
            (r["short_desc"] or "")[:60],
        ]
        for r in rows_data
    ]

    out.table(
        f"PostgreSQL Settings ({len(rows_data)})",
        [("Name", "cyan"), ("Value", ""), ("Unit", "dim"), ("Source", ""), ("Description", "dim")],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def get(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Setting name")],
) -> None:
    """Get details of a specific PostgreSQL setting."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    row = c.fetchone(
        """
        SELECT name, setting, unit, category, short_desc, extra_desc,
               context, vartype, source, min_val, max_val, enumvals,
               boot_val, reset_val, pending_restart
        FROM pg_settings WHERE name = %s
        """,
        (name,),
    )

    if not row:
        out.error(f"Setting not found: {name}")
        raise typer.Exit(1)

    sections = [
        (
            "Setting",
            [
                ("Name", str(row["name"])),
                ("Value", str(row["setting"])),
                ("Unit", str(row["unit"] or "-")),
                ("Type", str(row["vartype"])),
                ("Source", str(row["source"])),
            ],
        ),
        (
            "Details",
            [
                ("Category", str(row["category"] or "-")),
                ("Description", str(row["short_desc"] or "-")),
                ("Extra", str(row["extra_desc"] or "-")[:200]),
                ("Context", str(row["context"])),
            ],
        ),
        (
            "Ranges",
            [
                ("Boot Value", str(row["boot_val"] or "-")),
                ("Reset Value", str(row["reset_val"] or "-")),
                ("Min", str(row["min_val"] or "-")),
                ("Max", str(row["max_val"] or "-")),
                ("Enum Values", str(row["enumvals"] or "-")),
                ("Pending Restart", str(row["pending_restart"])),
            ],
        ),
    ]

    out.detail(f"Setting: {name}", sections, data_for_json=row)


@app.command("set")
def set_(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Setting name")],
    value: Annotated[str, typer.Argument(help="New value")],
) -> None:
    """Set a PostgreSQL configuration parameter (ALTER SYSTEM + reload)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Validate the setting exists
    row = c.fetchone("SELECT name, context FROM pg_settings WHERE name = %s", (name,))
    if not row:
        out.error(f"Setting not found: {name}")
        raise typer.Exit(1)

    context = row["context"]
    if context == "internal":
        out.error(f"Setting '{name}' is read-only (internal)")
        raise typer.Exit(1)

    # Use format string for SET since parameterized ALTER SYSTEM is not supported
    # Safely quote the value
    c.execute(f"ALTER SYSTEM SET {name} = %s", (value,))
    c.execute("SELECT pg_reload_conf()")

    if context == "postmaster":
        out.warn(f"Setting '{name}' requires a server restart to take effect")
    else:
        out.success(f"Setting '{name}' set to '{value}' and configuration reloaded")


@app.command()
def reset(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Setting name to reset")],
) -> None:
    """Reset a PostgreSQL configuration parameter to default (ALTER SYSTEM RESET + reload)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Validate
    row = c.fetchone("SELECT name, context FROM pg_settings WHERE name = %s", (name,))
    if not row:
        out.error(f"Setting not found: {name}")
        raise typer.Exit(1)

    # ALTER SYSTEM RESET doesn't support parameterized names, but name is validated above
    c.execute(f'ALTER SYSTEM RESET "{name}"')
    c.execute("SELECT pg_reload_conf()")

    context = row["context"]
    if context == "postmaster":
        out.warn(f"Setting '{name}' reset to default; requires restart to take effect")
    else:
        out.success(f"Setting '{name}' reset to default and configuration reloaded")


@app.command()
def reload(ctx: typer.Context) -> None:
    """Reload PostgreSQL configuration (pg_reload_conf)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    result = c.fetchval("SELECT pg_reload_conf()")
    if result:
        out.success("Configuration reloaded successfully")
    else:
        out.error("Configuration reload failed")
        raise typer.Exit(1)


@app.command()
def diff(ctx: typer.Context) -> None:
    """Show settings that differ from their default (boot) values."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    rows_data = c.fetchall("""
        SELECT name, setting, boot_val, unit, source, pending_restart
        FROM pg_settings
        WHERE setting != boot_val
          AND source != 'default'
        ORDER BY source, name
    """)

    if not rows_data:
        out.success("All settings are at default values")
        return

    rows = [
        [
            r["name"],
            str(r["setting"]),
            str(r["boot_val"]),
            r["unit"] or "-",
            r["source"],
            "[yellow]yes[/yellow]" if r["pending_restart"] else "no",
        ]
        for r in rows_data
    ]

    out.table(
        f"Non-Default Settings ({len(rows_data)})",
        [
            ("Name", "cyan"),
            ("Current", ""),
            ("Default", "dim"),
            ("Unit", "dim"),
            ("Source", ""),
            ("Restart?", "yellow"),
        ],
        rows,
        data_for_json=rows_data,
    )
