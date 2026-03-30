"""Token management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_ak.core.callbacks import AppContext
from kctl_ak.core.resolve import resolve_user

app = typer.Typer(name="tokens", help="API token management.")

_ENDPOINT = "core/tokens/"


def _format_token_row(t: dict) -> list[str]:
    """Format a token dict into a table row."""
    user_obj = t.get("user_obj") or {}
    username = user_obj.get("username", str(t.get("user", "-")))
    expires = str(t.get("expires", "-") or "-")[:19].replace("T", " ")
    managed = "Yes" if t.get("managed") else ""
    return [
        t.get("identifier", ""),
        username,
        t.get("intent", ""),
        expires,
        managed,
        t.get("description", "") or "",
    ]


_TOKEN_COLUMNS: list[tuple[str, str]] = [
    ("Identifier", "cyan"),
    ("User", ""),
    ("Intent", "yellow"),
    ("Expires", "green"),
    ("Managed", "dim"),
    ("Description", ""),
]


@app.command("list")
def list_(
    ctx: typer.Context,
    user: Annotated[str | None, typer.Option(help="Filter by user (ID, username, or email).")] = None,
) -> None:
    """List tokens."""
    c: AppContext = ctx.obj
    params: dict = {}
    if user:
        pk = resolve_user(c.client, user)
        params["user"] = pk

    tokens = c.client.get_all(_ENDPOINT, params=params)

    if not tokens:
        c.output.info("No tokens found.")
        return

    rows = [_format_token_row(t) for t in tokens]
    c.output.table(
        f"Tokens ({len(tokens)})",
        _TOKEN_COLUMNS,
        rows,
        data_for_json=tokens,
    )


@app.command()
def get(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Token identifier.")],
) -> None:
    """Show token details (without the key)."""
    c: AppContext = ctx.obj
    t = c.client.get(f"{_ENDPOINT}{identifier}/")

    user_obj = t.get("user_obj") or {}
    username = user_obj.get("username", str(t.get("user", "-")))
    email = user_obj.get("email", "-") if isinstance(user_obj, dict) else "-"
    expires = str(t.get("expires", "-") or "-")[:19].replace("T", " ")

    c.output.detail(
        f"Token: {t.get('identifier', identifier)}",
        [
            (
                "Token",
                [
                    ("Identifier", t.get("identifier", "")),
                    ("Intent", t.get("intent", "")),
                    ("Description", t.get("description", "") or "-"),
                    ("Expiring", "Yes" if t.get("expiring") else "No"),
                    ("Expires", expires),
                    ("Managed", t.get("managed", "") or "-"),
                ],
            ),
            (
                "User",
                [
                    ("Username", username),
                    ("Email", email),
                    ("User PK", str(t.get("user", ""))),
                ],
            ),
        ],
        data_for_json=t,
    )


@app.command()
def create(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Token identifier (unique string).")],
    user: Annotated[str, typer.Argument(help="User (ID, username, or email).")],
    intent: Annotated[str, typer.Option(help="Token intent: api or verification.")] = "api",
    description: Annotated[str | None, typer.Option(help="Token description.")] = None,
) -> None:
    """Create a new token and display the key."""
    c: AppContext = ctx.obj
    pk = resolve_user(c.client, user)

    payload: dict = {
        "identifier": identifier,
        "user": pk,
        "intent": intent,
    }
    if description:
        payload["description"] = description

    t = c.client.post(_ENDPOINT, data=payload)
    c.output.success(f"Token '{identifier}' created.")

    # Retrieve the key
    key_data = c.client.get(f"{_ENDPOINT}{identifier}/view_key/")
    key = key_data.get("key", "")
    if key:
        c.output.info(f"Key: {key}")
    else:
        c.output.warn("Could not retrieve token key.")


@app.command()
def view(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Token identifier.")],
) -> None:
    """View the actual token key."""
    c: AppContext = ctx.obj
    key_data = c.client.get(f"{_ENDPOINT}{identifier}/view_key/")
    key = key_data.get("key", "")

    if c.output.json_mode:
        c.output.raw_json(key_data)
    elif key:
        c.output.info(f"Key for '{identifier}': {key}")
    else:
        c.output.warn("Could not retrieve token key.")


@app.command()
def delete(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Token identifier.")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation.")] = False,
) -> None:
    """Delete a token."""
    c: AppContext = ctx.obj

    if not force:
        confirm = typer.confirm(f"Delete token '{identifier}'?")
        if not confirm:
            c.output.info("Aborted.")
            return

    c.client.delete(f"{_ENDPOINT}{identifier}/")
    c.output.success(f"Token '{identifier}' deleted.")


@app.command()
def rotate(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Token identifier to rotate.")],
) -> None:
    """Rotate a token (delete and recreate with same settings, show new key)."""
    c: AppContext = ctx.obj

    # Get existing token details
    existing = c.client.get(f"{_ENDPOINT}{identifier}/")
    user_pk = existing.get("user", 0)
    intent = existing.get("intent", "api")
    description = existing.get("description", "")

    # Delete the old token
    c.client.delete(f"{_ENDPOINT}{identifier}/")
    c.output.info(f"Old token '{identifier}' deleted.")

    # Recreate with same settings
    payload: dict = {
        "identifier": identifier,
        "user": user_pk,
        "intent": intent,
    }
    if description:
        payload["description"] = description

    c.client.post(_ENDPOINT, data=payload)
    c.output.success(f"Token '{identifier}' recreated.")

    # Show the new key
    key_data = c.client.get(f"{_ENDPOINT}{identifier}/view_key/")
    key = key_data.get("key", "")
    if key:
        c.output.info(f"New key: {key}")
    else:
        c.output.warn("Could not retrieve new token key.")


@app.command("expire-all")
def expire_all(
    ctx: typer.Context,
    user: Annotated[str, typer.Argument(help="User identifier (ID, username, or email).")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation.")] = False,
) -> None:
    """Delete all tokens for a user."""
    c: AppContext = ctx.obj
    pk = resolve_user(c.client, user)
    tokens = c.client.get_all(_ENDPOINT, params={"user": pk})

    if not tokens:
        c.output.info(f"No tokens found for user {user}.")
        return

    # Filter out managed tokens (e.g. system tokens)
    deletable = [t for t in tokens if not t.get("managed")]
    managed_count = len(tokens) - len(deletable)

    if not deletable:
        c.output.info(f"All {len(tokens)} token(s) are managed and cannot be deleted.")
        return

    if managed_count:
        c.output.warn(f"Skipping {managed_count} managed token(s).")

    if not force:
        confirm = typer.confirm(f"Delete {len(deletable)} token(s) for user {user}?")
        if not confirm:
            c.output.info("Aborted.")
            return

    deleted = 0
    for t in deletable:
        ident = t.get("identifier", "")
        if ident:
            c.client.delete(f"{_ENDPOINT}{ident}/")
            deleted += 1

    c.output.success(f"Deleted {deleted} token(s) for user {user}.")
