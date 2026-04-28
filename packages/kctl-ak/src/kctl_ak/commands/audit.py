"""Audit / event log commands."""

from __future__ import annotations

import csv
import io
import json
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from kctl_ak.core.callbacks import AppContext
from kctl_ak.core.resolve import resolve_user

app = typer.Typer(name="audit", help="Event and audit log management.")

_ENDPOINT = "events/events/"


def _format_event_row(ev: dict) -> list[str]:
    """Format a single event dict into a table row."""
    user = ev.get("user") or {}
    username = user.get("username", "-") if isinstance(user, dict) else "-"
    created = str(ev.get("created", ""))[:19].replace("T", " ")
    return [
        ev.get("pk", "")[:8],
        ev.get("action", ""),
        username,
        ev.get("client_ip", "-") or "-",
        ev.get("app", "-") or "-",
        created,
    ]


_EVENT_COLUMNS: list[tuple[str, str]] = [
    ("ID", "dim"),
    ("Action", "yellow"),
    ("User", "cyan"),
    ("Client IP", ""),
    ("App", ""),
    ("Created", "green"),
]


@app.command("list")
def list_(
    ctx: typer.Context,
    page: Annotated[int, typer.Option(help="Page number.")] = 1,
    action: Annotated[str | None, typer.Option(help="Filter by action type.")] = None,
    user: Annotated[str | None, typer.Option(help="Filter by user (ID, username, or email).")] = None,
    client_ip: Annotated[str | None, typer.Option("--client-ip", help="Filter by client IP.")] = None,
) -> None:
    """List audit events."""
    c: AppContext = ctx.obj
    params: dict = {"ordering": "-created", "page": page, "page_size": 20}
    if action:
        params["action"] = action
    if user:
        pk = resolve_user(c.client, user)
        params["user"] = pk
    if client_ip:
        params["client_ip"] = client_ip

    data = c.client.get(_ENDPOINT, params=params)
    results = data.get("results", [])
    pagination = data.get("pagination", {})

    if not results:
        c.output.info("No events found.")
        return

    rows = [_format_event_row(ev) for ev in results]
    c.output.table(
        f"Audit Events (page {page}, {pagination.get('count', len(results))} total)",
        _EVENT_COLUMNS,
        rows,
        data_for_json=results,
    )


@app.command()
def logins(
    ctx: typer.Context,
    failed: Annotated[bool, typer.Option("--failed", help="Show only failed logins.")] = False,
) -> None:
    """List login events."""
    c: AppContext = ctx.obj
    action = "login_failed" if failed else "login"
    params: dict = {"ordering": "-created", "action": action, "page_size": 20}

    data = c.client.get(_ENDPOINT, params=params)
    results = data.get("results", [])

    if not results:
        label = "failed logins" if failed else "logins"
        c.output.info(f"No {label} found.")
        return

    rows = [_format_event_row(ev) for ev in results]
    title = "Failed Logins" if failed else "Login Events"
    c.output.table(title, _EVENT_COLUMNS, rows, data_for_json=results)


@app.command()
def changes(
    ctx: typer.Context,
    model: Annotated[str | None, typer.Option(help="Filter by model type (e.g. user, group, application).")] = None,
) -> None:
    """List model change events."""
    c: AppContext = ctx.obj
    params: dict = {"ordering": "-created", "action": "model_updated", "page_size": 20}
    if model:
        params["context__model__app"] = model

    # Also include model_created and model_deleted
    all_results: list[dict] = []
    for act in ("model_created", "model_updated", "model_deleted"):
        p = {**params, "action": act}
        data = c.client.get(_ENDPOINT, params=p)
        all_results.extend(data.get("results", []))

    # Sort by created descending
    all_results.sort(key=lambda e: e.get("created", ""), reverse=True)
    all_results = all_results[:40]

    if not all_results:
        c.output.info("No change events found.")
        return

    rows = [_format_event_row(ev) for ev in all_results]
    c.output.table("Model Change Events", _EVENT_COLUMNS, rows, data_for_json=all_results)


