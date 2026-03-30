"""Stage management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_ak.core.callbacks import AppContext

app = typer.Typer(help="Stage management (prompt, password, identification, consent, email, etc.).")


@app.command("list")
def list_(
    ctx: typer.Context,
    type_: Annotated[str | None, typer.Option("--type", help="Filter by stage type")] = None,
) -> None:
    """List all stages."""
    c: AppContext = ctx.obj
    params: dict = {}
    if type_:
        params["type"] = type_

    stages = c.client.get_all("stages/all/", params=params)

    rows = []
    for s in stages:
        rows.append(
            [
                str(s.get("pk", "")),
                s.get("verbose_name", s.get("object_type", "")),
                s.get("name", ""),
                str(s.get("flow_set", []).__len__()) if isinstance(s.get("flow_set"), list) else "-",
            ]
        )

    c.output.table(
        "Stages",
        [("ID", "cyan"), ("Type", "yellow"), ("Name", ""), ("Flows", "dim")],
        rows,
        data_for_json=stages,
    )


@app.command()
def get(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Stage UUID")],
) -> None:
    """Get stage details."""
    c: AppContext = ctx.obj
    s = c.client.get(f"stages/all/{id_}/")

    c.output.detail(
        s.get("name", str(id_)),
        [
            (
                "Stage",
                [
                    ("ID", str(s.get("pk", ""))),
                    ("Name", s.get("name", "")),
                    ("Type", s.get("verbose_name", s.get("object_type", ""))),
                ],
            ),
        ],
        data_for_json=s,
    )


@app.command("create-prompt")
def create_prompt(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Stage name")],
    fields: Annotated[str | None, typer.Option("--fields", help="Comma-separated prompt field UUIDs")] = None,
) -> None:
    """Create a prompt stage."""
    c: AppContext = ctx.obj
    payload: dict = {"name": name}
    if fields:
        payload["fields"] = [f.strip() for f in fields.split(",") if f.strip()]
    result = c.client.post("stages/prompt/", data=payload)
    c.output.success(f"Created prompt stage '{result.get('name', name)}' (ID: {result.get('pk', '?')})")


@app.command("create-password")
def create_password(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Stage name")],
) -> None:
    """Create a password stage."""
    c: AppContext = ctx.obj
    payload = {"name": name, "backends": ["authentik.core.auth.InbuiltBackend"]}
    result = c.client.post("stages/password/", data=payload)
    c.output.success(f"Created password stage '{result.get('name', name)}' (ID: {result.get('pk', '?')})")


@app.command("create-identification")
def create_identification(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Stage name")],
    sources: Annotated[str | None, typer.Option("--sources", help="Comma-separated source UUIDs")] = None,
    user_fields: Annotated[
        str | None, typer.Option("--user-fields", help="Comma-separated user fields (email, username)")
    ] = None,
) -> None:
    """Create an identification stage."""
    c: AppContext = ctx.obj
    payload: dict = {"name": name}
    if sources:
        payload["sources"] = [s.strip() for s in sources.split(",") if s.strip()]
    if user_fields:
        payload["user_fields"] = [f.strip() for f in user_fields.split(",") if f.strip()]
    else:
        payload["user_fields"] = ["email", "username"]
    result = c.client.post("stages/identification/", data=payload)
    c.output.success(f"Created identification stage '{result.get('name', name)}' (ID: {result.get('pk', '?')})")


@app.command("create-consent")
def create_consent(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Stage name")],
    mode: Annotated[
        str, typer.Option("--mode", help="Consent mode: always_require, permanent, expiring")
    ] = "always_require",
) -> None:
    """Create a consent stage."""
    c: AppContext = ctx.obj
    payload = {"name": name, "mode": mode}
    result = c.client.post("stages/consent/", data=payload)
    c.output.success(f"Created consent stage '{result.get('name', name)}' (ID: {result.get('pk', '?')})")


@app.command("create-email")
def create_email(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Stage name")],
    template: Annotated[str, typer.Option("--template", help="Email template name")] = "email/account_confirm.html",
) -> None:
    """Create an email stage."""
    c: AppContext = ctx.obj
    payload = {"name": name, "template": template}
    result = c.client.post("stages/email/", data=payload)
    c.output.success(f"Created email stage '{result.get('name', name)}' (ID: {result.get('pk', '?')})")


@app.command("create-user-login")
def create_user_login(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Stage name")],
) -> None:
    """Create a user login stage."""
    c: AppContext = ctx.obj
    payload = {"name": name}
    result = c.client.post("stages/user_login/", data=payload)
    c.output.success(f"Created user-login stage '{result.get('name', name)}' (ID: {result.get('pk', '?')})")


@app.command("create-user-logout")
def create_user_logout(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Stage name")],
) -> None:
    """Create a user logout stage."""
    c: AppContext = ctx.obj
    payload = {"name": name}
    result = c.client.post("stages/user_logout/", data=payload)
    c.output.success(f"Created user-logout stage '{result.get('name', name)}' (ID: {result.get('pk', '?')})")


@app.command("create-authenticator-validate")
def create_authenticator_validate(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Stage name")],
) -> None:
    """Create an authenticator validation stage."""
    c: AppContext = ctx.obj
    payload = {"name": name}
    result = c.client.post("stages/authenticator_validate/", data=payload)
    c.output.success(f"Created authenticator-validate stage '{result.get('name', name)}' (ID: {result.get('pk', '?')})")


@app.command()
def update(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Stage UUID")],
    name: Annotated[str | None, typer.Option("--name", help="New name")] = None,
) -> None:
    """Update a stage."""
    c: AppContext = ctx.obj
    payload: dict = {}
    if name is not None:
        payload["name"] = name

    if not payload:
        c.output.error("No fields to update. Use --name.")
        raise typer.Exit(1)

    result = c.client.put(f"stages/all/{id_}/", data=payload)
    c.output.success(f"Updated stage '{result.get('name', id_)}'")


@app.command()
def delete(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Stage UUID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a stage."""
    if not force:
        typer.confirm(f"Delete stage {id_}?", abort=True)
    c: AppContext = ctx.obj
    c.client.delete(f"stages/all/{id_}/")
    c.output.success(f"Deleted stage {id_}")


@app.command()
def prompts(ctx: typer.Context) -> None:
    """List prompt fields (prompt stage field definitions)."""
    c: AppContext = ctx.obj
    data = c.client.get_all("stages/prompt/prompts/")

    rows = []
    for p in data:
        rows.append(
            [
                str(p.get("pk", "")),
                p.get("name", p.get("field_key", "")),
                p.get("field_key", ""),
                p.get("type", ""),
                str(p.get("required", False)),
                str(p.get("order", 0)),
            ]
        )

    c.output.table(
        "Prompt Fields",
        [("ID", "cyan"), ("Name", ""), ("Field Key", ""), ("Type", "yellow"), ("Required", ""), ("Order", "dim")],
        rows,
        data_for_json=data,
    )
