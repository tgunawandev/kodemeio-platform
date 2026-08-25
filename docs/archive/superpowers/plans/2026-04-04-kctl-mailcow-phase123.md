# kctl-mailcow Phase 1-3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 15 new command groups (~52 commands) to kctl-mailcow, bringing it from 16 to 31 groups with Authentik integration.

**Architecture:** Each command group is a single file in `commands/` following the established pattern (Typer app, mc_get/mc_add/mc_edit/mc_delete, handle_result, output.table/detail). The provisioner is the only cross-service component, living in `core/provisioner.py`.

**Tech Stack:** Python 3.12+, Typer, kctl-lib 0.4.0, httpx, kctl-ak (optional dep for provisioning)

---

## File Structure

All files under `packages/kctl-mailcow/`:

| File | Phase | Responsibility |
|------|-------|---------------|
| `src/kctl_mailcow/commands/identity_provider.py` | 1 | Authentik OIDC SSO config for Mailcow admin |
| `src/kctl_mailcow/commands/oauth2_clients.py` | 1 | OAuth2 client management |
| `src/kctl_mailcow/commands/provision.py` | 1 | Thin CLI for sync commands |
| `src/kctl_mailcow/core/provisioner.py` | 1 | Authentik→Mailcow sync logic |
| `src/kctl_mailcow/commands/fail2ban.py` | 2 | Ban/unban IP management |
| `src/kctl_mailcow/commands/policies.py` | 2 | Spam whitelist/blacklist |
| `src/kctl_mailcow/commands/app_passwords.py` | 2 | Per-mailbox app passwords |
| `src/kctl_mailcow/commands/password_policy.py` | 2 | Global password rules |
| `src/kctl_mailcow/commands/domain_admins.py` | 2 | Delegated admin management |
| `src/kctl_mailcow/commands/filters.py` | 2 | Per-mailbox Sieve rules |
| `src/kctl_mailcow/commands/transports.py` | 3 | Outbound mail routing |
| `src/kctl_mailcow/commands/relay_hosts.py` | 3 | Sender-dependent smarthost |
| `src/kctl_mailcow/commands/bcc_maps.py` | 3 | Compliance BCC copies |
| `src/kctl_mailcow/commands/alias_domains.py` | 3 | Whole-domain aliasing |
| `src/kctl_mailcow/commands/recipient_maps.py` | 3 | Inbound address rewriting |
| `src/kctl_mailcow/commands/rspamd.py` | 3 | Spam filter tuning |
| `src/kctl_mailcow/cli.py` | all | Add imports + registrations for all 15 groups |
| `tests/test_smoke.py` | all | Add all 15 new groups to smoke tests |
| `pyproject.toml` | 1 | Add optional kctl-ak dependency |

---

### Task 1: Phase 1a — identity-provider and oauth2-clients commands

**Files:**
- Create: `packages/kctl-mailcow/src/kctl_mailcow/commands/identity_provider.py`
- Create: `packages/kctl-mailcow/src/kctl_mailcow/commands/oauth2_clients.py`
- Modify: `packages/kctl-mailcow/src/kctl_mailcow/cli.py`

- [ ] **Step 1: Create identity_provider.py**

```python
"""Identity provider (OIDC/OAuth2) configuration for Mailcow admin SSO."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage external identity provider (OIDC SSO) for admin login.")


@app.command()
def get(ctx: typer.Context) -> None:
    """Show current identity provider configuration."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("identity-provider")

    if not data or (isinstance(data, dict) and not data.get("authsource")):
        c.output.info("No identity provider configured.")
        if c.json_mode:
            c.output.raw_json(data or {})
        return

    item = data if isinstance(data, dict) else {}
    sections = [
        (
            "Identity Provider",
            [
                ("Auth Source", str(item.get("authsource", ""))),
                ("Server URL", str(item.get("server_url", ""))),
                ("Client ID", str(item.get("client_id", ""))),
                ("Authorize URL", str(item.get("authorize_url", ""))),
                ("Token URL", str(item.get("token_url", ""))),
                ("Userinfo URL", str(item.get("userinfo_url", ""))),
                ("Scopes", str(item.get("scopes", ""))),
                ("Redirect URI", str(item.get("redirect_url", ""))),
            ],
        )
    ]
    c.output.detail("Identity Provider Config", sections, data_for_json=item)


@app.command("set")
def set_(
    ctx: typer.Context,
    server_url: Annotated[str, typer.Option("--server-url", help="OIDC provider URL (e.g. https://auth.kodeme.io)")],
    client_id: Annotated[str, typer.Option("--client-id", help="OAuth2 client ID")],
    client_secret: Annotated[str, typer.Option("--client-secret", help="OAuth2 client secret", prompt=True, hide_input=True)],
    redirect_url: Annotated[str | None, typer.Option("--redirect-uri", help="Redirect URI")] = None,
    authorize_url: Annotated[str | None, typer.Option("--authorize-url", help="Authorization endpoint")] = None,
    token_url: Annotated[str | None, typer.Option("--token-url", help="Token endpoint")] = None,
    userinfo_url: Annotated[str | None, typer.Option("--userinfo-url", help="Userinfo endpoint")] = None,
    scopes: Annotated[str, typer.Option("--scopes", help="OAuth2 scopes")] = "openid profile email",
) -> None:
    """Configure external OIDC identity provider for Mailcow admin SSO."""
    c: AppContext = ctx.obj
    payload: dict = {
        "authsource": "oidc",
        "server_url": server_url,
        "client_id": client_id,
        "client_secret": client_secret,
        "scopes": scopes,
    }
    if redirect_url:
        payload["redirect_url"] = redirect_url
    if authorize_url:
        payload["authorize_url"] = authorize_url
    if token_url:
        payload["token_url"] = token_url
    if userinfo_url:
        payload["userinfo_url"] = userinfo_url

    result = c.client.mc_edit("identity-provider", payload)
    handle_result(c, result, "Identity provider configured")


@app.command()
def delete(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Remove identity provider configuration."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm("Remove identity provider configuration?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("identity-provider", ["oidc"])
    handle_result(c, result, "Identity provider removed")


@app.command()
def test(ctx: typer.Context) -> None:
    """Test identity provider connectivity."""
    c: AppContext = ctx.obj
    try:
        data = c.client.mc_get("identity-provider")
        if isinstance(data, dict) and data.get("authsource"):
            c.output.success(f"Identity provider configured: {data.get('server_url', 'unknown')}")
        else:
            c.output.warn("No identity provider configured")
    except Exception as e:
        c.output.error(f"Test failed: {e}")
        raise typer.Exit(1)
```

- [ ] **Step 2: Create oauth2_clients.py**

