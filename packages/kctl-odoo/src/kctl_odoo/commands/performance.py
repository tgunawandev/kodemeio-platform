"""Performance diagnostics and profiling commands."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError
from kctl_odoo.core.utils import module_state_color

app = typer.Typer(help="Performance diagnostics, profiling, and benchmarks.")


@app.command()
def stats(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously monitor")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Watch interval in seconds")] = 60,
) -> None:
    """Show database and system statistics overview."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    def _run_once() -> None:
        _stats_body(out, c)

    _run_once()
    if watch:
        import time

        try:
            while True:
                time.sleep(interval)
                out.header(f"Refresh at {time.strftime('%H:%M:%S')}")
                _run_once()
        except KeyboardInterrupt:
            out.info("Stopped watching")


def _stats_body(out, c) -> None:
    """Performance stats body — extracted for --watch support."""
    sections = []
    json_result: dict = {}

    # Key model record counts
    key_models = [
        ("res.partner", "Partners"),
        ("res.users", "Users"),
        ("sale.order", "Sale Orders"),
        ("purchase.order", "Purchase Orders"),
        ("account.move", "Journal Entries"),
        ("stock.picking", "Stock Pickings"),
        ("product.product", "Products"),
        ("mail.message", "Mail Messages"),
        ("mail.mail", "Mail Queue"),
        ("ir.attachment", "Attachments"),
        ("ir.logging", "Log Entries"),
    ]

    record_kvs = []
    record_json = {}
    for model, label in key_models:
        try:
            count = c.search_count(model, [])
            record_kvs.append((label, f"{count:,}"))
            record_json[model] = count
        except RPCError:
            record_kvs.append((label, "[dim]N/A (module not installed)[/dim]"))
            record_json[model] = None

    sections.append(("Record Counts", record_kvs))
    json_result["record_counts"] = record_json

    # Module stats
    installed = c.search_count("ir.module.module", [("state", "=", "installed")])
    total_modules = c.search_count("ir.module.module", [])
    sections.append(
        (
            "Modules",
            [
                ("Installed", str(installed)),
                ("Total available", str(total_modules)),
            ],
        )
    )
    json_result["modules_installed"] = installed
    json_result["modules_total"] = total_modules

    # Attachment stats (often a major contributor to DB size)
    try:
        attachment_count = c.search_count("ir.attachment", [])
        sections.append(
            (
                "Storage",
                [
                    ("Total attachments", f"{attachment_count:,}"),
                ],
            )
        )
        json_result["attachments"] = attachment_count
    except RPCError:
        pass

    out.detail("Performance Statistics", sections, data_for_json=json_result)  # noqa: E501


@app.command()
def tables(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 30,
) -> None:
    """Show record counts per model (largest tables first)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Get all models, then count records individually (count is non-stored computed)
    models = c.search_read(
        "ir.model",
        domain=[("transient", "=", False)],
        fields=["id", "model", "name"],
        limit=500,
    )

    # Count records per model
    for m in models:
        try:
            m["count"] = c.search_count(m["model"], [])
        except Exception:
            m["count"] = 0

    # Sort by count descending
    models.sort(key=lambda x: x.get("count", 0), reverse=True)

    # Filter to models with records and take top N
    models_with_data = [m for m in models if m.get("count", 0) > 0][:limit]

    if not models_with_data:
        out.info("No model record count data available.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for m in models_with_data:
        count = m.get("count", 0)
        rows.append(
            [
                m["model"],
                m.get("name", "")[:35],
                f"{count:,}",
            ]
        )
        json_data.append(
            {
                "model": m["model"],
                "name": m.get("name"),
                "count": count,
            }
        )

    out.table(
        f"Largest Tables by Record Count (top {len(models_with_data)})",
        [("Model", ""), ("Description", ""), ("Records", "cyan")],
        rows,
        data_for_json=json_data,
    )


@app.command("modules-count")
def modules_count(ctx: typer.Context) -> None:
    """Count modules by state."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    states = ["installed", "uninstalled", "to upgrade", "to install", "to remove"]
    rows = []
    json_data = []
    total = 0

    for state in states:
        count = c.search_count("ir.module.module", [("state", "=", state)])
        total += count
        color = module_state_color(state)
        rows.append([color, str(count)])
        json_data.append({"state": state, "count": count})

    rows.append(["[bold]total[/bold]", f"[bold]{total}[/bold]"])
    json_data.append({"state": "total", "count": total})

    out.table(
        "Modules by State",
        [("State", ""), ("Count", "cyan")],
        rows,
        data_for_json=json_data,
    )


