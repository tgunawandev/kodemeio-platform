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
