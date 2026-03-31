"""Export and backup Cloudflare configuration as JSON."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

import typer

from kctl_cf.core.callbacks import AppContext
from kctl_cf.core.exceptions import KctlError
from kctl_cf.core.utils import require_account

app = typer.Typer(help="Export and backup Cloudflare configuration.")

# ── Zone settings to export ──────────────────────────────────────────

_ZONE_SETTINGS = (
    "ssl",
    "cache_level",
    "browser_cache_ttl",
    "security_level",
    "min_tls_version",
    "always_use_https",
    "automatic_https_rewrites",
    "http2",
    "http3",
    "0rtt",
    "ipv6",
    "websockets",
    "opportunistic_encryption",
    "tls_1_3",
    "early_hints",
    "minify",
    "polish",
    "brotli",
    "rocket_loader",
    "email_obfuscation",
    "server_side_exclude",
    "hotlink_protection",
    "challenge_ttl",
    "browser_check",
    "development_mode",
)


# ── Pagination helper ────────────────────────────────────────────────


def _paginate(
    client: Any,
    endpoint: str,
    *,
    params: dict[str, Any] | None = None,
    per_page: int = 100,
) -> list[Any]:
    """Fetch all pages from a Cloudflare API list endpoint.

    The Cloudflare API returns ``result_info.total_pages`` in the envelope.
    We iterate through every page and collect all ``result`` items.
    """
    params = dict(params) if params else {}
    params["per_page"] = per_page
    params["page"] = 1

    all_items: list[Any] = []

    while True:
        response = client._request("GET", endpoint, params=params)  # noqa: SLF001
        data = response.json() if response.content else {}

        result = data.get("result", [])
        if isinstance(result, list):
            all_items.extend(result)
        elif isinstance(result, dict):
            # Some endpoints wrap the list in a nested key (e.g., R2 buckets)
            all_items.append(result)

        result_info = data.get("result_info", {})
        total_pages = result_info.get("total_pages", 1)
        current_page = result_info.get("page", 1)

        if current_page >= total_pages:
            break
        params["page"] = current_page + 1

    return all_items


# ── Data collection helpers ──────────────────────────────────────────


def _collect_zone_data(c: AppContext, zone_name: str) -> dict[str, Any]:
    """Collect full export data for a single zone."""
    zone_id = c.client.get_zone_id(zone_name)

    # Zone details
    zone_data = c.client.get(f"/zones/{zone_id}")
    if not isinstance(zone_data, dict):
        zone_data = {}

    # DNS records (paginated)
    records = _paginate(c.client, f"/zones/{zone_id}/dns_records")

    # Zone settings
    settings: dict[str, Any] = {}
    for name in _ZONE_SETTINGS:
        try:
            result = c.client.get(f"/zones/{zone_id}/settings/{name}")
            settings[name] = result.get("value", result) if isinstance(result, dict) else result
        except Exception:  # noqa: BLE001
            settings[name] = None

    # Firewall rulesets
    rulesets: list[Any] = []
    try:
        raw = c.client.get(f"/zones/{zone_id}/rulesets")
        rulesets = raw if isinstance(raw, list) else []
    except Exception:  # noqa: BLE001
        pass

    # Expand each ruleset to include its rules
    expanded_rulesets: list[dict[str, Any]] = []
    for rs in rulesets:
        rs_id = rs.get("id", "")
        if not rs_id:
            expanded_rulesets.append(rs)
            continue
        try:
            full_rs = c.client.get(f"/zones/{zone_id}/rulesets/{rs_id}")
            expanded_rulesets.append(full_rs if isinstance(full_rs, dict) else rs)
        except Exception:  # noqa: BLE001
            expanded_rulesets.append(rs)

    # Page rules
    page_rules: list[Any] = []
    try:
        raw = c.client.get(f"/zones/{zone_id}/pagerules")
        page_rules = raw if isinstance(raw, list) else []
    except Exception:  # noqa: BLE001
        pass

    return {
        "zone": zone_data,
        "dns_records": records,
        "settings": settings,
        "rulesets": expanded_rulesets,
        "page_rules": page_rules,
    }


def _collect_tunnels(c: AppContext, account_id: str) -> list[dict[str, Any]]:
    """Collect all tunnels with their ingress configurations."""
    tunnels = _paginate(
        c.client,
        f"/accounts/{account_id}/cfd_tunnel",
        params={"is_deleted": "false"},
    )

    enriched: list[dict[str, Any]] = []
    for t in tunnels:
        tunnel_id = t.get("id", "")
        tunnel_entry: dict[str, Any] = dict(t)

        # Fetch ingress rules (tunnel configuration)
        if tunnel_id:
            try:
                config = c.client.get(f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations")
                tunnel_entry["ingress_config"] = config if isinstance(config, dict) else {}
            except Exception:  # noqa: BLE001
                tunnel_entry["ingress_config"] = {}

        enriched.append(tunnel_entry)

    return enriched


def _collect_r2_buckets(c: AppContext, account_id: str) -> list[Any]:
    """Collect all R2 buckets."""
    try:
        raw = c.client.get(f"/accounts/{account_id}/r2/buckets")
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            return raw.get("buckets", [raw])
        return []
    except Exception:  # noqa: BLE001
        return []


def _collect_all(
    c: AppContext,
    *,
    zone_filter: str | None = None,
) -> dict[str, Any]:
    """Collect the full export across all zones and account-level resources."""
    account_id = require_account(c)

    # Determine zone list
    if zone_filter:
        zone_names = [zone_filter]
    else:
        zones_raw = _paginate(c.client, "/zones")
        zone_names = [z.get("name", "") for z in zones_raw if z.get("name")]

    # Collect per-zone data
    zones_data: dict[str, Any] = {}
    for name in zone_names:
        c.output.info(f"Exporting zone: {name}")
        try:
            zones_data[name] = _collect_zone_data(c, name)
        except Exception as exc:  # noqa: BLE001
            c.output.warn(f"Failed to export zone {name}: {exc}")
            zones_data[name] = {"error": str(exc)}

    # Account-level resources
    c.output.info("Exporting tunnels")
    tunnels = _collect_tunnels(c, account_id)

    c.output.info("Exporting R2 buckets")
    r2_buckets = _collect_r2_buckets(c, account_id)

    timestamp = datetime.now(tz=timezone.utc).isoformat()

    return {
        "exported_at": timestamp,
        "account_id": account_id,
        "zones": zones_data,
        "tunnels": tunnels,
        "r2_buckets": r2_buckets,
    }


# ── File writing helper ─────────────────────────────────────────────


def _write_json(path: Path, data: Any) -> None:
    """Write data as pretty-printed JSON to *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


