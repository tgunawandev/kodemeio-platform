"""Maintenance and operational commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_rustdesk.core.callbacks import AppContext

app = typer.Typer(help="Maintenance and operational tasks.")


@app.command()
def status(ctx: typer.Context) -> None:
    """Show container status and resource usage."""
    c: AppContext = ctx.obj
    ex = c.executor

    containers = ex.docker_ps()
    rows = [
        [
            ct.get("Service", ct.get("Name", "")),
            ct.get("State", ct.get("Status", "")),
            ct.get("Health", ""),
            ct.get("Ports", ""),
        ]
        for ct in containers
    ]

    c.output.table(
        "Container Status",
        [("Service", "cyan"), ("State", "green"), ("Health", ""), ("Ports", "dim")],
        rows,
        data_for_json=containers,
    )


@app.command()
def version(ctx: typer.Context) -> None:
    """Show version information."""
    c: AppContext = ctx.obj
    ex = c.executor

    from kctl_rustdesk import __version__

    compose_ver = ex.get_compose_version()

    try:
        hbbs_image = ex.shell(
            ["docker", "inspect", "--format", "{{.Config.Image}}", f"{ex.config.project_name}-hbbs-1"],
            check=False,
        )
    except Exception:
        hbbs_image = "unknown"

    sections = [
        (
            "Versions",
            [
                ("kctl-rustdesk", __version__),
                ("Docker Compose", compose_ver),
                ("hbbs image", hbbs_image),
            ],
        )
    ]

    c.output.detail(
        "Version Info",
        sections,
        data_for_json={
            "kctl_rustdesk": __version__,
            "docker_compose": compose_ver,
            "hbbs_image": hbbs_image,
        },
    )


@app.command()
def logs(
    ctx: typer.Context,
    service: Annotated[str | None, typer.Argument(help="Service (hbbs or hbbr)")] = None,
    lines: Annotated[int, typer.Option("--lines", "-n", help="Number of lines")] = 100,
) -> None:
    """View container logs."""
    c: AppContext = ctx.obj
    output = c.executor.docker_logs(service=service, tail=lines)
    c.output.text(output)


@app.command("db-optimize")
def db_optimize(ctx: typer.Context) -> None:
    """Optimize the SQLite database (VACUUM + ANALYZE)."""
    c: AppContext = ctx.obj
    out = c.output
    ex = c.executor

    out.info("Running integrity check...")
    integrity = ex.exec_hbbs(["sqlite3", ex.DB_PATH, "PRAGMA integrity_check;"])
    out.kv("Integrity", integrity)

    out.info("Running VACUUM...")
    ex.exec_hbbs(["sqlite3", ex.DB_PATH, "VACUUM;"])

    out.info("Running ANALYZE...")
    ex.exec_hbbs(["sqlite3", ex.DB_PATH, "ANALYZE;"])

    out.success("Database optimized.")


@app.command("db-stats")
def db_stats(ctx: typer.Context) -> None:
    """Show database statistics."""
    c: AppContext = ctx.obj
    ex = c.executor

    tables = ["peer", "user", "grp", "conn_log", "login_log"]
    rows: list[list[str]] = []
    json_data: dict[str, int] = {}

    for table in tables:
        try:
            count = ex.query_db_scalar(f"SELECT count(*) FROM {table};")
            rows.append([table, count])
            json_data[table] = int(count)
        except Exception:
            rows.append([table, "(error)"])
            json_data[table] = -1

    try:
        size = ex.exec_hbbs(
            ["stat", "-c", "%s", ex.DB_PATH],
            check=False,
        )
        if size.strip().isdigit():
            size_mb = f"{int(size) / 1048576:.2f} MB"
        else:
            size_mb = "unknown"
    except Exception:
        size_mb = "unknown"

    rows.append(["---", "---"])
    rows.append(["DB size", size_mb])

    c.output.table(
        "Database Statistics",
        [("Table", "cyan"), ("Rows", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def cleanup(ctx: typer.Context) -> None:
    """Clean up unused Docker resources."""
    c: AppContext = ctx.obj
    out = c.output
    ex = c.executor

    if not typer.confirm("Remove dangling images and build cache?"):
        out.info("Cleanup cancelled.")
        raise typer.Exit()

    out.info("Removing dangling images...")
    ex.shell(["docker", "image", "prune", "-f"], check=False)

    out.info("Clearing build cache...")
    ex.shell(["docker", "builder", "prune", "-f"], check=False)

    out.success("Cleanup complete.")
