"""User management commands."""

from __future__ import annotations

import csv
import json
import secrets
import sys
from pathlib import Path
from typing import Annotated

import typer

from kctl_ak.core.callbacks import AppContext
from kctl_ak.core.resolve import resolve_user
from kctl_ak.roles.loader import RoleLoader
from kctl_ak.roles.provisioner import Provisioner

app = typer.Typer(help="User management and provisioning.")


@app.command("list")
def list_(
    ctx: typer.Context,
    page: Annotated[int, typer.Option(help="Page number")] = 1,
    page_size: Annotated[int, typer.Option(help="Results per page")] = 20,
    active: Annotated[bool, typer.Option("--active", help="Show only active users")] = False,
    inactive: Annotated[bool, typer.Option("--inactive", help="Show only inactive users")] = False,
) -> None:
    """List all users."""
    c: AppContext = ctx.obj
    params: dict = {"page": page, "page_size": page_size}
    if active:
        params["is_active"] = True
    elif inactive:
        params["is_active"] = False

    data = c.client.get("core/users/", params=params)
    users = data.get("results", [])
    pagination = data.get("pagination", {})

    rows = [
        [
            str(u["pk"]),
            u.get("username", ""),
            u.get("email", ""),
            u.get("name", ""),
            "yes" if u.get("is_active") else "no",
            "yes" if u.get("is_superuser") else "no",
        ]
        for u in users
    ]

    c.output.table(
        f"Users (page {pagination.get('current', page)}/{pagination.get('total_pages', 1)})",
        [("ID", "cyan"), ("Username", "green"), ("Email", ""), ("Name", ""), ("Active", ""), ("Super", "dim")],
        rows,
        data_for_json=users,
    )


@app.command()
def get(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="User ID, username, or email")],
) -> None:
    """Get detailed user info."""
    c: AppContext = ctx.obj
    pk = resolve_user(c.client, identifier)
    user = c.client.get(f"core/users/{pk}/")

    groups = [g["name"] for g in user.get("groups_obj", [])]

    c.output.detail(
        f"User: {user.get('username', '')}",
        [
            (
                "Identity",
                [
                    ("ID", str(user["pk"])),
                    ("Username", user.get("username", "")),
                    ("Email", user.get("email", "")),
                    ("Name", user.get("name", "")),
                    ("UID", user.get("uid", "")),
                ],
            ),
            (
                "Status",
                [
                    ("Active", str(user.get("is_active", False))),
                    ("Superuser", str(user.get("is_superuser", False))),
                    ("Type", user.get("type", "internal")),
                    ("Last Login", str(user.get("last_login", "never"))),
                ],
            ),
            (
                "Groups",
                [
                    ("Member of", ", ".join(groups) if groups else "(none)"),
                ],
            ),
        ],
        data_for_json=user,
    )


@app.command()
def search(
    ctx: typer.Context,
    term: Annotated[str, typer.Argument(help="Search term")],
) -> None:
    """Search users by name, username, or email."""
    c: AppContext = ctx.obj
    data = c.client.get("core/users/", params={"search": term})
    users = data.get("results", [])

    rows = [[str(u["pk"]), u.get("username", ""), u.get("email", ""), u.get("name", "")] for u in users]

    c.output.table(
        f"Search results for '{term}'",
        [("ID", "cyan"), ("Username", "green"), ("Email", ""), ("Name", "")],
        rows,
        data_for_json=users,
    )


