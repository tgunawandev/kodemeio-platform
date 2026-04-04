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
        users = client.get_all("core/users/", params={"groups_by_pk": group_pk, "is_active": "true"})
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
                        mailcow_client.mc_edit(
                            "mailbox",
                            {
                                "items": [target_email],
                                "attr": {"name": name},
                            },
                        )
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
                    pw = _generate_password()
                    mailcow_client.mc_add(
                        "mailbox",
                        {
                            "local_part": local_part,
                            "domain": domain,
                            "name": name or local_part,
                            "password": pw,
                            "password2": pw,
                            "quota": str(default_quota),
                            "active": "1",
                            "force_pw_update": "1",
                            "tls_enforce_in": "0",
                            "tls_enforce_out": "0",
                        },
                    )
                    result.created.append(target_email)
                except Exception as e:
                    result.failed.append((target_email, str(e)))
            else:
                result.created.append(target_email)

    return result
