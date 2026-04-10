"""Staging environment management commands.

Currently provides ``neutralize-staging`` which idempotently neutralizes a
staging Odoo instance that has just been cloned from production so it cannot
leak outbound traffic (email, payments, webhooks) or be mistaken for the real
thing.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Staging environment helpers (neutralize after clone).")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_STAGING_TOKENS = ("stg", "staging")


def _is_staging_db(name: str | None) -> bool:
    """Return True if the database name identifies as staging.

    Matches on clear token boundaries (prefix, suffix, or underscore/hyphen
    separated) to avoid false positives like ``stage_prod`` or
    ``instagram_db``.
    """
    if not name:
        return False
    lowered = name.lower()
    # Prefix match: stg_mac_odoo_erp, staging_anything
    if lowered.startswith(("stg_", "stg-", "staging_", "staging-")):
        return True
    # Suffix match: mac_odoo_erp_stg, mac_odoo_erp_staging
    if lowered.endswith(("_stg", "-stg", "_staging", "-staging")):
        return True
    # Exact match: just 'stg' or 'staging'
    if lowered in _STAGING_TOKENS:
        return True
    # Token-separated anywhere: mac-odoo-erp-stg-clone
    parts = lowered.replace("-", "_").split("_")
    return any(tok in parts for tok in _STAGING_TOKENS)


def _model_exists(client: object, model: str) -> bool:
    """Return True if *model* exists in the target Odoo instance."""
    try:
        client.search_count(model, [("id", "=", 0)])  # type: ignore[attr-defined]
        return True
    except RPCError:
        return False
    except Exception:  # pragma: no cover - defensive for offline / edge cases
        return False


def _get_base_url(client: object) -> str:
    """Return the configured base URL of the Odoo client (best-effort)."""
    url = getattr(client, "_base_url", None) or getattr(client, "base_url", None)
    return str(url or "").rstrip("/")


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


@app.command("neutralize-staging")
def neutralize_staging(
    ctx: typer.Context,
    admin_password: Annotated[
        str | None,
        typer.Option(
            "--admin-password",
            envvar="STG_ADMIN_PASSWORD",
            help="New password for the admin user (required unless already set).",
        ),
    ] = None,
    company_prefix: Annotated[
        str,
        typer.Option("--company-prefix", help="Prefix to add to company names."),
    ] = "[STG] ",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would change without writing."),
    ] = False,
) -> None:
    """Neutralize a staging Odoo instance after cloning from production.

    Safety: refuses to run unless the active profile's database name contains
    ``stg`` or ``staging``.

    Actions (idempotent):
      1. Disable all active ``ir.mail_server`` records
      2. Disable all enabled ``payment.provider`` records
      3. Disable active ``webhook.endpoint`` records (if base_webhook installed)
      4. Prefix company name(s) with ``[STG] `` (unless already prefixed)
      5. Set the admin user's password (if ``--admin-password`` provided)
      6. Update ``web.base.url`` to the current profile URL
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    database = getattr(c, "database", None)
    if not _is_staging_db(database):
        out.error(
            f"Refusing to neutralize: database {database!r} does not contain "
            "'stg' or 'staging'. This command is only safe on staging clones."
        )
        raise typer.Exit(code=2)

    results: list[tuple[str, int, str]] = []  # (item, count, note)

    # 1. Mail servers ---------------------------------------------------------
    mail_ids: list[int] = c.search("ir.mail_server", [("active", "=", True)])
    if mail_ids:
        if not dry_run:
            c.write("ir.mail_server", list(mail_ids), {"active": False})
        results.append(("ir.mail_server disabled", len(mail_ids), "active -> False"))
    else:
        results.append(("ir.mail_server disabled", 0, "already neutralized"))

    # 2. Payment providers ----------------------------------------------------
    try:
        provider_ids: list[int] = c.search(
            "payment.provider",
            [("state", "in", ["enabled", "test"])],
        )
    except RPCError:
        provider_ids = []
        results.append(("payment.provider disabled", 0, "model not available"))
    else:
        if provider_ids:
            if not dry_run:
                c.write("payment.provider", list(provider_ids), {"state": "disabled"})
            results.append(("payment.provider disabled", len(provider_ids), "state -> disabled"))
        else:
            results.append(("payment.provider disabled", 0, "already neutralized"))

    # 3. Webhook endpoints (optional module) ----------------------------------
    if _model_exists(c, "webhook.endpoint"):
        try:
            webhook_ids: list[int] = c.search("webhook.endpoint", [("active", "=", True)])
        except RPCError:
            webhook_ids = []
        if webhook_ids:
            if not dry_run:
                c.write("webhook.endpoint", list(webhook_ids), {"active": False})
            results.append(("webhook.endpoint disabled", len(webhook_ids), "active -> False"))
        else:
            results.append(("webhook.endpoint disabled", 0, "already neutralized"))
    else:
        results.append(("webhook.endpoint disabled", 0, "base_webhook not installed"))

    # 4. Company name prefix --------------------------------------------------
    companies = c.search_read("res.company", [], ["id", "name"]) or []
    prefixed = 0
    for comp in companies:
        name = comp.get("name") or ""
        if name.startswith(company_prefix):
            continue
        new_name = f"{company_prefix}{name}"
        if not dry_run:
            c.write("res.company", [comp["id"]], {"name": new_name})
        prefixed += 1
    results.append(
        (
            "res.company prefixed",
            prefixed,
            f"prefix {company_prefix!r}" if prefixed else "already prefixed",
        )
    )

    # 5. Admin password -------------------------------------------------------
    if admin_password:
        admins = (
            c.search_read(
                "res.users",
                [("login", "=", "admin")],
                ["id", "login"],
            )
            or []
        )
        if admins:
            if not dry_run:
                c.write("res.users", [admins[0]["id"]], {"password": admin_password})
            results.append(("admin password set", 1, "res.users[admin]"))
        else:
            results.append(("admin password set", 0, "admin user not found"))
    else:
        results.append(("admin password set", 0, "no password provided"))

    # 6. web.base.url ---------------------------------------------------------
    base_url = _get_base_url(c)
    if base_url:
        params = (
            c.search_read(
                "ir.config_parameter",
                [("key", "=", "web.base.url")],
                ["id", "key", "value"],
            )
            or []
        )
        if params:
            current = params[0].get("value") or ""
            if current != base_url:
                if not dry_run:
                    c.write("ir.config_parameter", [params[0]["id"]], {"value": base_url})
                results.append(("web.base.url updated", 1, f"-> {base_url}"))
            else:
                results.append(("web.base.url updated", 0, "already current"))
        else:
            if not dry_run:
                c.create("ir.config_parameter", {"key": "web.base.url", "value": base_url})
            results.append(("web.base.url updated", 1, f"created -> {base_url}"))
    else:
        results.append(("web.base.url updated", 0, "no base URL available"))

    # ------------------------------------------------------------------------
    mode = "[DRY RUN] " if dry_run else ""
    out.table(
        f"{mode}Neutralize staging ({database})",
        [("Item", "cyan"), ("Count", ""), ("Note", "dim")],
        [[item, str(count), note] for item, count, note in results],
        data_for_json=[{"item": i, "count": c, "note": n} for i, c, n in results],
    )
