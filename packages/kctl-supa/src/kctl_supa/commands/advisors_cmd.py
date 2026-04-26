"""Security and performance advisor commands for kctl-supa."""

from __future__ import annotations

import typer
from rich import print as rprint
from rich.table import Table

from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.docker import DockerOps
from kctl_supa.core.exceptions import DockerError

app = typer.Typer(help="Security and performance advisors.")


def _get_docker(actx: AppContext) -> DockerOps:
    return DockerOps(actx.config)


def _run_psql(actx: AppContext, query: str) -> str:
    out = actx.output
    try:
        docker = _get_docker(actx)
        result = docker.psql(query)
        docker.close()
        return result
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc


def _extract_last_value(raw: str) -> str:
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    return lines[-1] if lines else "N/A"


@app.command()
def security(ctx: typer.Context) -> None:
    """Security audit: tables without RLS, public schemas, superuser roles."""
    actx: AppContext = ctx.obj

    docker = _get_docker(actx)
    checks: list[tuple[str, str, str]] = []

    try:
        no_rls = docker.psql(
            "SELECT count(*) FROM pg_tables "
            "WHERE schemaname = 'public' AND tablename NOT IN ("
            "SELECT DISTINCT tablename FROM pg_policies WHERE schemaname = 'public'"
            ")",
        )
        val = _extract_last_value(no_rls)
        n = int(val) if val.isdigit() else 0
        checks.append(("Tables without RLS", val, "[red]WARN[/red]" if n > 0 else "[green]OK[/green]"))
    except DockerError:
        checks.append(("Tables without RLS", "error", "[red]ERROR[/red]"))

    try:
        superusers = docker.psql("SELECT count(*) FROM pg_roles WHERE rolsuper = true")
        val = _extract_last_value(superusers)
        checks.append(("Superuser roles", val, "[yellow]INFO[/yellow]"))
    except DockerError:
        checks.append(("Superuser roles", "error", "[red]ERROR[/red]"))

    try:
        exposed = docker.psql(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'",
        )
        val = _extract_last_value(exposed)
        checks.append(("Public schema tables", val, "[yellow]INFO[/yellow]"))
    except DockerError:
        checks.append(("Public schema tables", "error", "[red]ERROR[/red]"))

    docker.close()

    table = Table(title="Security Advisor", show_header=True, header_style="bold cyan")
    table.add_column("Check", style="cyan")
    table.add_column("Value")
    table.add_column("Status")
    for check_name, value, status in checks:
        table.add_row(check_name, value, status)
    rprint(table)


@app.command()
def performance(ctx: typer.Context) -> None:
    """Performance advisor: cache hit ratio, unused indexes, table bloat."""
    actx: AppContext = ctx.obj

    docker = _get_docker(actx)
    checks: list[tuple[str, str, str]] = []

    try:
        cache = docker.psql(
            "SELECT round(100.0 * sum(blks_hit) / nullif(sum(blks_hit) + sum(blks_read), 0), 2) FROM pg_stat_database",
        )
        val = _extract_last_value(cache)
        try:
            pct = float(val)
        except ValueError:
            pct = 0
        status = "[green]OK[/green]" if pct >= 99 else "[yellow]WARN[/yellow]" if pct >= 95 else "[red]LOW[/red]"
        checks.append(("Cache hit ratio", f"{val}%", status))
    except DockerError:
        checks.append(("Cache hit ratio", "error", "[red]ERROR[/red]"))

    try:
        unused = docker.psql(
            "SELECT count(*) FROM pg_stat_user_indexes WHERE idx_scan = 0",
        )
        val = _extract_last_value(unused)
        n = int(val) if val.isdigit() else 0
        status = "[green]OK[/green]" if n == 0 else "[yellow]WARN[/yellow]"
        checks.append(("Unused indexes", val, status))
    except DockerError:
        checks.append(("Unused indexes", "error", "[red]ERROR[/red]"))

    try:
        dead = docker.psql(
            "SELECT sum(n_dead_tup) FROM pg_stat_user_tables",
        )
        val = _extract_last_value(dead)
        try:
            n = int(val)
        except ValueError:
            n = 0
        status = "[green]OK[/green]" if n < 10000 else "[yellow]WARN[/yellow]" if n < 100000 else "[red]HIGH[/red]"
        checks.append(("Dead tuples", val, status))
    except DockerError:
        checks.append(("Dead tuples", "error", "[red]ERROR[/red]"))

    docker.close()

    table = Table(title="Performance Advisor", show_header=True, header_style="bold cyan")
    table.add_column("Check", style="cyan")
    table.add_column("Value")
    table.add_column("Status")
    for check_name, value, status in checks:
        table.add_row(check_name, value, status)
    rprint(table)


