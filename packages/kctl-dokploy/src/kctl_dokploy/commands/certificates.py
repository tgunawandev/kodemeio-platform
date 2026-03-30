"""SSL certificate management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage SSL certificates.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all SSL certificates."""
    c: AppContext = ctx.obj
    certs = c.client.get("/certificates.all")
    if not isinstance(certs, list):
        certs = []
    rows = []
    for cert in certs:
        cid = cert.get("certificateId", "")[:12]
        name = cert.get("name", "")
        cert_type = cert.get("certificateType", cert.get("type", "unknown"))
        auto_renew = str(cert.get("autoRenew", "-"))
        expires = cert.get("expiresAt", cert.get("expiration", "-"))
        rows.append([cid, name, cert_type, auto_renew, str(expires)])
    c.output.table(
        "SSL Certificates",
        [("ID", "dim"), ("Name", "cyan"), ("Type", ""), ("Auto Renew", ""), ("Expires", "dim")],
        rows,
        data_for_json=certs,
    )


@app.command()
def get(
    ctx: typer.Context,
    certificate_id: Annotated[str, typer.Argument(help="Certificate ID")],
) -> None:
    """Get certificate details."""
    c: AppContext = ctx.obj
    data = c.client.get("/certificates.one", params={"certificateId": certificate_id})
    if not isinstance(data, dict):
        c.output.error(f"Certificate '{certificate_id}' not found")
        raise typer.Exit(1)
    sections = [
        (
            "Certificate",
            [
                ("ID", data.get("certificateId", "")),
                ("Name", data.get("name", "")),
                ("Type", data.get("certificateType", data.get("type", "unknown"))),
                ("Auto Renew", str(data.get("autoRenew", "-"))),
                ("Expires", data.get("expiresAt", data.get("expiration", "-"))),
                ("Domain", data.get("domain", data.get("host", "-"))),
                ("Created", data.get("createdAt", "-")),
            ],
        ),
    ]
    c.output.detail(f"Certificate: {data.get('name', '')}", sections, data_for_json=data)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Certificate name")],
    domain: Annotated[str | None, typer.Option("--domain", "-d", help="Domain name")] = None,
    auto_renew: Annotated[bool, typer.Option("--auto-renew/--no-auto-renew", help="Enable auto-renewal")] = True,
) -> None:
    """Create a new Let's Encrypt certificate."""
    c: AppContext = ctx.obj
    payload: dict = {
        "name": name,
        "certificateType": "letsencrypt",
        "autoRenew": auto_renew,
    }
    if domain:
        payload["domain"] = domain
    result = c.client.post("/certificates.create", json=payload)
    cid = result.get("certificateId", "") if isinstance(result, dict) else ""
    c.output.success(f"Certificate '{name}' created: {cid}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("import")
def import_cert(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Certificate name")],
    cert_path: Annotated[str, typer.Option("--cert", help="Path to certificate file (PEM)")],
    key_path: Annotated[str, typer.Option("--key", help="Path to private key file (PEM)")],
    chain_path: Annotated[str | None, typer.Option("--chain", help="Path to CA chain file (PEM)")] = None,
) -> None:
    """Import a custom SSL certificate."""
    c: AppContext = ctx.obj
    try:
        with open(cert_path) as f:
            cert_data = f.read()
        with open(key_path) as f:
            key_data = f.read()
    except FileNotFoundError as e:
        c.output.error(f"File not found: {e}")
        raise typer.Exit(1) from e
    payload: dict = {
        "name": name,
        "certificateType": "custom",
        "certificateData": cert_data,
        "privateKey": key_data,
    }
    if chain_path:
        try:
            with open(chain_path) as f:
                chain_data = f.read()
            payload["certificateChain"] = chain_data
        except FileNotFoundError as e:
            c.output.error(f"Chain file not found: {e}")
            raise typer.Exit(1) from e
    result = c.client.post("/certificates.create", json=payload)
    cid = result.get("certificateId", "") if isinstance(result, dict) else ""
    c.output.success(f"Certificate '{name}' imported: {cid}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def remove(
    ctx: typer.Context,
    certificate_id: Annotated[str, typer.Argument(help="Certificate ID to remove")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Remove a certificate (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Remove certificate '{certificate_id}'? This cannot be undone.", abort=True)
    result = c.client.post("/certificates.remove", json={"certificateId": certificate_id})
    c.output.success(f"Certificate '{certificate_id}' removed")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def renew(
    ctx: typer.Context,
    certificate_id: Annotated[str, typer.Argument(help="Certificate ID to renew")],
) -> None:
    """Trigger certificate renewal."""
    c: AppContext = ctx.obj
    c.output.info(f"Renewing certificate '{certificate_id}'...")
    result = c.client.post("/certificates.renew", json={"certificateId": certificate_id})
    c.output.success(f"Certificate '{certificate_id}' renewal triggered")
    if c.json_mode:
        c.output.raw_json(result)
