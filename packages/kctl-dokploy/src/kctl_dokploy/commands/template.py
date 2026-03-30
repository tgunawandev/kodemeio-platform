"""Service template management commands — save and apply configurations."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
import yaml

from kctl_dokploy.core.callbacks import AppContext
from kctl_dokploy.core.utils import fmt_timestamp

app = typer.Typer(help="Service templates — save and apply configurations.")

TEMPLATES_DIR = Path.home() / ".config" / "kodemeio" / "templates"

REQUIRED_KEYS = {"name"}


def _ensure_templates_dir() -> Path:
    """Create the templates directory if it does not exist."""
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    return TEMPLATES_DIR


def _template_path(name: str) -> Path:
    """Return the file path for a given template name."""
    safe_name = name.replace("/", "_").replace("\\", "_")
    return _ensure_templates_dir() / f"{safe_name}.yaml"


def _load_template(path: Path) -> dict:
    """Load and return a template dict from a YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        msg = f"Invalid template format in {path}"
        raise ValueError(msg)
    return data


def _validate_template(data: dict) -> list[str]:
    """Validate template structure, returning a list of error messages."""
    errors: list[str] = []
    if not isinstance(data, dict):
        errors.append("Template must be a YAML mapping")
        return errors
    missing = REQUIRED_KEYS - set(data.keys())
    if missing:
        errors.append(f"Missing required keys: {', '.join(sorted(missing))}")
    if "compose_file" in data and not isinstance(data["compose_file"], str):
        errors.append("'compose_file' must be a string")
    if "env" in data and not isinstance(data["env"], str):
        errors.append("'env' must be a string")
    if "domains" in data:
        if not isinstance(data["domains"], list):
            errors.append("'domains' must be a list")
        else:
            for i, d in enumerate(data["domains"]):
                if not isinstance(d, dict):
                    errors.append(f"domains[{i}] must be a mapping")
                elif "host" not in d:
                    errors.append(f"domains[{i}] missing 'host'")
    return errors


