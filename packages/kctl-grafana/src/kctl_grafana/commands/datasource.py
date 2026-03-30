"""Datasource management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_grafana.core.callbacks import AppContext

app = typer.Typer(help="Datasource management.")


@app.command("list")
def list_datasources(ctx: typer.Context) -> None:
    """List all datasources with type and status."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    datasources = client.get("/datasources")

    rows: list[list[str]] = []
    for ds in datasources:
        uid = ds.get("uid", "")
        name = ds.get("name", "")
        ds_type = ds.get("type", "")
        url = ds.get("url", "")
        is_default = "[green]*[/green]" if ds.get("isDefault") else ""
        rows.append([uid, name, ds_type, url, is_default])

    out.table(
        f"Datasources ({len(datasources)})",
        [("UID", "cyan"), ("Name", ""), ("Type", ""), ("URL", "dim"), ("Default", "")],
        rows,
        data_for_json=datasources,
    )


@app.command("show")
def show_datasource(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Datasource name")],
) -> None:
    """Show datasource configuration details."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    ds = client.get(f"/datasources/name/{name}")

    sections = [
        (
            "Datasource",
            [
                ("UID", ds.get("uid", "")),
                ("Name", ds.get("name", "")),
                ("Type", ds.get("type", "")),
                ("URL", ds.get("url", "")),
                ("Database", ds.get("database", "")),
                ("Default", str(ds.get("isDefault", False))),
                ("Read-only", str(ds.get("readOnly", False))),
                ("Access", ds.get("access", "")),
            ],
        ),
    ]

    json_data = ds.get("jsonData", {})
    if json_data:
        sections.append(
            (
                "JSON Data",
                [(k, str(v)) for k, v in json_data.items()],
            )
        )

    out.detail(
        f"Datasource: {name}",
        sections,
        data_for_json=ds,
    )


@app.command("test")
def test_datasource(
    ctx: typer.Context,
    name: Annotated[str | None, typer.Argument(help="Datasource name (tests all if omitted)")] = None,
) -> None:
    """Test datasource connectivity. Tests all datasources if no name given."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    if name:
        # Test single datasource
        ds = client.get(f"/datasources/name/{name}")
        ds_uid = ds.get("uid", "")
        try:
            result = client.post(f"/datasources/uid/{ds_uid}/health", json_body={})
            status = result.get("status", "unknown")
            if status == "OK":
                out.success(f"Datasource '{name}' is healthy")
            else:
                out.error(f"Datasource '{name}' health: {status} \u2014 {result.get('message', '')}")
                raise typer.Exit(1)
        except Exception as e:
            out.error(f"Datasource '{name}' test failed: {e}")
            raise typer.Exit(1) from e
    else:
        # Test all datasources
        datasources = client.get("/datasources")
        rows: list[list[str]] = []
        all_ok = True

        for ds in datasources:
            ds_uid = ds.get("uid", "")
            ds_name = ds.get("name", "unknown")
            ds_type = ds.get("type", "unknown")

            try:
                result = client.post(f"/datasources/uid/{ds_uid}/health", json_body={})
                status = result.get("status", "unknown")
                message = result.get("message", "")
                if status == "OK":
                    status_display = "[green]OK[/green]"
                else:
                    status_display = f"[red]{status}[/red]"
                    all_ok = False
            except Exception as e:
                status_display = "[red]ERROR[/red]"
                message = str(e)
                all_ok = False

            rows.append([ds_name, ds_type, status_display, message])

        out.table(
            f"Datasource Health ({len(datasources)})",
            [("Name", ""), ("Type", "dim"), ("Status", ""), ("Message", "dim")],
            rows,
        )

        if all_ok:
            out.success("All datasources healthy")
        else:
            out.warn("Some datasources have issues")
            raise typer.Exit(1)
