"""Flow management commands.

List, inspect, and export Authentik authentication flows.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_ak.core.callbacks import AppContext

app = typer.Typer(help="Manage authentication flows.")


@app.command("list")
def list_(
    ctx: typer.Context,
    designation: Annotated[
        str | None,
        typer.Option(
            "--designation",
            "-d",
            help="Filter by designation (e.g. authorization, authentication, enrollment, invalidation, recovery, stage_configuration, unenrollment).",
        ),
    ] = None,
) -> None:
    """List all flows."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    params: dict = {}
    if designation:
        params["designation"] = designation

    flows = c.get_all("flows/instances/", params=params)

    rows: list[list[str]] = []
    for f in flows:
        slug = f.get("slug", "")
        name = f.get("name", "")
        desig = f.get("designation", "")
        title = f.get("title", "")
        rows.append([slug, name, desig, title])

    out.table(
        "Flows",
        [("Slug", "cyan"), ("Name", ""), ("Designation", "yellow"), ("Title", "dim")],
        rows,
        data_for_json=flows,
    )


@app.command()
def get(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Flow slug.")],
) -> None:
    """Show flow details."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    flow = c.get(f"flows/instances/{slug}/")

    sections: list[tuple[str, list[tuple[str, str]]]] = []
    sections.append(
        (
            "Identity",
            [
                ("Slug", flow.get("slug", "")),
                ("Name", flow.get("name", "")),
                ("Title", flow.get("title", "")),
                ("PK", flow.get("pk", "")),
            ],
        )
    )
    sections.append(
        (
            "Configuration",
            [
                ("Designation", flow.get("designation", "")),
                ("Policy Engine Mode", flow.get("policy_engine_mode", "")),
                ("Compatibility Mode", str(flow.get("compatibility_mode", False))),
                ("Denied Action", flow.get("denied_action", "")),
                ("Layout", flow.get("layout", "")),
            ],
        )
    )
    sections.append(
        (
            "Metadata",
            [
                ("Authentication", flow.get("authentication", "")),
                ("Background", flow.get("background", "")),
            ],
        )
    )

    out.detail(f"Flow: {flow.get('slug', slug)}", sections, data_for_json=flow)


@app.command()
def bindings(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Flow slug.")],
) -> None:
    """Show flow stage bindings."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    data = c.get_all(
        "flows/bindings/",
        params={"target__slug": slug, "ordering": "order"},
    )

    rows: list[list[str]] = []
    for b in data:
        order = str(b.get("order", ""))
        stage_obj = b.get("stage_obj", {})
        stage_name = stage_obj.get("name", "") if isinstance(stage_obj, dict) else ""
        stage_type = stage_obj.get("verbose_name", "") if isinstance(stage_obj, dict) else ""
        evaluate = str(b.get("evaluate_on_plan", True))
        re_eval = str(b.get("re_evaluate_policies", False))
        invalid_resp = b.get("invalid_response_action", "")
        rows.append([order, stage_name, stage_type, evaluate, re_eval, invalid_resp])

    out.table(
        f"Bindings: {slug}",
        [
            ("Order", "cyan"),
            ("Stage", ""),
            ("Type", "yellow"),
            ("Evaluate", "dim"),
            ("Re-evaluate", "dim"),
            ("Invalid Action", "dim"),
        ],
        rows,
        data_for_json=data,
    )


@app.command()
def stages(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Flow slug.")],
) -> None:
    """List stages used in a flow (via bindings)."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    binding_data = c.get_all(
        "flows/bindings/",
        params={"target__slug": slug, "ordering": "order"},
    )

    rows: list[list[str]] = []
    for b in binding_data:
        stage_obj = b.get("stage_obj", {})
        if not isinstance(stage_obj, dict):
            continue
        pk = stage_obj.get("pk", "")
        name = stage_obj.get("name", "")
        verbose = stage_obj.get("verbose_name", "")
        component = stage_obj.get("component", "")
        order = str(b.get("order", ""))
        rows.append([order, name, verbose, component, str(pk)])

    out.table(
        f"Stages in flow: {slug}",
        [
            ("Order", "cyan"),
            ("Name", ""),
            ("Type", "yellow"),
            ("Component", "dim"),
            ("PK", "dim"),
        ],
        rows,
    )


@app.command("export")
def export_(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Flow slug to export.")],
) -> None:
    """Export a flow as YAML."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    # The export endpoint returns YAML content
    resp = c.request("GET", f"flows/instances/{slug}/export/")
    content = resp.text

    if out.json_mode:
        out.raw_json({"slug": slug, "content": content})
    else:
        out.header(f"Flow Export: {slug}")
        out.text(content)