@app.command()
def get(
    ctx: typer.Context,
    event_id: Annotated[str, typer.Argument(help="Event UUID.")],
) -> None:
    """Show details for a single event."""
    c: AppContext = ctx.obj
    ev = c.client.get(f"{_ENDPOINT}{event_id}/")

    user = ev.get("user") or {}
    username = user.get("username", "-") if isinstance(user, dict) else "-"
    email = user.get("email", "-") if isinstance(user, dict) else "-"
    created = str(ev.get("created", ""))[:19].replace("T", " ")
    expires = str(ev.get("expires", ""))[:19].replace("T", " ")
    context_str = json.dumps(ev.get("context", {}), indent=2, default=str)

    c.output.detail(
        f"Event {ev.get('pk', event_id)[:12]}",
        [
            (
                "Event",
                [
                    ("ID", ev.get("pk", "")),
                    ("Action", ev.get("action", "")),
                    ("App", ev.get("app", "-") or "-"),
                    ("Created", created),
                    ("Expires", expires),
                ],
            ),
            (
                "User",
                [
                    ("Username", username),
                    ("Email", email),
                    ("Client IP", ev.get("client_ip", "-") or "-"),
                ],
            ),
            (
                "Context",
                [("Data", context_str)],
            ),
        ],
        data_for_json=ev,
    )


@app.command()
def stats(
    ctx: typer.Context,
    days: Annotated[int, typer.Option(help="Number of recent days to analyze.")] = 7,
) -> None:
    """Show event statistics aggregated by action type."""
    c: AppContext = ctx.obj
    c.output.header("Event Statistics")

    # Fetch recent events (up to 1000)
    from datetime import datetime, timedelta

    since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    events = c.client.get_all(_ENDPOINT, params={"ordering": "-created", "created__gte": since})

    if not events:
        c.output.info(f"No events in the last {days} days.")
        return

    counter: Counter[str] = Counter()
    for ev in events:
        counter[ev.get("action", "unknown")] += 1

    rows = [[action, str(count)] for action, count in counter.most_common()]
    stats_json = [{"action": a, "count": ct} for a, ct in counter.most_common()]

    c.output.table(
        f"Event Stats (last {days} days, {len(events)} total)",
        [("Action", "yellow"), ("Count", "cyan")],
        rows,
        data_for_json=stats_json,
    )


@app.command()
def export(
    ctx: typer.Context,
    days: Annotated[int, typer.Option(help="Number of days to export.")] = 30,
    format: Annotated[str, typer.Option(help="Output format: json or csv.")] = "json",
) -> None:
    """Export audit events to JSON or CSV."""
    c: AppContext = ctx.obj
    from datetime import datetime, timedelta

    since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    c.output.info(f"Fetching events from last {days} days...")

    events = c.client.get_all(_ENDPOINT, params={"ordering": "-created", "created__gte": since})

    if not events:
        c.output.info("No events to export.")
        return

    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["pk", "action", "user", "client_ip", "app", "created", "context"])
        for ev in events:
            user = ev.get("user") or {}
            username = user.get("username", "") if isinstance(user, dict) else ""
            writer.writerow(
                [
                    ev.get("pk", ""),
                    ev.get("action", ""),
                    username,
                    ev.get("client_ip", ""),
                    ev.get("app", ""),
                    ev.get("created", ""),
                    json.dumps(ev.get("context", {}), default=str),
                ]
            )
        print(buf.getvalue())
    else:
        c.output.raw_json(events)

    c.output.success(f"Exported {len(events)} events.")


@app.command()
def tail(
    ctx: typer.Context,
    interval: Annotated[int, typer.Option(help="Poll interval in seconds.")] = 5,
) -> None:
    """Tail new audit events (polls the API)."""
    c: AppContext = ctx.obj
    c.output.info(f"Tailing events every {interval}s (Ctrl+C to stop)...")

    last_seen_pk: str | None = None

    # Seed with the latest event
    data = c.client.get(_ENDPOINT, params={"ordering": "-created", "page_size": 1})
    results = data.get("results", [])
    if results:
        last_seen_pk = results[0].get("pk")

    try:
        while True:
            time.sleep(interval)
            data = c.client.get(_ENDPOINT, params={"ordering": "-created", "page_size": 20})
            results = data.get("results", [])

            new_events: list[dict] = []
            for ev in results:
                if ev.get("pk") == last_seen_pk:
                    break
                new_events.append(ev)

            if new_events:
                last_seen_pk = new_events[0].get("pk")
                for ev in reversed(new_events):
                    row = _format_event_row(ev)
                    c.output.info(f"{row[5]}  {row[1]:<20}  {row[2]:<16}  {row[3]}")
    except KeyboardInterrupt:
        c.output.info("Stopped.")


