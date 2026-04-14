"""Property mapping management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_ak.core.callbacks import AppContext

app = typer.Typer(help="Property mapping management (scope, SAML, LDAP, SCIM).")


@app.command("list")
def list_(
    ctx: typer.Context,
    type_: Annotated[str | None, typer.Option("--type", help="Filter by type: saml, ldap, scim, scope")] = None,
) -> None:
    """List all property mappings."""
    c: AppContext = ctx.obj
    params: dict = {}
    if type_:
        params["type"] = type_

    mappings = c.client.get_all("propertymappings/all/", params=params)

    rows = []
    for m in mappings:
        rows.append(
            [
                str(m.get("pk", "")),
                m.get("verbose_name", m.get("object_type", "")),
                m.get("name", ""),
                str(m.get("managed", "") or "-"),
            ]
        )

    c.output.table(
        "Property Mappings",
        [("ID", "cyan"), ("Type", "yellow"), ("Name", ""), ("Managed", "dim")],
        rows,
        data_for_json=mappings,
    )


@app.command()
def get(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Property mapping UUID")],
) -> None:
    """Get property mapping details."""
    c: AppContext = ctx.obj
    m = c.client.get(f"propertymappings/all/{id_}/")

    c.output.detail(
        m.get("name", str(id_)),
        [
            (
                "Mapping",
                [
                    ("ID", str(m.get("pk", ""))),
                    ("Name", m.get("name", "")),
                    ("Type", m.get("verbose_name", m.get("object_type", ""))),
                    ("Managed", str(m.get("managed", "") or "-")),
                    ("Expression", m.get("expression", "-")),
                ],
            ),
        ],
        data_for_json=m,
    )


@app.command("create-scope")
def create_scope(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Mapping name")],
    scope_name: Annotated[str, typer.Option("--scope-name", help="OAuth2 scope name")],
    expression: Annotated[str, typer.Option("--expression", help="Python expression")],
) -> None:
    """Create an OAuth2 scope mapping."""
    c: AppContext = ctx.obj
    payload = {
        "name": name,
        "scope_name": scope_name,
        "expression": expression,
    }
    result = c.client.post("propertymappings/provider/scope/", data=payload)
    c.output.success(f"Created scope mapping '{result.get('name', name)}' (ID: {result.get('pk', '?')})")


@app.command("create-saml")
def create_saml(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Mapping name")],
    saml_name: Annotated[str, typer.Option("--saml-name", help="SAML attribute name")],
    expression: Annotated[str, typer.Option("--expression", help="Python expression")],
) -> None:
    """Create a SAML property mapping."""
    c: AppContext = ctx.obj
    payload = {
        "name": name,
        "saml_name": saml_name,
        "expression": expression,
    }
    result = c.client.post("propertymappings/provider/saml/", data=payload)
    c.output.success(f"Created SAML mapping '{result.get('name', name)}' (ID: {result.get('pk', '?')})")


@app.command("create-ldap")
def create_ldap(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Mapping name")],
    object_field: Annotated[str, typer.Option("--object-field", help="LDAP object field")],
    expression: Annotated[str, typer.Option("--expression", help="Python expression")],
) -> None:
    """Create an LDAP property mapping."""
    c: AppContext = ctx.obj
    payload = {
        "name": name,
        "object_field": object_field,
        "expression": expression,
    }
    result = c.client.post("propertymappings/source/ldap/", data=payload)
    c.output.success(f"Created LDAP mapping '{result.get('name', name)}' (ID: {result.get('pk', '?')})")


@app.command("create-scim")
def create_scim(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Mapping name")],
    expression: Annotated[str, typer.Option("--expression", help="Python expression")],
) -> None:
    """Create a SCIM property mapping."""
    c: AppContext = ctx.obj
    payload = {
        "name": name,
        "expression": expression,
    }
    result = c.client.post("propertymappings/provider/scim/", data=payload)
    c.output.success(f"Created SCIM mapping '{result.get('name', name)}' (ID: {result.get('pk', '?')})")


@app.command()
def update(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Property mapping UUID")],
    name: Annotated[str | None, typer.Option("--name", help="New name")] = None,
    expression: Annotated[str | None, typer.Option("--expression", help="New expression")] = None,
) -> None:
    """Update a property mapping."""
    c: AppContext = ctx.obj
    payload: dict = {}
    if name is not None:
        payload["name"] = name
    if expression is not None:
        payload["expression"] = expression

    if not payload:
        c.output.error("No fields to update. Use --name or --expression.")
        raise typer.Exit(1)

    result = c.client.put(f"propertymappings/all/{id_}/", data=payload)
    c.output.success(f"Updated property mapping '{result.get('name', id_)}'")


@app.command()
def delete(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Property mapping UUID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a property mapping."""
    if not force:
        typer.confirm(f"Delete property mapping {id_}?", abort=True)
    c: AppContext = ctx.obj
    c.client.delete(f"propertymappings/all/{id_}/")
    c.output.success(f"Deleted property mapping {id_}")


@app.command()
def test(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Property mapping UUID")],
    user: Annotated[int, typer.Option("--user", help="User PK to test against")],
) -> None:
    """Test a property mapping against a user."""
    c: AppContext = ctx.obj
    result = c.client.post(f"propertymappings/all/{id_}/test/", data={"user": user})

    successful = result.get("successful", False)
    status = "[green]OK[/green]" if successful else "[red]FAIL[/red]"

    sections = [
        (
            "Result",
            [
                ("Mapping", str(id_)),
                ("User", str(user)),
                ("Status", status),
                ("Result", str(result.get("result", "-"))),
            ],
        ),
    ]

    c.output.detail("Property Mapping Test", sections, data_for_json=result)