```python
"""OAuth2 client management — Mailcow as OAuth2 provider."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage OAuth2 clients (Mailcow as provider).")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all OAuth2 clients."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("oauth2-client/all")
    items = data if isinstance(data, list) else []

    if not items:
        c.output.info("No OAuth2 clients configured.")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for item in items:
        rows.append([
            str(item.get("id", "")),
            item.get("client_id", ""),
            item.get("redirect_uri", ""),
            item.get("scope", ""),
        ])

    c.output.table(
        "OAuth2 Clients",
        [("ID", "dim"), ("Client ID", "cyan"), ("Redirect URI", ""), ("Scope", "")],
        rows,
        data_for_json=items,
    )


@app.command()
def get(
    ctx: typer.Context,
    client_id: Annotated[str, typer.Argument(help="Client ID")],
) -> None:
    """Get OAuth2 client details."""
    c: AppContext = ctx.obj
    data = c.client.mc_get(f"oauth2-client/{client_id}")
    item = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else {}

    if not item:
        c.output.error(f"OAuth2 client not found: {client_id}")
        raise typer.Exit(1)

    sections = [
        ("OAuth2 Client", [
            ("ID", str(item.get("id", ""))),
            ("Client ID", str(item.get("client_id", ""))),
            ("Redirect URI", str(item.get("redirect_uri", ""))),
            ("Scope", str(item.get("scope", ""))),
        ])
    ]
    c.output.detail(f"OAuth2 Client: {client_id}", sections, data_for_json=item)


@app.command()
def create(
    ctx: typer.Context,
    redirect_uri: Annotated[str, typer.Option("--redirect-uri", "-r", help="OAuth2 redirect URI")],
    scope: Annotated[str, typer.Option("--scope", help="Allowed scopes")] = "profile",
) -> None:
    """Create a new OAuth2 client."""
    c: AppContext = ctx.obj
    payload = {
        "redirect_uri": redirect_uri,
        "scope": scope,
    }
    result = c.client.mc_add("oauth2-client", payload)
    handle_result(c, result, "OAuth2 client created")


@app.command()
def delete(
    ctx: typer.Context,
    client_id: Annotated[str, typer.Argument(help="Client ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete an OAuth2 client."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete OAuth2 client '{client_id}'?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("oauth2-client", [client_id])
    handle_result(c, result, f"OAuth2 client '{client_id}' deleted")
```

- [ ] **Step 3: Register both in cli.py**

Add these imports and registrations to `cli.py`:

```python
# Add imports after existing ones:
from kctl_mailcow.commands.identity_provider import app as identity_provider_app
from kctl_mailcow.commands.oauth2_clients import app as oauth2_clients_app

# Add registrations after existing ones:
app.add_typer(identity_provider_app, name="identity-provider")
app.add_typer(oauth2_clients_app, name="oauth2-clients")
```

- [ ] **Step 4: Verify CLI loads**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
uv run kctl-mailcow identity-provider --help
uv run kctl-mailcow oauth2-clients --help
```

- [ ] **Step 5: Commit**

```bash
git add packages/kctl-mailcow/src/kctl_mailcow/commands/identity_provider.py \
       packages/kctl-mailcow/src/kctl_mailcow/commands/oauth2_clients.py \
       packages/kctl-mailcow/src/kctl_mailcow/cli.py
git commit -m "feat(kctl-mailcow): add identity-provider and oauth2-clients commands

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Phase 1b — Provisioner (Authentik → Mailcow sync)

**Files:**
- Create: `packages/kctl-mailcow/src/kctl_mailcow/core/provisioner.py`
- Create: `packages/kctl-mailcow/src/kctl_mailcow/commands/provision.py`
- Modify: `packages/kctl-mailcow/pyproject.toml`
- Modify: `packages/kctl-mailcow/src/kctl_mailcow/cli.py`

- [ ] **Step 1: Add optional kctl-ak dependency to pyproject.toml**

Add to `[project.optional-dependencies]`:
```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-httpx>=0.35.0",
    "ruff>=0.9.0",
    "mypy>=1.14.0",
    "types-PyYAML>=6.0.0",
]
provision = [
    "kctl-ak>=0.1.0",
]
```

Add to `[tool.uv.sources]`:
```toml
[tool.uv.sources]
kctl-lib = { workspace = true }
kctl-ak = { workspace = true }
```

- [ ] **Step 2: Create core/provisioner.py**

```python
"""Authentik-to-Mailcow user provisioning.

Reads users from an Authentik group and ensures each has a
corresponding Mailcow mailbox in the target domain.
"""

from __future__ import annotations

import secrets
import string
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SyncResult:
    """Result of a provision sync operation."""

    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.created) + len(self.updated) + len(self.skipped) + len(self.failed)


def _generate_password(length: int = 24) -> str:
    """Generate a random password for new mailboxes."""
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def fetch_authentik_users(
    ak_base_url: str,
    ak_token: str,
    group_name: str,
) -> list[dict[str, Any]]:
    """Fetch users from an Authentik group.

    Returns list of dicts with keys: username, email, name, is_active.
    """
    from kctl_ak.core.client import AuthentikClient

    client = AuthentikClient(base_url=ak_base_url, credential=ak_token)
    try:
        # Get group by name
        groups = client.get_all("core/groups/", params={"name": group_name})
        if not groups:
            return []
        group = groups[0]
        group_pk = group.get("pk", "")

        # Get users in group
        users = client.get_all("core/users/", params={"groups_by_pk": group_pk, "is_active": True})
        return [
            {
                "username": u.get("username", ""),
                "email": u.get("email", ""),
                "name": u.get("name", ""),
                "is_active": u.get("is_active", True),
            }
            for u in users
            if u.get("email")
        ]
    finally:
        client.close()


def sync_users_to_mailboxes(
    mailcow_client: Any,
    users: list[dict[str, Any]],
    domain: str,
    default_quota: int = 3072,
    dry_run: bool = False,
) -> SyncResult:
    """Create or update Mailcow mailboxes for a list of users.

    Args:
        mailcow_client: MailcowClient instance
        users: List of user dicts from fetch_authentik_users
        domain: Target Mailcow domain
        default_quota: Default mailbox quota in MB
        dry_run: If True, don't actually create/update
    """
    result = SyncResult()

    # Fetch existing mailboxes in domain
    existing_data = mailcow_client.mc_get(f"mailbox/{domain}")
    existing: dict[str, dict] = {}
    if isinstance(existing_data, list):
        for mb in existing_data:
            email = mb.get("username", "")
            if email:
                existing[email] = mb

    for user in users:
        email = user["email"]
        name = user.get("name", "")
        local_part = email.split("@")[0] if "@" in email else email

        # Determine target email in this domain
        target_email = f"{local_part}@{domain}"

        if target_email in existing:
            # Mailbox exists — check if name needs update
            mb = existing[target_email]
            if name and mb.get("name", "") != name:
                if not dry_run:
                    try:
                        mailcow_client.mc_edit("mailbox", {
                            "items": [target_email],
                            "attr": {"name": name},
                        })
                        result.updated.append(target_email)
                    except Exception as e:
                        result.failed.append((target_email, str(e)))
                else:
                    result.updated.append(target_email)
            else:
                result.skipped.append(target_email)
        else:
            # Create new mailbox
            if not dry_run:
                try:
                    mailcow_client.mc_add("mailbox", {
                        "local_part": local_part,
                        "domain": domain,
                        "name": name or local_part,
                        "password": _generate_password(),
                        "password2": "",
                        "quota": str(default_quota),
                        "active": "1",
                        "force_pw_update": "1",
                        "tls_enforce_in": "0",
                        "tls_enforce_out": "0",
                    })
                    result.created.append(target_email)
                except Exception as e:
                    result.failed.append((target_email, str(e)))
            else:
                result.created.append(target_email)

    return result
```

