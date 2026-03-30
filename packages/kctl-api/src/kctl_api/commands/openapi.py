"""OpenAPI spec management commands for kctl-api.

Export, validate, diff, and analyze the API specification.
"""

from __future__ import annotations

import json
import subprocess
from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.utils import find_project_root

app = typer.Typer(name="openapi", help="OpenAPI spec — export, validate, diff, breaking changes.", no_args_is_help=True)


def _fetch_spec(actx: AppContext) -> dict:
    """Fetch OpenAPI spec from running API or raise."""
    data = actx.client.get("/openapi.json")
    if not data:
        raise RuntimeError("Empty response from /openapi.json")
    return data


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------
@app.command()
def export(
    ctx: typer.Context,
    fmt: Annotated[str, typer.Option("--format", help="Output format: json or yaml.")] = "json",
    output: Annotated[str | None, typer.Option("--output", "-o", help="Write to file instead of stdout.")] = None,
) -> None:
    """Fetch /openapi.json from running API and export as JSON or YAML."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        spec = _fetch_spec(actx)
    except Exception as e:
        out.error(f"Failed to fetch spec: {e}")
        raise typer.Exit(1) from None

    if fmt.lower() == "yaml":
        try:
            import yaml  # type: ignore[import-untyped]

            content = yaml.dump(spec, allow_unicode=True, sort_keys=False)
        except ImportError:
            out.error("PyYAML not installed. Run: uv add pyyaml")
            raise typer.Exit(1) from None
    else:
        content = json.dumps(spec, indent=2)

    if output:
        import pathlib

        pathlib.Path(output).write_text(content)
        out.success(f"Spec written to {output}")
    else:
        typer.echo(content)


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------
@app.command()
def validate(ctx: typer.Context) -> None:
    """Check spec completeness — missing descriptions, examples, error schemas."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        spec = _fetch_spec(actx)
    except Exception as e:
        out.error(f"Failed to fetch spec: {e}")
        raise typer.Exit(1) from None

    issues: list[dict] = []
    paths = spec.get("paths", {})

    for path, path_item in paths.items():
        for method, operation in path_item.items():
            if method not in ("get", "post", "put", "patch", "delete", "head", "options"):
                continue
            # Missing summary/description
            if not operation.get("summary") and not operation.get("description"):
                issues.append({"path": path, "method": method.upper(), "issue": "Missing summary/description"})

            # Check for error response schemas (400/422/500)
            responses = operation.get("responses", {})
            has_error_schema = any(str(code) in responses for code in (400, 401, 403, 404, 422, 500))
            if not has_error_schema:
                issues.append({"path": path, "method": method.upper(), "issue": "No error response schema"})

            # Check request body has examples
            req_body = operation.get("requestBody", {})
            if req_body:
                content = req_body.get("content", {})
                for media_type, media_obj in content.items():
                    if not media_obj.get("example") and not media_obj.get("examples"):
                        issues.append(
                            {
                                "path": path,
                                "method": method.upper(),
                                "issue": f"Request body missing example ({media_type})",
                            }
                        )

    if not issues:
        out.success(f"Spec validation passed — {len(paths)} paths checked, no issues found.")
        return

    rows = [[i["method"], i["path"], i["issue"]] for i in issues]
    out.table(
        title=f"Spec Issues ({len(issues)})",
        columns=[("Method", "bold"), ("Path", ""), ("Issue", "yellow")],
        rows=rows,
        data_for_json=issues,
    )
    raise typer.Exit(1)


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------
@app.command()
def diff(
    ctx: typer.Context,
    base: Annotated[str, typer.Option("--base", help="Git ref to compare against.")] = "main",
) -> None:
    """Diff OpenAPI spec between current state and a git ref."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()

    # Export current spec to temp file
    try:
        current_spec = _fetch_spec(actx)
    except Exception as e:
        out.error(f"Failed to fetch current spec: {e}")
        raise typer.Exit(1) from None

    import pathlib
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(current_spec, f, indent=2)
        current_file = f.name

    # Get spec from base ref
    base_file = pathlib.Path(tempfile.mktemp(suffix=".json"))
    result = subprocess.run(
        ["git", "show", f"{base}:apps/api/openapi.json"],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        out.warn(f"Could not find spec at {base}:apps/api/openapi.json — showing current spec only.")
        out.info("To generate a base spec: kctl-api openapi export -o apps/api/openapi.json && git commit")
        raise typer.Exit(0)

    base_file.write_text(result.stdout)

    subprocess.run(["diff", "-u", str(base_file), current_file], capture_output=False)

    pathlib.Path(current_file).unlink(missing_ok=True)
    base_file.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# breaking
# ---------------------------------------------------------------------------
@app.command()
def breaking(
    ctx: typer.Context,
    base: Annotated[str, typer.Option("--base", help="Git ref to compare against.")] = "main",
) -> None:
    """Detect breaking changes — removed endpoints, changed types, removed fields."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()

    try:
        current_spec = _fetch_spec(actx)
    except Exception as e:
        out.error(f"Failed to fetch current spec: {e}")
        raise typer.Exit(1) from None

    # Attempt to load base spec from git
    result = subprocess.run(
        ["git", "show", f"{base}:apps/api/openapi.json"],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        out.warn(f"No base spec found at {base}:apps/api/openapi.json")
        out.info("Commit your openapi.json to enable breaking change detection.")
        raise typer.Exit(0)

    try:
        base_spec = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        out.error(f"Could not parse base spec: {e}")
        raise typer.Exit(1) from None

    changes: list[dict] = []
    base_paths = base_spec.get("paths", {})
    curr_paths = current_spec.get("paths", {})

    # Removed endpoints
    for path in base_paths:
        if path not in curr_paths:
            changes.append({"severity": "BREAKING", "type": "Removed endpoint", "detail": path})
        else:
            for method in base_paths[path]:
                if method not in ("get", "post", "put", "patch", "delete"):
                    continue
                if method not in curr_paths.get(path, {}):
                    changes.append(
                        {
                            "severity": "BREAKING",
                            "type": "Removed method",
                            "detail": f"{method.upper()} {path}",
                        }
                    )

    # New endpoints (informational)
    for path in curr_paths:
        if path not in base_paths:
            changes.append({"severity": "INFO", "type": "New endpoint", "detail": path})

    if not changes:
        out.success("No breaking changes detected.")
        return

    rows = [[c["severity"], c["type"], c["detail"]] for c in changes]
    out.table(
        title=f"Breaking Change Analysis ({len(changes)} changes)",
        columns=[("Severity", "bold"), ("Type", ""), ("Detail", "")],
        rows=rows,
        data_for_json=changes,
    )

    has_breaking = any(c["severity"] == "BREAKING" for c in changes)
    if has_breaking:
        out.error("Breaking changes detected!")
        raise typer.Exit(1)
    else:
        out.warn("Non-breaking changes only.")


# ---------------------------------------------------------------------------
# clients
# ---------------------------------------------------------------------------
@app.command()
def clients(ctx: typer.Context) -> None:
    """Show information about generating client SDKs from the OpenAPI spec."""
    actx: AppContext = ctx.obj
    out = actx.output

    url = actx.client.base_url.rstrip("/")
    spec_url = f"{url}/openapi.json"

    out.header("Client SDK Generation")
    out.text("")
    out.text("[bold]OpenAPI spec URL:[/bold]")
    out.text(f"  {spec_url}")
    out.text("")
    out.text("[bold]Generate TypeScript client (openapi-typescript-codegen):[/bold]")
    out.text(f"  npx openapi-typescript-codegen --input {spec_url} --output src/api --client axios")
    out.text("")
    out.text("[bold]Generate Python client (openapi-python-client):[/bold]")
    out.text(f"  uvx openapi-python-client generate --url {spec_url}")
    out.text("")
    out.text("[bold]Export spec first:[/bold]")
    out.text("  kctl-api openapi export --format json -o openapi.json")
    out.text("  kctl-api openapi export --format yaml -o openapi.yaml")
    out.text("")
    out.text("[bold]Validate before generating:[/bold]")
    out.text("  kctl-api openapi validate")

    if actx.json_mode:
        out.raw_json(
            {
                "spec_url": spec_url,
                "tools": {
                    "typescript": f"npx openapi-typescript-codegen --input {spec_url} --output src/api --client axios",
                    "python": f"uvx openapi-python-client generate --url {spec_url}",
                },
            }
        )
