"""Shared identifier resolution utilities for API resources."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from kctl_api.core.client import ApiClient


def resolve_user(
    client: ApiClient,
    identifier: str,
) -> dict:
    """Resolve a user by numeric ID or email.

    Returns the full user dict from the API.
    Raises ``typer.Exit(1)`` when the user cannot be found.
    """
    # Try numeric ID first
    if identifier.isdigit():
        try:
            return client.get(f"/api/v1/users/{identifier}")
        except Exception as exc:
            typer.echo(f"User not found: {identifier}", err=True)
            raise typer.Exit(1) from exc

    # Search by email via list endpoint
    data = client.get("/api/v1/users", params={"search": identifier, "per_page": 1})
    items = data.get("items", []) if isinstance(data, dict) else []
    if not items:
        typer.echo(f"User not found: {identifier}", err=True)
        raise typer.Exit(1)
    return items[0]


def resolve_user_id(
    client: ApiClient,
    identifier: str,
) -> int:
    """Resolve a user identifier to a numeric ID."""
    if identifier.isdigit():
        return int(identifier)
    user = resolve_user(client, identifier)
    return user["id"]
