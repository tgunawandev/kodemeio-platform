"""Shared identifier resolution utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from kctl_odoo.core.client import OdooClient


def resolve_id(
    client: OdooClient,
    model: str,
    identifier: str,
    search_field: str = "name",
    label: str | None = None,
    ilike: bool = False,
) -> int:
    """Resolve a numeric ID or name string to an integer record ID.

    If *identifier* is purely digits it is returned as-is (cast to int).
    Otherwise a search is performed on *model* using *search_field*.

    Raises ``typer.Exit(1)`` when the record cannot be found.
    """
    if identifier.isdigit():
        return int(identifier)
    op = "ilike" if ilike else "="
    ids = client.search(model, [(search_field, op, identifier)], limit=1)
    if not ids:
        display = label or model
        typer.echo(f"{display} not found: {identifier}", err=True)
        raise typer.Exit(1)
    return ids[0]


def resolve_user_id(
    client: OdooClient,
    identifier: str,
) -> int:
    """Resolve user by login or numeric ID.

    Supports:
    - Numeric ID: "42"
    - Login string: "admin"

    Raises ``typer.Exit(1)`` when the user cannot be found.
    """
    if identifier.isdigit():
        return int(identifier)
    users = client.search_read(
        "res.users",
        [("login", "=", identifier)],
        fields=["id"],
        limit=1,
    )
    if not users:
        typer.echo(f"User not found: {identifier}", err=True)
        raise typer.Exit(1)
    return users[0]["id"]


def resolve_group_id(
    client: OdooClient,
    identifier: str,
) -> int:
    """Resolve a security group by numeric ID, XML ID, or name.

    Supports:
    - Numeric ID: "42"
    - XML ID: "base.group_user"
    - Name search (ilike on full_name or name)
    """
    if identifier.isdigit():
        return int(identifier)

    # Try XML ID resolution (e.g. base.group_user)
    if "." in identifier:
        parts = identifier.split(".", 1)
        module, xml_id = parts[0], parts[1]
        records = client.search_read(
            "ir.model.data",
            domain=[("module", "=", module), ("name", "=", xml_id), ("model", "=", "res.groups")],
            fields=["res_id"],
            limit=1,
        )
        if records:
            return records[0]["res_id"]

    # Fall back to name search
    ids = client.search(
        "res.groups",
        ["|", ("full_name", "ilike", identifier), ("name", "ilike", identifier)],
        limit=1,
    )
    if not ids:
        typer.echo(f"Group not found: {identifier}", err=True)
        raise typer.Exit(1)
    return ids[0]


def resolve_partner(
    client: OdooClient,
    identifier: str,
) -> int:
    """Resolve a partner by numeric ID or name (ilike).

    Raises ``typer.Exit(1)`` when the partner cannot be found.
    """
    return resolve_id(client, "res.partner", identifier, search_field="name", label="Partner", ilike=True)


def resolve_product(
    client: OdooClient,
    identifier: str,
) -> int:
    """Resolve a product by numeric ID or name (ilike).

    Raises ``typer.Exit(1)`` when the product cannot be found.
    """
    return resolve_id(client, "product.product", identifier, search_field="name", label="Product", ilike=True)


def resolve_account(
    client: OdooClient,
    identifier: str,
) -> int:
    """Resolve an account by numeric ID or account code.

    Raises ``typer.Exit(1)`` when the account cannot be found.
    """
    if identifier.isdigit() and len(identifier) > 4:
        # Likely a code like "11000", not an ID — search by code first
        ids = client.search("account.account", [("code", "=", identifier)], limit=1)
        if ids:
            return ids[0]
    return resolve_id(client, "account.account", identifier, search_field="code", label="Account")


def resolve_journal(
    client: OdooClient,
    identifier: str,
    company_id: int | None = None,
) -> int:
    """Resolve a journal by numeric ID or name (ilike).

    When *company_id* is provided the search is filtered to that company
    first.  If nothing matches with the company filter, falls back to a
    search without it.

    Raises ``typer.Exit(1)`` when the journal cannot be found.
    """
    if identifier.isdigit():
        return int(identifier)

    domain: list = [("name", "ilike", identifier)]
    if company_id:
        domain.append(("company_id", "=", company_id))

    ids = client.search("account.journal", domain, limit=1)
    if ids:
        return ids[0]

    # Fallback without company filter
    return resolve_id(client, "account.journal", identifier, search_field="name", label="Journal", ilike=True)
