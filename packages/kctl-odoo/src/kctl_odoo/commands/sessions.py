"""Session management commands."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError
from kctl_odoo.core.resolve import resolve_user_id

app = typer.Typer(help="Manage user sessions and login activity.")


@app.command()
def active(
    ctx: typer.Context,
    hours: Annotated[int, typer.Option("--hours", "-h", help="Look back N hours")] = 2,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 30,
) -> None:
    """Show recent login activity."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    cutoff = (datetime.now(tz=UTC) - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

    # res.users.log records each login event
    logs = c.search_read(
        "res.users.log",
        domain=[("create_date", ">", cutoff)],
        fields=["create_uid", "create_date"],
        limit=limit,
        order="create_date desc",
    )

    if not logs:
        out.info(f"No login activity in the last {hours} hour(s).")
        if actx.json_mode:
            out.raw_json([])
        return

    # Resolve user names
    user_ids = list(
        {log["create_uid"][0] if isinstance(log["create_uid"], list) else log["create_uid"] for log in logs}
    )
    users_data = c.read("res.users", user_ids, fields=["id", "login", "name"])
    user_map = {u["id"]: u for u in users_data}

    rows = []
    json_data = []
    for log in logs:
        uid = log["create_uid"][0] if isinstance(log["create_uid"], list) else log["create_uid"]
        user = user_map.get(uid, {})
        rows.append(
            [
                str(uid),
                user.get("login", "?"),
                user.get("name", "?"),
                str(log.get("create_date", "")),
            ]
        )
        json_data.append(
            {
                "uid": uid,
                "login": user.get("login"),
                "name": user.get("name"),
                "login_time": log.get("create_date"),
            }
        )

    out.table(
        f"Recent Logins (last {hours}h, showing {len(logs)})",
        [("UID", "cyan"), ("Login", ""), ("Name", ""), ("Login Time", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command("list")
def list_(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-d", help="Look back N days")] = 7,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List user login sessions with activity summary."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    cutoff = (datetime.now(tz=UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    # Get active internal users
    users = c.search_read(
        "res.users",
        domain=[("active", "=", True), ("share", "=", False)],
        fields=["id", "login", "name", "login_date"],
        limit=limit,
        order="id desc",
    )

    if not users:
        out.info("No active users found.")
        if actx.json_mode:
            out.raw_json([])
        return

    # Batch-fetch all login logs for these users in the period (fixes N+1)
    user_ids = [u["id"] for u in users]
    logs = c.search_read(
        "res.users.log",
        domain=[("create_uid", "in", user_ids), ("create_date", ">", cutoff)],
        fields=["create_uid"],
    )
    # Client-side grouping to count logins per user
    login_counts: dict[int, int] = {}
    for log in logs:
        uid = log["create_uid"][0] if isinstance(log["create_uid"], list) else log["create_uid"]
        login_counts[uid] = login_counts.get(uid, 0) + 1

    rows = []
    json_data = []
    for u in users:
        login_count = login_counts.get(u["id"], 0)
        last_login = str(u.get("login_date") or "never")
        rows.append(
            [
                str(u["id"]),
                u["login"],
                u.get("name", ""),
                str(login_count),
                last_login,
            ]
        )
        json_data.append(
            {
                "id": u["id"],
                "login": u["login"],
                "name": u.get("name"),
                "login_count": login_count,
                "last_login": u.get("login_date"),
            }
        )

    out.table(
        f"User Sessions (last {days} days)",
        [("UID", "cyan"), ("Login", ""), ("Name", ""), ("Logins", ""), ("Last Login", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def kick(
    ctx: typer.Context,
    login: Annotated[str, typer.Argument(help="User login to invalidate sessions for, or 'all'")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Invalidate user sessions by forcing a password change token.

    This effectively logs users out by rotating their session token.
    Requires the user to log in again.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if login.lower() == "all":
        if not force and not typer.confirm("Invalidate ALL user sessions? Everyone will need to re-login."):
            raise typer.Exit(0)
        users = c.search_read(
            "res.users",
            domain=[("active", "=", True)],
            fields=["id", "login"],
        )
        if not users:
            out.info("No active users found.")
            return

        user_ids = [u["id"] for u in users]
        try:
            c.execute_kw("res.users", "action_reset_password", [user_ids])
            out.success(f"Session invalidation triggered for {len(user_ids)} user(s)")
        except RPCError:
            # Fallback: update write_date to invalidate session cookies
            c.write("res.users", user_ids, {"action_id": False})
            out.success(f"Session tokens rotated for {len(user_ids)} user(s). Users will need to re-login.")
    else:
        user_id = resolve_user_id(c, login)
        user_ids = [user_id]

        if not force and not typer.confirm(f"Invalidate sessions for user '{login}'?"):
            raise typer.Exit(0)

        try:
            c.execute_kw("res.users", "action_reset_password", [user_ids])
            out.success(f"Session invalidation triggered for user '{login}'")
        except RPCError:
            c.write("res.users", user_ids, {"action_id": False})
            out.success(f"Session token rotated for user '{login}'. User will need to re-login.")


@app.command()
def stats(ctx: typer.Context) -> None:
    """Show session statistics."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    now = datetime.now(tz=UTC)

    # Login stats for different periods
    periods = [
        ("Last hour", (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")),
        ("Last 24 hours", (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")),
        ("Last 7 days", (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")),
        ("Last 30 days", (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")),
    ]

    sections = []
    json_result: dict = {}

    # Login activity
    activity_kvs = []
    activity_json = {}
    for label, cutoff in periods:
        total = c.search_count("res.users.log", [("create_date", ">", cutoff)])
        activity_kvs.append((label, str(total)))
        activity_json[label.lower().replace(" ", "_")] = total

    sections.append(("Login Activity", activity_kvs))
    json_result["login_activity"] = activity_json

    # Unique users today
    today_str = now.strftime("%Y-%m-%d 00:00:00")
    today_logs = c.search_read(
        "res.users.log",
        domain=[("create_date", ">", today_str)],
        fields=["create_uid"],
    )
    unique_today = len(
        {log["create_uid"][0] if isinstance(log["create_uid"], list) else log["create_uid"] for log in today_logs}
    )

    # Total active internal users
    total_active = c.search_count("res.users", [("active", "=", True), ("share", "=", False)])

    user_kvs = [
        ("Unique users today", str(unique_today)),
        ("Total active internal users", str(total_active)),
    ]
    sections.append(("User Summary", user_kvs))
    json_result["unique_users_today"] = unique_today
    json_result["total_active_users"] = total_active

    # Users who never logged in
    never_logged = c.search_count("res.users", [("active", "=", True), ("login_date", "=", False)])
    inactive_30d_cutoff = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    inactive_users = c.search_count(
        "res.users",
        [("active", "=", True), ("login_date", "<", inactive_30d_cutoff)],
    )

    sections.append(
        (
            "Inactive Users",
            [
                ("Never logged in", str(never_logged)),
                ("No login in 30 days", str(inactive_users)),
            ],
        )
    )
    json_result["never_logged_in"] = never_logged
    json_result["inactive_30d"] = inactive_users

    out.detail(
        "Session Statistics",
        sections,
        data_for_json=json_result,
    )
