"""Mailbox management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage mailboxes.")


@app.command("list")
def list_(
    ctx: typer.Context,
    domain: Annotated[str | None, typer.Option("--domain", "-d", help="Filter by domain")] = None,
) -> None:
    """List all mailboxes."""
    c: AppContext = ctx.obj
    endpoint = f"mailbox/{domain}" if domain else "mailbox/all"
    data = c.client.mc_get(endpoint)
    items = data if isinstance(data, list) else []

    rows = []
    for m in items:
        active = "[green]yes[/green]" if str(m.get("active")) == "1" else "[red]no[/red]"
        quota_used = m.get("quota_used", 0)
        quota_max = m.get("quota", 0)
        quota_pct = f"{int(quota_used / quota_max * 100)}%" if quota_max else "0%"
        rows.append(
            [
                m.get("username", ""),
                m.get("name", ""),
                f"{_human_size(quota_used)} / {_human_size(quota_max)} ({quota_pct})",
                str(m.get("messages", 0)),
                active,
            ]
        )

    c.output.table(
        "Mailboxes",
        [("Email", "cyan"), ("Name", ""), ("Quota", ""), ("Messages", ""), ("Active", "")],
        rows,
        data_for_json=items,
    )


@app.command()
def get(
    ctx: typer.Context,
    email: Annotated[str, typer.Argument(help="Mailbox email address")],
) -> None:
    """Get mailbox details."""
    c: AppContext = ctx.obj
    data = c.client.mc_get(f"mailbox/{email}")

    if isinstance(data, list) and data:
        item = data[0]
    elif isinstance(data, dict) and data:
        item = data
    else:
        c.output.error(f"Mailbox not found: {email}")
        raise typer.Exit(1)

    sections = [
        (
            "Mailbox Info",
            [
                ("Email", str(item.get("username", ""))),
                ("Name", str(item.get("name", ""))),
                ("Domain", str(item.get("domain", ""))),
                ("Quota Used", _human_size(item.get("quota_used", 0))),
                ("Quota Max", _human_size(item.get("quota", 0))),
                ("Messages", str(item.get("messages", 0))),
                ("Active", str(item.get("active", ""))),
                ("Created", str(item.get("created", ""))),
                ("Modified", str(item.get("modified", ""))),
            ],
        )
    ]

    attrs = item.get("attributes", {})
    if attrs:
        attr_kvs = []
        for k, v in attrs.items():
            attr_kvs.append((k, str(v)))
        sections.append(("Attributes", attr_kvs))

    c.output.detail(f"Mailbox: {email}", sections, data_for_json=item)


@app.command()
def add(
    ctx: typer.Context,
    local_part: Annotated[str, typer.Argument(help="Local part (before @)")],
    domain: Annotated[str, typer.Argument(help="Domain name")],
    password: Annotated[str, typer.Option("--password", "-p", help="Mailbox password", prompt=True, hide_input=True)],
    name: Annotated[str | None, typer.Option("--name", "-n", help="Display name")] = None,
    quota: Annotated[int, typer.Option("--quota", help="Quota in MB")] = 3072,
    active: Annotated[bool, typer.Option("--active/--inactive", help="Active state")] = True,
    expand_domain_quota: Annotated[
        bool,
        typer.Option(
            "--expand-domain-quota",
            help="If the domain quota cannot fit the new mailbox, expand it automatically (adds 2x the shortfall as headroom).",
        ),
    ] = False,
    skip_preflight: Annotated[
        bool,
        typer.Option("--skip-preflight", help="Skip domain quota preflight check."),
    ] = False,
    authsource: Annotated[
        str,
        typer.Option(
            "--authsource",
            help="Authentication source for UI/SSO login. Default 'generic-oidc' links the mailbox to the configured external IdP (SSO). Use 'mailcow' for local-password-only accounts (e.g., service accounts).",
        ),
    ] = "generic-oidc",
) -> None:
    """Add a new mailbox.

    Performs a domain-quota preflight check before calling the API so that
    ``mailbox_quota_left_exceeded`` errors surface as actionable messages
    (or get auto-resolved via ``--expand-domain-quota``).
    """
    c: AppContext = ctx.obj

    if not skip_preflight:
        _preflight_domain_quota(c, domain, quota, expand_domain_quota)

    payload = {
        "local_part": local_part,
        "domain": domain,
        "name": name or local_part,
        "password": password,
        "password2": password,
        "quota": quota,
        "active": "1" if active else "0",
    }
    result = c.client.mc_add("mailbox", payload)
    _handle_result(c, result, f"Mailbox '{local_part}@{domain}' added")

    # Mailcow's /add/mailbox doesn't accept authsource; set it via /edit/mailbox.
    if authsource and authsource != "mailcow":
        edit_result = c.client.mc_edit(
            "mailbox",
            {"items": [f"{local_part}@{domain}"], "attr": {"authsource": authsource}},
        )
        _handle_result(c, edit_result, f"Mailbox authsource set to '{authsource}'")


def _preflight_domain_quota(
    c: AppContext,
    domain: str,
    requested_mb: int,
    expand: bool,
) -> None:
    """Check whether the domain has enough quota for a new mailbox.

    If not, either expand the domain quota (when ``expand`` is true) or
    raise a friendly error describing exactly how much more is needed.
    Silently returns if the domain record can't be read (the API call will
    still enforce quotas server-side).
    """
    data = c.client.mc_get(f"domain/{domain}")
    item = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else None
    if not item:
        return

    max_bytes = int(item.get("max_quota_for_domain", 0) or 0)
    used_bytes = int(item.get("quota_used_in_domain", 0) or 0)
    if max_bytes <= 0:
        return

    requested_bytes = requested_mb * 1024 * 1024
    left_bytes = max_bytes - used_bytes
    if requested_bytes <= left_bytes:
        return

    shortfall = requested_bytes - left_bytes
    shortfall_mb = (shortfall + 1024 * 1024 - 1) // (1024 * 1024)
    if not expand:
        c.output.error(
            f"Domain '{domain}' quota too small: {left_bytes // (1024 * 1024)} MB left, "
            f"{requested_mb} MB requested (short by {shortfall_mb} MB). "
            f"Re-run with --expand-domain-quota to grow the domain automatically, "
            f"or bump manually: kctl-mailcow domains update {domain} --quota <bytes>."
        )
        raise typer.Exit(1)

    # Expand by the shortfall + 2x headroom so we don't have to do this every mailbox.
    new_max_bytes = max_bytes + shortfall + 2 * requested_bytes
    c.output.info(
        f"Expanding '{domain}' quota from {max_bytes // (1024 * 1024)} MB to "
        f"{new_max_bytes // (1024 * 1024)} MB to fit the new mailbox."
    )
    result = c.client.mc_edit("domain", {"items": [domain], "attr": {"quota": new_max_bytes}})
    _handle_result(c, result, f"Domain '{domain}' quota expanded")


@app.command()
def update(
    ctx: typer.Context,
    email: Annotated[str, typer.Argument(help="Mailbox email address")],
    name: Annotated[str | None, typer.Option("--name", "-n")] = None,
    quota: Annotated[int | None, typer.Option("--quota")] = None,
    password: Annotated[str | None, typer.Option("--password", "-p")] = None,
    active: Annotated[bool | None, typer.Option("--active/--inactive")] = None,
    authsource: Annotated[
        str | None,
        typer.Option(
            "--authsource",
            help="Change authentication source ('generic-oidc' for SSO, 'mailcow' for local password).",
        ),
    ] = None,
) -> None:
    """Update mailbox settings."""
    c: AppContext = ctx.obj
    attr: dict = {}
    if name is not None:
        attr["name"] = name
    if quota is not None:
        attr["quota"] = quota
    if password is not None:
        attr["password"] = password
        attr["password2"] = password
    if active is not None:
        attr["active"] = "1" if active else "0"
    if authsource is not None:
        attr["authsource"] = authsource

    if not attr:
        c.output.warn("No fields to update")
        raise typer.Exit(0)

    payload = {
        "items": [email],
        "attr": attr,
    }
    result = c.client.mc_edit("mailbox", payload)
    _handle_result(c, result, f"Mailbox '{email}' updated")


@app.command()
def delete(
    ctx: typer.Context,
    email: Annotated[str, typer.Argument(help="Mailbox email to delete")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a mailbox."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete mailbox '{email}'? This removes all mail data."):
            raise typer.Exit(0)

    result = c.client.mc_delete("mailbox", [email])
    _handle_result(c, result, f"Mailbox '{email}' deleted")


def _human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable size."""
    if not size_bytes:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024  # type: ignore[assignment]
    return f"{size_bytes:.1f} PB"


_handle_result = handle_result