@app.command()
def create(
    ctx: typer.Context,
    email: Annotated[str, typer.Argument(help="User email address")],
    name: Annotated[str | None, typer.Option(help="Display name")] = None,
    username: Annotated[str | None, typer.Option(help="Username (default: email prefix)")] = None,
    password: Annotated[str | None, typer.Option(help="Password (auto-generated if omitted)")] = None,
    groups: Annotated[str | None, typer.Option(help="Comma-separated group names")] = None,
    superuser: Annotated[bool, typer.Option("--superuser", help="Grant superuser")] = False,
) -> None:
    """Create a new user."""
    c: AppContext = ctx.obj
    username = username or email.split("@")[0]
    name = name or username
    generated_password = password or secrets.token_urlsafe(16)

    user_data = {
        "username": username,
        "email": email,
        "name": name,
        "is_active": True,
        "is_superuser": superuser,
    }
    user = c.client.post("core/users/", data=user_data)
    pk = user["pk"]

    c.client.post(f"core/users/{pk}/set_password/", data={"password": generated_password})

    group_names_added: list[str] = []
    from kctl_ak.core.resolve import resolve_group

    # Authentik ignores is_superuser on the API — superuser is granted via group membership.
    # Auto-add to the first group with is_superuser=True (typically "ak-admin-super").
    if superuser:
        try:
            all_groups = c.client.get_all("core/groups/", params={"page_size": 100})
            su_group = next((g for g in all_groups if g.get("is_superuser")), None)
            if su_group:
                gid = su_group["pk"]
                c.client.post(f"core/groups/{gid}/add_user/", data={"pk": pk})
                group_names_added.append(su_group["name"])
            else:
                c.output.warn("No superuser group found — user created without superuser privileges")
        except Exception:
            c.output.warn("Failed to add user to superuser group")

    if groups:
        for gname in groups.split(","):
            gname = gname.strip()
            if not gname:
                continue
            try:
                gid = resolve_group(c.client, gname)
                c.client.post(f"core/groups/{gid}/add_user/", data={"pk": pk})
                group_names_added.append(gname)
            except Exception:
                c.output.warn(f"Could not add to group: {gname}")

    c.output.detail(
        "User Created",
        [
            (
                "Details",
                [
                    ("ID", str(pk)),
                    ("Username", username),
                    ("Email", email),
                    ("Name", name),
                    ("Password", generated_password if not password else "(provided)"),
                    ("Groups", ", ".join(group_names_added) if group_names_added else "(none)"),
                ],
            ),
        ],
        data_for_json={
            "pk": pk,
            "username": username,
            "email": email,
            "name": name,
            "password": generated_password if not password else None,
            "groups_added": group_names_added,
        },
    )


@app.command()
def update(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="User ID, username, or email")],
    field: Annotated[str, typer.Argument(help="Field to update (username, email, name, is_active, is_superuser)")],
    value: Annotated[str, typer.Argument(help="New value")],
) -> None:
    """Update a user field."""
    c: AppContext = ctx.obj
    pk = resolve_user(c.client, identifier)

    bool_fields = {"is_active", "is_superuser"}
    update_value: str | bool = value
    if field in bool_fields:
        update_value = value.lower() in ("true", "1", "yes")

    c.client.patch(f"core/users/{pk}/", data={field: update_value})
    c.output.success(f"User {pk}: {field} = {value}")


@app.command()
def password(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="User ID, username, or email")],
    new_password: Annotated[str | None, typer.Argument(help="New password (auto-generated if omitted)")] = None,
) -> None:
    """Set a user's password."""
    c: AppContext = ctx.obj
    pk = resolve_user(c.client, identifier)
    pw = new_password or secrets.token_urlsafe(16)

    c.client.post(f"core/users/{pk}/set_password/", data={"password": pw})

    if new_password:
        c.output.success(f"Password updated for user {pk}")
    else:
        c.output.success(f"Password updated for user {pk}: {pw}")


@app.command()
def recovery(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="User ID, username, or email")],
) -> None:
    """Generate a recovery link for a user."""
    c: AppContext = ctx.obj
    pk = resolve_user(c.client, identifier)
    result = c.client.post(f"core/users/{pk}/recovery/", data={})
    link = result.get("link", "")

    if c.output.json_mode:
        c.output.raw_json({"user_id": pk, "link": link})
    else:
        c.output.success(f"Recovery link for user {pk}:")
        c.output.text(f"  {link}")


@app.command()
def activate(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="User ID, username, or email")],
) -> None:
    """Activate a user."""
    c: AppContext = ctx.obj
    pk = resolve_user(c.client, identifier)
    c.client.patch(f"core/users/{pk}/", data={"is_active": True})
    c.output.success(f"User {pk} activated")


@app.command()
def deactivate(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="User ID, username, or email")],
) -> None:
    """Deactivate a user."""
    c: AppContext = ctx.obj
    pk = resolve_user(c.client, identifier)
    c.client.patch(f"core/users/{pk}/", data={"is_active": False})
    c.output.success(f"User {pk} deactivated")