# Moved to cron group: kctl-odoo cron status
# (Previously: kctl-odoo performance slow-actions)

# Moved to storage group: kctl-odoo storage db-size
# (Previously: kctl-odoo performance db-size)


@app.command()
def cache(ctx: typer.Context) -> None:
    """Show cache-related system parameters."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Get all config parameters (filter for cache/performance related)
    params = c.search_read(
        "ir.config_parameter",
        domain=[],
        fields=["key", "value"],
        order="key",
    )

    cache_keywords = ["cache", "limit", "timeout", "session", "workers", "memory", "cron", "bus"]
    filtered = [p for p in params if any(kw in p.get("key", "").lower() for kw in cache_keywords)]

    if not filtered:
        # If no cache-specific params, show common system params
        filtered = [p for p in params if p.get("key", "").startswith(("web.", "database.", "mail."))]

    if not filtered:
        out.info("No cache-related parameters found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for p in filtered:
        rows.append([p.get("key", ""), p.get("value", "")[:60]])
        json_data.append({"key": p.get("key"), "value": p.get("value")})

    out.table(
        f"System Parameters ({len(filtered)})",
        [("Key", ""), ("Value", "cyan")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def indexes(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 30,
) -> None:
    """List models and their indexed fields."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Get fields that are indexed
    fields = c.search_read(
        "ir.model.fields",
        domain=[("index", "=", True)],
        fields=["model_id", "name", "field_description", "ttype", "model"],
        limit=limit * 5,
        order="model, name",
    )

    if not fields:
        out.info("No indexed fields found via ir.model.fields.")
        if actx.json_mode:
            out.raw_json([])
        return

    # Group by model
    by_model: dict[str, list] = {}
    for f in fields:
        model = f.get("model", "?")
        if model not in by_model:
            by_model[model] = []
        by_model[model].append(f)

    rows = []
    json_data = []
    count = 0
    for model in sorted(by_model):
        if count >= limit:
            break
        for f in by_model[model]:
            if count >= limit:
                break
            rows.append(
                [
                    model,
                    f.get("name", ""),
                    f.get("field_description", ""),
                    f.get("ttype", ""),
                ]
            )
            json_data.append(
                {
                    "model": model,
                    "field": f.get("name"),
                    "description": f.get("field_description"),
                    "type": f.get("ttype"),
                }
            )
            count += 1

    out.table(
        f"Indexed Fields ({len(json_data)})",
        [("Model", ""), ("Field", "cyan"), ("Description", ""), ("Type", "dim")],
        rows,
        data_for_json=json_data,
    )


# ---------------------------------------------------------------------------
# Real Profiling — RPC response times, cron timing, benchmarks
# ---------------------------------------------------------------------------


