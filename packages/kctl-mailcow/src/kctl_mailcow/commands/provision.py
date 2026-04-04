"""Provision commands — sync Authentik users to Mailcow mailboxes."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext

app = typer.Typer(help="Provision mailboxes from Authentik users.")


@app.command()
def sync(
    ctx: typer.Context,
    group: Annotated[str, typer.Option("--group", "-g", help="Authentik group name to sync (required)")],
    domain: Annotated[str, typer.Option("--domain", "-d", help="Target Mailcow domain (required)")],
    quota: Annotated[int, typer.Option("--quota", help="Default quota in MB for new mailboxes")] = 3072,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without making changes")] = False,
    ak_profile: Annotated[str | None, typer.Option("--ak-profile", help="Authentik profile name")] = None,
) -> None:
    """Sync users from an Authentik group to Mailcow mailboxes.

    For each user in the Authentik group that has an email address,
    creates a mailbox in the target domain if one doesn't exist.
    Existing mailboxes are skipped (or updated if name changed).
    New mailboxes get a random password with force_pw_update=1.
    """
    c: AppContext = ctx.obj

    # Resolve Authentik connection
    try:
        from kctl_ak.core.config import resolve_connection as ak_resolve_connection
    except ImportError:
        c.output.error("kctl-ak is required for provisioning. Install with: uv pip install kctl-ak")
        raise typer.Exit(1)

    ak_url, ak_token = ak_resolve_connection(profile_name=ak_profile)
    if not ak_url or not ak_token:
        c.output.error("Authentik not configured. Run: kctl-ak config init")
        raise typer.Exit(1)

    from kctl_mailcow.core.provisioner import fetch_authentik_users, sync_users_to_mailboxes

    # Fetch users
    if dry_run:
        c.output.info(f"[DRY RUN] Fetching users from Authentik group '{group}'...")
    else:
        c.output.info(f"Fetching users from Authentik group '{group}'...")

    users = fetch_authentik_users(ak_url, ak_token, group)
    if not users:
        c.output.warn(f"No users with email found in Authentik group '{group}'")
        return

    c.output.info(f"Found {len(users)} users with email addresses")

    # Sync to Mailcow
    result = sync_users_to_mailboxes(
        mailcow_client=c.client,
        users=users,
        domain=domain,
        default_quota=quota,
        dry_run=dry_run,
    )

    # Display results
    prefix = "[DRY RUN] " if dry_run else ""
    sections = [
        (
            f"{prefix}Sync Results",
            [
                ("Total users", str(result.total)),
                ("Created", str(len(result.created))),
                ("Updated", str(len(result.updated))),
                ("Skipped", str(len(result.skipped))),
                ("Failed", str(len(result.failed))),
            ],
        ),
    ]

    if result.created:
        sections.append(("Created Mailboxes", [(email, "new") for email in result.created]))
    if result.updated:
        sections.append(("Updated Mailboxes", [(email, "name changed") for email in result.updated]))
    if result.failed:
        sections.append(("Failed", [(email, reason) for email, reason in result.failed]))

    c.output.detail(
        f"{prefix}Provision: {group} → {domain}",
        sections,
        data_for_json={
            "group": group,
            "domain": domain,
            "dry_run": dry_run,
            "created": result.created,
            "updated": result.updated,
            "skipped": result.skipped,
            "failed": [{"email": e, "error": r} for e, r in result.failed],
        },
    )

    if result.failed and not dry_run:
        raise typer.Exit(1)


@app.command()
def status(
    ctx: typer.Context,
    group: Annotated[str, typer.Option("--group", "-g", help="Authentik group name")],
    domain: Annotated[str, typer.Option("--domain", "-d", help="Mailcow domain to check")],
    ak_profile: Annotated[str | None, typer.Option("--ak-profile", help="Authentik profile name")] = None,
) -> None:
    """Show which Authentik users have/don't have mailboxes."""
    c: AppContext = ctx.obj

    try:
        from kctl_ak.core.config import resolve_connection as ak_resolve_connection
    except ImportError:
        c.output.error("kctl-ak is required for provisioning. Install with: uv pip install kctl-ak")
        raise typer.Exit(1)

    ak_url, ak_token = ak_resolve_connection(profile_name=ak_profile)
    if not ak_url or not ak_token:
        c.output.error("Authentik not configured. Run: kctl-ak config init")
        raise typer.Exit(1)

    from kctl_mailcow.core.provisioner import fetch_authentik_users

    users = fetch_authentik_users(ak_url, ak_token, group)
    if not users:
        c.output.warn(f"No users with email found in Authentik group '{group}'")
        return

    # Fetch existing mailboxes
    existing_data = c.client.mc_get(f"mailbox/{domain}")
    existing_emails: set[str] = set()
    if isinstance(existing_data, list):
        for mb in existing_data:
            email = mb.get("username", "")
            if email:
                existing_emails.add(email)

    rows = []
    json_data = []
    for user in users:
        local_part = user["email"].split("@")[0] if "@" in user["email"] else user["email"]
        target = f"{local_part}@{domain}"
        has_mailbox = target in existing_emails
        status_str = "[green]yes[/green]" if has_mailbox else "[red]no[/red]"
        rows.append([user["username"], user["email"], target, status_str])
        json_data.append(
            {
                "username": user["username"],
                "authentik_email": user["email"],
                "mailcow_email": target,
                "has_mailbox": has_mailbox,
            }
        )

    c.output.table(
        f"Provision Status: {group} → {domain}",
        [("Username", "cyan"), ("Authentik Email", ""), ("Mailcow Email", ""), ("Has Mailbox", "")],
        rows,
        data_for_json=json_data,
    )