@app.command()
def queries(ctx: typer.Context) -> None:
    """Query performance: top queries by total time (requires pg_stat_statements)."""
    actx: AppContext = ctx.obj
    out = actx.output
    check = _run_psql(actx, "SELECT count(*) FROM pg_extension WHERE extname = 'pg_stat_statements'")
    if check.strip().splitlines()[-1].strip() == "0":
        out.warn("pg_stat_statements not installed. Enable it: CREATE EXTENSION pg_stat_statements;")
        return
    result = _run_psql(
        actx,
        "SELECT calls, round(total_exec_time::numeric, 2) AS total_ms, "
        "round(mean_exec_time::numeric, 2) AS mean_ms, "
        "left(query, 80) AS query "
        "FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 20",
    )
    typer.echo(result)


@app.command(name="indexes")
def index_advisor(ctx: typer.Context) -> None:
    """Index advisor: unused indexes and sequential scan ratios."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Unused indexes (0 scans):")
    unused = _run_psql(
        actx,
        "SELECT schemaname, relname AS table, indexrelname AS index, "
        "pg_size_pretty(pg_relation_size(indexrelid)) AS size "
        "FROM pg_stat_user_indexes WHERE idx_scan = 0 "
        "ORDER BY pg_relation_size(indexrelid) DESC",
    )
    typer.echo(unused)

    out.info("Tables with high sequential scan ratio:")
    seq_ratio = _run_psql(
        actx,
        "SELECT schemaname, relname AS table, "
        "seq_scan, idx_scan, "
        "CASE WHEN seq_scan + idx_scan > 0 "
        "THEN round(100.0 * seq_scan / (seq_scan + idx_scan), 1) ELSE 0 END AS seq_pct "
        "FROM pg_stat_user_tables "
        "WHERE seq_scan + idx_scan > 100 "
        "ORDER BY seq_pct DESC LIMIT 20",
    )
    typer.echo(seq_ratio)


@app.command(name="rls-audit")
def rls_audit(ctx: typer.Context) -> None:
    """RLS audit: tables without policies, permissive gaps, role coverage."""
    actx: AppContext = ctx.obj
    out = actx.output

    docker = _get_docker(actx)

    out.info("Tables WITHOUT any RLS policy (exposed to anon/authenticated):")
    no_policy = docker.psql(
        "SELECT schemaname, tablename, rowsecurity "
        "FROM pg_tables "
        "WHERE schemaname IN ('public', 'storage') "
        "AND tablename NOT IN (SELECT DISTINCT tablename FROM pg_policies WHERE schemaname = pg_tables.schemaname) "
        "ORDER BY schemaname, tablename",
    )
    typer.echo(no_policy)

    out.info("Tables with RLS DISABLED (bypasses all policies):")
    rls_disabled = docker.psql(
        "SELECT n.nspname AS schema, c.relname AS table "
        "FROM pg_class c JOIN pg_namespace n ON c.relnamespace = n.oid "
        "WHERE c.relkind = 'r' AND NOT c.relrowsecurity "
        "AND n.nspname IN ('public', 'storage') "
        "ORDER BY n.nspname, c.relname",
    )
    typer.echo(rls_disabled)

    out.info("All RLS policies (schema, table, policy, roles, command):")
    all_policies = docker.psql(
        "SELECT schemaname, tablename, policyname, permissive, roles, cmd "
        "FROM pg_policies "
        "WHERE schemaname IN ('public', 'storage', 'auth') "
        "ORDER BY schemaname, tablename, policyname",
    )
    typer.echo(all_policies)

    out.info("Tables with FORCE ROW SECURITY (applies to table owner too):")
    forced = docker.psql(
        "SELECT n.nspname AS schema, c.relname AS table "
        "FROM pg_class c JOIN pg_namespace n ON c.relnamespace = n.oid "
        "WHERE c.relkind = 'r' AND c.relforcerowsecurity "
        "AND n.nspname IN ('public', 'storage') "
        "ORDER BY n.nspname, c.relname",
    )
    typer.echo(forced)

    docker.close()