@app.command("create-recovery")
def create_recovery(
    ctx: typer.Context,
    slug: Annotated[str, typer.Option("--slug", help="Flow slug.")] = "default-recovery-flow",
    name: Annotated[str, typer.Option("--name", help="Flow display name.")] = "Recovery",
    title: Annotated[str, typer.Option("--title", help="Flow page title.")] = "Reset your password",
    set_on_brand: Annotated[
        str | None,
        typer.Option("--set-on-brand", help="Brand UUID to set flow_recovery on (or 'current')."),
    ] = None,
) -> None:
    """Create a minimal recovery flow (prompt + write + login) and optionally bind to a brand.

    The resulting flow is compatible with the built-in
    `POST /core/users/{id}/recovery/` endpoint used by `kctl-ak users recovery`.
    """
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    # Idempotent: reuse existing flow with the same slug if present.
    existing = c.get_all("flows/instances/", params={"slug": slug})
    if existing:
        flow = existing[0]
        out.info(f"Flow '{slug}' already exists (pk={flow['pk']}), reusing.")
    else:
        flow = c.post(
            "flows/instances/",
            data={
                "slug": slug,
                "name": name,
                "title": title,
                "designation": "recovery",
                "authentication": "require_unauthenticated",
            },
        )
        out.success(f"Created recovery flow '{slug}' (pk={flow['pk']})")

    # Resolve stage UUIDs by name
    required = [
        "default-password-change-prompt",
        "default-password-change-write",
        "default-authentication-login",
    ]
    stages = {s["name"]: s["pk"] for s in c.get_all("stages/all/", params={"name__in": ",".join(required)})}
    missing = [n for n in required if n not in stages]
    if missing:
        out.error(f"Missing required stages: {missing}. Are default blueprints applied?")
        raise typer.Exit(1)

    # Bindings already present?
    existing_bindings = c.get_all("flows/bindings/", params={"target": flow["pk"]})
    existing_stages = {b["stage"] for b in existing_bindings}

    plan = [
        (10, stages["default-password-change-prompt"]),
        (20, stages["default-password-change-write"]),
        (30, stages["default-authentication-login"]),
    ]
    for order, stage_pk in plan:
        if stage_pk in existing_stages:
            out.info(f"  order={order} already bound (stage {stage_pk}), skipping.")
            continue
        c.post(
            "flows/bindings/",
            data={
                "target": flow["pk"],
                "stage": stage_pk,
                "order": order,
                "evaluate_on_plan": True,
                "re_evaluate_policies": False,
            },
        )
        out.success(f"  Bound stage {stage_pk} at order {order}")

    if set_on_brand:
        if set_on_brand == "current":
            brands = c.get_all("core/brands/")
            if not brands:
                out.error("No brands configured to set flow_recovery on.")
                raise typer.Exit(1)
            brand_id = brands[0]["brand_uuid"]
        else:
            brand_id = set_on_brand
        current = c.get(f"core/brands/{brand_id}/")
        c.put(
            f"core/brands/{brand_id}/",
            data={"domain": current.get("domain", ""), "flow_recovery": flow["pk"]},
        )
        out.success(f"Set flow_recovery={slug} on brand {brand_id}")

    if out.json_mode:
        out.raw_json({"pk": flow["pk"], "slug": slug})


@app.command()
def execute(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Flow slug.")],
) -> None:
    """Show the flow execution URL."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    # Derive the execute URL from the client's root URL
    root = c._root_url
    execute_url = f"{root}/if/flow/{slug}/"

    if out.json_mode:
        out.raw_json({"slug": slug, "execute_url": execute_url})
    else:
        out.success(f"Flow execute URL: {execute_url}")
