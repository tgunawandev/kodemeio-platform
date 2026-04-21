"""Stage management commands."""

from __future__ import annotations

import json
from typing import Annotated, Any

import typer

from kctl_ak.core.callbacks import AppContext

app = typer.Typer(help="Stage management (prompt, password, identification, consent, email, etc.).")


def _stage_endpoint_from_meta(meta_model_name: str | None) -> str | None:
    # e.g. "authentik_stages_user_login.userloginstage" -> "user_login"
    if not meta_model_name:
        return None
    app_label = meta_model_name.split(".", 1)[0]
    if not app_label.startswith("authentik_stages_"):
        return None
    return app_label[len("authentik_stages_") :]


def _parse_set_items(items: list[str] | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for item in items or []:
        if "=" not in item:
            raise typer.BadParameter(f"--set expects KEY=VALUE, got: {item!r}")
        key, _, value = item.partition("=")
        key = key.strip()
        if not key:
            raise typer.BadParameter(f"--set has empty key in: {item!r}")
        try:
            payload[key] = json.loads(value)
        except json.JSONDecodeError:
            payload[key] = value
    return payload


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


_META_FIELDS = {"pk", "name", "component", "verbose_name", "verbose_name_plural", "meta_model_name", "flow_set"}


@app.command()
def get(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Stage UUID")],
) -> None:
    """Get stage details (including type-specific fields like session_duration)."""
    c: AppContext = ctx.obj
    # First hit the polymorphic endpoint to discover the concrete type.
    base = c.client.get(f"stages/all/{id_}/")
    endpoint = _stage_endpoint_from_meta(base.get("meta_model_name"))
    full = c.client.get(f"stages/{endpoint}/{id_}/") if endpoint else base

    meta_kvs: list[tuple[str, str]] = [
        ("ID", str(full.get("pk", ""))),
        ("Name", full.get("name", "")),
        ("Type", full.get("verbose_name", full.get("component", ""))),
    ]
    if endpoint:
        meta_kvs.append(("Endpoint", f"stages/{endpoint}/"))

    extra_kvs: list[tuple[str, str]] = []
    for key in sorted(full.keys()):
        if key in _META_FIELDS:
            continue
        val = full[key]
        if isinstance(val, (dict, list)):
            rendered = json.dumps(val, default=str)
            if len(rendered) > 200:
                rendered = rendered[:197] + "..."
        else:
            rendered = str(val)
        extra_kvs.append((key, rendered))

    sections: list[tuple[str, list[tuple[str, str]]]] = [("Stage", meta_kvs)]
    if extra_kvs:
        sections.append(("Configuration", extra_kvs))
    flow_set = full.get("flow_set") or []
    if flow_set:
        flow_kvs = [(f.get("slug", f.get("name", "?")), f.get("title", "")) for f in flow_set]
        sections.append(("Bound to Flows", flow_kvs))

    c.output.detail(full.get("name", str(id_)), sections, data_for_json=full)


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
    set_items: Annotated[
        list[str] | None,
        typer.Option(
            "--set",
            help="Set an arbitrary field, KEY=VALUE (repeatable). Value is JSON-parsed if possible, else string. "
            "Examples: --set session_duration=days=7  --set terminate_other_sessions=true",
        ),
    ] = None,
) -> None:
    """Update a stage. Dispatches PATCH to the typed endpoint so type-specific fields (session_duration, mode, ...) are accepted."""
    c: AppContext = ctx.obj
    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    payload.update(_parse_set_items(set_items))

    if not payload:
        c.output.error("No fields to update. Use --name or --set KEY=VALUE.")
        raise typer.Exit(1)

    base = c.client.get(f"stages/all/{id_}/")
    endpoint = _stage_endpoint_from_meta(base.get("meta_model_name"))
    target = f"stages/{endpoint}/{id_}/" if endpoint else f"stages/all/{id_}/"
    result = c.client.patch(target, data=payload)
    c.output.success(f"Updated stage '{result.get('name', id_)}' ({', '.join(payload.keys())})")


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