- [ ] **Step 3: Create commands/provision.py**

```python
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
        (f"{prefix}Sync Results", [
            ("Total users", str(result.total)),
            ("Created", str(len(result.created))),
            ("Updated", str(len(result.updated))),
            ("Skipped", str(len(result.skipped))),
            ("Failed", str(len(result.failed))),
        ]),
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
        json_data.append({
            "username": user["username"],
            "authentik_email": user["email"],
            "mailcow_email": target,
            "has_mailbox": has_mailbox,
        })

    c.output.table(
        f"Provision Status: {group} → {domain}",
        [("Username", "cyan"), ("Authentik Email", ""), ("Mailcow Email", ""), ("Has Mailbox", "")],
        rows,
        data_for_json=json_data,
    )
```

- [ ] **Step 4: Register in cli.py**

```python
from kctl_mailcow.commands.provision import app as provision_app
app.add_typer(provision_app, name="provision")
```

- [ ] **Step 5: Verify CLI loads**

```bash
uv run kctl-mailcow provision --help
uv run kctl-mailcow provision sync --help
uv run kctl-mailcow provision status --help
```

- [ ] **Step 6: Commit**

```bash
git add packages/kctl-mailcow/src/kctl_mailcow/core/provisioner.py \
       packages/kctl-mailcow/src/kctl_mailcow/commands/provision.py \
       packages/kctl-mailcow/src/kctl_mailcow/cli.py \
       packages/kctl-mailcow/pyproject.toml
git commit -m "feat(kctl-mailcow): add provision sync command (Authentik → Mailcow)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Phase 2 — Security & Compliance (6 command groups)

**Files:**
- Create: `packages/kctl-mailcow/src/kctl_mailcow/commands/fail2ban.py`
- Create: `packages/kctl-mailcow/src/kctl_mailcow/commands/policies.py`
- Create: `packages/kctl-mailcow/src/kctl_mailcow/commands/app_passwords.py`
- Create: `packages/kctl-mailcow/src/kctl_mailcow/commands/password_policy.py`
- Create: `packages/kctl-mailcow/src/kctl_mailcow/commands/domain_admins.py`
- Create: `packages/kctl-mailcow/src/kctl_mailcow/commands/filters.py`
- Modify: `packages/kctl-mailcow/src/kctl_mailcow/cli.py`

- [ ] **Step 1: Create fail2ban.py**

```python
"""Fail2ban management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage fail2ban bans.")


@app.command()
def status(ctx: typer.Context) -> None:
    """Show fail2ban status and banned IPs."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("fail2ban")
    item = data if isinstance(data, dict) else {}

    if not item:
        c.output.info("No fail2ban data available.")
        if c.json_mode:
            c.output.raw_json({})
        return

    banned = item.get("banned", [])
    sections = [
        ("Fail2ban Status", [
            ("Active Bans", str(len(banned))),
            ("Ban Time", str(item.get("ban_time", ""))),
            ("Max Attempts", str(item.get("max_attempts", ""))),
            ("Retry Window", str(item.get("retry_window", ""))),
        ]),
    ]
    if banned:
        sections.append(("Banned IPs", [(ip, "") for ip in banned[:50]]))

    c.output.detail("Fail2ban", sections, data_for_json=item)


@app.command()
def ban(
    ctx: typer.Context,
    ip: Annotated[str, typer.Argument(help="IP address to ban")],
) -> None:
    """Ban an IP address."""
    c: AppContext = ctx.obj
    result = c.client.mc_edit("fail2ban", {"attr": {"ban_ip": ip}})
    handle_result(c, result, f"IP '{ip}' banned")


@app.command()
def unban(
    ctx: typer.Context,
    ip: Annotated[str, typer.Argument(help="IP address to unban")],
) -> None:
    """Unban an IP address."""
    c: AppContext = ctx.obj
    result = c.client.mc_edit("fail2ban", {"attr": {"unban_ip": ip}})
    handle_result(c, result, f"IP '{ip}' unbanned")
```

- [ ] **Step 2: Create policies.py**

```python
"""Spam whitelist/blacklist policy management."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage spam whitelist/blacklist policies.")


@app.command("list")
def list_(
    ctx: typer.Context,
    domain: Annotated[str | None, typer.Option("--domain", "-d", help="Filter by domain")] = None,
    mailbox: Annotated[str | None, typer.Option("--mailbox", "-m", help="Filter by mailbox")] = None,
) -> None:
    """List whitelist/blacklist policies."""
    c: AppContext = ctx.obj
    all_items: list[dict] = []

    if domain:
        for ptype in ("wl", "bl"):
            data = c.client.mc_get(f"policy_{ptype}_domain/{domain}")
            if isinstance(data, list):
                for item in data:
                    item["_policy_type"] = "whitelist" if ptype == "wl" else "blacklist"
                    item["_scope"] = "domain"
                all_items.extend(data)
    elif mailbox:
        for ptype in ("wl", "bl"):
            data = c.client.mc_get(f"policy_{ptype}_mailbox/{mailbox}")
            if isinstance(data, list):
                for item in data:
                    item["_policy_type"] = "whitelist" if ptype == "wl" else "blacklist"
                    item["_scope"] = "mailbox"
                all_items.extend(data)
    else:
        c.output.error("Specify --domain or --mailbox")
        raise typer.Exit(1)

    if not all_items:
        c.output.info("No policies found.")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for item in all_items:
        rows.append([
            str(item.get("prefid", "")),
            item.get("_policy_type", ""),
            item.get("_scope", ""),
            item.get("object", ""),
            item.get("value", ""),
        ])

    c.output.table(
        "Policies",
        [("ID", "dim"), ("Type", "cyan"), ("Scope", ""), ("Object", ""), ("Value", "")],
        rows,
        data_for_json=all_items,
    )


@app.command("add-whitelist")
def add_whitelist(
    ctx: typer.Context,
    object_: Annotated[str, typer.Argument(help="Domain or mailbox to apply policy to")],
    value: Annotated[str, typer.Argument(help="Address/domain to whitelist")],
) -> None:
    """Add a whitelist entry."""
    c: AppContext = ctx.obj
    payload = {"object": object_, "value": value, "type": "wl"}
    result = c.client.mc_add("domain-policy", payload)
    handle_result(c, result, f"Whitelist added: {value} for {object_}")


@app.command("add-blacklist")
def add_blacklist(
    ctx: typer.Context,
    object_: Annotated[str, typer.Argument(help="Domain or mailbox to apply policy to")],
    value: Annotated[str, typer.Argument(help="Address/domain to blacklist")],
) -> None:
    """Add a blacklist entry."""
    c: AppContext = ctx.obj
    payload = {"object": object_, "value": value, "type": "bl"}
    result = c.client.mc_add("domain-policy", payload)
    handle_result(c, result, f"Blacklist added: {value} for {object_}")


@app.command()
def delete(
    ctx: typer.Context,
    policy_id: Annotated[str, typer.Argument(help="Policy ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a policy entry."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete policy {policy_id}?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("domain-policy", [policy_id])
    handle_result(c, result, f"Policy {policy_id} deleted")
```

- [ ] **Step 3: Create app_passwords.py**

```python
"""Per-mailbox application password management."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage per-mailbox app passwords.")


