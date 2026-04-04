"""DKIM key management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext

app = typer.Typer(help="Manage DKIM keys.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List DKIM keys for all domains."""
    c: AppContext = ctx.obj
    domains_data = c.client.mc_get("domain/all")
    domains = domains_data if isinstance(domains_data, list) else []

    rows = []
    json_data = []
    for d in domains:
        domain = d.get("domain_name", "")
        dkim = c.client.mc_get(f"dkim/{domain}")
        if isinstance(dkim, dict) and dkim.get("dkim_txt"):
            rows.append(
                [
                    domain,
                    str(dkim.get("length", "")),
                    str(dkim.get("dkim_selector", "dkim")),
                    "[green]configured[/green]",
                ]
            )
            json_data.append({"domain": domain, **dkim})
        else:
            rows.append([domain, "-", "-", "[red]not configured[/red]"])
            json_data.append({"domain": domain, "configured": False})

    c.output.table(
        "DKIM Keys",
        [("Domain", "cyan"), ("Key Length", ""), ("Selector", ""), ("Status", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def get(
    ctx: typer.Context,
    domain: Annotated[str, typer.Argument(help="Domain name")],
) -> None:
    """Get DKIM key details for a domain."""
    c: AppContext = ctx.obj
    data = c.client.mc_get(f"dkim/{domain}")

    if not isinstance(data, dict) or not data.get("dkim_txt"):
        c.output.warn(f"No DKIM key configured for {domain}")
        c.output.info(f"Generate one with: kctl-mailcow dkim generate {domain}")
        raise typer.Exit(0)

    sections = [
        (
            "DKIM Configuration",
            [
                ("Domain", domain),
                ("Selector", str(data.get("dkim_selector", "dkim"))),
                ("Key Length", str(data.get("length", ""))),
            ],
        ),
        (
            "DNS Record",
            [
                ("Record", str(data.get("dkim_txt", ""))),
            ],
        ),
    ]

    c.output.detail(f"DKIM: {domain}", sections, data_for_json=data)


@app.command()
def generate(
    ctx: typer.Context,
    domain: Annotated[str, typer.Argument(help="Domain name")],
    selector: Annotated[str, typer.Option("--selector", "-s", help="DKIM selector")] = "dkim",
    length: Annotated[int, typer.Option("--length", "-l", help="Key length")] = 2048,
) -> None:
    """Generate DKIM key for a domain."""
    c: AppContext = ctx.obj
    payload = {
        "domains": domain,
        "dkim_selector": selector,
        "key_size": length,
    }
    result = c.client.mc_add("dkim", payload)

    if isinstance(result, list):
        errors = [r for r in result if isinstance(r, dict) and r.get("type") == "danger"]
        if errors:
            for e in errors:
                c.output.error(str(e.get("msg", e)))
            raise typer.Exit(1)

    c.output.success(f"DKIM key generated for {domain}")

    # Fetch and display the new key
    data = c.client.mc_get(f"dkim/{domain}")
    if isinstance(data, dict) and data.get("dkim_txt"):
        c.output.info("Add this DNS TXT record:")
        c.output.kv(f"{selector}._domainkey.{domain}", str(data.get("dkim_txt", "")))
    if c.json_mode:
        c.output.raw_json(data)
