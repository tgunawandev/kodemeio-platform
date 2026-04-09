"""OpenAPI code generation commands."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Annotated

import typer

from kctl_react.core.callbacks import AppContext
from kctl_react.core.discovery import get_app_dir
from kctl_react.core.runner import run_pnpm

app = typer.Typer(help="OpenAPI schema fetch and type generation.")


@app.callback(invoke_without_command=True)
def codegen(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Option("--app", "-a", help="App name (omit for all apps)")] = None,
    module: Annotated[
        str | None,
        typer.Option("--module", "-m", help="Regenerate a single module (erp app only). Requires --app erp."),
    ] = None,
) -> None:
    """Fetch OpenAPI schema and regenerate TypeScript types.

    Examples:
      kctl-react codegen --app sfa         # Generate types for SFA
      kctl-react codegen --app erp         # Generate types for the erp app
      kctl-react codegen --app erp --module sfa  # Regenerate erp/sfa module types only
      kctl-react codegen                   # Generate types for all apps
    """
    if ctx.invoked_subcommand is not None:
        return

    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    # --module requires --app erp
    if module is not None:
        if app_name is None:
            out.error("--module requires --app erp")
            raise typer.Exit(1)
        if app_name != "erp":
            out.error(f"--module is only supported for the erp app, not '{app_name}'")
            raise typer.Exit(1)

        actx.validate_app("erp")
        erp_dir = get_app_dir(root, "erp")
        config_path = erp_dir / "src" / "modules" / module / "module.openapi.ts"

        if not config_path.exists():
            out.error(
                f"Module '{module}' does not have a codegen config yet. "
                f"Add src/modules/{module}/module.openapi.ts first."
            )
            raise typer.Exit(1)

        out.info(f"Regenerating types for erp/{module}...")
        try:
            result = subprocess.run(
                ["pnpm", "--filter", "@kodemeio/erp", "exec", "openapi-ts", "--config", str(config_path)],
                cwd=root,
                timeout=60,
                check=True,
            )
            out.success(f"erp/{module}: types generated")
        except subprocess.CalledProcessError as e:
            out.error(f"erp/{module}: codegen failed — {e}")
            raise typer.Exit(1) from None
        return

    apps_to_gen = [app_name] if app_name else actx.app_names
    if app_name:
        actx.validate_app(app_name)

    succeeded = 0
    failed = 0

    for name in apps_to_gen:
        app_dir = get_app_dir(root, name)

        if not (app_dir / "openapi-ts.config.ts").exists():
            out.warn(f"{name}: no openapi-ts.config.ts, skipping")
            continue

        out.info(f"Generating types for {name}...")
        try:
            run_pnpm(["generate:api"], cwd=app_dir, timeout=60)
            out.success(f"{name}: types generated")
            succeeded += 1
        except Exception as e:
            out.error(f"{name}: codegen failed — {e}")
            failed += 1

    if failed:
        out.warn(f"Codegen: {succeeded} succeeded, {failed} failed")
        raise typer.Exit(1) from None

    out.success(f"Codegen complete: {succeeded} app(s)")


@app.command()
def status(ctx: typer.Context) -> None:
    """Show codegen setup status for each app."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    rows: list[list[str]] = []
    json_data: list[dict] = []

    def icon(ok: bool) -> str:
        return "[green]OK[/green]" if ok else "[red]--[/red]"

    for name in actx.app_names:
        app_dir = get_app_dir(root, name)
        has_config = (app_dir / "openapi-ts.config.ts").exists()
        has_generated = (app_dir / "src" / "generated").is_dir()
        has_types_api = (app_dir / "src" / "types" / "api.ts").exists()

        rows.append([name, icon(has_config), icon(has_generated), icon(has_types_api)])
        json_data.append(
            {
                "app": name,
                "config": has_config,
                "generated": has_generated,
                "types_api": has_types_api,
            }
        )

    out.table(
        "OpenAPI Codegen Status",
        [("App", "cyan"), ("Config", ""), ("Generated", ""), ("types/api.ts", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def diff(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
) -> None:
    """Show what types changed after regenerating OpenAPI types.

    Runs codegen, then shows git diff of the generated files.
    """
    import subprocess

    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = get_app_dir(root, app_name)
    gen_dir = app_dir / "src" / "generated"

    if not (app_dir / "openapi-ts.config.ts").exists():
        out.error(f"{app_name}: no openapi-ts.config.ts")
        raise typer.Exit(1)

    out.info(f"Regenerating types for {app_name}...")
    try:
        run_pnpm(["generate:api"], cwd=app_dir, timeout=60)
    except Exception as e:
        out.error(f"Codegen failed: {e}")
        raise typer.Exit(1) from None

    # Show git diff of generated files
    out.info("Changes in generated types:")
    try:
        result = subprocess.run(
            ["git", "diff", "--stat", str(gen_dir)],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.stdout.strip():
            out.text(result.stdout)
            # Also show detailed diff
            detail = subprocess.run(
                ["git", "diff", str(gen_dir)],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if detail.stdout.strip():
                # Count additions/deletions
                adds = sum(
                    1 for line in detail.stdout.splitlines() if line.startswith("+") and not line.startswith("+++")
                )
                dels = sum(
                    1 for line in detail.stdout.splitlines() if line.startswith("-") and not line.startswith("---")
                )
                out.success(f"{adds} addition(s), {dels} deletion(s)")
        else:
            out.success("No changes — types are up to date")
    except Exception:
        out.warn("Could not compute diff (not in git repo?)")


@app.command()
def endpoints(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
) -> None:
    """List API endpoints from the app's generated types.

    Parses the generated types.gen.ts to extract endpoint paths.
    """
    import re

    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = get_app_dir(root, app_name)

    # Look for generated types file
    types_file = app_dir / "src" / "generated" / "types.gen.ts"
    if not types_file.exists():
        out.error(f"No generated types at {types_file.relative_to(root)}")
        out.info("Run `kctl-react codegen` first")
        raise typer.Exit(1) from None

    content = types_file.read_text()

    # Extract endpoint paths from type names (e.g., GetCustomersResponse, PostOrdersData)
    # Look for patterns like '/api/v1/customers/' in the file
    path_pattern = re.compile(r"""['"](/[a-z0-9/_-]+/?)['"]""", re.IGNORECASE)
    paths = sorted(set(path_pattern.findall(content)))

    # Also extract operation types (e.g., GetSfaCustomersListResponse)
    type_pattern = re.compile(r"export\s+type\s+(\w+(?:Response|Data|Error))\b")
    types = sorted(set(type_pattern.findall(content)))

    rows: list[list[str]] = []
    json_data: list[dict] = []

    if paths:
        out.header("API Endpoints")
        for path in paths:
            rows.append([path])
            json_data.append({"path": path})
        out.table(
            f"Endpoints: {app_name}",
            [("Path", "cyan")],
            rows,
            data_for_json=json_data,
        )

    if types:
        out.header("Generated Types")
        type_rows: list[list[str]] = []
        for t in types[:30]:  # Limit to 30
            kind = "Response" if "Response" in t else ("Data" if "Data" in t else "Error")
            type_rows.append([t, kind])
        out.table(
            f"Types: {app_name} ({len(types)} total)",
            [("Type", "cyan"), ("Kind", "dim")],
            type_rows,
        )

    out.success(f"{len(paths)} endpoint(s), {len(types)} type(s) found")


@app.command()
def verify(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
) -> None:
    """Verify generated types are properly wired.

    Checks that types.gen.ts exists, src/types/api.ts re-exports from @/generated/,
    and no .ts/.tsx files import directly from @/generated/ (should use @/types/api).
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = get_app_dir(root, app_name)
    src_dir = app_dir / "src"

    issues: list[list[str]] = []
    json_data: list[dict] = []

    # Check 1: types.gen.ts exists
    types_gen = src_dir / "generated" / "types.gen.ts"
    if not types_gen.exists():
        issues.append(["types.gen.ts", "missing", str(types_gen.relative_to(root))])
        json_data.append({"check": "types.gen.ts", "status": "missing", "detail": str(types_gen.relative_to(root))})
    else:
        json_data.append({"check": "types.gen.ts", "status": "ok", "detail": ""})

    # Check 2: src/types/api.ts exists and re-exports from @/generated/
    types_api = src_dir / "types" / "api.ts"
    if not types_api.exists():
        issues.append(["src/types/api.ts", "missing", "file not found"])
        json_data.append({"check": "src/types/api.ts", "status": "missing", "detail": "file not found"})
    else:
        content = types_api.read_text()
        if "@/generated/" not in content:
            issues.append(["src/types/api.ts", "no re-export", "does not import from @/generated/"])
            json_data.append(
                {"check": "src/types/api.ts", "status": "no re-export", "detail": "does not import from @/generated/"}
            )
        else:
            json_data.append({"check": "src/types/api.ts", "status": "ok", "detail": ""})

    # Check 3: scan all .ts/.tsx files for direct imports from @/generated/
    direct_import_pattern = re.compile(r"""from\s+["']@/generated/""")
    direct_violations: list[str] = []
    if src_dir.exists():
        for ts_file in list(src_dir.rglob("*.ts")) + list(src_dir.rglob("*.tsx")):
            # Skip the generated files themselves and types/api.ts
            rel = ts_file.relative_to(src_dir)
            if str(rel).startswith("generated/") or str(rel) == "types/api.ts":
                continue
            try:
                file_content = ts_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if direct_import_pattern.search(file_content):
                direct_violations.append(str(ts_file.relative_to(root)))

    for path in direct_violations:
        issues.append(["direct @/generated/ import", "violation", path])
        json_data.append({"check": "direct @/generated/ import", "status": "violation", "detail": path})

    if issues:
        rows = [[i[0], f"[red]{i[1]}[/red]", i[2]] for i in issues]
        out.table(
            f"Verify: {app_name} — {len(issues)} issue(s)",
            [("Check", "cyan"), ("Status", ""), ("Detail", "dim")],
            rows,
            data_for_json=json_data,
        )
    else:
        out.success(f"{app_name}: all wiring checks passed")
        if out.json_mode:
            out.raw_json(json_data)


@app.command()
def drift(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
) -> None:
    """Detect stale type references.

    Reads exported names from types.gen.ts, then finds hooks/pages importing
    types from @/types/api that no longer exist in the generated file.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = get_app_dir(root, app_name)
    src_dir = app_dir / "src"

    types_gen = src_dir / "generated" / "types.gen.ts"
    types_api = src_dir / "types" / "api.ts"

    if not types_gen.exists():
        out.error(f"{app_name}: types.gen.ts not found — run `kctl-react codegen {app_name}` first")
        raise typer.Exit(1) from None

    # Collect all exported type names from types.gen.ts
    export_pattern = re.compile(r"export\s+(?:type|interface|enum|const|function|class)\s+(\w+)")
    gen_exports: set[str] = set(export_pattern.findall(types_gen.read_text()))

    # Collect re-exported names from types/api.ts
    api_exports: set[str] = set()
    if types_api.exists():
        reexport_pattern = re.compile(r"export\s+(?:type\s+)?\{([^}]+)\}")
        for match in reexport_pattern.finditer(types_api.read_text()):
            for name in match.group(1).split(","):
                name = name.strip().split(" as ")[0].strip()
                if name:
                    api_exports.add(name)

    # Scan hooks and pages for imports from @/types/api
    import_from_api_pattern = re.compile(r"""import\s+(?:type\s+)?\{([^}]+)\}\s+from\s+["']@/types/api["']""")
    stale_refs: list[dict] = []

    for search_dir in [src_dir / "hooks", src_dir / "pages"]:
        if not search_dir.exists():
            continue
        for ts_file in list(search_dir.rglob("*.ts")) + list(search_dir.rglob("*.tsx")):
            try:
                file_content = ts_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for match in import_from_api_pattern.finditer(file_content):
                for name in match.group(1).split(","):
                    name = name.strip().split(" as ")[0].strip()
                    if name and name not in gen_exports and name not in api_exports:
                        stale_refs.append(
                            {
                                "type": name,
                                "file": str(ts_file.relative_to(root)),
                                "status": "stale",
                            }
                        )

    rows: list[list[str]] = []
    for ref in stale_refs:
        rows.append([ref["type"], ref["file"], f"[red]{ref['status']}[/red]"])

    if rows:
        out.table(
            f"Drift: {app_name} — {len(rows)} stale reference(s)",
            [("Type", "cyan"), ("File", "dim"), ("Status", "")],
            rows,
            data_for_json=stale_refs,
        )
    else:
        out.success(f"{app_name}: no stale type references detected")
        if out.json_mode:
            out.raw_json([])


@app.command(name="schema-health")
def schema_health(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
) -> None:
    """Check OpenAPI codegen health for an app.

    Verifies that openapi-ts.config.ts, src/generated/, types.gen.ts (non-empty),
    and src/types/api.ts are all present, and extracts the schema URL from config.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = get_app_dir(root, app_name)
    src_dir = app_dir / "src"

    checks: list[dict] = []

    def _add(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"check": name, "passed": passed, "detail": detail})

    # 1. openapi-ts.config.ts exists
    config_file = app_dir / "openapi-ts.config.ts"
    _add("openapi-ts.config.ts", config_file.exists())

    # 2. src/generated/ directory exists
    gen_dir = src_dir / "generated"
    _add("src/generated/ directory", gen_dir.is_dir())

    # 3. types.gen.ts is non-empty (>50 bytes)
    types_gen = gen_dir / "types.gen.ts"
    gen_size = types_gen.stat().st_size if types_gen.exists() else 0
    _add("types.gen.ts non-empty (>50 bytes)", gen_size > 50, f"{gen_size} bytes")

    # 4. src/types/api.ts exists
    types_api = src_dir / "types" / "api.ts"
    _add("src/types/api.ts", types_api.exists())

    # 5. Extract schema URL from config
    schema_url = ""
    if config_file.exists():
        config_text = config_file.read_text(encoding="utf-8", errors="replace")
        url_match = re.search(r"""input:\s*["']([^"']+)["']""", config_text)
        if url_match:
            schema_url = url_match.group(1)
    _add("schema URL configured", bool(schema_url), schema_url or "not found")

    rows: list[list[str]] = []
    for c in checks:
        icon = "[green]PASS[/green]" if c["passed"] else "[red]FAIL[/red]"
        rows.append([c["check"], icon, c["detail"]])

    out.table(
        f"Schema Health: {app_name}",
        [("Check", "cyan"), ("Status", ""), ("Detail", "dim")],
        rows,
        data_for_json=checks,
    )