@app.command()
def suspicious(
    ctx: typer.Context,
    days: Annotated[int, typer.Option(help="Number of recent days to analyze.")] = 7,
) -> None:
    """Show suspicious events (failed logins, privilege changes, impersonation)."""
    c: AppContext = ctx.obj
    from datetime import datetime, timedelta

    since = (datetime.now(UTC) - timedelta(days=days)).isoformat()

    suspicious_actions = [
        "login_failed",
        "impersonation_started",
        "impersonation_ended",
        "model_updated",
        "model_deleted",
        "authorize_application",
        "secret_view",
        "password_set",
    ]

    all_results: list[dict] = []
    for action in suspicious_actions:
        try:
            data = c.client.get(
                _ENDPOINT,
                params={"ordering": "-created", "action": action, "page_size": 20, "created__gte": since},
            )
            all_results.extend(data.get("results", []))
        except Exception:
            pass

    all_results.sort(key=lambda e: e.get("created", ""), reverse=True)

    if not all_results:
        c.output.success(f"No suspicious events in the last {days} days")
        return

    rows = [_format_event_row(ev) for ev in all_results[:50]]
    c.output.table(
        f"Suspicious Events (last {days} days, {len(all_results)} found)",
        _EVENT_COLUMNS,
        rows,
        data_for_json=all_results[:50],
    )


def _delete_events(c: AppContext, events: list[dict], label: str) -> None:
    """Delete a list of events by UUID via the API."""
    if not events:
        c.output.info(f"No {label} events found.")
        return

    c.output.info(f"Deleting {len(events)} {label} events...")
    deleted = 0
    errors = 0
    for ev in events:
        pk = ev.get("pk", "")
        try:
            c.client.delete(f"{_ENDPOINT}{pk}/")
            deleted += 1
        except Exception:
            errors += 1

    if errors:
        c.output.warn(f"Deleted {deleted}, failed {errors}")
    else:
        c.output.success(f"Deleted {deleted} {label} events")


@app.command()
def delete(
    ctx: typer.Context,
    event_id: Annotated[str | None, typer.Argument(help="Event UUID to delete (omit to use filters).")] = None,
    action: Annotated[str | None, typer.Option(help="Delete all events with this action type.")] = None,
    user: Annotated[str | None, typer.Option(help="Delete events by user (ID, username, or email).")] = None,
    days: Annotated[int | None, typer.Option(help="Only delete events from the last N days.")] = None,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation.")] = False,
) -> None:
    """Delete audit events by ID, action type, or user.

    Examples:
      kctl-ak audit delete <event-uuid>
      kctl-ak audit delete --action impersonation_started
      kctl-ak audit delete --action impersonation_started --action impersonation_ended
      kctl-ak audit delete --user tgunawan --action authorize_application --days 7
    """
    c: AppContext = ctx.obj

    if event_id:
        c.client.delete(f"{_ENDPOINT}{event_id}/")
        c.output.success(f"Deleted event {event_id}")
        return

    if not action and not user:
        c.output.error("Provide an event ID or at least --action or --user filter.")
        raise typer.Exit(1)

    params: dict = {"ordering": "-created", "page_size": 100}
    if action:
        params["action"] = action
    if user:
        pk = resolve_user(c.client, user)
        params["user"] = pk
    if days:
        from datetime import datetime, timedelta

        since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        params["created__gte"] = since

    events = c.client.get_all(_ENDPOINT, params=params)

    if not events:
        c.output.info("No matching events found.")
        return

    if not force:
        c.output.warn(f"About to delete {len(events)} events (action={action}, user={user})")
        if not typer.confirm("Continue?"):
            c.output.info("Cancelled.")
            raise typer.Exit(0)

    _delete_events(c, events, action or "filtered")


@app.command("delete-impersonation")
def delete_impersonation(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation.")] = False,
) -> None:
    """Delete all impersonation-related events.

    Removes impersonation_started, impersonation_ended, and any events
    performed on behalf of another user (authorize_application, login, etc.).

    Examples:
      kctl-ak audit delete-impersonation
      kctl-ak audit delete-impersonation --force
    """
    c: AppContext = ctx.obj

    # 1. Collect impersonation_started and impersonation_ended events
    imp_events: list[dict] = []
    for act in ("impersonation_started", "impersonation_ended"):
        imp_events.extend(c.client.get_all(_ENDPOINT, params={"action": act, "page_size": 100}))

    # 2. Collect events with on_behalf_of in the user field
    #    These are actions performed while impersonating — the API returns them with
    #    user.on_behalf_of populated. We need to fetch all events and filter.
    obo_events: list[dict] = []
    all_events = c.client.get_all(_ENDPOINT, params={"ordering": "-created", "page_size": 100})
    for ev in all_events:
        user_data = ev.get("user") or {}
        if isinstance(user_data, dict) and user_data.get("on_behalf_of"):
            obo_events.append(ev)

    # Deduplicate by pk
    seen: set[str] = set()
    combined: list[dict] = []
    for ev in imp_events + obo_events:
        pk = ev.get("pk", "")
        if pk not in seen:
            seen.add(pk)
            combined.append(ev)

    if not combined:
        c.output.success("No impersonation events found.")
        return

    imp_count = len(imp_events)
    obo_count = len(obo_events)
    c.output.info(
        f"Found {len(combined)} events: {imp_count} impersonation start/end + {obo_count} on-behalf-of actions"
    )

    if not force:
        if not typer.confirm(f"Delete all {len(combined)} impersonation-related events?"):
            c.output.info("Cancelled.")
            raise typer.Exit(0)

    _delete_events(c, combined, "impersonation")