# ── Commands ─────────────────────────────────────────────────────────


@app.command("all")
def all_(
    ctx: typer.Context,
    zone: Annotated[
        str | None,
        typer.Option("--zone", help="Filter to a specific zone (default: all zones)"),
    ] = None,
) -> None:
    """Export all Cloudflare configuration as JSON.

    Exports every zone (DNS records, settings, firewall rulesets, page rules)
    plus account-level resources (tunnels with ingress rules, R2 buckets).
    Use --zone to limit export to a single zone.
    """
    c: AppContext = ctx.obj
    export_data = _collect_all(c, zone_filter=zone)
    c.output.raw_json(export_data)


@app.command()
def backup(
    ctx: typer.Context,
    zone: Annotated[
        str | None,
        typer.Option("--zone", help="Filter to a specific zone (default: all zones)"),
    ] = None,
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", help="Base directory for backup files"),
    ] = Path("."),
    upload: Annotated[
        bool,
        typer.Option("--upload/--no-upload", help="Upload backup to S3 after writing"),
    ] = False,
    s3_remote: Annotated[
        str,
        typer.Option("--s3-remote", help="S3 remote path (e.g. s3:kodemeio-backups/cloudflare/)"),
    ] = "s3:kodemeio-backups/cloudflare/",
) -> None:
    """Save Cloudflare export to timestamped JSON files on disk.

    Creates a directory like ``cloudflare-backup-20260401-143022/`` containing
    separate JSON files per zone, plus account-level resources.

    Use --upload to push the backup directory to S3 via rclone.
    """
    c: AppContext = ctx.obj
    export_data = _collect_all(c, zone_filter=zone)

    # Build timestamped directory
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_dir = output_dir / f"cloudflare-backup-{ts}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Write the full combined export
    _write_json(backup_dir / "full-export.json", export_data)

    # Write per-zone files
    zones_data: dict[str, Any] = export_data.get("zones", {})
    for zone_name, zone_payload in zones_data.items():
        safe_name = zone_name.replace("/", "_")

        # Zone details + settings
        _write_json(
            backup_dir / f"zone-{safe_name}.json",
            {
                "zone": zone_payload.get("zone", {}),
                "settings": zone_payload.get("settings", {}),
            },
        )

        # DNS records
        _write_json(
            backup_dir / f"records-{safe_name}.json",
            zone_payload.get("dns_records", []),
        )

        # Firewall rulesets
        rulesets = zone_payload.get("rulesets", [])
        if rulesets:
            _write_json(backup_dir / f"rulesets-{safe_name}.json", rulesets)

        # Page rules
        page_rules = zone_payload.get("page_rules", [])
        if page_rules:
            _write_json(backup_dir / f"pagerules-{safe_name}.json", page_rules)

    # Account-level resources
    tunnels = export_data.get("tunnels", [])
    if tunnels:
        _write_json(backup_dir / "tunnels.json", tunnels)

    r2_buckets = export_data.get("r2_buckets", [])
    if r2_buckets:
        _write_json(backup_dir / "r2-buckets.json", r2_buckets)

    # Write metadata
    _write_json(
        backup_dir / "metadata.json",
        {
            "exported_at": export_data.get("exported_at", ""),
            "account_id": export_data.get("account_id", ""),
            "zone_count": len(zones_data),
            "zones": list(zones_data.keys()),
            "tunnel_count": len(tunnels),
            "r2_bucket_count": len(r2_buckets),
        },
    )

    file_count = len(list(backup_dir.glob("*.json")))
    c.output.success(f"Backup saved to {backup_dir} ({file_count} files)")

    # Upload to S3 if requested
    if upload:
        _upload_to_s3(c, backup_dir, s3_remote)


