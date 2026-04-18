"""Cloudflare API token management commands.

Wraps the Cloudflare /user/tokens/* API so users can mint, list, inspect,
and delete API tokens from the CLI. Primary use case: minting scoped
tokens for DNS-01 challenges (`lego`, cert-manager) without clicking
through the Cloudflare dashboard.

Note: these endpoints require a parent token with `User.API Tokens.Edit`
permission. When that permission is missing, Cloudflare returns error
code 9109 / HTTP 403 — we catch that and surface a guidance message
pointing users to the one-time dashboard bootstrap.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import typer

from kctl_cf.core.callbacks import AppContext
from kctl_cf.core.exceptions import APIError, AuthenticationError

app = typer.Typer(help="Manage Cloudflare API tokens.")


_GUIDANCE = """\
your current Cloudflare token lacks `User.API Tokens.Edit` permission.

To use `kctl-cf tokens`, first create a parent admin token via the Cloudflare
dashboard (one-time bootstrap):

  https://dash.cloudflare.com/profile/api-tokens → Create Token → Custom token
  Permissions: User > API Tokens > Edit
  Zone Resources: All zones (or a specific zone)

Then update your profile:
  kctl-cf -p <profile> config set api_token <new-token-value>\
"""


def _is_token_permission_error(exc: Exception) -> bool:
    """Heuristic: True if this exception looks like a Cloudflare 9109/403 on /user/tokens/*."""
    detail = str(exc)
    if "9109" in detail:
        return True
    if isinstance(exc, AuthenticationError):
        return True
    if isinstance(exc, APIError):
        if getattr(exc, "status_code", 0) in (401, 403):
            return True
    return False


def _guard_permission(c: AppContext, exc: Exception) -> None:
    """Re-raise a permission error with actionable guidance, else re-raise as-is."""
    if _is_token_permission_error(exc):
        c.output.error(_GUIDANCE)
        raise typer.Exit(1) from exc
    raise exc


def _get_permission_group_ids(c: AppContext, wanted: list[str]) -> dict[str, str]:
    """Fetch permission groups and return a {name: id} mapping for `wanted` names.

    Raises typer.Exit(1) with guidance if any requested group is missing.
    """
    try:
        groups = c.client.get("/user/tokens/permission_groups")
    except Exception as exc:
        _guard_permission(c, exc)
        raise  # pragma: no cover — _guard_permission always raises

    if not isinstance(groups, list):
        groups = []
    by_name = {g.get("name", ""): g.get("id", "") for g in groups if isinstance(g, dict)}
    resolved: dict[str, str] = {}
    missing: list[str] = []
    for name in wanted:
        pg_id = by_name.get(name)
        if pg_id:
            resolved[name] = pg_id
        else:
            missing.append(name)
    if missing:
        c.output.error(f"Could not find permission group(s): {', '.join(missing)}")
        raise typer.Exit(1)
    return resolved


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List API tokens on this account."""
    c: AppContext = ctx.obj
    try:
        tokens = c.client.get("/user/tokens")
    except Exception as exc:
        _guard_permission(c, exc)
        return  # pragma: no cover

    if not isinstance(tokens, list):
        tokens = []
    rows = []
    for t in tokens:
        rows.append(
            [
                t.get("id", ""),
                t.get("name", ""),
                t.get("status", ""),
                (t.get("issued_on") or "")[:19],
                (t.get("expires_on") or "")[:19] or "-",
            ]
        )
    c.output.table(
        "API Tokens",
        [("ID", "cyan"), ("Name", "green"), ("Status", ""), ("Issued", "dim"), ("Expires", "dim")],
        rows,
        data_for_json=tokens,
    )


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Token name (shown in Cloudflare dashboard)")],
    preset: Annotated[
        str | None,
        typer.Option(
            "--preset",
            help="Shortcut for common permission sets. Supported: dns-edit (DNS Write + Zone Read).",
        ),
    ] = None,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name to scope the token to")] = None,
    ttl_days: Annotated[
        int | None,
        typer.Option("--ttl-days", help="Expiry in days from now (default: no expiry)"),
    ] = None,
    permission_group: Annotated[
        list[str] | None,
        typer.Option(
            "--permission-group",
            help="Explicit permission group ID (repeatable). Bypasses --preset lookup.",
        ),
    ] = None,
) -> None:
    """Create a new API token.

    Two modes:

    - `--preset dns-edit --zone <zone>`: expands to DNS Write + Zone Read
      scoped to the named zone. Best for lego / cert-manager bootstrap.
    - `--permission-group <id> [--permission-group <id>...]`: explicit
      permission group IDs (use `tokens permission-groups` to discover them).

    The created token value is printed exactly once — Cloudflare never
    reveals it again. Save it immediately.
    """
    c: AppContext = ctx.obj
    out = c.output

    if not preset and not permission_group:
        raise typer.BadParameter("Must specify either --preset or at least one --permission-group")

    if not zone:
        raise typer.BadParameter("--zone is required")

    # Resolve zone name → zone_id
    try:
        zone_id = c.client.get_zone_id(zone)
    except Exception as exc:
        _guard_permission(c, exc)
        return  # pragma: no cover

    # Resolve permission group IDs
    if permission_group:
        pg_ids = list(permission_group)
    elif preset == "dns-edit":
        groups = _get_permission_group_ids(c, ["DNS Write", "Zone Read"])
        pg_ids = [groups["DNS Write"], groups["Zone Read"]]
    else:
        raise typer.BadParameter(f"Unknown preset: {preset}. Supported: dns-edit")

    payload: dict[str, Any] = {
        "name": name,
        "policies": [
            {
                "effect": "allow",
                "resources": {f"com.cloudflare.api.account.zone.{zone_id}": "*"},
                "permission_groups": [{"id": pg_id} for pg_id in pg_ids],
            }
        ],
    }
    if ttl_days is not None:
        expires = datetime.now(timezone.utc) + timedelta(days=ttl_days)
        # RFC3339 with 'Z' suffix
        payload["expires_on"] = expires.strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        result = c.client.post("/user/tokens", json=payload)
    except Exception as exc:
        _guard_permission(c, exc)
        return  # pragma: no cover

    if not isinstance(result, dict):
        result = {}
    token_value = result.get("value", "")
    token_id = result.get("id", "")

    if c.json_mode:
        # In --quiet JSON mode, mask the value; otherwise include it once.
        emit = dict(result)
        if c.quiet:
            emit["value"] = "****"
        out.raw_json(emit)
        return

    out.header("IMPORTANT: save this value now")
    out.warn("This token will NEVER be shown again. Copy it before closing the terminal.")
    out.text("")
    out.kv("ID", token_id)
    out.kv("Name", name)
    out.kv("Value", token_value)
    out.text("")
    out.success(f"Token created: {token_id}")


@app.command("delete")
def delete_(
    ctx: typer.Context,
    token_id: Annotated[str, typer.Argument(help="Token ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation prompt")] = False,
) -> None:
    """Delete an API token. Prompts for confirmation unless --force is passed."""
    c: AppContext = ctx.obj
    if not force:
        confirmed = typer.confirm(f"Delete token {token_id}? This cannot be undone.", default=False)
        if not confirmed:
            c.output.warn("Aborted")
            raise typer.Exit(1)

    try:
        c.client.delete(f"/user/tokens/{token_id}")
    except Exception as exc:
        _guard_permission(c, exc)
        return  # pragma: no cover

    c.output.success(f"Token deleted: {token_id}")


@app.command("permission-groups")
def permission_groups(
    ctx: typer.Context,
    filter_: Annotated[
        str | None,
        typer.Option("--filter", help="Case-insensitive substring filter on group name"),
    ] = None,
) -> None:
    """List permission groups (for discovering IDs to pass to `create --permission-group`)."""
    c: AppContext = ctx.obj
    try:
        groups = c.client.get("/user/tokens/permission_groups")
    except Exception as exc:
        _guard_permission(c, exc)
        return  # pragma: no cover

    if not isinstance(groups, list):
        groups = []
    if filter_:
        needle = filter_.lower()
        groups = [g for g in groups if isinstance(g, dict) and needle in g.get("name", "").lower()]

    rows = []
    for g in groups:
        scopes = g.get("scopes") or []
        rows.append(
            [
                g.get("id", ""),
                g.get("name", ""),
                ", ".join(str(s) for s in scopes),
            ]
        )
    c.output.table(
        "Permission Groups",
        [("ID", "cyan"), ("Name", "green"), ("Scopes", "dim")],
        rows,
        data_for_json=groups,
    )