@app.command()
def delete(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="User ID, username, or email")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a user."""
    c: AppContext = ctx.obj
    pk = resolve_user(c.client, identifier)

    if not force:
        user = c.client.get(f"core/users/{pk}/")
        confirm = typer.confirm(f"Delete user {user.get('username', pk)}?")
        if not confirm:
            raise typer.Abort()

    c.client.delete(f"core/users/{pk}/")
    c.output.success(f"User {pk} deleted")


@app.command("groups")
def user_groups(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="User ID, username, or email")],
) -> None:
    """List groups for a user."""
    c: AppContext = ctx.obj
    pk = resolve_user(c.client, identifier)
    user = c.client.get(f"core/users/{pk}/")
    groups = user.get("groups_obj", [])

    rows = [[g.get("pk", ""), g.get("name", ""), "yes" if g.get("is_superuser") else "no"] for g in groups]

    c.output.table(
        f"Groups for {user.get('username', pk)}",
        [("ID", "dim"), ("Name", "green"), ("Superuser", "")],
        rows,
        data_for_json=groups,
    )


@app.command()
def invite(
    ctx: typer.Context,
    email: Annotated[str, typer.Argument(help="User email address")],
    name: Annotated[str | None, typer.Option(help="Display name")] = None,
    groups: Annotated[str | None, typer.Option(help="Comma-separated group names")] = None,
    send_mail: Annotated[bool, typer.Option("--send-mail", help="Send welcome email")] = False,
) -> None:
    """Invite a user. Creates if new, re-sends welcome email if existing.

    Smart invite: if the user already exists, skips creation and
    re-sends the welcome email (re-invitation).
    """
    c: AppContext = ctx.obj
    username = email.split("@")[0]
    display_name = name or username
    operation = "created"

    # Check if user already exists
    existing = c.client.get("core/users/", params={"email": email})
    existing_users = existing.get("results", [])

    if existing_users:
        # Re-invite existing user
        pk = existing_users[0]["pk"]
        operation = "re-invited"
        display_name = existing_users[0].get("name", display_name)
        username = existing_users[0].get("username", username)
        c.output.info(f"User already exists (ID: {pk}), re-inviting...")
    else:
        # Create new user
        pw = secrets.token_urlsafe(16)
        user = c.client.post(
            "core/users/",
            data={
                "username": username,
                "email": email,
                "name": display_name,
                "is_active": True,
            },
        )
        pk = user["pk"]
        c.client.post(f"core/users/{pk}/set_password/", data={"password": pw})
        c.output.success(f"User created: {username} (ID: {pk})")

    # Add to groups (for both new and existing)
    group_names_added: list[str] = []
    if groups:
        from kctl_ak.core.resolve import resolve_group

        for gname in groups.split(","):
            gname = gname.strip()
            if not gname:
                continue
            try:
                gid = resolve_group(c.client, gname)
                c.client.post(f"core/groups/{gid}/add_user/", data={"pk": pk})
                group_names_added.append(gname)
            except Exception:
                pass

    # Generate recovery link
    recovery_link = ""
    try:
        result = c.client.post(f"core/users/{pk}/recovery/", data={})
        recovery_link = result.get("link", "")
    except Exception:
        recovery_link = "(recovery flow not configured)"

    # Send welcome email
    email_sent = False
    if send_mail:
        from kctl_ak.commands.mail import ensure_welcome_stage

        try:
            stage = ensure_welcome_stage(c.client, c.output)
            c.client.post(
                f"core/users/{pk}/recovery_email/",
                data={
                    "email": email,
                    "email_stage": stage,
                },
            )
            email_sent = True
            c.output.success(f"Welcome email sent to {email}")
        except Exception as e:
            c.output.warn(f"Failed to send email: {e}")

    c.output.detail(
        f"User {'Re-invited' if operation == 're-invited' else 'Invited'}",
        [
            (
                "Details",
                [
                    ("Operation", operation),
                    ("ID", str(pk)),
                    ("Username", username),
                    ("Email", email),
                    ("Name", display_name),
                    ("Groups Added", ", ".join(group_names_added) if group_names_added else "(none)"),
                ],
            ),
            (
                "Onboarding",
                [
                    ("Recovery Link", recovery_link),
                    ("Email Sent", "yes" if email_sent else "no"),
                ],
            ),
        ],
        data_for_json={
            "operation": operation,
            "pk": pk,
            "username": username,
            "email": email,
            "recovery_link": recovery_link,
            "groups_added": group_names_added,
            "email_sent": email_sent,
        },
    )


@app.command("re-invite")
def re_invite(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="User ID, username, or email")],
) -> None:
    """Re-send welcome email to an existing user.

    Useful when the original invitation expired or was lost.
    Sends a new welcome email with a fresh 72-hour link.
    """
    c: AppContext = ctx.obj
    pk = resolve_user(c.client, identifier)
    user = c.client.get(f"core/users/{pk}/")
    email = user.get("email", "")
    name = user.get("name", "") or user.get("username", "")

    if not email:
        c.output.error(f"User {pk} has no email address")
        raise typer.Exit(1)

    from kctl_ak.commands.mail import ensure_welcome_stage

    stage = ensure_welcome_stage(c.client, c.output)

    c.output.info(f"Re-sending welcome email to {email}...")
    try:
        c.client.post(
            f"core/users/{pk}/recovery_email/",
            data={
                "email": email,
                "email_stage": stage,
            },
        )
        c.output.success(f"Welcome email re-sent to {email}")
        c.output.info(f"User: {name} (ID: {pk})")
        c.output.info("New link expires in 72 hours")
    except Exception as e:
        c.output.error(f"Failed: {e}")
        raise typer.Exit(1) from e


@app.command()
def pending(ctx: typer.Context) -> None:
    """List users who have never logged in (invited but not activated).

    Shows users with last_login = null, excluding service accounts.
    """
    c: AppContext = ctx.obj
    all_users = c.client.get_all("core/users/", params={"is_active": True})

    pending_users = [
        u
        for u in all_users
        if u.get("last_login") is None
        and u.get("type", "internal") not in ("internal_service_account", "service_account")
        and not u.get("username", "").startswith("ak-outpost-")
    ]

    if not pending_users:
        c.output.success("No pending invitations. All users have logged in.")
        return

    rows = [
        [
            str(u["pk"]),
            u.get("username", ""),
            u.get("email", ""),
            u.get("name", ""),
        ]
        for u in pending_users
    ]

    c.output.table(
        f"Pending Invitations ({len(pending_users)} users never logged in)",
        [("ID", "cyan"), ("Username", "green"), ("Email", ""), ("Name", "")],
        rows,
        data_for_json=pending_users,
    )


@app.command("bulk-invite")
def bulk_invite(
    ctx: typer.Context,
    file: Annotated[Path, typer.Argument(help="JSON file with user list")],
    send_mail: Annotated[bool, typer.Option("--send-mail", help="Send welcome email to each user")] = False,
) -> None:
    """Bulk invite users from a JSON file.

    Creates new users or re-invites existing ones. Optionally sends
    welcome emails to all.

    File format: [{"email": "...", "name": "...", "groups": "g1,g2"}, ...]
    """
    c: AppContext = ctx.obj
    data = json.loads(file.read_text())
    if not isinstance(data, list):
        c.output.error("File must contain a JSON array")
        raise typer.Exit(1)

    from kctl_ak.commands.mail import ensure_welcome_stage
    from kctl_ak.core.resolve import resolve_group

    stage = None
    if send_mail:
        stage = ensure_welcome_stage(c.client, c.output)

    created = 0
    reinvited = 0
    emailed = 0
    failed = 0

    for entry in data:
        email = entry.get("email", "")
        if not email:
            c.output.warn("Skipping entry without email")
            failed += 1
            continue

        username = entry.get("username", email.split("@")[0])
        name = entry.get("name", username)

        try:
            # Check if exists
            existing = c.client.get("core/users/", params={"email": email})
            existing_users = existing.get("results", [])

            if existing_users:
                pk = existing_users[0]["pk"]
                c.output.info(f"Re-invite: {email} (ID: {pk})")
                reinvited += 1
            else:
                pw = secrets.token_urlsafe(16)
                user = c.client.post(
                    "core/users/",
                    data={
                        "username": username,
                        "email": email,
                        "name": name,
                        "is_active": True,
                    },
                )
                pk = user["pk"]
                c.client.post(f"core/users/{pk}/set_password/", data={"password": pw})
                c.output.success(f"Created: {username} ({email})")
                created += 1

            # Groups
            groups_str = entry.get("groups", "")
            if groups_str:
                for gname in groups_str.split(","):
                    gname = gname.strip()
                    if not gname:
                        continue
                    try:
                        gid = resolve_group(c.client, gname)
                        c.client.post(f"core/groups/{gid}/add_user/", data={"pk": pk})
                    except Exception:
                        pass

            # Send welcome email
            if send_mail and stage:
                try:
                    c.client.post(
                        f"core/users/{pk}/recovery_email/",
                        data={
                            "email": email,
                            "email_stage": stage,
                        },
                    )
                    emailed += 1
                except Exception:
                    c.output.warn(f"Email failed for {email}")

        except Exception as e:
            c.output.error(f"Failed: {email} - {e}")
            failed += 1

    c.output.header("Bulk Invite Summary")
    c.output.kv("Created", str(created))
    c.output.kv("Re-invited", str(reinvited))
    c.output.kv("Emails sent", str(emailed))
    c.output.kv("Failed", str(failed))


@app.command("export")
def export_(
    ctx: typer.Context,
    format: Annotated[str, typer.Option("--format", help="Output format: json or csv")] = "json",
) -> None:
    """Export all users."""
    c: AppContext = ctx.obj
    users = c.client.get_all("core/users/")

    if format == "csv":
        writer = csv.writer(sys.stdout)
        writer.writerow(["pk", "username", "email", "name", "is_active", "is_superuser", "last_login"])
        for u in users:
            writer.writerow(
                [
                    u.get("pk", ""),
                    u.get("username", ""),
                    u.get("email", ""),
                    u.get("name", ""),
                    u.get("is_active", ""),
                    u.get("is_superuser", ""),
                    u.get("last_login", ""),
                ]
            )
    else:
        c.output.raw_json(users)


def _load_user_entries(file: Path) -> list[dict]:
    """Load user entries from a JSON array or a CSV (with a header row).

    CSV columns recognised: email (required), name, username, groups (comma-
    separated), password, is_active, is_superuser. Lines starting with `#` are
    treated as comments and ignored.
    """
    if file.suffix.lower() == ".csv":
        with file.open(newline="") as f:
            rows = csv.DictReader(r for r in f if not r.lstrip().startswith("#"))
            return [{k: v for k, v in row.items() if v not in (None, "")} for row in rows]
    data = json.loads(file.read_text())
    if not isinstance(data, list):
        raise ValueError("JSON file must contain an array of user objects")
    return data


@app.command("bulk-import")
def bulk_import(
    ctx: typer.Context,
    file: Annotated[Path, typer.Argument(help="JSON or CSV file with user list")],
    groups: Annotated[
        str | None,
        typer.Option("--groups", help="Comma-separated group names to add every user to."),
    ] = None,
    skip_existing: Annotated[
        bool,
        typer.Option("--skip-existing/--fail-existing", help="Skip users whose username already exists."),
    ] = True,
) -> None:
    """Bulk-import users from a JSON or CSV file.

    JSON: [{"email": "...", "name": "...", "username": "...", "groups": "g1,g2"}, ...]
    CSV: header row with columns: email, name, username, groups, password (optional)
    """
    c: AppContext = ctx.obj
    try:
        data = _load_user_entries(file)
    except ValueError as e:
        c.output.error(str(e))
        raise typer.Exit(1) from e

    # Resolve default groups once (if provided at CLI level)
    default_groups = [g.strip() for g in (groups or "").split(",") if g.strip()]

    # Map group names → pks up-front
    group_pks: dict[str, str] = {}
    needed = set(default_groups)
    for entry in data:
        for g in (entry.get("groups") or "").split(","):
            g = g.strip()
            if g:
                needed.add(g)
    for g in needed:
        matches = c.client.get_all("core/groups/", params={"name": g})
        if matches:
            group_pks[g] = matches[0]["pk"]
        else:
            c.output.warn(f"Group not found: {g} (members assigned to this group will be skipped)")

    created = 0
    skipped = 0
    failed = 0
    for entry in data:
        email = entry.get("email", "")
        if not email:
            c.output.warn("Skipping entry without email")
            failed += 1
            continue

        username = entry.get("username") or email.split("@")[0]
        name = entry.get("name") or username
        pw = entry.get("password") or secrets.token_urlsafe(16)
        entry_groups = [g.strip() for g in (entry.get("groups") or "").split(",") if g.strip()]
        all_groups = default_groups + entry_groups

        try:
            existing = c.client.get_all("core/users/", params={"username": username})
            if existing:
                if skip_existing:
                    c.output.info(f"Skip existing: {username}")
                    skipped += 1
                    continue
                c.output.error(f"Exists: {username} (use --fail-existing to error loudly)")
                failed += 1
                continue

            user = c.client.post(
                "core/users/",
                data={
                    "username": username,
                    "email": email,
                    "name": name,
                    "is_active": str(entry.get("is_active", "true")).lower() != "false",
                    "is_superuser": str(entry.get("is_superuser", "false")).lower() == "true",
                    "groups": [group_pks[g] for g in all_groups if g in group_pks],
                },
            )
            c.client.post(f"core/users/{user['pk']}/set_password/", data={"password": pw})
            c.output.success(f"Created: {username} ({email})")
            created += 1
        except Exception as e:
            c.output.error(f"Failed: {email} - {e}")
            failed += 1

    c.output.info(f"Import complete: {created} created, {skipped} skipped, {failed} failed")


def _generate_qr_png(data: str) -> bytes:
    """Generate a QR code as a PNG byte string."""
    import io

    import qrcode

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _outline_profile(profile_name: str) -> tuple[str, str]:
    """Return (url, token) for the Outline service on a profile or raise."""
    from kctl_lib.config import get_service_config as _gsc

    raw = _gsc(profile_name, "outline")
    url = (raw or {}).get("url", "").rstrip("/")
    token = (raw or {}).get("token", "")
    if not url or not token:
        raise ValueError(
            f"Outline not configured for profile '{profile_name}'. Add profiles.{profile_name}.outline.url / .token in ~/.config/kodemeio/config.yaml",
        )
    return url, token


def _outline_upload(url: str, token: str, filename: str, png: bytes) -> str:
    """Upload a PNG attachment to Outline, return the public CDN URL."""
    import httpx

    # Step 1: get a pre-signed upload slot
    r = httpx.post(
        f"{url}/api/attachments.create",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": filename, "contentType": "image/png", "size": len(png)},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()["data"]
    upload_url = data["uploadUrl"]
    form = data["form"]
    attachment_url = data["attachment"]["url"]

    # Step 2: POST multipart to the upload URL
    files = {"file": (filename, png, "image/png")}
    r2 = httpx.post(upload_url, data=form, files=files, timeout=60)
    r2.raise_for_status()
    return attachment_url


def _outline_create_doc(url: str, token: str, collection_id: str, title: str, markdown: str) -> str:
    """Create a published Outline document and return the edit URL."""
    import httpx

    r = httpx.post(
        f"{url}/api/documents.create",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": title,
            "text": markdown,
            "collectionId": collection_id,
            "publish": True,
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()["data"]
    return f"{url}/doc/{data['id']}"


@app.command("bulk-recovery-links")
def bulk_recovery_links(
    ctx: typer.Context,
    file: Annotated[Path, typer.Argument(help="JSON or CSV file with user list (email or username column).")],
    out: Annotated[
        Path | None,
        typer.Option("--out", "-o", help="Output CSV path (default: stdout)."),
    ] = None,
    outline_collection: Annotated[
        str | None,
        typer.Option(
            "--outline-collection",
            help=(
                "Outline collection ID. When set, also publishes a phone-friendly QR roster "
                "as an Outline document (access controlled at the collection level — grant to "
                "HR/IT groups only in Outline UI). Uses the 'outline' block in the active profile "
                "for URL + token."
            ),
        ),
    ] = None,
    outline_doc_title: Annotated[
        str | None,
        typer.Option("--outline-doc-title", help="Title for the Outline roster doc."),
    ] = None,
) -> None:
    """Generate one-time recovery links for a list of users.

    Writes a CSV with columns: username, email, name, recovery_link.

    When --outline-collection is set, also builds a phone-friendly QR roster
    document in that Outline collection. Access is determined by the collection's
    permissions — set it up in Outline UI to grant only the HR + IT groups.
    """
    c: AppContext = ctx.obj
    try:
        entries = _load_user_entries(file)
    except ValueError as e:
        c.output.error(str(e))
        raise typer.Exit(1) from e

    rows: list[list[str]] = []
    roster: list[dict[str, str]] = []
    failed = 0
    for entry in entries:
        ident = entry.get("username") or entry.get("email")
        if not ident:
            c.output.warn("Skipping entry without username/email")
            failed += 1
            continue
        try:
            pk = resolve_user(c.client, ident)
            link = c.client.post(f"core/users/{pk}/recovery/", data={}).get("link", "")
            username = entry.get("username") or ident.split("@")[0]
            email = entry.get("email", "")
            name = entry.get("name", "")
            rows.append([username, email, name, link])
            roster.append(
                {
                    "username": username,
                    "email": email,
                    "name": name,
                    "wilayah": entry.get("wilayah", ""),
                    "position": entry.get("position", ""),
                    "link": link,
                },
            )
        except Exception as e:
            c.output.warn(f"Skip {ident}: {e}")
            failed += 1

    writer_out = sys.stdout if out is None else out.open("w", newline="")
    try:
        writer = csv.writer(writer_out)
        writer.writerow(["username", "email", "name", "recovery_link"])
        writer.writerows(rows)
    finally:
        if out is not None:
            writer_out.close()

    c.output.info(f"Generated {len(rows)} links, {failed} failed" + (f" → {out}" if out else ""))

    if outline_collection and roster:
        profile = c.profile or "default"
        try:
            ol_url, ol_token = _outline_profile(profile)
        except ValueError as e:
            c.output.error(str(e))
            raise typer.Exit(1) from e

        import datetime

        title = outline_doc_title or f"Onboarding QR Roster — {datetime.date.today().isoformat()}"
        c.output.info(f"Publishing Outline roster '{title}' ({len(roster)} users)...")

        # Markdown body
        lines: list[str] = [
            "> **RAHASIA — hanya untuk HR & IT.** Jangan share link QR ini keluar organisasi.",
            "",
            "Tampilkan QR ke karyawan untuk di-scan. Setelah scan, karyawan akan diarahkan ke halaman set-password. Link kedaluwarsa 7 hari.",
            "",
            "| Nama | Wilayah | Position | QR |",
            "|---|---|---|---|",
        ]
        for i, r in enumerate(roster, 1):
            try:
                png = _generate_qr_png(r["link"])
                att_url = _outline_upload(ol_url, ol_token, f"qr-{r['username']}.png", png)
                lines.append(f"| {r['name'] or r['username']} | {r['wilayah']} | {r['position']} | ![]({att_url}) |")
            except Exception as e:
                c.output.warn(f"QR upload failed for {r['username']}: {e}")
                lines.append(f"| {r['name'] or r['username']} | {r['wilayah']} | {r['position']} | (upload failed) |")
            if i % 10 == 0:
                c.output.info(f"  ...{i}/{len(roster)} QRs uploaded")

        try:
            doc_url = _outline_create_doc(ol_url, ol_token, outline_collection, title, "\n".join(lines))
            c.output.success(f"Outline roster: {doc_url}")
        except Exception as e:
            c.output.error(f"Failed to create Outline doc: {e}")
            raise typer.Exit(1) from e


@app.command()
def me(ctx: typer.Context) -> None:
    """Show the current authenticated user."""
    c: AppContext = ctx.obj
    user = c.client.get("core/users/me/")
    u = user.get("user", user)

    c.output.detail(
        "Current User",
        [
            (
                "Identity",
                [
                    ("ID", str(u.get("pk", ""))),
                    ("Username", u.get("username", "")),
                    ("Email", u.get("email", "")),
                    ("Name", u.get("name", "")),
                ],
            ),
            (
                "Status",
                [
                    ("Active", str(u.get("is_active", ""))),
                    ("Superuser", str(u.get("is_superuser", ""))),
                ],
            ),
        ],
        data_for_json=u,
    )


def _check_groups_exist(client: object, groups: list[str]) -> tuple[list[str], list[str]]:
    """Check which groups exist in Authentik. Returns (existing, missing)."""
    from kctl_ak.core.client import AuthentikClient

    assert isinstance(client, AuthentikClient)
    all_groups = client.get_all("core/groups/")
    existing_names = {g["name"] for g in all_groups}
    existing = [g for g in groups if g in existing_names]
    missing = [g for g in groups if g not in existing_names]
    return existing, missing


@app.command()
def roles(
    ctx: typer.Context,
    verify: Annotated[bool, typer.Option("--verify", help="Check which groups actually exist in Authentik")] = False,
) -> None:
    """List available provisioning roles."""
    c: AppContext = ctx.obj
    loader = RoleLoader()
    all_roles = loader.list_roles()

    if verify:
        all_groups: set[str] = set()
        for r in all_roles:
            all_groups.update(r.groups)
        existing, missing = _check_groups_exist(c.client, sorted(all_groups))

        rows = [[r.name, r.description, ", ".join(r.groups)] for r in all_roles]
        c.output.table(
            "Available Roles",
            [("Name", "green"), ("Description", ""), ("Groups", "dim")],
            rows,
            data_for_json=[r.model_dump() for r in all_roles],
        )

        if missing:
            c.output.warn(f"{len(missing)} groups missing in Authentik:")
            for g in missing:
                c.output.text(f"  [red]- {g}[/red]")
            c.output.info("Run 'kctl-ak groups sync --no-dry-run' to create missing groups")
        else:
            c.output.success(f"All {len(existing)} groups exist in Authentik")
    else:
        rows = [[r.name, r.description, ", ".join(r.groups)] for r in all_roles]
        c.output.table(
            "Available Roles",
            [("Name", "green"), ("Description", ""), ("Groups", "dim")],
            rows,
            data_for_json=[r.model_dump() for r in all_roles],
        )


@app.command()
def role(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Role name")],
    verify: Annotated[bool, typer.Option("--verify", help="Check which groups actually exist in Authentik")] = False,
) -> None:
    """Show details for a specific role."""
    c: AppContext = ctx.obj
    loader = RoleLoader()
    r = loader.get_role(name)
    if r is None:
        c.output.error(f"Role not found: {name}")
        raise typer.Exit(1)

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Definition",
            [
                ("Name", r.name),
                ("Description", r.description),
                ("File", r.file_path or "(unknown)"),
            ],
        ),
    ]

    if verify and r.groups:
        existing, missing = _check_groups_exist(c.client, r.groups)
        group_kvs: list[tuple[str, str]] = []
        for g in r.groups:
            status = "[green]exists[/green]" if g in existing else "[red]MISSING[/red]"
            group_kvs.append((g, status))
        sections.append(("Groups", group_kvs))
    else:
        sections.append(("Groups", [(str(i + 1), g) for i, g in enumerate(r.groups)] if r.groups else [("(none)", "")]))

    c.output.detail(f"Role: {r.name}", sections, data_for_json=r.model_dump())


@app.command()
def provision(
    ctx: typer.Context,
    email: Annotated[str, typer.Argument(help="User email address")],
    role_names: Annotated[list[str], typer.Argument(help="One or more role names")],
    name: Annotated[str | None, typer.Option(help="Display name")] = None,
    username: Annotated[str | None, typer.Option(help="Username (default: email prefix)")] = None,
    send_mail: Annotated[bool, typer.Option("--send-mail", help="Send welcome email with recovery link")] = False,
) -> None:
    """Provision a user with one or more roles."""
    c: AppContext = ctx.obj
    loader = RoleLoader()
    provisioner = Provisioner(client=c.client, role_loader=loader, output=c.output)
    result = provisioner.provision(email=email, role_names=role_names, name=name, username=username)

    email_sent = False
    if send_mail:
        from kctl_ak.commands.mail import ensure_welcome_stage

        try:
            stage = ensure_welcome_stage(c.client, c.output)
            c.client.post(
                f"core/users/{result.user_id}/recovery_email/",
                data={
                    "email": result.email,
                    "email_stage": stage,
                },
            )
            email_sent = True
            c.output.success(f"Welcome email sent to {result.email} (via Authentik)")
        except Exception as e:
            c.output.warn(f"Failed to send email: {e}")

    c.output.detail(
        f"Provisioned: {result.username}",
        [
            (
                "User",
                [
                    ("Operation", result.operation),
                    ("ID", str(result.user_id)),
                    ("Username", result.username),
                    ("Email", result.email),
                    ("Name", result.name),
                ],
            ),
            (
                "Roles",
                [
                    ("Applied", ", ".join(result.roles)),
                ],
            ),
            (
                "Groups",
                [
                    ("Added", ", ".join(result.groups_added) if result.groups_added else "(none)"),
                    ("Already member", ", ".join(result.groups_existed) if result.groups_existed else "(none)"),
                    ("Failed", ", ".join(result.groups_failed) if result.groups_failed else "(none)"),
                ],
            ),
            (
                "Access",
                [
                    ("Recovery Link", result.recovery_link or "(none)"),
                    ("Email Sent", "yes" if email_sent else "no"),
                ],
            ),
        ],
        data_for_json={
            "operation": result.operation,
            "user_id": result.user_id,
            "email": result.email,
            "username": result.username,
            "name": result.name,
            "roles": result.roles,
            "groups_added": result.groups_added,
            "groups_existed": result.groups_existed,
            "groups_failed": result.groups_failed,
            "recovery_link": result.recovery_link,
            "email_sent": email_sent,
        },
    )
