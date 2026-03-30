"""Session management commands."""

from __future__ import annotations

from collections import Counter
from typing import Annotated

import typer

from kctl_ak.core.callbacks import AppContext
from kctl_ak.core.resolve import resolve_user

app = typer.Typer(name="sessions", help="Authenticated session management.")

_ENDPOINT = "core/authenticated_sessions/"


def _format_session_row(s: dict) -> list[str]:
    """Format a session dict into a table row."""
    user_obj = s.get("user_obj") or {}
    username = user_obj.get("username", str(s.get("user", "-")))
    last_used = str(s.get("last_used", ""))[:19].replace("T", " ")
    current = "Yes" if s.get("current") else ""
    return [
        s.get("uuid", "")[:8],
        username,
        s.get("last_ip", "-") or "-",
        last_used,
        current,
    ]


_SESSION_COLUMNS: list[tuple[str, str]] = [
    ("ID", "dim"),
    ("User", "cyan"),
    ("Last IP", ""),
    ("Last Used", "green"),
    ("Current", "yellow"),
]


@app.command("list")
def list_(
    ctx: typer.Context,
    user: Annotated[str | None, typer.Option(help="Filter by user (ID, username, or email).")] = None,
) -> None:
    """List authenticated sessions."""
    c: AppContext = ctx.obj
    params: dict = {"ordering": "-last_used"}
    if user:
        pk = resolve_user(c.client, user)
        params["user"] = pk

    sessions = c.client.get_all(_ENDPOINT, params=params)

    if not sessions:
        c.output.info("No active sessions found.")
        return

    rows = [_format_session_row(s) for s in sessions]
    c.output.table(
        f"Authenticated Sessions ({len(sessions)})",
        _SESSION_COLUMNS,
        rows,
        data_for_json=sessions,
    )


@app.command()
def get(
    ctx: typer.Context,
    session_id: Annotated[str, typer.Argument(help="Session UUID.")],
) -> None:
    """Show details for a single session."""
    c: AppContext = ctx.obj
    s = c.client.get(f"{_ENDPOINT}{session_id}/")

    user_obj = s.get("user_obj") or {}
    username = user_obj.get("username", str(s.get("user", "-")))
    email = user_obj.get("email", "-")
    last_used = str(s.get("last_used", ""))[:19].replace("T", " ")
    geo = s.get("geo_ip") or {}
    geo_str = f"{geo.get('city', '')}, {geo.get('country', '')}" if geo else "-"

    c.output.detail(
        f"Session {s.get('uuid', session_id)[:12]}",
        [
            (
                "Session",
                [
                    ("UUID", s.get("uuid", "")),
                    ("Current", "Yes" if s.get("current") else "No"),
                    ("Last Used", last_used),
                    ("Last IP", s.get("last_ip", "-") or "-"),
                    ("GeoIP", geo_str),
                ],
            ),
            (
                "User",
                [
                    ("Username", username),
                    ("Email", email),
                    ("User PK", str(s.get("user", ""))),
                ],
            ),
            (
                "Client",
                [
                    ("User Agent", s.get("last_user_agent", "-") or "-"),
                ],
            ),
        ],
        data_for_json=s,
    )


@app.command()
def kill(
    ctx: typer.Context,
    session_id: Annotated[str, typer.Argument(help="Session UUID to terminate.")],
) -> None:
    """Terminate a single session."""
    c: AppContext = ctx.obj
    c.client.delete(f"{_ENDPOINT}{session_id}/")
    c.output.success(f"Session {session_id[:12]} terminated.")


@app.command("kill-user")
def kill_user(
    ctx: typer.Context,
    user: Annotated[str, typer.Argument(help="User identifier (ID, username, or email).")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation.")] = False,
) -> None:
    """Terminate all sessions for a user."""
    c: AppContext = ctx.obj
    pk = resolve_user(c.client, user)
    sessions = c.client.get_all(_ENDPOINT, params={"user": pk})

    if not sessions:
        c.output.info(f"No active sessions for user {user}.")
        return

    if not force:
        confirm = typer.confirm(f"Kill {len(sessions)} session(s) for user {user}?")
        if not confirm:
            c.output.info("Aborted.")
            return

    killed = 0
    for s in sessions:
        uuid = s.get("uuid", "")
        if uuid:
            c.client.delete(f"{_ENDPOINT}{uuid}/")
            killed += 1

    c.output.success(f"Terminated {killed} session(s) for user {user}.")


@app.command()
def stats(ctx: typer.Context) -> None:
    """Show session statistics aggregated by user."""
    c: AppContext = ctx.obj
    sessions = c.client.get_all(_ENDPOINT)

    if not sessions:
        c.output.info("No active sessions.")
        return

    counter: Counter[str] = Counter()
    for s in sessions:
        user_obj = s.get("user_obj") or {}
        username = user_obj.get("username", str(s.get("user", "unknown")))
        counter[username] += 1

    rows = [[username, str(count)] for username, count in counter.most_common()]
    stats_json = [{"user": u, "sessions": ct} for u, ct in counter.most_common()]

    c.output.table(
        f"Session Stats ({len(sessions)} total)",
        [("User", "cyan"), ("Sessions", "yellow")],
        rows,
        data_for_json=stats_json,
    )


@app.command()
def active(ctx: typer.Context) -> None:
    """List currently active sessions (most recent first)."""
    c: AppContext = ctx.obj
    sessions = c.client.get_all(_ENDPOINT, params={"ordering": "-last_used"})

    if not sessions:
        c.output.info("No active sessions.")
        return

    # Deduplicate by user, keeping most recent session per user
    seen_users: set[int] = set()
    unique: list[dict] = []
    for s in sessions:
        uid = s.get("user", 0)
        if uid not in seen_users:
            seen_users.add(uid)
            unique.append(s)

    rows = [_format_session_row(s) for s in unique]
    c.output.table(
        f"Active Users ({len(unique)} users, {len(sessions)} sessions)",
        _SESSION_COLUMNS,
        rows,
        data_for_json=unique,
    )
