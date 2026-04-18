"""Log streaming and analysis commands."""

from __future__ import annotations

import re
import subprocess
from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer
from rich.console import Console

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.local import LocalClient

app = typer.Typer(help="Stream and analyze Odoo logs.")
console = Console()

# Odoo log line:  "2026-04-18 10:30:45,123 12 INFO database odoo.module.x: message"
_ODOO_LINE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}[,.]\d+)\s+"
    r"(?P<pid>\d+)\s+"
    r"(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+"
    r"(?P<db>\S+)\s+"
    r"(?P<logger>\S+):\s+"
    r"(?P<msg>.*)$"
)
_LEVEL_RANK = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}


def _get_local_client() -> LocalClient:
    try:
        return LocalClient()
    except Exception:
        console.print(
            "[red]ERROR[/red] Not inside a Docker Compose project directory.\n"
            "  The 'follow' command requires a local Docker environment."
        )
        raise typer.Exit(1) from None


@app.command()
def follow(
    level: Annotated[
        str | None, typer.Option("--level", "-l", help="Filter by log level (INFO, WARNING, ERROR)")
    ] = None,
    lines: Annotated[int, typer.Option("--lines", "-n", help="Number of initial lines to show")] = 100,
    service: Annotated[str | None, typer.Option("--service", "-s", help="Docker service name")] = None,
) -> None:
    """Stream Docker container logs in real time.

    Connects to the local Docker Compose environment and streams logs.
    Optionally filter by log level using grep-style post-processing.

    Examples:
        kctl-odoo logs follow
        kctl-odoo logs follow --level ERROR --lines 50
        kctl-odoo logs follow --service db
    """
    client = _get_local_client()

    if level:
        console.print(f"[blue]INFO[/blue] Streaming logs (level filter: {level.upper()})...")
        # Use docker compose logs with grep for level filtering
        import subprocess

        compose_cmd = client.compose_cmd() + ["logs", f"--tail={lines}", "-f"]
        if service:
            compose_cmd.append(service)
        proc = None
        try:
            proc = subprocess.Popen(
                compose_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(client.project_dir),
            )
            assert proc.stdout is not None
            level_upper = level.upper()
            for line in proc.stdout:
                if level_upper in line.upper():
                    console.print(line, end="", highlight=False)
        except KeyboardInterrupt:
            pass
        finally:
            if proc is not None and proc.poll() is None:
                proc.terminate()
    else:
        client.logs(follow=True, lines=lines, service=service)


def _cutoff_date(days: int) -> str:
    """Return an Odoo-formatted datetime string N days ago."""
    dt = datetime.now(tz=UTC) - timedelta(days=days)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _is_local_url(url: str) -> bool:
    """Treat localhost/127.0.0.1/.local as local Docker compose."""
    if not url:
        return False
    lowered = url.lower()
    return any(h in lowered for h in ("localhost", "127.0.0.1", "host.docker.internal"))


def _line_matches(
    line: str,
    *,
    module: str | None,
    request: str | None,
    worker: str | None,
    min_level: int | None,
    grep: re.Pattern[str] | None,
) -> bool:
    """Apply structured filters to an Odoo log line. Lines that don't parse are kept."""
    m = _ODOO_LINE.match(line)
    if not m:
        # Non-standard line (traceback continuation, startup banner, etc.) — keep it.
        return grep.search(line) is not None if grep else True

    if min_level is not None and _LEVEL_RANK.get(m["level"], 0) < min_level:
        return False
    if module and module not in m["logger"]:
        return False
    if worker and worker != m["pid"]:
        return False
    if request and request not in m["msg"]:
        return False
    return not (grep and not grep.search(line))