@app.command("list")
def list_(
    ctx: typer.Context,
    mailbox: Annotated[str | None, typer.Option("--mailbox", "-m", help="Filter by mailbox")] = None,
) -> None:
    """List app passwords."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("app-passwd/all")
    items = data if isinstance(data, list) else []

    if mailbox:
        items = [p for p in items if p.get("mailbox", "") == mailbox]

    if not items:
        c.output.info("No app passwords found.")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for item in items:
        active = "[green]yes[/green]" if str(item.get("active")) == "1" else "[red]no[/red]"
        rows.append([
            str(item.get("id", "")),
            item.get("mailbox", ""),
            item.get("name", ""),
            active,
            item.get("created", ""),
        ])

    c.output.table(
        "App Passwords",
        [("ID", "dim"), ("Mailbox", "cyan"), ("Name", ""), ("Active", ""), ("Created", "dim")],
        rows,
        data_for_json=items,
    )


@app.command()
def create(
    ctx: typer.Context,
    mailbox: Annotated[str, typer.Argument(help="Mailbox email address")],
    name: Annotated[str, typer.Option("--name", "-n", help="App password name/label")],
    password: Annotated[str, typer.Option("--password", prompt=True, hide_input=True, help="App password")],
    active: Annotated[bool, typer.Option("--active/--inactive")] = True,
) -> None:
    """Create an app password for a mailbox."""
    c: AppContext = ctx.obj
    payload = {
        "username": mailbox,
        "name": name,
        "password": password,
        "password2": password,
        "active": "1" if active else "0",
    }
    result = c.client.mc_add("app-passwd", payload)
    handle_result(c, result, f"App password '{name}' created for {mailbox}")


@app.command()
def delete(
    ctx: typer.Context,
    password_id: Annotated[str, typer.Argument(help="App password ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete an app password."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete app password {password_id}?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("app-passwd", [password_id])
    handle_result(c, result, f"App password {password_id} deleted")
```

- [ ] **Step 4: Create password_policy.py**

```python
"""Global password policy management."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage global password policy.")


@app.command()
def get(ctx: typer.Context) -> None:
    """Show current password policy."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("passwordpolicy")
    item = data if isinstance(data, dict) else {}

    sections = [
        ("Password Policy", [
            ("Min Length", str(item.get("min_length", ""))),
            ("Min Uppercase", str(item.get("min_upper", ""))),
            ("Min Lowercase", str(item.get("min_lower", ""))),
            ("Min Digits", str(item.get("min_num", ""))),
            ("Min Special", str(item.get("min_special", ""))),
        ])
    ]
    c.output.detail("Password Policy", sections, data_for_json=item)


@app.command("set")
def set_(
    ctx: typer.Context,
    min_length: Annotated[int | None, typer.Option("--min-length", help="Minimum password length")] = None,
    min_upper: Annotated[int | None, typer.Option("--min-upper", help="Minimum uppercase characters")] = None,
    min_lower: Annotated[int | None, typer.Option("--min-lower", help="Minimum lowercase characters")] = None,
    min_num: Annotated[int | None, typer.Option("--min-num", help="Minimum digits")] = None,
    min_special: Annotated[int | None, typer.Option("--min-special", help="Minimum special characters")] = None,
) -> None:
    """Set password policy rules."""
    c: AppContext = ctx.obj
    attr: dict = {}
    if min_length is not None:
        attr["min_length"] = min_length
    if min_upper is not None:
        attr["min_upper"] = min_upper
    if min_lower is not None:
        attr["min_lower"] = min_lower
    if min_num is not None:
        attr["min_num"] = min_num
    if min_special is not None:
        attr["min_special"] = min_special

    if not attr:
        c.output.warn("No fields to update")
        raise typer.Exit(0)

    result = c.client.mc_edit("passwordpolicy", {"attr": attr})
    handle_result(c, result, "Password policy updated")
```

- [ ] **Step 5: Create domain_admins.py**

```python
"""Domain admin management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage domain administrators.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all domain admins."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("domain-admin/all")
    items = data if isinstance(data, list) else []

    if not items:
        c.output.info("No domain admins found.")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for item in items:
        active = "[green]yes[/green]" if str(item.get("active")) == "1" else "[red]no[/red]"
        domains = ", ".join(item.get("selected_domains", []))
        rows.append([item.get("username", ""), domains, active])

    c.output.table(
        "Domain Admins",
        [("Username", "cyan"), ("Domains", ""), ("Active", "")],
        rows,
        data_for_json=items,
    )


@app.command()
def get(
    ctx: typer.Context,
    username: Annotated[str, typer.Argument(help="Admin username")],
) -> None:
    """Get domain admin details."""
    c: AppContext = ctx.obj
    data = c.client.mc_get(f"domain-admin/{username}")
    item = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else {}

    if not item:
        c.output.error(f"Domain admin not found: {username}")
        raise typer.Exit(1)

    sections = [
        ("Domain Admin", [
            ("Username", str(item.get("username", ""))),
            ("Domains", ", ".join(item.get("selected_domains", []))),
            ("Active", str(item.get("active", ""))),
            ("Created", str(item.get("created", ""))),
        ])
    ]
    c.output.detail(f"Domain Admin: {username}", sections, data_for_json=item)


@app.command()
def create(
    ctx: typer.Context,
    username: Annotated[str, typer.Argument(help="Admin username")],
    password: Annotated[str, typer.Option("--password", prompt=True, hide_input=True)],
    domains: Annotated[str, typer.Option("--domains", help="Comma-separated domain list")],
    active: Annotated[bool, typer.Option("--active/--inactive")] = True,
) -> None:
    """Create a domain admin."""
    c: AppContext = ctx.obj
    payload = {
        "username": username,
        "password": password,
        "password2": password,
        "domains": domains,
        "active": "1" if active else "0",
    }
    result = c.client.mc_add("domain-admin", payload)
    handle_result(c, result, f"Domain admin '{username}' created")


