"""Realm (server) settings commands.

Mix of REST API operations (settings/get/update) and server-side
admin operations (create/list/delete/set-string-id) that go through
SSH + docker exec because the Zulip REST API does not support them.
"""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from kctl_zulip.core.callbacks import AppContext
from kctl_zulip.core.server_admin import ServerAdminError, run_django_shell

app = typer.Typer(help="Realm (server) settings.")


@app.command("settings")
def settings_(ctx: typer.Context) -> None:
    """Show server settings (public endpoint)."""
    c: AppContext = ctx.obj
    data = c.client.get("server_settings")

    auth_methods = data.get("authentication_methods", {})
    enabled_auth = [k for k, v in auth_methods.items() if v]

    c.output.detail(
        "Server Settings",
        [
            (
                "Server",
                [
                    ("Zulip Version", data.get("zulip_version", "")),
                    ("Feature Level", str(data.get("zulip_feature_level", ""))),
                    ("Merge Base", data.get("zulip_merge_base", "")),
                    ("Push Notifications", str(data.get("push_notifications_enabled", False))),
                ],
            ),
            (
                "Realm",
                [
                    ("Name", data.get("realm_name", "")),
                    ("Description", data.get("realm_description", "")),
                    ("Icon URL", data.get("realm_icon", "")),
                    ("URI", data.get("realm_uri", "")),
                    ("Web Public", str(data.get("realm_web_public_access_enabled", False))),
                ],
            ),
            (
                "Authentication",
                [
                    ("Enabled Methods", ", ".join(enabled_auth) if enabled_auth else "(none)"),
                    ("Require Email Format", str(data.get("require_email_format_usernames", True))),
                ],
            ),
        ],
        data_for_json=data,
    )


@app.command()
def get(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Setting key to retrieve")],
) -> None:
    """Get a specific server setting."""
    c: AppContext = ctx.obj
    data = c.client.get("server_settings")

    value = data.get(key)
    if value is None:
        c.output.error(f"Setting '{key}' not found")
        c.output.info(f"Available keys: {', '.join(sorted(data.keys())[:20])}...")
        raise typer.Exit(1)

    if c.output.json_mode:
        c.output.raw_json({key: value})
    else:
        c.output.kv(key, str(value))


@app.command()
def update(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Setting key")],
    value: Annotated[str, typer.Argument(help="New value")],
) -> None:
    """Update a realm setting (admin required).

    Common settings: name, description, emails_restricted_to_domains,
    invite_required, message_retention_days, etc.
    """
    c: AppContext = ctx.obj

    # Try to coerce booleans/ints
    coerced: str | bool | int = value
    if value.lower() in ("true", "false"):
        coerced = value.lower() == "true"
    else:
        try:
            coerced = int(value)
        except ValueError:
            pass

    c.client.patch("realm", data={key: coerced})
    c.output.success(f"Realm setting '{key}' updated to: {value}")


# ---------------------------------------------------------------------------
# Server-side admin (SSH + docker exec) — Zulip REST API does not support
# realm CRUD; these go through the Django shell on the host.
# ---------------------------------------------------------------------------


@app.command("create")
def create_realm(
    ctx: typer.Context,
    string_id: Annotated[str, typer.Argument(help="Realm subdomain (use '' for root realm)")],
    name: Annotated[str, typer.Option("--name", "-n", help="Realm display name")],
    owner_email: Annotated[Optional[str], typer.Option("--owner-email", help="Owner email to create")] = None,
    owner_password: Annotated[Optional[str], typer.Option("--owner-password", help="Owner password")] = None,
    owner_name: Annotated[str, typer.Option("--owner-name", help="Owner full name")] = "Realm Owner",
    restrict_emails: Annotated[
        bool, typer.Option("--restrict-emails/--open-signup", help="Restrict to email domains")
    ] = False,
) -> None:
    """Create a new realm (server-side via Django shell).

    Zulip's REST API does not support realm creation. This command runs
    `do_create_realm` inside the Zulip server container via SSH.

    Requires the active profile to have ssh_host configured. Set with:
        kctl-zulip config set-ssh --host <ip>
    """
    c: AppContext = ctx.obj

    code = f"""
        from zerver.actions.create_realm import do_create_realm
        from zerver.actions.create_user import do_create_user
        from zerver.models import Realm, UserProfile

        existing = Realm.objects.filter(string_id={string_id!r}).first()
        if existing:
            print('REALM_EXISTS', existing.string_id, existing.name)
        else:
            r = do_create_realm(
                string_id={string_id!r},
                name={name!r},
                emails_restricted_to_domains={restrict_emails!r},
            )
            print('REALM_CREATED', r.string_id, r.name)
    """
    try:
        out = run_django_shell(c.profile, code)
    except ServerAdminError as e:
        c.output.error(str(e))
        raise typer.Exit(1) from e

    last = [ln for ln in out.splitlines() if ln.startswith("REALM_")]
    if not last:
        c.output.error("Realm creation produced no output")
        c.output.info(out)
        raise typer.Exit(1)
    status, sid, *rest = last[-1].split(" ", 2)
    realm_name = rest[0] if rest else ""
    if status == "REALM_CREATED":
        c.output.success(f"Realm '{sid or '(root)'}' created: {realm_name}")
    else:
        c.output.warn(f"Realm '{sid or '(root)'}' already exists: {realm_name}")

    if owner_email:
        if not owner_password:
            c.output.error("--owner-password is required when --owner-email is given")
            raise typer.Exit(1)
        owner_code = f"""
            from zerver.actions.create_user import do_create_user
            from zerver.models import Realm, UserProfile
            r = Realm.objects.get(string_id={string_id!r})
            u = UserProfile.objects.filter(delivery_email={owner_email!r}, realm=r).first()
            if u:
                u.role = UserProfile.ROLE_REALM_OWNER
                u.save()
                print('OWNER_UPDATED', u.delivery_email)
            else:
                u = do_create_user(
                    email={owner_email!r},
                    password={owner_password!r},
                    realm=r,
                    full_name={owner_name!r},
                    role=UserProfile.ROLE_REALM_OWNER,
                    acting_user=None,
                )
                print('OWNER_CREATED', u.delivery_email)
        """
        try:
            out2 = run_django_shell(c.profile, owner_code)
        except ServerAdminError as e:
            c.output.error(str(e))
            raise typer.Exit(1) from e
        owner_lines = [ln for ln in out2.splitlines() if ln.startswith("OWNER_")]
        if owner_lines:
            status2, email = owner_lines[-1].split(" ", 1)
            verb = "created" if status2 == "OWNER_CREATED" else "promoted to owner"
            c.output.success(f"Owner {verb}: {email}")