def _upload_to_s3(c: AppContext, backup_dir: Path, s3_remote: str) -> None:
    """Upload *backup_dir* to S3 using rclone or aws CLI."""
    remote_path = s3_remote.rstrip("/") + "/" + backup_dir.name + "/"

    # Try rclone first, fall back to aws CLI
    for cmd_name, build_args in [
        ("rclone", lambda: ["rclone", "copy", str(backup_dir), remote_path, "--progress"]),
        ("aws", lambda: ["aws", "s3", "cp", str(backup_dir), remote_path, "--recursive"]),
    ]:
        try:
            args = build_args()
            c.output.info(f"Uploading with {cmd_name}: {' '.join(args)}")
            result = subprocess.run(  # noqa: S603
                args,
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
            if result.returncode == 0:
                c.output.success(f"Backup uploaded to {remote_path}")
                return
            # If the tool exists but failed, report and stop
            if result.returncode != 127:
                c.output.error(
                    f"{cmd_name} failed (exit {result.returncode}): {result.stderr.strip() or result.stdout.strip()}"
                )
                raise typer.Exit(1)
        except FileNotFoundError:
            continue
        except subprocess.TimeoutExpired:
            raise KctlError(f"{cmd_name} upload timed out after 600s") from None

    c.output.error("Neither rclone nor aws CLI found. Install one to use --upload.")
    raise typer.Exit(1)