@app.command()
def save(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID to save as template")],
    name: Annotated[str, typer.Argument(help="Template name")],
    description: Annotated[str | None, typer.Option("--description", "-d", help="Template description")] = None,
) -> None:
    """Save a compose service as a reusable template."""
    c: AppContext = ctx.obj
    try:
        data = c.client.get("/compose.one", params={"composeId": compose_id})
    except Exception as exc:
        c.output.error(f"Failed to fetch compose service: {exc}")
        raise typer.Exit(1) from exc

    if not isinstance(data, dict):
        c.output.error(f"Compose service '{compose_id}' not found")
        raise typer.Exit(1)

    compose_file = data.get("composeFile", "")
    env = data.get("env", "")
    domains_raw = data.get("domains", [])

    domains: list[dict] = []
    if isinstance(domains_raw, list):
        for d in domains_raw:
            domains.append(
                {
                    "host": d.get("host", ""),
                    "port": d.get("port", 80),
                    "https": d.get("https", True),
                    "certificateType": d.get("certificateType", "letsencrypt"),
                }
            )

    template: dict = {
        "name": name,
        "description": description or f"Template from compose {data.get('name', compose_id)}",
        "created_at": datetime.now(tz=UTC).isoformat(),
        "compose_file": compose_file,
        "env": env,
        "domains": domains,
    }

    path = _template_path(name)
    if path.exists():
        typer.confirm(f"Template '{name}' already exists. Overwrite?", abort=True)

    _ensure_templates_dir()
    with open(path, "w") as f:
        yaml.dump(template, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    c.output.success(f"Template '{name}' saved to {path}")
    if c.json_mode:
        c.output.raw_json(template)


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all saved templates."""
    c: AppContext = ctx.obj
    tpl_dir = _ensure_templates_dir()

    templates: list[dict] = []
    for yaml_file in sorted(tpl_dir.glob("*.yaml")):
        try:
            data = _load_template(yaml_file)
        except Exception:
            continue
        templates.append(
            {
                "name": data.get("name", yaml_file.stem),
                "description": data.get("description", ""),
                "created_at": data.get("created_at", "-"),
                "file": str(yaml_file),
            }
        )

    rows: list[list[str]] = []
    for t in templates:
        rows.append(
            [
                t["name"],
                t["description"],
                fmt_timestamp(t["created_at"]),
            ]
        )

    c.output.table(
        "Templates",
        [("Name", "cyan"), ("Description", ""), ("Created", "dim")],
        rows,
        data_for_json=templates,
    )


@app.command()
def show(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Template name")],
) -> None:
    """Display template contents."""
    c: AppContext = ctx.obj
    path = _template_path(name)
    if not path.exists():
        c.output.error(f"Template '{name}' not found at {path}")
        raise typer.Exit(1)

    try:
        data = _load_template(path)
    except Exception as exc:
        c.output.error(f"Failed to parse template: {exc}")
        raise typer.Exit(1) from exc

    compose_file = data.get("compose_file", "")
    env = data.get("env", "")
    domains = data.get("domains", [])

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Template",
            [
                ("Name", data.get("name", name)),
                ("Description", data.get("description", "-")),
                ("Created", fmt_timestamp(data.get("created_at"))),
                ("File", str(path)),
            ],
        ),
    ]

    if compose_file:
        preview = compose_file.strip()[:500]
        sections.append(("Compose File", [("Content", preview)]))

    if env:
        env_lines = [line for line in env.strip().splitlines() if line.strip() and not line.strip().startswith("#")]
        env_items = []
        for line in env_lines[:20]:
            if "=" in line:
                key, _, value = line.partition("=")
                env_items.append((key.strip(), value.strip()))
            else:
                env_items.append((line, ""))
        if env_items:
            sections.append(("Environment Variables", env_items))

    if domains and isinstance(domains, list):
        domain_items = []
        for d in domains:
            host = d.get("host", "")
            port = str(d.get("port", 80))
            https = "yes" if d.get("https") else "no"
            domain_items.append((host, f"port={port} https={https}"))
        sections.append(("Domains", domain_items))

    c.output.detail(f"Template: {name}", sections, data_for_json=data)


@app.command()
def apply(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Template name to apply")],
    project: Annotated[str, typer.Option("--project", "-p", help="Project ID or name (required)")],
    service_name: Annotated[
        str | None, typer.Option("--service-name", "-n", help="Service name (default: template name)")
    ] = None,
) -> None:
    """Create a new compose service from a saved template."""
    c: AppContext = ctx.obj
    path = _template_path(name)
    if not path.exists():
        c.output.error(f"Template '{name}' not found")
        raise typer.Exit(1)

    try:
        data = _load_template(path)
    except Exception as exc:
        c.output.error(f"Failed to parse template: {exc}")
        raise typer.Exit(1) from exc

    svc_name = service_name or data.get("name", name)

    # Step 1: Create compose service
    c.output.info(f"Creating compose service '{svc_name}' in project '{project}'...")
    try:
        result = c.client.post(
            "/compose.create",
            json={
                "name": svc_name,
                "projectId": project,
            },
        )
    except Exception as exc:
        c.output.error(f"Failed to create compose service: {exc}")
        raise typer.Exit(1) from exc

    compose_id = result.get("composeId", "") if isinstance(result, dict) else ""
    if not compose_id:
        c.output.error("Failed to get compose ID from creation response")
        raise typer.Exit(1)

    c.output.info(f"Compose service created: {compose_id}")

    # Step 2: Upload compose file
    compose_file = data.get("compose_file", "")
    if compose_file:
        try:
            c.client.post(
                "/compose.update",
                json={
                    "composeId": compose_id,
                    "composeFile": compose_file,
                    "sourceType": "raw",
                },
            )
            c.output.info("Compose file uploaded")
        except Exception as exc:
            c.output.warn(f"Failed to upload compose file: {exc}")

    # Step 3: Set environment variables
    env = data.get("env", "")
    if env:
        try:
            c.client.post(
                "/compose.update",
                json={
                    "composeId": compose_id,
                    "env": env,
                },
            )
            c.output.info("Environment variables set")
        except Exception as exc:
            c.output.warn(f"Failed to set environment: {exc}")

    # Step 4: Configure domains
    domains = data.get("domains", [])
    if isinstance(domains, list):
        for d in domains:
            try:
                c.client.post(
                    "/domain.create",
                    json={
                        "composeId": compose_id,
                        "host": d.get("host", ""),
                        "port": d.get("port", 80),
                        "https": d.get("https", True),
                        "certificateType": d.get("certificateType", "letsencrypt"),
                    },
                )
                c.output.info(f"Domain '{d.get('host', '')}' configured")
            except Exception as exc:
                c.output.warn(f"Failed to configure domain '{d.get('host', '')}': {exc}")

    c.output.success(f"Template '{name}' applied as compose '{svc_name}' ({compose_id})")
    if c.json_mode:
        c.output.raw_json({"composeId": compose_id, "name": svc_name, "template": name})


@app.command()
def delete(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Template name to delete")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Remove a saved template."""
    c: AppContext = ctx.obj
    path = _template_path(name)
    if not path.exists():
        c.output.error(f"Template '{name}' not found")
        raise typer.Exit(1)

    if not force:
        typer.confirm(f"Delete template '{name}'? This cannot be undone.", abort=True)

    path.unlink()
    c.output.success(f"Template '{name}' deleted")


@app.command()
def export(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Template name to export")],
    output: Annotated[str, typer.Option("--output", "-o", help="Output file path (required)")],
) -> None:
    """Export a template to a file."""
    c: AppContext = ctx.obj
    path = _template_path(name)
    if not path.exists():
        c.output.error(f"Template '{name}' not found")
        raise typer.Exit(1)

    dest = Path(output)
    if dest.exists():
        typer.confirm(f"File '{output}' already exists. Overwrite?", abort=True)

    try:
        shutil.copy2(path, dest)
    except OSError as exc:
        c.output.error(f"Failed to export template: {exc}")
        raise typer.Exit(1) from exc

    c.output.success(f"Template '{name}' exported to {dest}")


@app.command("import-file")
def import_file(
    ctx: typer.Context,
    file: Annotated[str, typer.Argument(help="Path to template YAML file")],
) -> None:
    """Import a template from an external YAML file."""
    c: AppContext = ctx.obj
    src = Path(file)
    if not src.exists():
        c.output.error(f"File not found: {file}")
        raise typer.Exit(1)

    try:
        data = _load_template(src)
    except Exception as exc:
        c.output.error(f"Failed to parse YAML: {exc}")
        raise typer.Exit(1) from exc

    errors = _validate_template(data)
    if errors:
        for err in errors:
            c.output.error(f"Validation error: {err}")
        raise typer.Exit(1)

    name = data.get("name", src.stem)
    dest = _template_path(name)

    if dest.exists():
        typer.confirm(f"Template '{name}' already exists. Overwrite?", abort=True)

    # Ensure created_at is present
    if "created_at" not in data:
        data["created_at"] = datetime.now(tz=UTC).isoformat()

    _ensure_templates_dir()
    with open(dest, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    c.output.success(f"Template '{name}' imported from {src}")
    if c.json_mode:
        c.output.raw_json(data)
