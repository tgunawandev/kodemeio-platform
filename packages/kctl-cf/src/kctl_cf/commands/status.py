"""Account-level status dashboard commands."""

from __future__ import annotations

import typer

from kctl_cloudflare.core.callbacks import AppContext
from kctl_cloudflare.core.exceptions import KctlError
from kctl_cloudflare.core.utils import mask_token, require_account, status_color

app = typer.Typer(help="Account status dashboard.")


def _safe_list(client: object, path: str, params: dict | None = None) -> list:
    """Fetch a list endpoint, returning [] on any failure."""
    try:
        from kctl_cloudflare.core.client import CloudflareClient

        assert isinstance(client, CloudflareClient)  # noqa: S101
        result = client.get(path, params=params or {})
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            # Some endpoints wrap lists in a key (e.g. R2 buckets)
            for key in ("buckets", "result"):
                if key in result and isinstance(result[key], list):
                    return result[key]
        return []
    except Exception:  # noqa: BLE001
        return []


@app.command()
def overview(ctx: typer.Context) -> None:
    """Show a comprehensive account-level dashboard.

    Displays API token status, account info, zone summary,
    tunnel count, R2 buckets, and Workers scripts.
    """
    c: AppContext = ctx.obj
    acct = require_account(c)
    out = c.output

    # -- API token verification ------------------------------------------------
    token_status = "unknown"
    token_expires = ""
    try:
        verify = c.client.check_health()
        if isinstance(verify, dict):
            token_status = verify.get("status", "unknown")
            token_expires = verify.get("expires_on", "") or ""
    except KctlError:
        token_status = "error"

    # -- Account details -------------------------------------------------------
    account_name = ""
    try:
        acct_data = c.client.get(f"/accounts/{acct}")
        if isinstance(acct_data, dict):
            account_name = acct_data.get("name", "")
    except KctlError:
        account_name = "(unable to fetch)"

    # -- Zones -----------------------------------------------------------------
    zones = _safe_list(c.client, "/zones")
    zone_count = len(zones)
    zone_summaries: list[str] = []
    for z in zones:
        name = z.get("name", "")
        plan = z.get("plan", {}).get("name", "")
        zstatus = z.get("status", "")
        zone_summaries.append(f"{name} ({plan}, {status_color(zstatus)})")

    # -- Tunnels ---------------------------------------------------------------
    tunnels = _safe_list(
        c.client,
        f"/accounts/{acct}/cfd_tunnel",
        params={"is_deleted": "false"},
    )
    tunnel_total = len(tunnels)
    tunnel_active = sum(1 for t in tunnels if (t.get("status", "") or "").lower() in ("healthy", "active"))

    # -- R2 Buckets ------------------------------------------------------------
    r2_raw = _safe_list(c.client, f"/accounts/{acct}/r2/buckets")
    r2_count = len(r2_raw)

    # -- Workers ---------------------------------------------------------------
    workers = _safe_list(c.client, f"/accounts/{acct}/workers/scripts")
    workers_count = len(workers)

    # -- Build sections for detail output --------------------------------------
    masked_token = mask_token(c.client._credential)  # noqa: SLF001
    token_display = status_color(token_status)

    sections = [
        (
            "API Token",
            [
                ("Status", token_display),
                ("Token", masked_token),
                ("Expires", token_expires if token_expires else "n/a"),
            ],
        ),
        (
            "Account",
            [
                ("Account ID", acct),
                ("Account Name", account_name if account_name else "n/a"),
            ],
        ),
        (
            "Resources",
            [
                ("Zones", str(zone_count)),
                ("Tunnels", f"{tunnel_active} active / {tunnel_total} total"),
                ("R2 Buckets", str(r2_count)),
                ("Workers", str(workers_count)),
            ],
        ),
    ]

    if zone_summaries:
        sections.append(
            (
                "Zone Details",
                [(str(i + 1), s) for i, s in enumerate(zone_summaries)],
            ),
        )

    json_data = {
        "api_token": {
            "status": token_status,
            "expires_on": token_expires or None,
        },
        "account": {
            "id": acct,
            "name": account_name,
        },
        "zones": {
            "count": zone_count,
            "items": [
                {
                    "name": z.get("name", ""),
                    "status": z.get("status", ""),
                    "plan": z.get("plan", {}).get("name", ""),
                }
                for z in zones
            ],
        },
        "tunnels": {
            "total": tunnel_total,
            "active": tunnel_active,
        },
        "r2_buckets": {
            "count": r2_count,
        },
        "workers": {
            "count": workers_count,
        },
    }

    out.detail("Cloudflare Account Overview", sections, data_for_json=json_data)
