"""User provisioning with role-based group assignment."""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_ak.core.client import AuthentikClient
from kctl_ak.core.output import Output
from kctl_ak.roles.loader import RoleLoader


@dataclass
class ProvisionResult:
    operation: str = ""
    user_id: int = 0
    email: str = ""
    username: str = ""
    name: str = ""
    roles: list[str] = field(default_factory=list)
    groups_added: list[str] = field(default_factory=list)
    groups_existed: list[str] = field(default_factory=list)
    groups_failed: list[str] = field(default_factory=list)
    recovery_link: str = ""
    password: str = ""


class Provisioner:
    """Provisions users with role-based group assignment."""

    def __init__(self, client: AuthentikClient, role_loader: RoleLoader, output: Output):
        self.client = client
        self.roles = role_loader
        self.output = output

    def provision(
        self,
        email: str,
        role_names: list[str],
        name: str | None = None,
        username: str | None = None,
    ) -> ProvisionResult:
        """Create or update user with roles."""
        groups = self.roles.resolve_groups(role_names)
        if not username:
            username = email.split("@")[0]
        if not name:
            name = username

        result = ProvisionResult(
            email=email,
            username=username,
            name=name,
            roles=role_names,
        )

        # Check if user exists
        existing = self.client.get("core/users/", params={"email": email})
        users = existing.get("results", [])

        if users:
            result.operation = "update"
            result.user_id = users[0]["pk"]
            self.output.info(f"User exists (ID: {result.user_id}), updating groups...")
        else:
            result.operation = "create"
            self.output.info(f"Creating user: {username} ({email})")
            user_data = {
                "username": username,
                "email": email,
                "name": name,
                "is_active": True,
                "is_superuser": False,
            }
            created = self.client.post("core/users/", data=user_data)
            result.user_id = created["pk"]
            self.output.success(f"User created: ID {result.user_id}")

        # Add to groups
        for group_name in groups:
            group_results = self.client.get("core/groups/", params={"name": group_name})
            if not group_results.get("results"):
                result.groups_failed.append(group_name)
                self.output.warn(f"Group not found: {group_name}")
                continue

            group_id = group_results["results"][0]["pk"]
            self.output.info(f"Adding to group: {group_name}")
            try:
                self.client.post(f"core/groups/{group_id}/add_user/", data={"pk": result.user_id})
                result.groups_added.append(group_name)
            except Exception:
                result.groups_existed.append(group_name)

        # Generate recovery link
        try:
            recovery = self.client.post(f"core/users/{result.user_id}/recovery/", data={})
            result.recovery_link = recovery.get("link", "")
        except Exception:
            result.recovery_link = "(recovery flow not configured)"

        return result
