"""SSL/TLS certificate and settings commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_cloudflare.core.callbacks import AppContext
from kctl_cloudflare.core.utils import resolve_zone

app = typer.Typer(help="Manage SSL/TLS settings and certificates.")


@app.command()
def status(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Show SSL/TLS mode for a zone."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    ssl = c.client.get(f"/zones/{zone_id}/settings/ssl")

    ssl_val = ssl.get("value", "") if isinstance(ssl, dict) else str(ssl)

    data = {"zone": zone, "ssl_mode": ssl_val}
    sections = [
        (
            "SSL/TLS",
            [
                ("Zone", zone),
                ("Mode", str(ssl_val)),
            ],
        )
    ]
    c.output.detail(f"SSL — {zone}", sections, data_for_json=data)


@app.command()
def certificates(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """List SSL certificate packs for a zone."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    certs = c.client.get(f"/zones/{zone_id}/ssl/certificate_packs")
    if not isinstance(certs, list):
        certs = []
    rows = []
    for cert in certs:
        hosts = cert.get("hosts", [])
        rows.append(
            [
                cert.get("id", "")[:12],
                cert.get("type", ""),
                cert.get("status", ""),
                ", ".join(hosts[:3]) + ("..." if len(hosts) > 3 else ""),
                str(cert.get("validity_days", "")),
            ]
        )
    c.output.table(
        f"SSL Certificates — {zone}",
        [("ID", "dim"), ("Type", "cyan"), ("Status", "green"), ("Hosts", ""), ("Validity", "dim")],
        rows,
        data_for_json=certs,
    )


@app.command("origin-certs")
def origin_certs(ctx: typer.Context) -> None:
    """List Origin CA certificates."""
    c: AppContext = ctx.obj
    result = c.client.get("/certificates")
    if not isinstance(result, list):
        result = []
    rows = []
    for cert in result:
        hostnames = cert.get("hostnames", [])
        rows.append(
            [
                cert.get("id", "")[:12],
                ", ".join(hostnames[:3]) + ("..." if len(hostnames) > 3 else ""),
                cert.get("request_type", ""),
                str(cert.get("requested_validity", "")),
                cert.get("expires_on", "")[:19],
            ]
        )
    c.output.table(
        "Origin CA Certificates",
        [("ID", "dim"), ("Hostnames", "cyan"), ("Type", ""), ("Validity (days)", "dim"), ("Expires", "green")],
        rows,
        data_for_json=result,
    )


@app.command("create-origin-cert")
def create_origin_cert(
    ctx: typer.Context,
    hostnames: Annotated[list[str], typer.Option("--hostname", help="Hostnames for the certificate")],
    validity: Annotated[int, typer.Option("--validity", help="Validity in days (5475=15y, 365=1y)")] = 5475,
    request_type: Annotated[
        str, typer.Option("--type", help="Certificate type (origin-rsa, origin-ecc)")
    ] = "origin-rsa",
) -> None:
    """Create an Origin CA certificate."""
    c: AppContext = ctx.obj
    payload = {
        "hostnames": hostnames,
        "requested_validity": validity,
        "request_type": request_type,
    }
    result = c.client.post("/certificates", json=payload)
    if not isinstance(result, dict):
        result = {}
    cert_id = result.get("id", "")
    if c.output.json_mode:
        c.output.raw_json(result)
    else:
        c.output.success(f"Origin CA certificate created: {cert_id}")
        cert_pem = result.get("certificate", "")
        if cert_pem:
            c.output.info("Certificate PEM (save this):")
            c.output.text(cert_pem)


@app.command("delete-origin-cert")
def delete_origin_cert(
    ctx: typer.Context,
    cert_id: Annotated[str, typer.Argument(help="Certificate ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
) -> None:
    """Delete an Origin CA certificate. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    c.client.delete(f"/certificates/{cert_id}")
    c.output.success(f"Origin CA certificate deleted: {cert_id}")


@app.command("min-tls")
def min_tls(
    ctx: typer.Context,
    version: Annotated[
        str | None, typer.Option("--version", help="Set minimum TLS version (1.0, 1.1, 1.2, 1.3)")
    ] = None,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Show or set minimum TLS version for a zone."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    if version:
        c.client.patch(f"/zones/{zone_id}/settings/min_tls_version", json={"value": version})
        c.output.success(f"Minimum TLS version set to {version} for {zone}")
    else:
        result = c.client.get(f"/zones/{zone_id}/settings/min_tls_version")
        val = result.get("value", "") if isinstance(result, dict) else str(result)
        data = {"zone": zone, "min_tls_version": val}
        sections = [
            (
                "Minimum TLS Version",
                [
                    ("Zone", zone),
                    ("Version", str(val)),
                ],
            )
        ]
        c.output.detail(f"Min TLS — {zone}", sections, data_for_json=data)


@app.command("always-https")
def always_https(
    ctx: typer.Context,
    enable: Annotated[
        bool | None, typer.Option("--enable/--disable", help="Enable or disable Always Use HTTPS")
    ] = None,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Show or toggle Always Use HTTPS for a zone."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    if enable is not None:
        value = "on" if enable else "off"
        c.client.patch(f"/zones/{zone_id}/settings/always_use_https", json={"value": value})
        c.output.success(f"Always Use HTTPS {'enabled' if enable else 'disabled'} for {zone}")
    else:
        result = c.client.get(f"/zones/{zone_id}/settings/always_use_https")
        val = result.get("value", "") if isinstance(result, dict) else str(result)
        data = {"zone": zone, "always_use_https": val}
        sections = [
            (
                "Always Use HTTPS",
                [
                    ("Zone", zone),
                    ("Status", str(val)),
                ],
            )
        ]
        c.output.detail(f"Always HTTPS — {zone}", sections, data_for_json=data)