@app.command()
def tail(
    ctx: typer.Context,
    compose_id: Annotated[str | None, typer.Option("--compose-id", help="Dokploy compose ID (remote profiles)")] = None,
    dokploy_profile: Annotated[
        str | None, typer.Option("--dokploy-profile", help="kctl-dokploy profile (default: current odoo profile name)")
    ] = None,
    service: Annotated[str, typer.Option("--service", "-s", help="Compose service name")] = "odoo-web",
    lines: Annotated[int, typer.Option("--lines", "-n", help="Initial tail lines")] = 200,
    follow: Annotated[bool, typer.Option("--follow/--no-follow", "-f", help="Stream live (default)")] = True,
    level: Annotated[
        str | None, typer.Option("--level", "-l", help="Min level: DEBUG/INFO/WARNING/ERROR/CRITICAL")
    ] = None,
    module: Annotated[str | None, typer.Option("--module", help="Only lines whose logger contains this")] = None,
    request: Annotated[str | None, typer.Option("--request", help="Only lines containing this request id")] = None,
    worker: Annotated[str | None, typer.Option("--worker", help="Only lines from this worker PID")] = None,
    grep: Annotated[str | None, typer.Option("--grep", "-g", help="Regex to match anywhere in the line")] = None,
) -> None:
    """Unified log tail for local + remote Odoo with structured filters.

    Auto-detects the transport from the current kctl-odoo profile:

    - **local** (URL is localhost/127.0.0.1): streams `docker compose logs` in
      the current project directory. No extra flags needed.
    - **remote**: streams `docker logs -f` over SSH via kctl-dokploy. Requires
      ``--compose-id``; the Dokploy profile defaults to the current odoo profile
      name unless ``--dokploy-profile`` is given.

    Filters are applied client-side on the stream so they work identically in
    both modes and compose together:

    ``--level``, ``--module``, ``--request``, ``--worker``, ``--grep``.

    Examples:

        kctl-odoo logs tail                                       # local, all
        kctl-odoo logs tail --level WARNING                       # local, level≥WARNING
        kctl-odoo logs tail --module account.move --grep "draft"  # local, filtered
        kctl-odoo -p tpp-odoo-erp logs tail --compose-id Qki...   # remote tpp prod
    """
    actx: AppContext = ctx.obj
    out = actx.output

    min_level: int | None = None
    if level:
        lvl_up = level.upper()
        if lvl_up not in _LEVEL_RANK:
            out.error(f"Unknown --level '{level}'. Use DEBUG/INFO/WARNING/ERROR/CRITICAL")
            raise typer.Exit(1)
        min_level = _LEVEL_RANK[lvl_up]

    grep_re: re.Pattern[str] | None = None
    if grep:
        try:
            grep_re = re.compile(grep)
        except re.error as exc:
            out.error(f"Invalid --grep regex: {exc}")
            raise typer.Exit(1) from exc

    # Resolve transport from the odoo profile URL.
    from kctl_odoo.core.config import get_service_config, resolve_active_profile_name

    profile_name = resolve_active_profile_name(actx.profile)
    svc = get_service_config(profile_name)
    is_local = _is_local_url(svc.url)

    if is_local:
        cmd = _build_local_cmd(lines=lines, follow=follow, service=service)
        cwd: str | None = None
        try:
            client = LocalClient()
            cwd = str(client.project_dir)
        except Exception:
            out.warn("Not in a Docker Compose project dir — expected for local profile. Falling back to CWD.")
    else:
        if not compose_id:
            out.error("Remote profile requires --compose-id (find with `kctl-dokploy compose list`)")
            raise typer.Exit(1)
        dp_profile = dokploy_profile or profile_name
        cmd = _build_remote_cmd(
            dokploy_profile=dp_profile,
            compose_id=compose_id,
            service=service,
            lines=lines,
            follow=follow,
        )
        cwd = None

    out.info(f"[{profile_name}] Tailing {'local compose' if is_local else 'remote via dokploy'} — Ctrl-C to stop")
    _stream(
        cmd,
        cwd=cwd,
        module=module,
        request=request,
        worker=worker,
        min_level=min_level,
        grep=grep_re,
    )


def _build_local_cmd(*, lines: int, follow: bool, service: str) -> list[str]:
    """Build `docker compose logs` argv for local mode."""
    try:
        client = LocalClient()
        base = client.compose_cmd()
    except Exception:
        base = ["docker", "compose"]
    cmd = [*base, "logs", f"--tail={lines}"]
    if follow:
        cmd.append("-f")
    if service:
        cmd.append(service)
    return cmd


def _build_remote_cmd(*, dokploy_profile: str, compose_id: str, service: str, lines: int, follow: bool) -> list[str]:
    """Build `kctl-dokploy compose service-logs` argv that streams via SSH."""
    cmd = [
        "kctl-dokploy",
        "--profile",
        dokploy_profile,
        "compose",
        "service-logs",
        compose_id,
        "--service",
        service,
        "--tail",
        str(lines),
    ]
    if follow:
        cmd.append("-f")
    return cmd


