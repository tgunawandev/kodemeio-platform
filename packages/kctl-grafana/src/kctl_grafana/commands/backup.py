"""Backup and restore commands."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from kctl_grafana.core.callbacks import AppContext

app = typer.Typer(help="Backup and restore dashboards and datasources.")


@app.command("create")
def create_backup(
    ctx: typer.Context,
    output_dir: Annotated[str | None, typer.Option("--output", "-o", help="Output directory")] = None,
) -> None:
    """Export all dashboards and datasources to a backup directory."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    if output_dir is None:
        output_dir = f"grafana-backup-{timestamp}"

    backup_path = Path(output_dir)
    dashboards_path = backup_path / "dashboards"
    datasources_path = backup_path / "datasources"
    dashboards_path.mkdir(parents=True, exist_ok=True)
    datasources_path.mkdir(parents=True, exist_ok=True)

    # Export dashboards
    out.info("Exporting dashboards...")
    dashboards = client.get("/search", params={"type": "dash-db", "limit": 5000})
    dashboard_count = 0

    for dash in dashboards:
        uid = dash.get("uid", "")
        if not uid:
            continue
        try:
            result = client.get(f"/dashboards/uid/{uid}")
            dashboard_data = result.get("dashboard", {})
            dashboard_data.pop("id", None)  # Remove id for portability

            export_data = {
                "dashboard": dashboard_data,
                "meta": result.get("meta", {}),
                "overwrite": True,
            }

            title_slug = dash.get("title", uid).replace(" ", "-").replace("/", "-").lower()
            file_path = dashboards_path / f"{title_slug}-{uid}.json"
            file_path.write_text(json.dumps(export_data, indent=2))
            dashboard_count += 1
        except Exception as e:
            out.warn(f"Failed to export dashboard '{dash.get('title', uid)}': {e}")

    # Export datasources
    out.info("Exporting datasources...")
    datasources = client.get("/datasources")
    datasource_count = 0

    for ds in datasources:
        ds_name = ds.get("name", "unknown")
        try:
            # Remove sensitive fields
            safe_ds = dict(ds)
            safe_ds.pop("secureJsonFields", None)
            safe_ds.pop("secureJsonData", None)
            safe_ds.pop("id", None)

            name_slug = ds_name.replace(" ", "-").replace("/", "-").lower()
            file_path = datasources_path / f"{name_slug}.json"
            file_path.write_text(json.dumps(safe_ds, indent=2))
            datasource_count += 1
        except Exception as e:
            out.warn(f"Failed to export datasource '{ds_name}': {e}")

    # Write manifest
    manifest = {
        "created_at": timestamp,
        "grafana_version": client.get_version(),
        "dashboards": dashboard_count,
        "datasources": datasource_count,
    }
    (backup_path / "manifest.json").write_text(json.dumps(manifest, indent=2))

    out.success(f"Backup created: {backup_path}")
    out.kv("Dashboards", str(dashboard_count))
    out.kv("Datasources", str(datasource_count))


@app.command("restore")
def restore_backup(
    ctx: typer.Context,
    backup_dir: Annotated[str, typer.Argument(help="Backup directory to restore from")],
    skip_datasources: Annotated[bool, typer.Option("--skip-datasources", help="Skip datasource restore")] = False,
    skip_dashboards: Annotated[bool, typer.Option("--skip-dashboards", help="Skip dashboard restore")] = False,
) -> None:
    """Restore dashboards and datasources from a backup directory."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    backup_path = Path(backup_dir)
    if not backup_path.exists():
        out.error(f"Backup directory not found: {backup_path}")
        raise typer.Exit(1)

    manifest_path = backup_path / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        created = manifest.get("created_at", "unknown")
        gf_ver = manifest.get("grafana_version", "unknown")
        out.info(f"Restoring backup from {created} (Grafana v{gf_ver})")

    # Restore datasources first (dashboards may depend on them)
    ds_restored = 0
    if not skip_datasources:
        datasources_path = backup_path / "datasources"
        if datasources_path.exists():
            out.info("Restoring datasources...")
            for ds_file in sorted(datasources_path.glob("*.json")):
                try:
                    ds_data = json.loads(ds_file.read_text())
                    ds_name = ds_data.get("name", ds_file.stem)

                    # Check if datasource already exists
                    try:
                        existing = client.get(f"/datasources/name/{ds_name}")
                        # Update existing
                        ds_data["id"] = existing.get("id")
                        client.put(f"/datasources/{existing.get('id')}", json_body=ds_data)
                        out.info(f"  Updated datasource: {ds_name}")
                    except Exception:
                        # Create new
                        client.post("/datasources", json_body=ds_data)
                        out.info(f"  Created datasource: {ds_name}")

                    ds_restored += 1
                except Exception as e:
                    out.warn(f"  Failed to restore datasource from {ds_file.name}: {e}")

    # Restore dashboards
    dash_restored = 0
    if not skip_dashboards:
        dashboards_path = backup_path / "dashboards"
        if dashboards_path.exists():
            out.info("Restoring dashboards...")
            for dash_file in sorted(dashboards_path.glob("*.json")):
                try:
                    dash_data = json.loads(dash_file.read_text())

                    # Ensure proper import format
                    payload = dash_data if "dashboard" in dash_data else {"dashboard": dash_data}

                    payload["overwrite"] = True
                    payload.get("dashboard", {}).pop("id", None)

                    client.post("/dashboards/db", json_body=payload)
                    title = payload.get("dashboard", {}).get("title", dash_file.stem)
                    out.info(f"  Restored dashboard: {title}")
                    dash_restored += 1
                except Exception as e:
                    out.warn(f"  Failed to restore dashboard from {dash_file.name}: {e}")

    out.success("Restore complete")
    out.kv("Datasources restored", str(ds_restored))
    out.kv("Dashboards restored", str(dash_restored))
