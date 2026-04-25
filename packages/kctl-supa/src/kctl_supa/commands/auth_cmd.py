"""Authentication and user management commands for kctl-supa.

Authentication and user management.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich import print as rprint
from rich.table import Table

from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.client import SupabaseClient
from kctl_supa.core.docker import DockerOps
from kctl_supa.core.exceptions import DockerError, SupabaseError

app = typer.Typer(help="Authentication and user management.")


def _get_client(actx: AppContext) -> SupabaseClient:
    cfg = actx.config
    return SupabaseClient(base_url=cfg.url, service_role_key=cfg.service_role_key, anon_key=cfg.anon_key)


def _get_docker(actx: AppContext) -> DockerOps:
    return DockerOps(actx.config)


@app.command(name="list")
def list_users(
    ctx: typer.Context,
    page: Annotated[int, typer.Option("--page", help="Page number")] = 1,
    per_page: Annotated[int, typer.Option("--per-page", help="Users per page")] = 50,
) -> None:
    """List users."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        client = _get_client(actx)
        result = client.auth_list_users(page=page, per_page=per_page)
        client.close()
    except SupabaseError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    users = result if isinstance(result, list) else result.get("users", [])

    if not users:
        out.warn("No users found.")
        return

    table = Table(title=f"Auth Users (page {page})", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim")
    table.add_column("Email", style="cyan")
    table.add_column("Created At")
    table.add_column("Confirmed")

    for user in users:
        uid = user.get("id", "")
        email = user.get("email", "")
        created = user.get("created_at", "")[:19] if user.get("created_at") else ""
        confirmed = "[green]yes[/green]" if user.get("email_confirmed_at") else "[red]no[/red]"
        table.add_row(uid, email, created, confirmed)

    rprint(table)


@app.command()
def get(
    ctx: typer.Context,
    user_id: Annotated[str, typer.Argument(help="User ID")],
) -> None:
    """Get user details by ID."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        client = _get_client(actx)
        user = client.auth_get_user(user_id)
        client.close()
    except SupabaseError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    out.kv("ID", user.get("id", ""))
    out.kv("Email", user.get("email", ""))
    out.kv("Phone", user.get("phone", "") or "[dim]not set[/dim]")
    out.kv("Created", user.get("created_at", "")[:19])
    out.kv("Updated", user.get("updated_at", "")[:19])
    out.kv("Email confirmed", "yes" if user.get("email_confirmed_at") else "no")
    out.kv("Role", user.get("role", ""))
    ban_duration = user.get("ban_duration")
    if ban_duration and ban_duration != "none":
        out.kv("Banned", f"[red]yes ({ban_duration})[/red]")
    else:
        out.kv("Banned", "no")


@app.command()
def create(
    ctx: typer.Context,
    email: Annotated[str, typer.Option("--email", help="User email", prompt=True)],
    password: Annotated[str, typer.Option("--password", help="User password", prompt=True, hide_input=True)],
) -> None:
    """Create a new user."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        client = _get_client(actx)
        user = client.auth_create_user(email=email, password=password)
        client.close()
    except SupabaseError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    out.success(f"User created: {user.get('id')}")
    out.kv("Email", email)


@app.command()
def delete(
    ctx: typer.Context,
    user_id: Annotated[str, typer.Argument(help="User ID to delete")],
    confirm: Annotated[bool, typer.Option("--confirm", help="Skip confirmation prompt")] = False,
) -> None:
    """Delete a user."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not confirm:
        if not typer.confirm(f"Delete user '{user_id}'?"):
            raise typer.Exit(0)

    try:
        client = _get_client(actx)
        client.auth_delete_user(user_id)
        client.close()
    except SupabaseError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    out.success(f"User '{user_id}' deleted")


@app.command()
def ban(
    ctx: typer.Context,
    user_id: Annotated[str, typer.Argument(help="User ID to ban")],
) -> None:
    """Ban a user."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        client = _get_client(actx)
        client.auth_update_user(user_id, ban_duration="876600h")
        client.close()
    except SupabaseError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    out.success(f"User '{user_id}' banned")


@app.command()
def unban(
    ctx: typer.Context,
    user_id: Annotated[str, typer.Argument(help="User ID to unban")],
) -> None:
    """Unban a user."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        client = _get_client(actx)
        client.auth_update_user(user_id, ban_duration="none")
        client.close()
    except SupabaseError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    out.success(f"User '{user_id}' unbanned")


@app.command()
def stats(ctx: typer.Context) -> None:
    """Show auth user statistics."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        docker = _get_docker(actx)
        total = docker.psql("SELECT count(*) FROM auth.users")
        confirmed = docker.psql("SELECT count(*) FROM auth.users WHERE email_confirmed_at IS NOT NULL")
        banned = docker.psql("SELECT count(*) FROM auth.users WHERE banned_until IS NOT NULL AND banned_until > now()")
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    def _extract_count(raw: str) -> str:
        for line in raw.splitlines():
            line = line.strip()
            if line.isdigit():
                return line
        return raw.strip()

    out.kv("Total users", _extract_count(total))
    out.kv("Confirmed", _extract_count(confirmed))
    out.kv("Banned", _extract_count(banned))