@app.command("access-report")
def access_report(
    ctx: typer.Context,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Output file (format from extension: .xlsx, .md).")
    ] = None,
    format: Annotated[str, typer.Option("--format", "-f", help="Output format: md, xlsx, json.")] = "md",
    active_only: Annotated[bool, typer.Option("--active-only", help="Only active human users.")] = False,
    include_service_accounts: Annotated[
        bool, typer.Option("--include-service-accounts", help="Include service accounts.")
    ] = False,
    include_deactivated: Annotated[
        bool, typer.Option("--include-deactivated", help="Include deactivated users.")
    ] = False,
    app_slug: Annotated[str | None, typer.Option("--app", help="Filter to a specific app slug.")] = None,
    summary: Annotated[
        bool, typer.Option("--summary", help="One row per user with groups and apps aggregated.")
    ] = False,
) -> None:
    """Generate a user x application access control report."""
    from kctl_ak.reports.access_control import (
        ReportFilters,
        ReportMeta,
        build_app_binding_rows,
        build_rows,
        build_summary_rows,
        fetch_report_data,
        to_json,
        write_markdown,
        write_summary_markdown,
        write_summary_xlsx,
        write_xlsx,
    )

    c: AppContext = ctx.obj

    filters = ReportFilters(
        active_only=active_only,
        include_service_accounts=include_service_accounts,
        include_deactivated=include_deactivated,
        app_slug=app_slug,
    )

    c.output.info("Fetching users, applications, and policy bindings...")
    data = fetch_report_data(c.client, filters)

    if output:
        ext = output.suffix.lower()
        if ext == ".xlsx":
            fmt = "xlsx"
        elif ext == ".md":
            fmt = "md"
        elif ext == ".json":
            fmt = "json"
        else:
            fmt = format
    else:
        fmt = format

    if summary:
        urows = build_summary_rows(data, filters)
        arows = build_app_binding_rows(data)
        meta = ReportMeta(
            profile=c.profile or "default",
            generated_at=datetime.now(UTC).isoformat(),
            user_count=len(urows),
            app_count=len(arows),
            row_count=len(urows),
        )
        if fmt == "xlsx":
            if output is None:
                c.output.error("Excel format requires --output file path.")
                raise typer.Exit(1)
            write_summary_xlsx(urows, arows, meta, output)
            c.output.success(f"Summary Excel written to {output} ({len(urows)} users, {len(arows)} apps)")
        elif fmt == "json":
            payload = {
                "meta": meta.model_dump(),
                "users": [r.model_dump() for r in urows],
                "apps": [a.model_dump() for a in arows],
            }
            if output:
                with open(output, "w") as f:
                    json.dump(payload, f, indent=2)
                c.output.success(f"Summary JSON written to {output} ({len(urows)} users, {len(arows)} apps)")
            else:
                c.output.raw_json(payload)
        else:
            if output:
                with open(output, "w") as f:
                    write_summary_markdown(urows, arows, meta, f)
                c.output.success(f"Summary Markdown written to {output} ({len(urows)} users, {len(arows)} apps)")
            else:
                write_summary_markdown(urows, arows, meta, sys.stdout)
        return

    rows = build_rows(data, filters)
    meta = ReportMeta(
        profile=c.profile or "default",
        generated_at=datetime.now(UTC).isoformat(),
        user_count=len({r.username for r in rows}),
        app_count=len({r.app_slug for r in rows}),
        row_count=len(rows),
    )

    if fmt == "xlsx":
        if output is None:
            c.output.error("Excel format requires --output file path.")
            raise typer.Exit(1)
        write_xlsx(rows, meta, output)
        c.output.success(f"Excel report written to {output} ({meta.row_count} rows)")
    elif fmt == "json":
        if output:
            with open(output, "w") as f:
                json.dump(to_json(rows, meta), f, indent=2)
            c.output.success(f"JSON report written to {output} ({meta.row_count} rows)")
        else:
            c.output.raw_json(to_json(rows, meta))
    else:
        if output:
            with open(output, "w") as f:
                write_markdown(rows, meta, f)
            c.output.success(f"Markdown report written to {output} ({meta.row_count} rows)")
        else:
            write_markdown(rows, meta, sys.stdout)
