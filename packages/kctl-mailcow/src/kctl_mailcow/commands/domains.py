"""Domain management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext

app = typer.Typer(help="Manage mail domains.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all domains."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("domain/all")
    items = data if isinstance(data, list) else []

    rows = []
    for d in items:
        active = "[green]yes[/green]" if str(d.get("active")) == "1" else "[red]no[/red]"
        rows.append(
            [
                d.get("domain_name", ""),
                str(d.get("aliases_left", 0)),
                str(d.get("mboxes_left", 0)),
                str(d.get("quota", 0)),
                active,
            ]
        )

    c.output.table(
        "Domains",
        [("Domain", "cyan"), ("Aliases Left", ""), ("Mailboxes Left", ""), ("Quota", ""), ("Active", "")],
        rows,
        data_for_json=items,
    )


@app.command()
def get(
    ctx: typer.Context,
    domain: Annotated[str, typer.Argument(help="Domain name")],
) -> None:
    """Get domain details."""
    c: AppContext = ctx.obj
    data = c.client.mc_get(f"domain/{domain}")

    if isinstance(data, list) and data:
        item = data[0]
    elif isinstance(data, dict):
        item = data
    else:
        c.output.error(f"Domain not found: {domain}")
        raise typer.Exit(1)

    sections = [
        (
            "Domain Info",
            [
                ("Domain", str(item.get("domain_name", ""))),
                ("Description", str(item.get("description", ""))),
                ("Aliases", f"{item.get('aliases_in_domain', 0)} / max {item.get('max_num_aliases_for_domain', 0)}"),
                ("Mailboxes", f"{item.get('mboxes_in_domain', 0)} / max {item.get('max_num_mboxes_for_domain', 0)}"),
                ("Quota", f"{item.get('quota_used_in_domain', 0)} / max {item.get('max_quota_for_domain', 0)}"),
                ("Active", str(item.get("active", ""))),
                ("Relay", str(item.get("relay_all_recipients", ""))),
                ("Backupmx", str(item.get("backupmx", ""))),
            ],
        )
    ]

    c.output.detail(f"Domain: {domain}", sections, data_for_json=item)


@app.command()
def add(
    ctx: typer.Context,
    domain: Annotated[str, typer.Argument(help="Domain name to add")],
    description: Annotated[str | None, typer.Option("--description", "-d", help="Domain description")] = None,
    aliases: Annotated[int, typer.Option("--aliases", help="Max aliases")] = 400,
    mailboxes: Annotated[int, typer.Option("--mailboxes", help="Max mailboxes")] = 10,
    defquota: Annotated[int, typer.Option("--defquota", help="Default quota in MB")] = 3072,
    maxquota: Annotated[int, typer.Option("--maxquota", help="Max quota in MB")] = 10240,
    quota: Annotated[int, typer.Option("--quota", help="Domain quota in MB")] = 10240,
    active: Annotated[bool, typer.Option("--active/--inactive", help="Active state")] = True,
) -> None:
    """Add a new domain."""
    c: AppContext = ctx.obj
    payload = {
        "domain": domain,
        "description": description or domain,
        "aliases": aliases,
        "mailboxes": mailboxes,
        "defquota": defquota,
        "maxquota": maxquota,
        "quota": quota,
        "active": "1" if active else "0",
        "restart_sogo": "1",
    }
    result = c.client.mc_add("domain", payload)
    _handle_result(c, result, f"Domain '{domain}' added")


@app.command()
def update(
    ctx: typer.Context,
    domain: Annotated[str, typer.Argument(help="Domain name to update")],
    description: Annotated[str | None, typer.Option("--description", "-d")] = None,
    aliases: Annotated[int | None, typer.Option("--aliases")] = None,
    mailboxes: Annotated[int | None, typer.Option("--mailboxes")] = None,
    maxquota: Annotated[int | None, typer.Option("--maxquota")] = None,
    quota: Annotated[int | None, typer.Option("--quota")] = None,
    active: Annotated[bool | None, typer.Option("--active/--inactive")] = None,
) -> None:
    """Update domain settings."""
    c: AppContext = ctx.obj
    attr: dict = {}
    if description is not None:
        attr["description"] = description
    if aliases is not None:
        attr["aliases"] = aliases
    if mailboxes is not None:
        attr["mailboxes"] = mailboxes
    if maxquota is not None:
        attr["maxquota"] = maxquota
    if quota is not None:
        attr["quota"] = quota
    if active is not None:
        attr["active"] = "1" if active else "0"

    if not attr:
        c.output.warn("No fields to update")
        raise typer.Exit(0)

    payload = {
        "items": [domain],
        "attr": attr,
    }
    result = c.client.mc_edit("domain", payload)
    _handle_result(c, result, f"Domain '{domain}' updated")


@app.command()
def delete(
    ctx: typer.Context,
    domain: Annotated[str, typer.Argument(help="Domain name to delete")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a domain."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete domain '{domain}'? This removes all mailboxes and aliases."):
            raise typer.Exit(0)

    result = c.client.mc_delete("domain", [domain])
    _handle_result(c, result, f"Domain '{domain}' deleted")


@app.command("dns-check")
def dns_check(
    ctx: typer.Context,
    domain: Annotated[str, typer.Argument(help="Domain name to check DNS for")],
) -> None:
    """Check DNS records for a domain (MX, SPF, DKIM, DMARC, etc.)."""
    c: AppContext = ctx.obj
    data = c.client.get(f"get/dns/{domain}/check")

    if not isinstance(data, dict):
        c.output.error(f"Unexpected DNS check response for {domain}")
        raise typer.Exit(1)

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    for record_type, records in data.items():
        if isinstance(records, list):
            kvs: list[tuple[str, str]] = []
            for rec in records:
                if isinstance(rec, dict):
                    name = rec.get("name", rec.get("type", record_type))
                    expected = rec.get("expected", "")
                    found = rec.get("found", "")
                    ok = rec.get("ok", rec.get("match", False))
                    status = "[green]OK[/green]" if ok else "[red]FAIL[/red]"
                    kvs.append((f"{name} {status}", f"expected={expected}, found={found}"))
                elif isinstance(rec, str):
                    kvs.append((record_type, rec))
            if kvs:
                sections.append((record_type.upper(), kvs))
        elif isinstance(records, dict):
            kvs = []
            for k, v in records.items():
                kvs.append((k, str(v)))
            if kvs:
                sections.append((record_type.upper(), kvs))

    if not sections:
        sections = [("DNS Check", [("Result", str(data))])]

    c.output.detail(f"DNS Check -- {domain}", sections, data_for_json=data)


def _handle_result(c: AppContext, result: dict | list, success_msg: str) -> None:
    """Handle Mailcow API result (list of {type, log, msg})."""
    if isinstance(result, list):
        errors = [r for r in result if isinstance(r, dict) and r.get("type") == "danger"]
        if errors:
            for e in errors:
                c.output.error(str(e.get("msg", e)))
            raise typer.Exit(1)
        c.output.success(success_msg)
        if c.json_mode:
            c.output.raw_json(result)
    elif isinstance(result, dict):
        if result.get("type") == "danger":
            c.output.error(str(result.get("msg", result)))
            raise typer.Exit(1)
        c.output.success(success_msg)
        if c.json_mode:
            c.output.raw_json(result)
    else:
        c.output.success(success_msg)