@app.command()
def update(
    ctx: typer.Context,
    username: Annotated[str, typer.Argument(help="Admin username")],
    password: Annotated[str | None, typer.Option("--password")] = None,
    domains: Annotated[str | None, typer.Option("--domains")] = None,
    active: Annotated[bool | None, typer.Option("--active/--inactive")] = None,
) -> None:
    """Update domain admin settings."""
    c: AppContext = ctx.obj
    attr: dict = {}
    if password is not None:
        attr["password"] = password
        attr["password2"] = password
    if domains is not None:
        attr["domains"] = domains
    if active is not None:
        attr["active"] = "1" if active else "0"

    if not attr:
        c.output.warn("No fields to update")
        raise typer.Exit(0)

    payload = {"items": [username], "attr": attr}
    result = c.client.mc_edit("domain-admin", payload)
    handle_result(c, result, f"Domain admin '{username}' updated")


@app.command()
def delete(
    ctx: typer.Context,
    username: Annotated[str, typer.Argument(help="Admin username")],
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Delete a domain admin."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete domain admin '{username}'?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("domain-admin", [username])
    handle_result(c, result, f"Domain admin '{username}' deleted")
```

- [ ] **Step 6: Create filters.py**

```python
"""Per-mailbox Sieve filter management."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage per-mailbox Sieve filters.")


@app.command("list")
def list_(
    ctx: typer.Context,
    mailbox: Annotated[str, typer.Argument(help="Mailbox email address")],
) -> None:
    """List Sieve filters for a mailbox."""
    c: AppContext = ctx.obj
    data = c.client.mc_get(f"filters/{mailbox}")
    items = data if isinstance(data, list) else []

    if not items:
        c.output.info(f"No filters for {mailbox}.")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for item in items:
        active = "[green]yes[/green]" if str(item.get("active")) == "1" else "[red]no[/red]"
        rows.append([
            str(item.get("id", "")),
            item.get("script_desc", ""),
            active,
        ])

    c.output.table(
        f"Filters: {mailbox}",
        [("ID", "dim"), ("Description", "cyan"), ("Active", "")],
        rows,
        data_for_json=items,
    )


@app.command()
def create(
    ctx: typer.Context,
    mailbox: Annotated[str, typer.Argument(help="Mailbox email address")],
    script_desc: Annotated[str, typer.Option("--desc", help="Filter description")],
    script_data: Annotated[str, typer.Option("--script", help="Sieve script content or @filepath")],
    active: Annotated[bool, typer.Option("--active/--inactive")] = True,
) -> None:
    """Create a Sieve filter for a mailbox."""
    c: AppContext = ctx.obj

    # Support @filepath for script content
    if script_data.startswith("@"):
        from pathlib import Path
        path = Path(script_data[1:])
        if not path.exists():
            c.output.error(f"File not found: {path}")
            raise typer.Exit(1)
        script_data = path.read_text()

    payload = {
        "username": mailbox,
        "script_desc": script_desc,
        "script_data": script_data,
        "active": "1" if active else "0",
    }
    result = c.client.mc_add("filter", payload)
    handle_result(c, result, f"Filter '{script_desc}' created for {mailbox}")


@app.command()
def update(
    ctx: typer.Context,
    filter_id: Annotated[str, typer.Argument(help="Filter ID")],
    script_desc: Annotated[str | None, typer.Option("--desc")] = None,
    script_data: Annotated[str | None, typer.Option("--script")] = None,
    active: Annotated[bool | None, typer.Option("--active/--inactive")] = None,
) -> None:
    """Update a Sieve filter."""
    c: AppContext = ctx.obj
    attr: dict = {}
    if script_desc is not None:
        attr["script_desc"] = script_desc
    if script_data is not None:
        if script_data.startswith("@"):
            from pathlib import Path
            path = Path(script_data[1:])
            if not path.exists():
                c.output.error(f"File not found: {path}")
                raise typer.Exit(1)
            script_data = path.read_text()
        attr["script_data"] = script_data
    if active is not None:
        attr["active"] = "1" if active else "0"

    if not attr:
        c.output.warn("No fields to update")
        raise typer.Exit(0)

    payload = {"items": [filter_id], "attr": attr}
    result = c.client.mc_edit("filter", payload)
    handle_result(c, result, f"Filter {filter_id} updated")


@app.command()
def delete(
    ctx: typer.Context,
    filter_id: Annotated[str, typer.Argument(help="Filter ID")],
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Delete a Sieve filter."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete filter {filter_id}?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("filter", [filter_id])
    handle_result(c, result, f"Filter {filter_id} deleted")
```

- [ ] **Step 7: Register all 6 groups in cli.py**

```python
from kctl_mailcow.commands.fail2ban import app as fail2ban_app
from kctl_mailcow.commands.policies import app as policies_app
from kctl_mailcow.commands.app_passwords import app as app_passwords_app
from kctl_mailcow.commands.password_policy import app as password_policy_app
from kctl_mailcow.commands.domain_admins import app as domain_admins_app
from kctl_mailcow.commands.filters import app as filters_app

app.add_typer(fail2ban_app, name="fail2ban")
app.add_typer(policies_app, name="policies")
app.add_typer(app_passwords_app, name="app-passwords")
app.add_typer(password_policy_app, name="password-policy")
app.add_typer(domain_admins_app, name="domain-admins")
app.add_typer(filters_app, name="filters")
```

- [ ] **Step 8: Verify all 6 load**

```bash
for g in fail2ban policies app-passwords password-policy domain-admins filters; do
    uv run kctl-mailcow $g --help || echo "FAILED: $g"
done
```

- [ ] **Step 9: Commit**

```bash
git add packages/kctl-mailcow/src/kctl_mailcow/commands/{fail2ban,policies,app_passwords,password_policy,domain_admins,filters}.py \
       packages/kctl-mailcow/src/kctl_mailcow/cli.py
git commit -m "feat(kctl-mailcow): add Phase 2 — security & compliance commands (6 groups)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Phase 3 — Routing & Advanced (6 command groups)

**Files:**
- Create: `packages/kctl-mailcow/src/kctl_mailcow/commands/transports.py`
- Create: `packages/kctl-mailcow/src/kctl_mailcow/commands/relay_hosts.py`
- Create: `packages/kctl-mailcow/src/kctl_mailcow/commands/bcc_maps.py`
- Create: `packages/kctl-mailcow/src/kctl_mailcow/commands/alias_domains.py`
- Create: `packages/kctl-mailcow/src/kctl_mailcow/commands/recipient_maps.py`
- Create: `packages/kctl-mailcow/src/kctl_mailcow/commands/rspamd.py`
- Modify: `packages/kctl-mailcow/src/kctl_mailcow/cli.py`

- [ ] **Step 1: Create transports.py**

```python
"""Outbound mail transport routing."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage outbound transport maps.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all transport maps."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("transport/all")
    items = data if isinstance(data, list) else []

    if not items:
        c.output.info("No transport maps configured.")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for item in items:
        active = "[green]yes[/green]" if str(item.get("active")) == "1" else "[red]no[/red]"
        rows.append([
            str(item.get("id", "")),
            item.get("destination", ""),
            item.get("nexthop", ""),
            active,
        ])

    c.output.table(
        "Transport Maps",
        [("ID", "dim"), ("Destination", "cyan"), ("Next Hop", ""), ("Active", "")],
        rows,
        data_for_json=items,
    )


@app.command()
def get(
    ctx: typer.Context,
    transport_id: Annotated[str, typer.Argument(help="Transport ID")],
) -> None:
    """Get transport map details."""
    c: AppContext = ctx.obj
    data = c.client.mc_get(f"transport/{transport_id}")
    item = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else {}
    if not item:
        c.output.error(f"Transport not found: {transport_id}")
        raise typer.Exit(1)

    sections = [("Transport Map", [
        ("ID", str(item.get("id", ""))),
        ("Destination", str(item.get("destination", ""))),
        ("Next Hop", str(item.get("nexthop", ""))),
        ("Username", str(item.get("username", ""))),
        ("Active", str(item.get("active", ""))),
    ])]
    c.output.detail(f"Transport: {transport_id}", sections, data_for_json=item)


@app.command()
def create(
    ctx: typer.Context,
    destination: Annotated[str, typer.Argument(help="Destination pattern (domain or email)")],
    nexthop: Annotated[str, typer.Option("--nexthop", help="Next hop server (host:port)")],
    username: Annotated[str | None, typer.Option("--username", help="Auth username")] = None,
    password: Annotated[str | None, typer.Option("--password", help="Auth password")] = None,
    active: Annotated[bool, typer.Option("--active/--inactive")] = True,
) -> None:
    """Create a transport map."""
    c: AppContext = ctx.obj
    payload: dict = {
        "destination": destination,
        "nexthop": nexthop,
        "active": "1" if active else "0",
    }
    if username:
        payload["username"] = username
    if password:
        payload["password"] = password
    result = c.client.mc_add("transport", payload)
    handle_result(c, result, f"Transport '{destination}' → '{nexthop}' created")


@app.command()
def update(
    ctx: typer.Context,
    transport_id: Annotated[str, typer.Argument(help="Transport ID")],
    destination: Annotated[str | None, typer.Option("--destination")] = None,
    nexthop: Annotated[str | None, typer.Option("--nexthop")] = None,
    username: Annotated[str | None, typer.Option("--username")] = None,
    password: Annotated[str | None, typer.Option("--password")] = None,
    active: Annotated[bool | None, typer.Option("--active/--inactive")] = None,
) -> None:
    """Update a transport map."""
    c: AppContext = ctx.obj
    attr: dict = {}
    if destination is not None:
        attr["destination"] = destination
    if nexthop is not None:
        attr["nexthop"] = nexthop
    if username is not None:
        attr["username"] = username
    if password is not None:
        attr["password"] = password
    if active is not None:
        attr["active"] = "1" if active else "0"
    if not attr:
        c.output.warn("No fields to update")
        raise typer.Exit(0)

    result = c.client.mc_edit("transport", {"items": [transport_id], "attr": attr})
    handle_result(c, result, f"Transport {transport_id} updated")


@app.command()
def delete(
    ctx: typer.Context,
    transport_id: Annotated[str, typer.Argument(help="Transport ID")],
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Delete a transport map."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete transport {transport_id}?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("transport", [transport_id])
    handle_result(c, result, f"Transport {transport_id} deleted")
```

- [ ] **Step 2: Create relay_hosts.py**

```python
"""Sender-dependent relay host management."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage sender-dependent relay hosts.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all relay hosts."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("relayhost/all")
    items = data if isinstance(data, list) else []
    if not items:
        c.output.info("No relay hosts configured.")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for item in items:
        active = "[green]yes[/green]" if str(item.get("active")) == "1" else "[red]no[/red]"
        rows.append([str(item.get("id", "")), item.get("hostname", ""), str(item.get("used_by_domains", "")), active])

    c.output.table("Relay Hosts", [("ID", "dim"), ("Hostname", "cyan"), ("Used By", ""), ("Active", "")], rows, data_for_json=items)


@app.command()
def get(ctx: typer.Context, relay_id: Annotated[str, typer.Argument(help="Relay host ID")]) -> None:
    """Get relay host details."""
    c: AppContext = ctx.obj
    data = c.client.mc_get(f"relayhost/{relay_id}")
    item = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else {}
    if not item:
        c.output.error(f"Relay host not found: {relay_id}")
        raise typer.Exit(1)
    sections = [("Relay Host", [(k, str(v)) for k, v in item.items()])]
    c.output.detail(f"Relay Host: {relay_id}", sections, data_for_json=item)


@app.command()
def create(
    ctx: typer.Context,
    hostname: Annotated[str, typer.Argument(help="Relay hostname:port")],
    username: Annotated[str | None, typer.Option("--username")] = None,
    password: Annotated[str | None, typer.Option("--password")] = None,
    active: Annotated[bool, typer.Option("--active/--inactive")] = True,
) -> None:
    """Create a relay host."""
    c: AppContext = ctx.obj
    payload: dict = {"hostname": hostname, "active": "1" if active else "0"}
    if username:
        payload["username"] = username
    if password:
        payload["password"] = password
    result = c.client.mc_add("relayhost", payload)
    handle_result(c, result, f"Relay host '{hostname}' created")


@app.command()
def update(
    ctx: typer.Context,
    relay_id: Annotated[str, typer.Argument(help="Relay host ID")],
    hostname: Annotated[str | None, typer.Option("--hostname")] = None,
    username: Annotated[str | None, typer.Option("--username")] = None,
    password: Annotated[str | None, typer.Option("--password")] = None,
    active: Annotated[bool | None, typer.Option("--active/--inactive")] = None,
) -> None:
    """Update a relay host."""
    c: AppContext = ctx.obj
    attr: dict = {}
    if hostname is not None:
        attr["hostname"] = hostname
    if username is not None:
        attr["username"] = username
    if password is not None:
        attr["password"] = password
    if active is not None:
        attr["active"] = "1" if active else "0"
    if not attr:
        c.output.warn("No fields to update")
        raise typer.Exit(0)
    result = c.client.mc_edit("relayhost", {"items": [relay_id], "attr": attr})
    handle_result(c, result, f"Relay host {relay_id} updated")


@app.command()
def delete(ctx: typer.Context, relay_id: Annotated[str, typer.Argument(help="Relay host ID")], force: Annotated[bool, typer.Option("--force")] = False) -> None:
    """Delete a relay host."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete relay host {relay_id}?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("relayhost", [relay_id])
    handle_result(c, result, f"Relay host {relay_id} deleted")
```

- [ ] **Step 3: Create bcc_maps.py**

```python
"""BCC map management for compliance copies."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage BCC maps (compliance copies).")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all BCC maps."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("bcc/all")
    items = data if isinstance(data, list) else []
    if not items:
        c.output.info("No BCC maps configured.")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for item in items:
        active = "[green]yes[/green]" if str(item.get("active")) == "1" else "[red]no[/red]"
        rows.append([str(item.get("id", "")), item.get("local_dest", ""), item.get("bcc_dest", ""), item.get("type", ""), active])

    c.output.table("BCC Maps", [("ID", "dim"), ("Source", "cyan"), ("BCC To", ""), ("Type", ""), ("Active", "")], rows, data_for_json=items)


@app.command()
def create(
    ctx: typer.Context,
    local_dest: Annotated[str, typer.Argument(help="Source address/domain to BCC from")],
    bcc_dest: Annotated[str, typer.Argument(help="BCC destination address")],
    bcc_type: Annotated[str, typer.Option("--type", help="sender or rcpt")] = "sender",
    active: Annotated[bool, typer.Option("--active/--inactive")] = True,
) -> None:
    """Create a BCC map."""
    c: AppContext = ctx.obj
    payload = {"local_dest": local_dest, "bcc_dest": bcc_dest, "type": bcc_type, "active": "1" if active else "0"}
    result = c.client.mc_add("bcc", payload)
    handle_result(c, result, f"BCC map '{local_dest}' → '{bcc_dest}' created")


@app.command()
def update(
    ctx: typer.Context,
    bcc_id: Annotated[str, typer.Argument(help="BCC map ID")],
    local_dest: Annotated[str | None, typer.Option("--local-dest")] = None,
    bcc_dest: Annotated[str | None, typer.Option("--bcc-dest")] = None,
    bcc_type: Annotated[str | None, typer.Option("--type")] = None,
    active: Annotated[bool | None, typer.Option("--active/--inactive")] = None,
) -> None:
    """Update a BCC map."""
    c: AppContext = ctx.obj
    attr: dict = {}
    if local_dest is not None:
        attr["local_dest"] = local_dest
    if bcc_dest is not None:
        attr["bcc_dest"] = bcc_dest
    if bcc_type is not None:
        attr["type"] = bcc_type
    if active is not None:
        attr["active"] = "1" if active else "0"
    if not attr:
        c.output.warn("No fields to update")
        raise typer.Exit(0)
    result = c.client.mc_edit("bcc", {"items": [bcc_id], "attr": attr})
    handle_result(c, result, f"BCC map {bcc_id} updated")


@app.command()
def delete(ctx: typer.Context, bcc_id: Annotated[str, typer.Argument(help="BCC map ID")], force: Annotated[bool, typer.Option("--force")] = False) -> None:
    """Delete a BCC map."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete BCC map {bcc_id}?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("bcc", [bcc_id])
    handle_result(c, result, f"BCC map {bcc_id} deleted")
```

- [ ] **Step 4: Create alias_domains.py**

```python
"""Whole-domain alias management."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage domain aliases (whole-domain aliasing).")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all domain aliases."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("alias-domain/all")
    items = data if isinstance(data, list) else []
    if not items:
        c.output.info("No domain aliases configured.")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for item in items:
        active = "[green]yes[/green]" if str(item.get("active")) == "1" else "[red]no[/red]"
        rows.append([item.get("alias_domain", ""), item.get("target_domain", ""), active])

    c.output.table("Domain Aliases", [("Alias Domain", "cyan"), ("Target Domain", ""), ("Active", "")], rows, data_for_json=items)


@app.command()
def create(
    ctx: typer.Context,
    alias_domain: Annotated[str, typer.Argument(help="Alias domain name")],
    target_domain: Annotated[str, typer.Argument(help="Target domain name")],
    active: Annotated[bool, typer.Option("--active/--inactive")] = True,
) -> None:
    """Create a domain alias."""
    c: AppContext = ctx.obj
    payload = {"alias_domain": alias_domain, "target_domain": target_domain, "active": "1" if active else "0"}
    result = c.client.mc_add("alias-domain", payload)
    handle_result(c, result, f"Domain alias '{alias_domain}' → '{target_domain}' created")


@app.command()
def update(
    ctx: typer.Context,
    alias_domain: Annotated[str, typer.Argument(help="Alias domain")],
    target_domain: Annotated[str | None, typer.Option("--target-domain")] = None,
    active: Annotated[bool | None, typer.Option("--active/--inactive")] = None,
) -> None:
    """Update a domain alias."""
    c: AppContext = ctx.obj
    attr: dict = {}
    if target_domain is not None:
        attr["target_domain"] = target_domain
    if active is not None:
        attr["active"] = "1" if active else "0"
    if not attr:
        c.output.warn("No fields to update")
        raise typer.Exit(0)
    result = c.client.mc_edit("alias-domain", {"items": [alias_domain], "attr": attr})
    handle_result(c, result, f"Domain alias '{alias_domain}' updated")


@app.command()
def delete(ctx: typer.Context, alias_domain: Annotated[str, typer.Argument(help="Alias domain")], force: Annotated[bool, typer.Option("--force")] = False) -> None:
    """Delete a domain alias."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete domain alias '{alias_domain}'?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("alias-domain", [alias_domain])
    handle_result(c, result, f"Domain alias '{alias_domain}' deleted")
```

- [ ] **Step 5: Create recipient_maps.py**

```python
"""Inbound recipient map management."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage recipient maps (inbound address rewriting).")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all recipient maps."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("recipient_map/all")
    items = data if isinstance(data, list) else []
    if not items:
        c.output.info("No recipient maps configured.")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for item in items:
        active = "[green]yes[/green]" if str(item.get("active")) == "1" else "[red]no[/red]"
        rows.append([str(item.get("id", "")), item.get("old_dest", ""), item.get("new_dest", ""), active])

    c.output.table("Recipient Maps", [("ID", "dim"), ("Old Dest", "cyan"), ("New Dest", ""), ("Active", "")], rows, data_for_json=items)


@app.command()
def create(
    ctx: typer.Context,
    old_dest: Annotated[str, typer.Argument(help="Original recipient address")],
    new_dest: Annotated[str, typer.Argument(help="New recipient address")],
    active: Annotated[bool, typer.Option("--active/--inactive")] = True,
) -> None:
    """Create a recipient map."""
    c: AppContext = ctx.obj
    payload = {"old_dest": old_dest, "new_dest": new_dest, "active": "1" if active else "0"}
    result = c.client.mc_add("recipient_map", payload)
    handle_result(c, result, f"Recipient map '{old_dest}' → '{new_dest}' created")


@app.command()
def delete(ctx: typer.Context, map_id: Annotated[str, typer.Argument(help="Recipient map ID")], force: Annotated[bool, typer.Option("--force")] = False) -> None:
    """Delete a recipient map."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete recipient map {map_id}?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("recipient_map", [map_id])
    handle_result(c, result, f"Recipient map {map_id} deleted")
```

- [ ] **Step 6: Create rspamd.py**

```python
"""Rspamd settings management (spam filter tuning)."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage rspamd filter settings.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all rspamd settings."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("rsetting/all")
    items = data if isinstance(data, list) else []
    if not items:
        c.output.info("No rspamd settings configured.")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for item in items:
        active = "[green]yes[/green]" if str(item.get("active")) == "1" else "[red]no[/red]"
        rows.append([str(item.get("id", "")), item.get("desc", ""), item.get("content", "")[:60], active])

    c.output.table("Rspamd Settings", [("ID", "dim"), ("Description", "cyan"), ("Content", "dim"), ("Active", "")], rows, data_for_json=items)


@app.command()
def create(
    ctx: typer.Context,
    desc: Annotated[str, typer.Option("--desc", help="Setting description")],
    content: Annotated[str, typer.Option("--content", help="Rspamd setting content or @filepath")],
    active: Annotated[bool, typer.Option("--active/--inactive")] = True,
) -> None:
    """Create an rspamd setting."""
    c: AppContext = ctx.obj
    if content.startswith("@"):
        from pathlib import Path
        path = Path(content[1:])
        if not path.exists():
            c.output.error(f"File not found: {path}")
            raise typer.Exit(1)
        content = path.read_text()

    payload = {"desc": desc, "content": content, "active": "1" if active else "0"}
    result = c.client.mc_add("rsetting", payload)
    handle_result(c, result, f"Rspamd setting '{desc}' created")


@app.command()
def update(
    ctx: typer.Context,
    setting_id: Annotated[str, typer.Argument(help="Setting ID")],
    desc: Annotated[str | None, typer.Option("--desc")] = None,
    content: Annotated[str | None, typer.Option("--content")] = None,
    active: Annotated[bool | None, typer.Option("--active/--inactive")] = None,
) -> None:
    """Update an rspamd setting."""
    c: AppContext = ctx.obj
    attr: dict = {}
    if desc is not None:
        attr["desc"] = desc
    if content is not None:
        if content.startswith("@"):
            from pathlib import Path
            path = Path(content[1:])
            if not path.exists():
                c.output.error(f"File not found: {path}")
                raise typer.Exit(1)
            content = path.read_text()
        attr["content"] = content
    if active is not None:
        attr["active"] = "1" if active else "0"
    if not attr:
        c.output.warn("No fields to update")
        raise typer.Exit(0)
    result = c.client.mc_edit("rsetting", {"items": [setting_id], "attr": attr})
    handle_result(c, result, f"Rspamd setting {setting_id} updated")


@app.command()
def delete(ctx: typer.Context, setting_id: Annotated[str, typer.Argument(help="Setting ID")], force: Annotated[bool, typer.Option("--force")] = False) -> None:
    """Delete an rspamd setting."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete rspamd setting {setting_id}?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("rsetting", [setting_id])
    handle_result(c, result, f"Rspamd setting {setting_id} deleted")
```

- [ ] **Step 7: Register all 6 groups in cli.py**

```python
from kctl_mailcow.commands.transports import app as transports_app
from kctl_mailcow.commands.relay_hosts import app as relay_hosts_app
from kctl_mailcow.commands.bcc_maps import app as bcc_maps_app
from kctl_mailcow.commands.alias_domains import app as alias_domains_app
from kctl_mailcow.commands.recipient_maps import app as recipient_maps_app
from kctl_mailcow.commands.rspamd import app as rspamd_app

app.add_typer(transports_app, name="transports")
app.add_typer(relay_hosts_app, name="relay-hosts")
app.add_typer(bcc_maps_app, name="bcc-maps")
app.add_typer(alias_domains_app, name="alias-domains")
app.add_typer(recipient_maps_app, name="recipient-maps")
app.add_typer(rspamd_app, name="rspamd")
```

- [ ] **Step 8: Verify all 6 load**

```bash
for g in transports relay-hosts bcc-maps alias-domains recipient-maps rspamd; do
    uv run kctl-mailcow $g --help || echo "FAILED: $g"
done
```

- [ ] **Step 9: Commit**

```bash
git add packages/kctl-mailcow/src/kctl_mailcow/commands/{transports,relay_hosts,bcc_maps,alias_domains,recipient_maps,rspamd}.py \
       packages/kctl-mailcow/src/kctl_mailcow/cli.py
git commit -m "feat(kctl-mailcow): add Phase 3 — routing & advanced commands (6 groups)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Update smoke tests, docs, and final validation

**Files:**
- Modify: `packages/kctl-mailcow/tests/test_smoke.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update test_smoke.py — add all 15 new groups**

Update the `GROUPS` list in `TestCommandGroupsRegistered`:

```python
GROUPS = [
    # Original 16
    "domains", "mailboxes", "aliases", "dkim", "queue", "logs",
    "ratelimits", "quarantine", "status", "health", "dashboard",
    "sync-jobs", "fwdhost", "config", "tls", "resources",
    # Phase 1
    "identity-provider", "oauth2-clients", "provision",
    # Phase 2
    "fail2ban", "policies", "app-passwords", "password-policy",
    "domain-admins", "filters",
    # Phase 3
    "transports", "relay-hosts", "bcc-maps", "alias-domains",
    "recipient-maps", "rspamd",
]
```

- [ ] **Step 2: Run all tests**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
uv run pytest packages/kctl-mailcow/tests/ -v
```

- [ ] **Step 3: Run ruff lint**

```bash
uv run ruff check packages/kctl-mailcow/src/ --fix
```

- [ ] **Step 4: Update CLAUDE.md**

Change kctl-mailcow entry from `(16 groups)` to `(31 groups)`.

- [ ] **Step 5: Reinstall CLI globally**

```bash
uv tool install packages/kctl-mailcow/ --force
kctl-mailcow --help
```

- [ ] **Step 6: Update mailcow-admin skill**

Update `~/.claude/skills/mailcow-admin/SKILL.md` to include all new command groups.

- [ ] **Step 7: Commit and push**

```bash
git add packages/kctl-mailcow/ CLAUDE.md uv.lock
git commit -m "feat(kctl-mailcow): complete Phase 1-3 — 31 command groups, Authentik integration

Co-Authored-By: Claude <noreply@anthropic.com>"
git push
```