@app.command("list")
def list_realms(ctx: typer.Context) -> None:
    """List all realms on the Zulip server (server-side)."""
    c: AppContext = ctx.obj

    code = """
        from zerver.models import Realm
        for r in Realm.objects.all().order_by('string_id'):
            print('|'.join([
                r.string_id or '(root)',
                r.name,
                str(r.deactivated),
                str(r.id),
            ]))
    """
    try:
        out = run_django_shell(c.profile, code)
    except ServerAdminError as e:
        c.output.error(str(e))
        raise typer.Exit(1) from e

    rows = []
    json_data = []
    for line in out.splitlines():
        if "|" not in line:
            continue
        parts = line.split("|", 3)
        if len(parts) != 4:
            continue
        sid, rname, deactivated, rid = parts
        rows.append([sid, rname, "yes" if deactivated == "True" else "no", rid])
        json_data.append(
            {
                "string_id": sid,
                "name": rname,
                "deactivated": deactivated == "True",
                "id": int(rid),
            }
        )

    c.output.table(
        "Realms",
        [("String ID", "cyan"), ("Name", "green"), ("Deactivated", "dim"), ("ID", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command("set-string-id")
def set_string_id(
    ctx: typer.Context,
    current: Annotated[str, typer.Argument(help="Current string_id (use '' for root realm)")],
    new: Annotated[str, typer.Argument(help="New string_id (use '' to make root realm)")],
) -> None:
    """Change a realm's string_id (subdomain) — server-side.

    Use empty string ('') to make a realm the root realm at the EXTERNAL_HOST.
    """
    c: AppContext = ctx.obj

    code = f"""
        from zerver.models import Realm
        r = Realm.objects.get(string_id={current!r})
        old = r.string_id
        r.string_id = {new!r}
        r.save()
        print('STRING_ID_UPDATED', old or '(root)', '->', r.string_id or '(root)', '|', r.url)
    """
    try:
        out = run_django_shell(c.profile, code)
    except ServerAdminError as e:
        c.output.error(str(e))
        raise typer.Exit(1) from e

    line = next((ln for ln in out.splitlines() if ln.startswith("STRING_ID_UPDATED")), None)
    if line:
        c.output.success(line.replace("STRING_ID_UPDATED ", "Realm string_id: "))
    else:
        c.output.warn("Update completed but no confirmation in output")


@app.command("delete")
def delete_realm(
    ctx: typer.Context,
    string_id: Annotated[str, typer.Argument(help="Realm string_id to deactivate")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Deactivate a realm (server-side).

    Zulip does not hard-delete realms; it deactivates them. The realm
    becomes invisible and unusable but data is preserved.
    """
    c: AppContext = ctx.obj
    if not force:
        confirm = typer.confirm(f"Deactivate realm '{string_id or '(root)'}'?", default=False)
        if not confirm:
            c.output.warn("Aborted")
            raise typer.Exit(0)

    code = f"""
        from zerver.actions.realm_settings import do_deactivate_realm
        from zerver.models import Realm
        r = Realm.objects.get(string_id={string_id!r})
        do_deactivate_realm(r, acting_user=None, deactivation_reason='owner_request', email_owners=False)
        print('REALM_DEACTIVATED', r.string_id or '(root)')
    """
    try:
        out = run_django_shell(c.profile, code)
    except ServerAdminError as e:
        c.output.error(str(e))
        raise typer.Exit(1) from e

    if "REALM_DEACTIVATED" in out:
        c.output.success(f"Realm '{string_id or '(root)'}' deactivated")
    else:
        c.output.error("Deactivation may have failed; check server")
        c.output.info(out)
        raise typer.Exit(1)


@app.command("create-link")
def create_link(ctx: typer.Context) -> None:
    """Generate a single-use realm creation link (server-side)."""
    c: AppContext = ctx.obj
    try:
        out = run_django_shell(
            c.profile,
            "from django.core.management import call_command; call_command('generate_realm_creation_link')",
        )
    except ServerAdminError as e:
        c.output.error(str(e))
        raise typer.Exit(1) from e

    # The link is in the output; extract it
    for line in out.splitlines():
        if "/new/" in line and "https://" in line:
            link = line.strip()
            c.output.success("Realm creation link (single-use):")
            c.output.info(link)
            return
    c.output.warn("No link found in output:")
    c.output.info(out)
