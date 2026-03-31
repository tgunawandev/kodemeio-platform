"""Audit / event log commands."""

from __future__ import annotations

import csv
import io
import json
import time
from collections import Counter
from datetime import UTC
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