@app.command("benchmark")
def benchmark(
    ctx: typer.Context,
    iterations: Annotated[int, typer.Option("--iterations", "-n", help="Number of iterations")] = 5,
) -> None:
    """Benchmark ORM operations — measure RPC response times.

    Runs timed calls against key models to measure JSON-RPC latency,
    search speed, and read performance. Useful for comparing instances
    or detecting degradation.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    results: list[dict] = []

    def _bench(name: str, fn) -> None:
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            try:
                fn()
                elapsed = (time.perf_counter() - start) * 1000
                times.append(elapsed)
            except Exception:
                times.append(-1)
        valid = [t for t in times if t >= 0]
        avg = sum(valid) / len(valid) if valid else -1
        mn = min(valid) if valid else -1
        mx = max(valid) if valid else -1
        results.append(
            {
                "operation": name,
                "avg_ms": round(avg, 1),
                "min_ms": round(mn, 1),
                "max_ms": round(mx, 1),
                "iterations": len(valid),
            }
        )

    out.info(f"Running benchmark ({iterations} iterations each)...")

    _bench("authenticate", lambda: c.version_info())
    _bench("search_count res.partner", lambda: c.search_count("res.partner", []))
    _bench("search_read res.partner (10)", lambda: c.search_read("res.partner", [], fields=["name", "email"], limit=10))
    _bench(
        "search_read res.partner (100)", lambda: c.search_read("res.partner", [], fields=["name", "email"], limit=100)
    )
    _bench("search_count sale.order", lambda: c.search_count("sale.order", []))
    _bench("search_count account.move.line", lambda: c.search_count("account.move.line", []))
    _bench("fields_get res.partner", lambda: c.fields_get("res.partner", attributes=["string", "type"]))
    _bench(
        "read ir.config_parameter (1)",
        lambda: c.search_read("ir.config_parameter", [("key", "=", "web.base.url")], fields=["value"]),
    )

    rows = []
    for r in results:
        avg = f"{r['avg_ms']:.0f}ms" if r["avg_ms"] >= 0 else "[red]FAIL[/red]"
        speed = (
            "[green]fast[/green]"
            if r["avg_ms"] < 50
            else "[yellow]ok[/yellow]"
            if r["avg_ms"] < 200
            else "[red]slow[/red]"
        )
        rows.append([r["operation"], avg, f"{r['min_ms']:.0f}ms", f"{r['max_ms']:.0f}ms", speed])

    out.table(
        f"ORM Benchmark ({iterations} iterations)",
        [("Operation", "cyan"), ("Avg", ""), ("Min", "dim"), ("Max", "dim"), ("Rating", "")],
        rows,
        results,
    )


@app.command("cron-timing")
def cron_timing(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 20,
) -> None:
    """Show cron execution timing — identify slow scheduled actions.

    Analyzes the gap between lastcall and nextcall to estimate execution
    frequency and detect crons that run longer than expected.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    crons = c.search_read(
        "ir.cron",
        domain=[("active", "=", True)],
        fields=["name", "interval_number", "interval_type", "lastcall", "nextcall", "priority"],
        order="priority, name",
        limit=limit,
    )

    if not crons:
        out.info("No active cron jobs found.")
        return

    now = datetime.now(tz=UTC)
    rows = []
    json_data = []

    for cr in crons:
        lastcall = cr.get("lastcall")
        nextcall = cr.get("nextcall")
        interval = f"{cr.get('interval_number', '?')} {cr.get('interval_type', '?')}"

        # Calculate time since last run
        since_last = ""
        overdue = False
        if lastcall:
            try:
                last_dt = datetime.strptime(str(lastcall)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
                delta = now - last_dt
                if delta.total_seconds() < 3600:
                    since_last = f"{int(delta.total_seconds() / 60)}m ago"
                elif delta.total_seconds() < 86400:
                    since_last = f"{int(delta.total_seconds() / 3600)}h ago"
                else:
                    since_last = f"{delta.days}d ago"
            except (ValueError, TypeError):
                since_last = "?"

        if nextcall:
            try:
                next_dt = datetime.strptime(str(nextcall)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
                if next_dt < now - timedelta(hours=1):
                    overdue = True
            except (ValueError, TypeError):
                pass

        status = "[red]OVERDUE[/red]" if overdue else "[green]OK[/green]"

        rows.append([cr["name"][:40], interval, since_last, status])
        json_data.append(
            {
                "name": cr["name"],
                "interval": interval,
                "last_run": since_last,
                "overdue": overdue,
            }
        )

    out.table(
        f"Cron Execution Timing ({len(crons)} active)",
        [("Cron Job", "cyan"), ("Interval", ""), ("Last Run", "dim"), ("Status", "")],
        rows,
        json_data,
    )


@app.command("queue-throughput")
def queue_throughput(
    ctx: typer.Context,
    hours: Annotated[int, typer.Option("--hours", "-h", help="Hours to look back")] = 24,
) -> None:
    """Show queue job throughput — jobs processed per hour.

    Requires the OCA queue_job module. Shows done/failed rates
    to detect processing bottlenecks.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    now = datetime.now(tz=UTC)
    cutoff = (now - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

    # Check if queue_job module is installed before querying
    qj_installed = c.search_count("ir.module.module", [("name", "=", "queue_job"), ("state", "=", "installed")])
    if not qj_installed:
        out.error("queue_job module not available. Install via: kctl-odoo modules install queue_job")
        raise typer.Exit(1)

    try:
        done = c.search_count("queue.job", [("state", "=", "done"), ("date_done", ">", cutoff)])
        failed = c.search_count("queue.job", [("state", "=", "failed"), ("date_created", ">", cutoff)])
        pending = c.search_count("queue.job", [("state", "in", ["pending", "enqueued", "started"])])
    except RPCError as exc:
        out.error(f"Failed to query queue.job: {exc}")
        raise typer.Exit(1) from exc

    rate = done / hours if hours else 0

    sections = [
        (
            f"Queue Throughput (last {hours}h)",
            [
                ("Completed", f"[green]{done}[/green]"),
                ("Failed", f"[red]{failed}[/red]" if failed else "[green]0[/green]"),
                ("Pending now", str(pending)),
                ("Rate", f"{rate:.1f} jobs/hour"),
                ("Failure rate", f"{(failed / (done + failed) * 100):.1f}%" if (done + failed) else "0%"),
            ],
        ),
    ]

    json_data = {"hours": hours, "done": done, "failed": failed, "pending": pending, "rate_per_hour": round(rate, 1)}
    out.detail("Queue Job Throughput", sections, json_data)


@app.command("model-speed")
def model_speed(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Model to profile (e.g., res.partner)")],
    limit: Annotated[int, typer.Option("--limit", "-l", help="Records to fetch")] = 100,
) -> None:
    """Profile a specific model — measure search, read, and count speeds.

    Useful for identifying slow models. Run before and after adding
    indexes or optimizing queries.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    results: list[dict] = []

    def _time(name: str, fn) -> None:
        start = time.perf_counter()
        try:
            result = fn()
            elapsed = (time.perf_counter() - start) * 1000
            if isinstance(result, dict):
                count = f"{len(result)} fields"
            elif isinstance(result, list):
                count = len(result)
            else:
                count = result
            results.append({"operation": name, "ms": round(elapsed, 1), "records": count})
        except Exception as e:
            results.append({"operation": name, "ms": -1, "records": 0, "error": str(e)})

    out.info(f"Profiling model: {model}")

    _time("search_count (all)", lambda: c.search_count(model, []))
    _time(f"search_read (limit {limit})", lambda: c.search_read(model, [], fields=["id", "display_name"], limit=limit))
    _time("search_read (limit 1)", lambda: c.search_read(model, [], fields=["id", "display_name"], limit=1))
    _time("fields_get", lambda: c.fields_get(model, attributes=["string", "type", "required"]))

    # Try a filtered search if model has common fields
    try:
        fields = c.fields_get(model, attributes=["type"])
        if "name" in fields:
            _time("search name ilike 'a'", lambda: c.search_count(model, [("name", "ilike", "a")]))
        if "create_date" in fields:
            cutoff = (datetime.now(tz=UTC) - timedelta(days=30)).strftime("%Y-%m-%d")
            _time("search last 30 days", lambda: c.search_count(model, [("create_date", ">", cutoff)]))
    except Exception:
        pass

    rows = []
    for r in results:
        ms = f"{r['ms']:.0f}ms" if r["ms"] >= 0 else "[red]FAIL[/red]"
        speed = "[green]fast[/green]" if r["ms"] < 50 else "[yellow]ok[/yellow]" if r["ms"] < 200 else "[red]slow[/red]"
        rows.append([r["operation"], ms, str(r.get("records", "")), speed])

    out.table(
        f"Model Profile: {model}",
        [("Operation", "cyan"), ("Time", ""), ("Records", "dim"), ("Rating", "")],
        rows,
        results,
    )


@app.command("pg")
def pg_hint(ctx: typer.Context) -> None:
    """Show how to use kctl-pg for database-level profiling.

    kctl-odoo operates via JSON-RPC (application level). For deep database
    profiling (slow queries, locks, bloat, VACUUM), use kctl-pg which
    connects directly to PostgreSQL.
    """
    from rich.console import Console

    console = Console()
    console.print("""
[bold cyan]Database-Level Profiling with kctl-pg[/bold cyan]

kctl-odoo measures [bold]application-level[/bold] performance (RPC times, ORM speed).
For [bold]database-level[/bold] profiling, use [bold]kctl-pg[/bold]:

[bold]Quick diagnostics:[/bold]
  kctl-pg perf overview                    # Cache hits, connections, DB sizes
  kctl-pg perf slow-queries                # Slowest queries (pg_stat_statements)
  kctl-pg perf locks                       # Current lock contention
  kctl-pg perf connections                 # Connection pool usage

[bold]Table analysis:[/bold]
  kctl-pg maintenance bloat                # Dead tuple ratio per table
  kctl-pg maintenance autovacuum-status    # Last vacuum/analyze per table
  kctl-pg stats tables                     # Seq scans, index scans, live/dead tuples
  kctl-pg tables size                      # Table + index + TOAST sizes

[bold]Index analysis:[/bold]
  kctl-pg perf index-usage                 # Find unused indexes
  kctl-pg indexes missing                  # Tables needing indexes (high seq scans)
  kctl-pg indexes duplicate                # Overlapping indexes to drop
  kctl-pg indexes bloat                    # Bloated indexes to reindex

[bold]Maintenance:[/bold]
  kctl-pg maintenance vacuum <table>       # Run VACUUM
  kctl-pg maintenance analyze <table>      # Update planner statistics
  kctl-pg maintenance reindex-concurrently <table>  # Rebuild indexes (non-blocking)

[bold]Combined workflow:[/bold]
  kctl-odoo performance benchmark          # App-level: RPC response times
  kctl-pg perf slow-queries                # DB-level: which SQL is slow
  kctl-pg indexes missing                  # Find tables needing indexes
  kctl-pg maintenance analyze              # Update statistics
  kctl-odoo performance benchmark          # Re-measure — improvement?

[dim]Install: uv tool install ../kodemeio-postgres/cli[/dim]
[dim]Config: kctl-pg config init[/dim]
""")


# ---------------------------------------------------------------------------
# Wave 5: memory, connections
# ---------------------------------------------------------------------------


@app.command("memory")
def memory_cmd(ctx: typer.Context) -> None:
    """Show Odoo server memory usage and configuration guidance.

    Attempts to retrieve system parameters related to memory/workers,
    and provides guidance on monitoring tools for actual process memory.

    Examples:
        kctl-odoo performance memory
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Gather system params related to workers/memory
    try:
        params = c.search_read(
            "ir.config_parameter",
            domain=[],
            fields=["key", "value"],
            order="key",
        )
    except RPCError as exc:
        out.error(f"Cannot read system parameters: {exc}")
        raise typer.Exit(1) from exc

    memory_keys = {"workers", "memory", "limit_memory", "limit_time", "max_cron"}
    relevant = [p for p in params if any(kw in p.get("key", "").lower() for kw in memory_keys)]

    rows: list[list[str]] = []
    json_data: list[dict] = []
    for p in relevant:
        rows.append([p.get("key", ""), p.get("value", "")])
        json_data.append({"key": p.get("key"), "value": p.get("value")})

    if rows:
        out.table(
            f"Memory-Related System Parameters ({len(rows)})",
            [("Key", "cyan"), ("Value", "")],
            rows,
            data_for_json=json_data,
        )
    else:
        out.info("No memory-related system parameters found in ir.config_parameter.")

    from rich.console import Console

    _console = Console()
    _console.print("""
[bold]To monitor actual process memory:[/bold]
  docker compose exec odoo bash -c "ps aux --sort=-%mem | head -10"
  docker stats --no-stream

[bold]Key Odoo memory config (set in odoo.conf or env):[/bold]
  limit_memory_soft = 2147483648   # 2 GB — worker soft limit
  limit_memory_hard = 2684354560   # 2.5 GB — worker hard limit (killed)
  workers = 4                      # gevent+prefork workers
  max_cron_threads = 1             # cron threads

[dim]For detailed memory profiling, use kctl-pg perf connections on the DB side.[/dim]
""")


@app.command("connections")
def connections(ctx: typer.Context) -> None:
    """Show active database connection counts.

    Uses ir.config_parameter to show db_maxconn and attempts to show
    current connection info. For detailed pg_stat_activity data, use kctl-pg.

    Examples:
        kctl-odoo performance connections
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    rows: list[list[str]] = []
    json_data: list[dict] = []

    # Show db_maxconn system param
    try:
        params = c.search_read(
            "ir.config_parameter",
            domain=[("key", "in", ["db_maxconn", "db_maxconn_gevent"])],
            fields=["key", "value"],
        )
        for p in params:
            rows.append([p.get("key", ""), p.get("value", ""), "config"])
            json_data.append({"source": "config", "key": p.get("key"), "value": p.get("value")})
    except RPCError:
        pass

    # Show installed databases count as a proxy
    try:
        db_count = c.search_count("ir.module.module", [("state", "=", "installed")])
        rows.append(["installed_modules", str(db_count), "info"])
        json_data.append({"source": "info", "key": "installed_modules", "value": db_count})
    except RPCError:
        pass

    if rows:
        out.table(
            "Connection Configuration",
            [("Key", "cyan"), ("Value", ""), ("Source", "dim")],
            rows,
            data_for_json=json_data,
        )

    from rich.console import Console

    _console = Console()
    _console.print("""
[bold]For live pg_stat_activity data (actual DB connections):[/bold]
  docker compose exec db psql -U odoo -c \\
    "SELECT datname, count(*) FROM pg_stat_activity GROUP BY datname ORDER BY count DESC;"

[bold]Or use kctl-pg for full connection analysis:[/bold]
  kctl-pg perf connections
  kctl-pg perf overview

[dim]db_maxconn default: 64 per worker. Tune based on PostgreSQL max_connections.[/dim]
""")
