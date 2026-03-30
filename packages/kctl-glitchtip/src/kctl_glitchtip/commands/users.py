"""User management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_glitchtip.core.callbacks import AppContext

app = typer.Typer(help="Manage GlitchTip users.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List users."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    users = c.get_list("users/")

    rows: list[list[str]] = []
    for u in users:
        user_id = str(u.get("id", ""))
        email = u.get("email", "")
        username = u.get("username", "")
        is_active = "[green]yes[/green]" if u.get("isActive", u.get("is_active", True)) else "[red]no[/red]"
        created = str(u.get("dateJoined") or u.get("date_joined") or "")[:10]
        rows.append([user_id, email, username, is_active, created])

    out.table(
        "Users",
        [("ID", "cyan"), ("Email", ""), ("Username", ""), ("Active", ""), ("Joined", "dim")],
        rows,
        data_for_json=users,
    )


@app.command()
def create(
    ctx: typer.Context,
    email: Annotated[str, typer.Argument(help="User email")],
    superuser: Annotated[bool, typer.Option("--superuser", help="Create as superuser (requires Docker)")] = False,
) -> None:
    """Create a user."""
    actx: AppContext = ctx.obj
    out = actx.output

    if superuser:
        import subprocess

        out.info(f"Creating superuser {email} via Django management command...")
        try:
            result = subprocess.run(
                ["docker", "exec", "kodemeio-glitchtip", "./manage.py", "createsuperuser", "--email", email, "--noinput"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                out.success(f"Superuser created: {email}")
                out.info("Set password via Django admin or OIDC login")
            else:
                out.error(f"Failed: {result.stderr.strip()}")
                raise typer.Exit(1)
        except FileNotFoundError:
            out.error("Docker not found. Superuser creation requires Docker access.")
            raise typer.Exit(1)
    else:
        # Use the org members API to invite a user
        c = actx.client
        orgs = c.get_list("organizations/")
        if not orgs:
            out.error("No organizations found")
            raise typer.Exit(1)

        org_slug = orgs[0].get("slug", "")
        result = c.post(f"organizations/{org_slug}/members/", data={"email": email, "orgRole": "member"})
        out.success(f"User '{email}' invited to organization '{org_slug}'")
        if out.json_mode:
            out.raw_json(result)
