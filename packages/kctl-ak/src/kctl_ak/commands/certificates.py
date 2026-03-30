"""Certificate management commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from kctl_ak.core.callbacks import AppContext

app = typer.Typer(help="Certificate and key pair management.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all certificate-key pairs."""
    c: AppContext = ctx.obj
    certs = c.client.get_all("crypto/certificatekeypairs/")

    rows = []
    for cert in certs:
        rows.append(
            [
                str(cert.get("pk", "")),
                cert.get("name", ""),
                str(cert.get("managed", "") or "-"),
                cert.get("cert_expiry", "-"),
                str(cert.get("private_key_available", False)),
            ]
        )

    c.output.table(
        "Certificates",
        [("ID", "cyan"), ("Name", ""), ("Managed", "dim"), ("Expires", "yellow"), ("Has Key", "")],
        rows,
        data_for_json=certs,
    )


@app.command()
def get(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Certificate UUID")],
) -> None:
    """Get certificate details."""
    c: AppContext = ctx.obj
    cert = c.client.get(f"crypto/certificatekeypairs/{id_}/")

    c.output.detail(
        cert.get("name", str(id_)),
        [
            (
                "Certificate",
                [
                    ("ID", str(cert.get("pk", ""))),
                    ("Name", cert.get("name", "")),
                    ("Managed", str(cert.get("managed", "") or "-")),
                    ("Expiry", cert.get("cert_expiry", "-")),
                    ("Subject", cert.get("cert_subject", "-")),
                    ("Private Key", str(cert.get("private_key_available", False))),
                ],
            ),
        ],
        data_for_json=cert,
    )


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Certificate name")],
    cert_file: Annotated[Path, typer.Option("--cert-file", help="Path to PEM certificate file")],
    key_file: Annotated[Path | None, typer.Option("--key-file", help="Path to PEM private key file")] = None,
) -> None:
    """Upload a certificate (and optional key) from PEM files."""
    c: AppContext = ctx.obj

    if not cert_file.exists():
        c.output.error(f"Certificate file not found: {cert_file}")
        raise typer.Exit(1)

    cert_data = cert_file.read_text()
    files: dict = {
        "certificate_data": (cert_file.name, cert_data, "application/x-pem-file"),
    }
    form_data: dict = {"name": name}

    if key_file:
        if not key_file.exists():
            c.output.error(f"Key file not found: {key_file}")
            raise typer.Exit(1)
        key_data = key_file.read_text()
        files["key_data"] = (key_file.name, key_data, "application/x-pem-file")

    result = c.client.post_multipart("crypto/certificatekeypairs/", files=files, data=form_data)
    c.output.success(f"Created certificate '{result.get('name', name)}' (ID: {result.get('pk', '?')})")


@app.command()
def generate(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Certificate name")],
    common_name: Annotated[str, typer.Option("--common-name", help="Certificate Common Name (CN)")] = "authentik",
    days: Annotated[int, typer.Option("--days", help="Validity in days")] = 365,
) -> None:
    """Generate a self-signed certificate-key pair."""
    c: AppContext = ctx.obj
    payload = {
        "common_name": common_name,
        "subject_alt_name": common_name,
        "validity_days": days,
    }
    result = c.client.post("crypto/certificatekeypairs/generate/", data=payload)
    c.output.success(f"Generated certificate '{result.get('name', name)}' (ID: {result.get('pk', '?')})")


@app.command()
def delete(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Certificate UUID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a certificate-key pair."""
    if not force:
        typer.confirm(f"Delete certificate {id_}?", abort=True)
    c: AppContext = ctx.obj
    c.client.delete(f"crypto/certificatekeypairs/{id_}/")
    c.output.success(f"Deleted certificate {id_}")


@app.command()
def view(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Certificate UUID")],
) -> None:
    """View certificate details (parsed certificate info)."""
    c: AppContext = ctx.obj
    data = c.client.get(f"crypto/certificatekeypairs/{id_}/view_certificate/")

    if c.output.json_mode:
        c.output.raw_json(data)
        return

    sections = [
        (
            "Certificate Info",
            [
                ("Subject", str(data.get("subject", "-"))),
                ("Issuer", str(data.get("issuer", "-"))),
                ("Serial", str(data.get("serial", "-"))),
                ("Not Before", str(data.get("not_before", "-"))),
                ("Not After", str(data.get("not_after", "-"))),
                ("SHA1 Fingerprint", str(data.get("sha1", data.get("fingerprint_sha1", "-")))),
                ("SHA256 Fingerprint", str(data.get("sha256", data.get("fingerprint_sha256", "-")))),
            ],
        ),
    ]

    c.output.detail("Certificate View", sections, data_for_json=data)


@app.command("used-by")
def used_by(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Certificate UUID")],
) -> None:
    """Show what uses this certificate."""
    c: AppContext = ctx.obj
    data = c.client.get(f"crypto/certificatekeypairs/{id_}/used_by/")

    if isinstance(data, list):
        rows = []
        for item in data:
            rows.append(
                [
                    str(item.get("app", "")),
                    str(item.get("model_name", "")),
                    str(item.get("pk", "")),
                    str(item.get("name", "")),
                ]
            )
        c.output.table(
            f"Used By (certificate {id_[:8]}...)",
            [("App", ""), ("Model", "yellow"), ("ID", "dim"), ("Name", "")],
            rows,
            data_for_json=data,
        )
    else:
        c.output.raw_json(data)