def _stream(
    cmd: list[str],
    *,
    cwd: str | None,
    module: str | None,
    request: str | None,
    worker: str | None,
    min_level: int | None,
    grep: re.Pattern[str] | None,
) -> None:
    """Stream `cmd` stdout line-by-line, applying filters, until EOF or Ctrl-C."""
    proc: subprocess.Popen[str] | None = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=cwd,
            bufsize=1,  # line-buffered so --follow feels live
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            if _line_matches(
                line,
                module=module,
                request=request,
                worker=worker,
                min_level=min_level,
                grep=grep,
            ):
                console.print(line, end="", highlight=False)
    except KeyboardInterrupt:
        pass
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


@app.command()
def errors(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-d", help="Look back N days")] = 7,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max records to return")] = 50,
) -> None:
    """Show recent errors from ir.logging (works remotely via JSON-RPC).

    Queries the ir.logging model for error-level log entries.
    Falls back gracefully if ir.logging is not available.

    Examples:
        kctl-odoo logs errors
        kctl-odoo logs errors --days 1 --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    cutoff = _cutoff_date(days)
    domain = [
        ("level", "in", ["ERROR", "CRITICAL"]),
        ("create_date", ">=", cutoff),
    ]

    try:
        records = c.search_read(
            "ir.logging",
            domain=domain,
            fields=["id", "name", "type", "path", "message", "level", "create_date"],
            limit=limit,
            order="create_date desc",
        )
    except Exception as exc:
        out.warn(f"ir.logging not available: {exc}")
        out.info("This model may not be installed or accessible on this instance.")
        if actx.json_mode:
            out.raw_json([])
        return

    if not records:
        out.info(f"No errors found in the last {days} day(s).")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        msg = str(r.get("message", ""))[:80]
        rows.append(
            [
                str(r["id"]),
                str(r.get("create_date", ""))[:19],
                r.get("level", ""),
                r.get("type", ""),
                str(r.get("path", ""))[:40],
                msg,
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "create_date": r.get("create_date"),
                "level": r.get("level"),
                "type": r.get("type"),
                "path": r.get("path"),
                "message": r.get("message"),
            }
        )

    out.table(
        f"Errors ({len(records)}, last {days} days)",
        [
            ("ID", "cyan"),
            ("Date", "dim"),
            ("Level", "red"),
            ("Type", ""),
            ("Path", "dim"),
            ("Message", ""),
        ],
        rows,
        data_for_json=json_data,
    )


@app.command()
def search(
    ctx: typer.Context,
    pattern: Annotated[str, typer.Argument(help="Search pattern (matched against message and path)")],
    days: Annotated[int, typer.Option("--days", "-d", help="Look back N days")] = 7,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max records to return")] = 50,
) -> None:
    """Search ir.logging records matching a pattern.

    Searches both message and path fields using ilike.

    Examples:
        kctl-odoo logs search "account.move"
        kctl-odoo logs search "timeout" --days 1
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    cutoff = _cutoff_date(days)
    domain = [
        ("create_date", ">=", cutoff),
        "|",
        ("message", "ilike", pattern),
        ("path", "ilike", pattern),
    ]

    try:
        records = c.search_read(
            "ir.logging",
            domain=domain,
            fields=["id", "name", "type", "path", "level", "message", "create_date"],
            limit=limit,
            order="create_date desc",
        )
    except Exception as exc:
        out.warn(f"ir.logging not available: {exc}")
        if actx.json_mode:
            out.raw_json([])
        return

    if not records:
        out.info(f"No log entries matching '{pattern}' in the last {days} day(s).")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        msg = str(r.get("message", ""))[:80]
        rows.append(
            [
                str(r["id"]),
                str(r.get("create_date", ""))[:19],
                r.get("level", ""),
                r.get("type", ""),
                str(r.get("path", ""))[:40],
                msg,
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "create_date": r.get("create_date"),
                "level": r.get("level"),
                "type": r.get("type"),
                "path": r.get("path"),
                "message": r.get("message"),
            }
        )

    out.table(
        f"Log Search: '{pattern}' ({len(records)} matches, last {days} days)",
        [
            ("ID", "cyan"),
            ("Date", "dim"),
            ("Level", ""),
            ("Type", ""),
            ("Path", "dim"),
            ("Message", ""),
        ],
        rows,
        data_for_json=json_data,
    )
