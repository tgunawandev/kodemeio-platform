"""Identifier resolution for users and groups.

Resolves flexible identifiers (ID, username, email, UUID, group name)
to their API primary keys.
"""

from __future__ import annotations

from kctl_ak.core.client import AuthentikClient
from kctl_ak.core.exceptions import NotFoundError


def resolve_user(client: AuthentikClient, identifier: str) -> int:
    """Resolve a user identifier to a numeric PK.

    Accepts: numeric ID, username, or email.
    """
    # Numeric ID
    if identifier.isdigit():
        return int(identifier)

    # Search by username
    result = client.get("core/users/", params={"username": identifier})
    if result.get("results"):
        return result["results"][0]["pk"]

    # Search by email
    result = client.get("core/users/", params={"email": identifier})
    if result.get("results"):
        return result["results"][0]["pk"]

    # General search
    result = client.get("core/users/", params={"search": identifier})
    if result.get("results"):
        return result["results"][0]["pk"]

    raise NotFoundError("User", identifier)


def resolve_group(client: AuthentikClient, identifier: str) -> str:
    """Resolve a group identifier to a UUID PK.

    Accepts: UUID, numeric ID, or group name.
    """
    # UUID format (8-4-4-4-12)
    if len(identifier) == 36 and identifier.count("-") == 4:
        return identifier

    # Numeric (shouldn't happen for groups but just in case)
    if identifier.isdigit():
        return identifier

    # Search by exact name
    result = client.get("core/groups/", params={"name": identifier})
    if result.get("results"):
        return result["results"][0]["pk"]

    # Search by partial name
    result = client.get("core/groups/", params={"search": identifier})
    if result.get("results"):
        return result["results"][0]["pk"]

    raise NotFoundError("Group", identifier)


def resolve_user_username(client: AuthentikClient, pk: int) -> str:
    """Get username for a user PK."""
    result = client.get(f"core/users/{pk}/")
    return result.get("username", str(pk))
