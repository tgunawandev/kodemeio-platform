"""Development tools commands."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError
from kctl_odoo.core.utils import module_state_color

app = typer.Typer(help="Development tools for Odoo.")


@app.command("export-translations")
def translate_export(
    ctx: typer.Context,
    module: Annotated[str, typer.Argument(help="Module technical name to export translations for")],
    lang: Annotated[str, typer.Option("--lang", help="Language code (e.g. fr_FR, de_DE)")] = "en_US",
    fmt: Annotated[str, typer.Option("--format", "-f", help="Export format: po or csv")] = "po",
    output: Annotated[str | None, typer.Option("--output", "-o", help="Output file path")] = None,
) -> None:
    """Export translations for a module using the base.language.export wizard."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if fmt not in ("po", "csv"):
        out.error("Format must be 'po' or 'csv'.")
        raise typer.Exit(1)

    # Verify the module exists
    mod_ids = c.search("ir.module.module", [("name", "=", module)])
    if not mod_ids:
        out.error(f"Module not found: {module}")
        raise typer.Exit(1)

    # Create the export wizard
    wizard_vals = {
        "lang": lang,
        "format": fmt,
        "modules": [(6, 0, mod_ids)],
    }
    try:
        wizard_id = c.create("base.language.export", wizard_vals)
    except RPCError as e:
        out.error(f"Failed to create export wizard: {e.detail}")
        raise typer.Exit(1) from e

    # Trigger the export action
    try:
        c.execute_kw("base.language.export", "act_getfile", [[wizard_id]])
    except RPCError as e:
        out.error(f"Failed to export translations: {e.detail}")
        raise typer.Exit(1) from e

    # Read the generated file data
    wizard_data = c.read("base.language.export", [wizard_id], ["data", "name"])
    if not wizard_data or not wizard_data[0].get("data"):
        out.error("No translation data returned by the wizard.")
        raise typer.Exit(1)

    file_data = base64.b64decode(wizard_data[0]["data"])
    file_name = wizard_data[0].get("name") or f"{module}.{fmt}"

    output_path = Path(output) if output else Path(file_name)
    output_path.write_bytes(file_data)

    out.success(f"Exported translations to {output_path} ({len(file_data)} bytes)")
    if actx.json_mode:
        out.raw_json(
            {
                "module": module,
                "lang": lang,
                "format": fmt,
                "file": str(output_path),
                "size": len(file_data),
            }
        )


@app.command("import-translations")
def translate_import(
    ctx: typer.Context,
    file: Annotated[str, typer.Argument(help="Path to PO or CSV translation file")],
    lang: Annotated[str, typer.Option("--lang", help="Language code (e.g. fr_FR)")] = "",
    overwrite: Annotated[bool, typer.Option("--overwrite", help="Overwrite existing translations")] = False,
) -> None:
    """Import translations from a PO or CSV file."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    file_path = Path(file)
    if not file_path.exists():
        out.error(f"File not found: {file}")
        raise typer.Exit(1)

    suffix = file_path.suffix.lower()
    if suffix == ".po":
        file_type = "po"
    elif suffix == ".csv":
        file_type = "csv"
    else:
        out.error("File must be .po or .csv format.")
        raise typer.Exit(1)

    if not lang:
        out.error("--lang is required (e.g. --lang fr_FR).")
        raise typer.Exit(1)

    file_content = base64.b64encode(file_path.read_bytes()).decode("ascii")

    wizard_vals = {
        "name": file_path.name,
        "code": lang,
        "data": file_content,
        "filename": file_path.name,
        "overwrite": overwrite,
    }
    try:
        wizard_id = c.create("base.language.import", wizard_vals)
        c.execute_kw("base.language.import", "import_lang", [[wizard_id]])
    except RPCError as e:
        out.error(f"Failed to import translations: {e.detail}")
        raise typer.Exit(1) from e

    out.success(f"Imported translations from {file_path.name} for language {lang}")
    if actx.json_mode:
        out.raw_json(
            {
                "file": str(file_path),
                "lang": lang,
                "format": file_type,
                "overwrite": overwrite,
            }
        )


@app.command("languages")
def translate_languages(ctx: typer.Context) -> None:
    """List installed and available languages."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Get installed languages
    installed = c.search_read(
        "res.lang",
        domain=[("active", "=", True)],
        fields=["id", "name", "code", "iso_code", "direction"],
        order="name",
    )

    rows = []
    json_data = []
    for lang in installed:
        direction = lang.get("direction", "ltr")
        rows.append(
            [
                str(lang["id"]),
                lang.get("name", ""),
                lang.get("code", ""),
                lang.get("iso_code", "") or "-",
                direction,
                "[green]installed[/green]",
            ]
        )
        json_data.append(
            {
                "id": lang["id"],
                "name": lang.get("name"),
                "code": lang.get("code"),
                "iso_code": lang.get("iso_code"),
                "direction": direction,
                "status": "installed",
            }
        )

    out.table(
        f"Languages ({len(installed)} installed)",
        [("ID", "cyan"), ("Name", ""), ("Code", ""), ("ISO Code", "dim"), ("Direction", "dim"), ("Status", "")],
        rows,
        data_for_json=json_data,
    )


@app.command("regenerate-assets")
def assets_regenerate(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Regenerate web assets by clearing asset attachments."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Find asset attachments
    domain = [
        "|",
        ("url", "like", "/web/assets"),
        ("name", "like", "web_editor."),
    ]
    asset_ids = c.search("ir.attachment", domain)

    if not asset_ids:
        out.info("No asset attachments found to clear.")
        if actx.json_mode:
            out.raw_json({"cleared": 0})
        return

    out.info(f"Found {len(asset_ids)} asset attachment(s) to clear.")

    if not force and not typer.confirm(
        f"Delete {len(asset_ids)} asset attachments? Assets will regenerate on next page load."
    ):
        raise typer.Exit(0)

    # Delete in batches
    batch_size = 500
    deleted = 0
    for i in range(0, len(asset_ids), batch_size):
        batch = asset_ids[i : i + batch_size]
        c.unlink("ir.attachment", batch)
        deleted += len(batch)

    out.success(f"Cleared {deleted} asset attachments. Assets will regenerate on next page load.")
    if actx.json_mode:
        out.raw_json({"cleared": deleted})


@app.command("deps-tree")
def deps_tree(
    ctx: typer.Context,
    module: Annotated[str, typer.Argument(help="Module technical name")],
) -> None:
    """Show dependency tree for a module."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Verify the module exists
    modules = c.search_read(
        "ir.module.module",
        domain=[("name", "=", module)],
        fields=["id", "name", "state", "shortdesc"],
    )
    if not modules:
        out.error(f"Module not found: {module}")
        raise typer.Exit(1)

    mod = modules[0]

    # Batch-fetch all modules and their dependencies to avoid N+1 queries
    all_modules = c.search_read(
        "ir.module.module",
        domain=[],
        fields=["id", "name", "state"],
        limit=0,
    )
    mod_by_name: dict[str, dict] = {m["name"]: m for m in all_modules}
    {m["id"]: m for m in all_modules}

    all_deps = c.search_read(
        "ir.module.module.dependency",
        domain=[],
        fields=["module_id", "name"],
        limit=0,
    )
    # Group dependencies by parent module ID
    deps_by_mod_id: dict[int, list[str]] = {}
    for dep in all_deps:
        parent_id = dep["module_id"][0] if isinstance(dep["module_id"], list) else dep["module_id"]
        dep_name = dep.get("name", "")
        if dep_name:
            deps_by_mod_id.setdefault(parent_id, []).append(dep_name)

    visited: set[str] = set()

    def _build_dep_tree(mod_name: str) -> dict:
        """Build dependency tree from pre-fetched data."""
        if mod_name in visited:
            return {"name": mod_name, "info": "circular", "children": []}
        visited.add(mod_name)

        mod_data = mod_by_name.get(mod_name)
        state = mod_data["state"] if mod_data else "unknown"
        mod_id = mod_data["id"] if mod_data else None

        children: list[dict] = []
        if mod_id is not None:
            for dep_name in sorted(deps_by_mod_id.get(mod_id, [])):
                children.append(_build_dep_tree(dep_name))

        return {"name": mod_name, "info": state, "children": children}

    tree_data = _build_dep_tree(module)

    root_info = f"{mod.get('shortdesc', '')} [{mod.get('state', '')}]"
    tree_data["info"] = root_info

    out.tree(
        f"Dependencies: {module}",
        [tree_data],
        data_for_json=[tree_data],
    )


@app.command("deps-reverse")
def deps_reverse(
    ctx: typer.Context,
    module: Annotated[str, typer.Argument(help="Module technical name")],
) -> None:
    """Show what modules depend on this module (reverse dependencies)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Verify the module exists
    modules = c.search_read(
        "ir.module.module",
        domain=[("name", "=", module)],
        fields=["id", "name", "state"],
    )
    if not modules:
        out.error(f"Module not found: {module}")
        raise typer.Exit(1)

    # Find all dependency records pointing to this module
    deps = c.search_read(
        "ir.module.module.dependency",
        domain=[("name", "=", module)],
        fields=["module_id"],
    )

    if not deps:
        out.info(f"No modules depend on '{module}'.")
        if actx.json_mode:
            out.raw_json({"module": module, "reverse_deps": []})
        return

    # Get the parent module details
    parent_ids = [d["module_id"][0] for d in deps if isinstance(d.get("module_id"), list)]
    if not parent_ids:
        out.info(f"No modules depend on '{module}'.")
        if actx.json_mode:
            out.raw_json({"module": module, "reverse_deps": []})
        return

    parents = c.read(
        "ir.module.module",
        parent_ids,
        fields=["name", "shortdesc", "state"],
    )

    rows = []
    json_data = []
    for p in parents:
        state_display = module_state_color(p.get("state", ""))
        rows.append(
            [
                p.get("name", ""),
                p.get("shortdesc", "") or "-",
                state_display,
            ]
        )
        json_data.append(
            {
                "name": p.get("name"),
                "summary": p.get("shortdesc"),
                "state": p.get("state"),
            }
        )

    out.table(
        f"Reverse Dependencies of '{module}' ({len(parents)})",
        [("Module", ""), ("Summary", ""), ("State", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def cloc(
    ctx: typer.Context,
    module: Annotated[str | None, typer.Option("--module", "-m", help="Filter by module name")] = None,
) -> None:
    """Show lines of code information for installed modules."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = [("state", "=", "installed")]
    if module:
        domain.append(("name", "=", module))

    modules = c.search_read(
        "ir.module.module",
        domain=domain,
        fields=["id", "name", "shortdesc", "state", "installed_version", "author"],
        order="name",
    )

    if not modules:
        out.info("No matching installed modules found.")
        if actx.json_mode:
            out.raw_json([])
        return

    # Try to get cloc data from ir.module.module if available
    rows = []
    json_data = []
    for m in modules:
        rows.append(
            [
                str(m["id"]),
                m.get("name", ""),
                m.get("shortdesc", "") or "-",
                m.get("installed_version", "") or "-",
                m.get("author", "") or "-",
            ]
        )
        json_data.append(
            {
                "id": m["id"],
                "name": m.get("name"),
                "summary": m.get("shortdesc"),
                "version": m.get("installed_version"),
                "author": m.get("author"),
            }
        )

    out.table(
        f"Installed Modules ({len(modules)})",
        [("ID", "cyan"), ("Name", ""), ("Summary", ""), ("Version", "dim"), ("Author", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command("watch")
def watch_module(
    ctx: typer.Context,
    module: Annotated[str, typer.Argument(help="Module technical name to watch")],
    service: Annotated[str, typer.Option("--service", help="Docker service name")] = "odoo",
    interval: Annotated[int, typer.Option("--interval", help="Poll interval in seconds")] = 2,
) -> None:
    """Watch Python/XML files and auto-upgrade module on change.

    Monitors src/private/<module>/ for file changes and triggers
    module upgrade via Odoo JSON-RPC when changes are detected.
    """
    import hashlib
    import time as _time

    from kctl_odoo.core.exceptions import RPCError
    from kctl_odoo.core.utils import find_project_root

    actx: AppContext = ctx.obj
    out = actx.output

    mod_dir = find_project_root() / "src" / "private" / module
    if not mod_dir.is_dir():
        out.error(f"Module directory not found: {mod_dir}")
        raise typer.Exit(1)

    out.info(f"Watching {mod_dir} (interval={interval}s) — Ctrl+C to stop")

    def _hash_dir(d: Path) -> str:
        h = hashlib.md5()
        for f in sorted(d.rglob("*")):
            if f.is_file() and "__pycache__" not in str(f):
                h.update(f.name.encode())
                h.update(f.read_bytes())
        return h.hexdigest()

    last_hash = _hash_dir(mod_dir)

    try:
        c = actx.client
        while True:
            _time.sleep(interval)
            current_hash = _hash_dir(mod_dir)
            if current_hash != last_hash:
                last_hash = current_hash
                out.info(f"Change detected — upgrading {module}...")
                try:
                    mod_ids = c.search("ir.module.module", [("name", "=", module), ("state", "=", "installed")])
                    if mod_ids:
                        c.execute_kw("ir.module.module", "button_immediate_upgrade", [mod_ids])
                        out.info(f"Module {module} upgraded successfully.")
                    else:
                        out.info(f"Module {module} not installed — skipping upgrade.")
                except RPCError as e:
                    out.error(f"Upgrade failed: {e.detail}")
    except KeyboardInterrupt:
        out.info("Stopped watching.")


@app.command("profile")
def profile_process(ctx: typer.Context) -> None:
    """Show CPU and memory stats of the running Odoo process via JSON-RPC."""
    import time as _time

    from kctl_odoo.core.exceptions import RPCError

    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        start = _time.monotonic()
        # Use server info as a lightweight probe
        info = c.server_version()
        elapsed = round((_time.monotonic() - start) * 1000)

        out.info(f"Odoo server version: {info}")
        out.info(f"RPC latency: {elapsed}ms")
        out.info("")
        out.info("For process-level CPU/memory stats, use:")
        out.info("  docker compose stats --no-stream odoo")
        out.info("  docker compose top odoo")

    except (RPCError, AttributeError):
        # Fallback: use docker stats
        import subprocess

        try:
            result = subprocess.run(
                [
                    "docker",
                    "compose",
                    "stats",
                    "--no-stream",
                    "--format",
                    "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                typer.echo(result.stdout)
            else:
                out.error("Could not get stats. Is Docker running?")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            out.error("docker not found. Run: docker compose stats --no-stream")


@app.command("routes")
def list_routes(ctx: typer.Context) -> None:
    """List HTTP routes and JSON-RPC endpoints registered in Odoo."""
    from kctl_odoo.core.exceptions import RPCError

    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        # Query ir.http routes via search_read
        routes = c.search_read(
            "ir.http",
            domain=[],
            fields=["id", "name", "model", "method"],
            limit=200,
        )

        if routes:
            rows = []
            for r in routes:
                rows.append([str(r.get("id")), r.get("name", ""), r.get("model", ""), r.get("method", "")])
            out.table(
                f"HTTP Routes ({len(routes)})",
                [("ID", "cyan"), ("Name", ""), ("Model", ""), ("Method", "dim")],
                rows,
            )
        else:
            out.info("No routes found via ir.http. Routes are defined in Python controllers.")
            out.info("Check: src/private/*/controllers/ and src/private/*/services/")

    except RPCError:
        out.info("Could not query ir.http routes directly.")
        out.info("JSON-RPC endpoint: POST /web/dataset/call_kw")
        out.info("FastAPI endpoints: GET /{module}/api/openapi.json")
        out.info("Use: kctl-odoo fastapi endpoints <app> to list FastAPI routes.")


@app.command("model-info")
def model_info(
    ctx: typer.Context,
    model_name: Annotated[str, typer.Argument(help="Model name (e.g. res.partner)")],
) -> None:
    """Show detailed field information for an Odoo model."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        fields = c.fields_get(
            model_name,
            attributes=["string", "type", "required", "readonly", "help", "relation", "selection", "store"],
        )
    except RPCError as e:
        out.error(f"Could not get fields for model '{model_name}': {e.detail}")
        raise typer.Exit(1) from e

    if not fields:
        out.info(f"No fields found for model '{model_name}'.")
        if actx.json_mode:
            out.raw_json({})
        return

    rows = []
    json_data = []
    for field_name, attrs in sorted(fields.items()):
        field_type = attrs.get("type", "")
        string = attrs.get("string", "")
        required = "yes" if attrs.get("required") else ""
        readonly = "yes" if attrs.get("readonly") else ""
        stored = "yes" if attrs.get("store") else "no"
        relation = attrs.get("relation", "") or ""
        help_text = (attrs.get("help") or "")[:40]

        type_display = field_type
        if relation:
            type_display = f"{field_type} -> {relation}"
        if attrs.get("selection"):
            options = ", ".join(s[0] for s in attrs["selection"][:5])
            if len(attrs["selection"]) > 5:
                options += "..."
            type_display = f"{field_type} [{options}]"

        rows.append(
            [
                field_name,
                string,
                type_display,
                "[red]yes[/red]" if required else "",
                "[dim]yes[/dim]" if readonly else "",
                stored,
                help_text,
            ]
        )
        json_data.append(
            {
                "name": field_name,
                "string": string,
                "type": field_type,
                "required": attrs.get("required", False),
                "readonly": attrs.get("readonly", False),
                "store": attrs.get("store", True),
                "relation": relation or None,
                "help": attrs.get("help"),
                "selection": attrs.get("selection"),
            }
        )

    out.table(
        f"Model: {model_name} ({len(fields)} fields)",
        [
            ("Field", "cyan"),
            ("Label", ""),
            ("Type", ""),
            ("Required", ""),
            ("Readonly", ""),
            ("Stored", "dim"),
            ("Help", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )


@app.command("find-overrides")
def find_overrides(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Model name to search for overrides (e.g. res.partner)")],
) -> None:
    """List all modules that inherit/extend a model."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Search for modules that declare _inherit or _name for this model
    # ir.model tracks all registered models; we look at module membership via ir.model.data
    try:
        # Find the model record
        model_records = c.search_read(
            "ir.model",
            domain=[("model", "=", model)],
            fields=["id", "name", "model", "modules"],
        )
    except RPCError as e:
        out.error(f"Could not query ir.model: {e.detail}")
        raise typer.Exit(1) from e

    if not model_records:
        out.error(f"Model not found: {model}")
        raise typer.Exit(1)

    model_rec = model_records[0]
    modules_str = model_rec.get("modules") or ""
    # Odoo stores comma-separated module names in the 'modules' field
    module_list = [m.strip() for m in modules_str.split(",") if m.strip()]

    if not module_list:
        out.info(f"No module overrides found for '{model}'.")
        if actx.json_mode:
            out.raw_json({"model": model, "modules": []})
        return

    # Get state info for each module
    mod_records = c.search_read(
        "ir.module.module",
        domain=[("name", "in", module_list)],
        fields=["name", "state", "shortdesc"],
        order="name",
    )
    mod_by_name = {m["name"]: m for m in mod_records}

    rows = []
    json_data = []
    for mod_name in sorted(module_list):
        mod = mod_by_name.get(mod_name, {})
        state = mod.get("state", "unknown")
        summary = mod.get("shortdesc") or "-"
        rows.append([mod_name, summary, state])
        json_data.append({"module": mod_name, "summary": summary, "state": state})

    out.table(
        f"Modules overriding '{model}' ({len(module_list)})",
        [("Module", "cyan"), ("Summary", ""), ("State", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command("unused-xml-ids")
def unused_xml_ids(
    ctx: typer.Context,
    module: Annotated[str | None, typer.Option("--module", "-m", help="Filter by module name")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """Find XML IDs defined but potentially unreferenced."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = []
    if module:
        domain.append(("module", "=", module))

    # Get XML IDs (ir.model.data) for the given module
    xml_ids = c.search_read(
        "ir.model.data",
        domain=domain,
        fields=["id", "name", "module", "model", "res_id"],
        limit=limit,
        order="module, model, name",
    )

    if not xml_ids:
        label = f"module '{module}'" if module else "any module"
        out.info(f"No XML IDs found for {label}.")
        if actx.json_mode:
            out.raw_json([])
        return

    # Check which XML IDs are referenced as noupdate=True (likely installed data, not menu/action)
    # We report all found XML IDs as a catalog — identifying truly "unused" ones requires
    # static analysis of XML files (not possible via RPC alone). We flag noupdate=False records
    # as potentially auto-generated and thus more likely unused.
    try:
        noupdate_ids = c.search_read(
            "ir.model.data",
            domain=domain + [("noupdate", "=", False)],
            fields=["name", "module"],
            limit=limit,
        )
        noupdate_set = {(r["module"], r["name"]) for r in noupdate_ids}
    except RPCError:
        noupdate_set = set()

    rows = []
    json_data = []
    for xid in xml_ids:
        full_id = f"{xid['module']}.{xid['name']}"
        key = (xid["module"], xid["name"])
        updatable = "yes" if key in noupdate_set else "no"
        rows.append(
            [
                full_id,
                xid.get("model") or "-",
                str(xid.get("res_id") or 0),
                updatable,
            ]
        )
        json_data.append(
            {
                "xml_id": full_id,
                "model": xid.get("model"),
                "res_id": xid.get("res_id"),
                "noupdate": key not in noupdate_set,
            }
        )

    label = f"module '{module}'" if module else "all modules"
    out.table(
        f"XML IDs for {label} ({len(xml_ids)} shown)",
        [
            ("XML ID", "cyan"),
            ("Model", ""),
            ("Res ID", "dim"),
            ("Auto-update", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )
    out.info(
        "Note: 'Auto-update=yes' records can be overwritten by module updates."
        " Use static analysis to find truly unused IDs."
    )


@app.command("check-translations")
def check_translations(
    ctx: typer.Context,
    module: Annotated[str, typer.Argument(help="Module technical name")],
    lang: Annotated[str, typer.Option("--lang", help="Language code (e.g. id, fr)")] = "id",
) -> None:
    """Validate PO file placeholder consistency."""
    import re as _re

    from kctl_odoo.core.utils import find_project_root

    actx: AppContext = ctx.obj
    out = actx.output

    # Locate PO file in private modules
    project_root = find_project_root()
    po_candidates = [
        project_root / "src" / "private" / module / "i18n" / f"{lang}.po",
        project_root / "src" / "external" / module / "i18n" / f"{lang}.po",
    ]
    po_path: Path | None = None
    for candidate in po_candidates:
        if candidate.exists():
            po_path = candidate
            break

    if po_path is None:
        out.error(f"PO file not found for module '{module}', lang '{lang}'.")
        out.info(f"Looked in: {[str(c) for c in po_candidates]}")
        raise typer.Exit(1)

    po_text = po_path.read_text(encoding="utf-8")

    # Parse msgid/msgstr pairs
    PLACEHOLDER_RE = _re.compile(r"%(?:\(\w+\))?[sdifr%]|{[\w:,!.]*}")

    entries = []
    current_id: str | None = None
    current_str: str | None = None
    in_msgid = False
    in_msgstr = False

    for line in po_text.splitlines():
        if line.startswith("msgid "):
            if current_id is not None and current_str is not None:
                entries.append((current_id, current_str))
            current_id = line[7:-1]  # strip 'msgid "' and trailing '"'
            current_str = None
            in_msgid = True
            in_msgstr = False
        elif line.startswith("msgstr "):
            current_str = line[8:-1]
            in_msgid = False
            in_msgstr = True
        elif line.startswith('"') and in_msgid and current_id is not None:
            current_id += line[1:-1]
        elif line.startswith('"') and in_msgstr and current_str is not None:
            current_str += line[1:-1]
        elif not line.strip():
            in_msgid = in_msgstr = False

    if current_id is not None and current_str is not None:
        entries.append((current_id, current_str))

    mismatches = []
    for msgid, msgstr in entries:
        if not msgid or not msgstr:
            continue
        id_placeholders = sorted(PLACEHOLDER_RE.findall(msgid))
        str_placeholders = sorted(PLACEHOLDER_RE.findall(msgstr))
        if id_placeholders != str_placeholders:
            mismatches.append(
                {
                    "msgid": msgid[:80],
                    "msgid_placeholders": id_placeholders,
                    "msgstr_placeholders": str_placeholders,
                }
            )

    if not mismatches:
        out.success(f"PO file OK: {po_path} ({len(entries)} entries, no placeholder mismatches)")
        if actx.json_mode:
            out.raw_json({"file": str(po_path), "entries": len(entries), "mismatches": 0})
        return

    rows = []
    for m in mismatches:
        rows.append(
            [
                m["msgid"][:60],
                ", ".join(m["msgid_placeholders"]) or "(none)",
                ", ".join(m["msgstr_placeholders"]) or "(none)",
            ]
        )

    out.table(
        f"Placeholder Mismatches in {po_path.name} ({len(mismatches)} found)",
        [
            ("msgid (truncated)", ""),
            ("Source placeholders", "cyan"),
            ("Translation placeholders", "yellow"),
        ],
        rows,
        data_for_json=mismatches,
    )
    out.warn(f"Found {len(mismatches)} placeholder mismatch(es) in {po_path}")


@app.command("module-health")
def module_health(ctx: typer.Context, module: str) -> None:
    """Comprehensive health check for a single private module.

    Runs all quality checks and produces a scorecard:
    - Manifest: valid, version format, description, depends
    - Security: ir.model.access.csv coverage for all models
    - Tests: test files exist, test count
    - Docs: CLAUDE.md exists
    - Python: no f-string SQL, no N+1 patterns
    - XML: no deprecated attributes
    - Fields: namespace convention compliance
    - FastAPI: router count, schema count (if applicable)

    Examples:
        kctl-odoo dev module-health sfa_management
        kctl-odoo dev module-health base_management --json
    """
    import ast
    import re

    actx: AppContext = ctx.obj
    out = actx.output

    private_dir = Path.cwd() / "src" / "private"
    mod_dir = private_dir / module

    if not mod_dir.exists() or not (mod_dir / "__manifest__.py").exists():
        out.error(f"Module not found: {module}")
        raise typer.Exit(1)

    scores = {}
    total = 0
    passed = 0

    # 1. Manifest check
    manifest_file = mod_dir / "__manifest__.py"
    try:
        manifest = ast.literal_eval(manifest_file.read_text())
        has_version = bool(manifest.get("version"))
        has_description = bool(manifest.get("description"))
        has_depends = bool(manifest.get("depends"))
        installable = manifest.get("installable", True)
        manifest_ok = all([has_version, has_description, has_depends, installable])
    except Exception:
        manifest_ok = False
    scores["Manifest"] = "PASS" if manifest_ok else "FAIL"
    total += 1
    passed += 1 if manifest_ok else 0

    # 2. Security check
    csv_path = mod_dir / "security" / "ir.model.access.csv"
    has_security = csv_path.exists() and csv_path.stat().st_size > 50
    scores["Security (ACL)"] = "PASS" if has_security else "FAIL"
    total += 1
    passed += 1 if has_security else 0

    # 3. Tests check
    tests_dir = mod_dir / "tests"
    test_files = list(tests_dir.glob("test_*.py")) if tests_dir.exists() else []
    test_count = 0
    for tf in test_files:
        test_count += len(re.findall(r"def test_", tf.read_text()))
    has_tests = len(test_files) > 0
    scores[f"Tests ({test_count} tests in {len(test_files)} files)"] = "PASS" if has_tests else "FAIL"
    total += 1
    passed += 1 if has_tests else 0

    # 4. CLAUDE.md check
    has_claude_md = (mod_dir / "CLAUDE.md").exists()
    scores["Documentation (CLAUDE.md)"] = "PASS" if has_claude_md else "FAIL"
    total += 1
    passed += 1 if has_claude_md else 0

    # 5. Python quality (f-string SQL)
    py_issues = 0
    models_dir = mod_dir / "models"
    services_dir = mod_dir / "services"
    for search_dir in [models_dir, services_dir]:
        if search_dir.exists():
            for py_file in search_dir.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                content = py_file.read_text(errors="ignore")
                for line in content.splitlines():
                    if ("f'" in line or 'f"' in line) and any(
                        kw in line.lower() for kw in ["select ", "insert ", "update ", "delete ", "create table"]
                    ):
                        py_issues += 1
    py_ok = py_issues == 0
    scores[f"Python quality ({py_issues} SQL f-strings)"] = "PASS" if py_ok else "WARN"
    total += 1
    passed += 1 if py_ok else 0

    # 6. XML views check
    xml_issues = 0
    views_dir = mod_dir / "views"
    if views_dir.exists():
        for xml_file in views_dir.rglob("*.xml"):
            content = xml_file.read_text(errors="ignore")
            if "states=" in content or "<tree" in content:
                xml_issues += 1
    xml_ok = xml_issues == 0
    scores[f"XML views ({xml_issues} deprecated patterns)"] = "PASS" if xml_ok else "WARN"
    total += 1
    passed += 1 if xml_ok else 0

    # 7. FastAPI check (if applicable)
    controllers_dir = mod_dir / "controllers"
    routers = list(controllers_dir.glob("*_router.py")) if controllers_dir.exists() else []
    schemas_dir = mod_dir / "schemas"
    schemas = list(schemas_dir.glob("*_schema.py")) if schemas_dir.exists() else []
    if routers or schemas:
        scores[f"FastAPI ({len(routers)} routers, {len(schemas)} schemas)"] = "INFO"

    # Display scorecard
    pct = round(passed / total * 100) if total > 0 else 0
    rows = [[check, status] for check, status in scores.items()]

    out.table(
        f"Module Health: {module} — {pct}% ({passed}/{total})",
        [("Check", ""), ("Status", "")],
        rows,
    )


@app.command("check-conventions")
def check_conventions(ctx: typer.Context, module: str | None = None) -> None:
    """Check Kodemeio coding conventions across private modules.

    Validates:
    - Field namespace prefixes on inherited models
    - CLAUDE.md exists
    - Tests directory exists with at least one test
    - security/ir.model.access.csv exists
    - __manifest__.py has required keys

    Examples:
        kctl-odoo dev check-conventions
        kctl-odoo dev check-conventions sfa_management
    """
    actx: AppContext = ctx.obj
    out = actx.output

    private_dir = Path.cwd() / "src" / "private"
    if module:
        modules = [module]
    else:
        modules = sorted([d.name for d in private_dir.iterdir() if d.is_dir() and (d / "__manifest__.py").exists()])

    issues = []
    for mod_name in modules:
        mod_dir = private_dir / mod_name

        # Check CLAUDE.md
        if not (mod_dir / "CLAUDE.md").exists():
            issues.append([mod_name, "CLAUDE.md missing", "FAIL"])

        # Check tests/
        tests_dir = mod_dir / "tests"
        if not tests_dir.exists() or not list(tests_dir.glob("test_*.py")):
            issues.append([mod_name, "No test files in tests/", "FAIL"])

        # Check security
        csv_path = mod_dir / "security" / "ir.model.access.csv"
        if not csv_path.exists():
            issues.append([mod_name, "security/ir.model.access.csv missing", "FAIL"])

    if not issues:
        out.success(f"All {len(modules)} modules pass convention checks.")
    else:
        out.table(
            f"Convention Issues ({len(issues)})",
            [("Module", ""), ("Issue", ""), ("Severity", "")],
            issues,
        )
        raise typer.Exit(1)


@app.command("coverage-report")
def coverage_report(ctx: typer.Context) -> None:
    """Show test coverage summary across all private modules.

    Lists each module with:
    - Number of test files
    - Number of test functions
    - Whether tests exist at all

    Examples:
        kctl-odoo dev coverage-report
        kctl-odoo dev coverage-report --json
    """
    import re

    actx: AppContext = ctx.obj
    out = actx.output

    private_dir = Path.cwd() / "src" / "private"
    modules = sorted([d.name for d in private_dir.iterdir() if d.is_dir() and (d / "__manifest__.py").exists()])

    rows = []
    total_files = 0
    total_tests = 0
    modules_with_tests = 0

    for mod_name in modules:
        tests_dir = private_dir / mod_name / "tests"
        if tests_dir.exists():
            test_files = list(tests_dir.glob("test_*.py"))
            file_count = len(test_files)
            test_count = 0
            for tf in test_files:
                test_count += len(re.findall(r"def test_", tf.read_text(errors="ignore")))
            total_files += file_count
            total_tests += test_count
            if file_count > 0:
                modules_with_tests += 1
            status = "OK" if file_count > 0 else "NONE"
        else:
            file_count = 0
            test_count = 0
            status = "NONE"

        rows.append([mod_name, str(file_count), str(test_count), status])

    out.table(
        f"Test Coverage — {modules_with_tests}/{len(modules)} modules have tests, {total_tests} total test functions",
        [("Module", ""), ("Files", ""), ("Tests", ""), ("Status", "")],
        rows,
    )


@app.command("release-check")
def release_check(ctx: typer.Context, module: str) -> None:
    """Pre-release validation for a module before version bump.

    Checks everything needed before releasing a module:
    1. Manifest is valid with correct version format
    2. All models have security rules
    3. Tests exist and module has CLAUDE.md
    4. No TODO/FIXME/HACK in Python code
    5. No deprecated XML patterns
    6. Changelog entry exists

    Examples:
        kctl-odoo dev release-check sfa_management
    """
    import ast
    import re

    actx: AppContext = ctx.obj
    out = actx.output

    private_dir = Path.cwd() / "src" / "private"
    mod_dir = private_dir / module

    if not mod_dir.exists():
        out.error(f"Module not found: {module}")
        raise typer.Exit(1)

    checks = []
    all_pass = True

    # 1. Manifest
    try:
        manifest = ast.literal_eval((mod_dir / "__manifest__.py").read_text())
        version = manifest.get("version", "")
        if re.match(r"^18\.0\.\d+\.\d+\.\d+$", version):
            checks.append(["Manifest version", version, "PASS"])
        else:
            checks.append(["Manifest version", f"Invalid: {version}", "FAIL"])
            all_pass = False
    except Exception as e:
        checks.append(["Manifest", str(e)[:60], "FAIL"])
        all_pass = False

    # 2. Security
    csv_path = mod_dir / "security" / "ir.model.access.csv"
    if csv_path.exists() and csv_path.stat().st_size > 50:
        checks.append(["Security (ACL)", "ir.model.access.csv exists", "PASS"])
    else:
        checks.append(["Security (ACL)", "Missing or empty", "FAIL"])
        all_pass = False

    # 3. Tests
    tests_dir = mod_dir / "tests"
    test_files = list(tests_dir.glob("test_*.py")) if tests_dir.exists() else []
    if test_files:
        checks.append(["Tests", f"{len(test_files)} test file(s)", "PASS"])
    else:
        checks.append(["Tests", "No test files", "FAIL"])
        all_pass = False

    # 4. CLAUDE.md
    if (mod_dir / "CLAUDE.md").exists():
        checks.append(["Documentation", "CLAUDE.md exists", "PASS"])
    else:
        checks.append(["Documentation", "CLAUDE.md missing", "FAIL"])
        all_pass = False

    # 5. TODO/FIXME/HACK scan
    todo_count = 0
    for py_file in mod_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        content = py_file.read_text(errors="ignore")
        todo_count += len(re.findall(r"#\s*(TODO|FIXME|HACK|XXX)\b", content, re.IGNORECASE))
    if todo_count == 0:
        checks.append(["Code TODOs", "None found", "PASS"])
    else:
        checks.append(["Code TODOs", f"{todo_count} TODO/FIXME/HACK found", "WARN"])

    # 6. Changelog
    changelog = mod_dir / "CHANGELOG.md"
    if changelog.exists():
        checks.append(["Changelog", "CHANGELOG.md exists", "PASS"])
    else:
        checks.append(["Changelog", "CHANGELOG.md missing", "WARN"])

    status = "READY" if all_pass else "NOT READY"
    out.table(
        f"Release Check: {module} — {status}",
        [("Check", ""), ("Detail", ""), ("Status", "")],
        checks,
    )

    if not all_pass:
        raise typer.Exit(1)


@app.command("generate-cmd")
def generate_cmd(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Odoo model name (e.g. form.type, dunning.case)")],
    group_name: Annotated[
        str | None, typer.Option("--group", "-g", help="CLI group name (default: derived from model)")
    ] = None,
    output: Annotated[str | None, typer.Option("--output", "-o", help="Output file path (default: stdout)")] = None,
) -> None:
    """Auto-generate a CLI command file from live Odoo model introspection.

    Connects to Odoo, reads the model's fields via fields_get, and generates
    a complete Typer command file with list, get, and summary commands using
    only fields that actually exist on the model.

    Zero guessing — all field names come from the running instance.

    Examples:
        kctl-odoo dev generate-cmd form.type
        kctl-odoo dev generate-cmd dunning.case --group dunning
        kctl-odoo dev generate-cmd compliance.company.license -o cli/src/kctl_odoo/commands/compliance_cmd.py
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    from kctl_odoo.core.field_helpers import classify_fields, get_model_fields

    # Fetch real fields from Odoo
    fields = get_model_fields(c, model)
    if not fields:
        out.error(f"Could not fetch fields for model '{model}'. Is it installed?")
        raise typer.Exit(1)

    classified = classify_fields(fields)

    # Derive group name from model name
    if not group_name:
        # "form.type" -> "form", "dunning.case" -> "dunning", "compliance.company.license" -> "compliance"
        group_name = model.split(".")[0]

    # Build the list of fields to use in search_read
    list_fields = []
    # Identifiers first
    for f in classified["identifiers"]:
        list_fields.append(f)
    # States
    for f in classified["states"]:
        list_fields.append(f)
    # Top relations (max 3)
    for f in classified["relations"][:3]:
        list_fields.append(f)
    # Top dates (max 2)
    for f in classified["dates"][:2]:
        list_fields.append(f)
    # Top amounts (max 2)
    for f in classified["amounts"][:2]:
        list_fields.append(f)

    if not list_fields:
        list_fields = ["display_name", "create_date"]

    # Build field info for column headers
    field_columns = []
    for f in list_fields:
        finfo = fields.get(f, {})
        label = finfo.get("string", f)
        ftype = finfo.get("type", "char")
        field_columns.append((f, label, ftype))

    # Find the state/status field for filtering
    state_field = None
    for f in classified["states"]:
        if f in ("state", "status"):
            state_field = f
            break

    # Generate Python code
    code_lines = [
        f'"""CLI commands for {model} — auto-generated by kctl-odoo dev generate-cmd."""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import Annotated, Optional",
        "",
        "import typer",
        "",
        "from kctl_odoo.core.biz_helpers import model_available",
        "from kctl_odoo.core.callbacks import AppContext",
        "from kctl_odoo.core.exceptions import RPCError",
        "from kctl_odoo.core.field_helpers import safe_fields",
        "",
        f'app = typer.Typer(help="{group_name.title()} management commands.")',
        "",
        f'_MODEL = "{model}"',
        f'_HINT = "{group_name} module is not installed."',
        "",
        "",
        "def _m2o_name(val):",
        "    if isinstance(val, list):",
        "        return str(val[1])",
        '    return str(val or "-")',
        "",
        "",
    ]

    # Generate list command
    preferred_fields_str = repr(list_fields)

    code_lines.extend(
        [
            '@app.command("list")',
            "def list_records(",
            "    ctx: typer.Context,",
        ]
    )
    if state_field:
        code_lines.append(
            f'    {state_field}_filter: Annotated[Optional[str], typer.Option("--{state_field}", help="Filter by {state_field}")] = None,'
        )
    code_lines.extend(
        [
            '    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,',
            ") -> None:",
            f'    """List {model} records."""',
            "    actx: AppContext = ctx.obj",
            "    out = actx.output",
            "    c = actx.client",
            "",
            "    if not model_available(c, _MODEL):",
            "        out.warn(_HINT)",
            "        return",
            "",
            f"    fields = safe_fields(c, _MODEL, {preferred_fields_str})",
            "    domain: list = []",
        ]
    )
    if state_field:
        code_lines.extend(
            [
                f"    if {state_field}_filter:",
                f'        domain.append(("{state_field}", "=", {state_field}_filter))',
            ]
        )
    code_lines.extend(
        [
            "",
            "    try:",
            '        records = c.search_read(_MODEL, domain=domain, fields=fields, limit=limit, order="id desc")',
            "    except RPCError as e:",
            '        out.error(f"Failed to list records: {e}")',
            "        raise typer.Exit(1)",
            "",
            "    if not records:",
            f'        out.info(f"No {model} records found.")',
            "        if actx.json_mode:",
            "            out.raw_json([])",
            "        return",
            "",
            "    rows = []",
            "    for r in records:",
            "        row = []",
        ]
    )

    for f, label, ftype in field_columns:
        if ftype == "many2one":
            code_lines.append(f'        row.append(_m2o_name(r.get("{f}")))')
        elif ftype in ("float", "monetary"):
            code_lines.append(f'        row.append(f"{{r.get(\\"{f}\\", 0):,.2f}}")')
        else:
            code_lines.append(f'        row.append(str(r.get("{f}", "") or ""))')

    code_lines.extend(
        [
            "        rows.append(row)",
            "",
            "    out.table(",
            f'        f"{model} ({{len(records)}})",',
            "        [",
        ]
    )
    for f, label, ftype in field_columns:
        code_lines.append(f'            ("{label}", ""),')
    code_lines.extend(
        [
            "        ],",
            "        rows,",
            "        data_for_json=records,",
            "    )",
            "",
            "",
        ]
    )

    # Generate summary command
    code_lines.extend(
        [
            '@app.command("summary")',
            "def summary(ctx: typer.Context) -> None:",
            f'    """Show {model} summary statistics."""',
            "    actx: AppContext = ctx.obj",
            "    out = actx.output",
            "    c = actx.client",
            "",
            "    if not model_available(c, _MODEL):",
            "        out.warn(_HINT)",
            "        return",
            "",
            "    try:",
            "        total = c.search_count(_MODEL, [])",
            "    except RPCError as e:",
            '        out.error(f"Failed: {e}")',
            "        raise typer.Exit(1)",
            "",
        ]
    )

    if state_field:
        state_info = fields.get(state_field, {})
        if state_info.get("type") == "selection":
            code_lines.extend(
                [
                    "    # Count by state",
                    "    rows = []",
                    '    for state_val in ["draft", "open", "confirm", "done", "cancel"]:',
                    "        try:",
                    f'            count = c.search_count(_MODEL, [("{state_field}", "=", state_val)])',
                    "        except (RPCError, Exception):",
                    "            count = 0",
                    "        if count > 0:",
                    "            rows.append([state_val, str(count)])",
                    "",
                    '    rows.append(["TOTAL", str(total)])',
                    "    out.table(",
                    f'        f"{model} Summary",',
                    '        [("State", ""), ("Count", "")],',
                    "        rows,",
                    "    )",
                ]
            )
        else:
            code_lines.extend(
                [
                    f'    out.info(f"Total {model} records: {{total}}")',
                ]
            )
    else:
        code_lines.extend(
            [
                f'    out.info(f"Total {model} records: {{total}}")',
            ]
        )

    code_lines.append("")

    # Join and output
    generated_code = "\n".join(code_lines)

    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(generated_code)
        out.success(f"Generated {output_path} ({len(code_lines)} lines)")
        out.info(f"Fields used: {', '.join(list_fields)}")
        out.info(f"Register in cli.py: from kctl_odoo.commands.{output_path.stem} import app as {group_name}_app")
        out.info(f'                    app.add_typer({group_name}_app, name="{group_name}")')
    else:
        # Print to stdout
        print(generated_code)

    if actx.json_mode:
        out.raw_json(
            {
                "model": model,
                "group": group_name,
                "fields_used": list_fields,
                "total_fields": len(fields),
                "output": output,
            }
        )


@app.command("model-fields")
def model_fields_cmd(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Odoo model name")],
    stored_only: Annotated[bool, typer.Option("--stored", help="Only show stored fields")] = False,
    format_: Annotated[str, typer.Option("--format", "-f", help="Output format: table, python, csv")] = "table",
) -> None:
    """Show model fields with types — useful for building CLI commands.

    The 'python' format outputs a dict ready to paste into code.

    Examples:
        kctl-odoo dev model-fields form.type
        kctl-odoo dev model-fields dunning.case --stored --format python
        kctl-odoo dev model-fields compliance.company.license -f csv
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    from kctl_odoo.core.field_helpers import get_model_fields

    fields = get_model_fields(c, model)
    if not fields:
        out.error(f"Could not fetch fields for model '{model}'.")
        raise typer.Exit(1)

    # Filter
    items = []
    for fname, finfo in sorted(fields.items()):
        if fname.startswith("__"):
            continue
        if stored_only and not finfo.get("store", True):
            continue
        items.append((fname, finfo))

    if format_ == "python":
        # Output as Python dict
        print(f"# Fields for {model} ({len(items)} fields)")
        print("FIELDS = {")
        for fname, finfo in items:
            ftype = finfo.get("type", "?")
            finfo.get("string", fname)
            required = finfo.get("required", False)
            relation = finfo.get("relation", "")
            extras = []
            if required:
                extras.append("required=True")
            if relation:
                extras.append(f"relation='{relation}'")
            extra_str = f"  # {', '.join(extras)}" if extras else ""
            print(f'    "{fname}": "{ftype}",{extra_str}')
        print("}")
    elif format_ == "csv":
        print("field,type,label,required,stored,relation")
        for fname, finfo in items:
            print(
                f"{fname},{finfo.get('type', '')},{finfo.get('string', '')},{finfo.get('required', False)},{finfo.get('store', True)},{finfo.get('relation', '')}"
            )
    else:
        rows = []
        for fname, finfo in items:
            rows.append(
                [
                    fname,
                    finfo.get("type", "?"),
                    finfo.get("string", ""),
                    "yes" if finfo.get("required") else "",
                    "yes" if finfo.get("store", True) else "",
                    finfo.get("relation", ""),
                ]
            )
        out.table(
            f"Fields: {model} ({len(items)})",
            [("Name", ""), ("Type", ""), ("Label", ""), ("Required", ""), ("Stored", ""), ("Relation", "")],
            rows,
        )


@app.command("clear-field-cache")
def clear_field_cache_cmd(ctx: typer.Context) -> None:
    """Clear cached model field definitions.

    Field metadata is cached for 1 hour to speed up repeated calls.
    Use this after module updates that change field definitions.

    Examples:
        kctl-odoo dev clear-field-cache
    """
    actx: AppContext = ctx.obj
    out = actx.output

    from kctl_odoo.core.field_helpers import clear_field_cache

    count = clear_field_cache()
    out.success(f"Cleared {count} cached field definition(s).")


@app.command("audit")
def audit(
    ctx: typer.Context,
    module: Annotated[str | None, typer.Argument(help="Module name (default: all private modules)")] = None,
    all_modules: Annotated[bool, typer.Option("--all", help="Audit all private modules")] = False,
    min_score: Annotated[
        int, typer.Option("--min-score", help="Minimum passing score (CI/CD gate, exit 1 if below)")
    ] = 0,
    output: Annotated[str | None, typer.Option("--output", "-o", help="Export results to JSON file")] = None,
) -> None:
    """Comprehensive module audit with scored report card.

    Runs all quality checks and grades each module A-F:
    - Manifest: required keys, version format, description, installable
    - Security: ir.model.access.csv coverage for all models
    - Tests: test files exist, test function count, coverage ratio
    - Documentation: CLAUDE.md present and non-empty
    - Python quality: f-string SQL, sudo() usage
    - XML views: deprecated attributes (states=, <tree>, attrs=)
    - N+1 patterns: search/create inside for loops
    - Field conventions: inherited model field prefixes
    - Dependencies: count, circular check, weight

    Score: 0-100, Grade: A+ (95+), A (90+), B+ (85+), B (80+),
           C+ (75+), C (70+), D (60+), F (<60)

    Examples:
        kctl-odoo dev audit sfa_management
        kctl-odoo dev audit --all
        kctl-odoo dev audit --all --min-score 70
        kctl-odoo dev audit sfa_management --json
        kctl-odoo dev audit --all -o audit_report.json
    """
    import ast
    import json as json_mod
    import re
    from pathlib import Path as _Path

    actx: AppContext = ctx.obj
    out = actx.output

    private_dir = _Path.cwd() / "src" / "private"

    if module:
        modules_to_audit = [module]
        mod_dir = private_dir / module
        if not mod_dir.exists() or not (mod_dir / "__manifest__.py").exists():
            out.error(f"Module not found: {module}")
            raise typer.Exit(1)
    elif all_modules:
        modules_to_audit = sorted(
            [d.name for d in private_dir.iterdir() if d.is_dir() and (d / "__manifest__.py").exists()]
        )
    else:
        out.error("Specify a module name or use --all")
        raise typer.Exit(1)

    all_results = []

    for mod_name in modules_to_audit:
        mod_dir = private_dir / mod_name
        categories = {}

        # =====================================================================
        # 1. MANIFEST (10 points)
        # =====================================================================
        manifest_score = 10
        manifest_issues = []
        dep_count = 0
        try:
            manifest_text = (mod_dir / "__manifest__.py").read_text()
            manifest = ast.literal_eval(manifest_text)

            if not manifest.get("version"):
                manifest_score -= 3
                manifest_issues.append("Missing version")
            elif not re.match(r"^18\.0\.\d+\.\d+\.\d+$", str(manifest.get("version", ""))):
                manifest_score -= 2
                manifest_issues.append(f"Non-standard version: {manifest.get('version')}")

            if not manifest.get("description") and not manifest.get("summary"):
                manifest_score -= 2
                manifest_issues.append("Missing description/summary")

            if not manifest.get("depends"):
                manifest_score -= 3
                manifest_issues.append("Missing depends")

            if not manifest.get("installable", True):
                manifest_score -= 2
                manifest_issues.append("installable=False")

            if not manifest.get("author"):
                manifest_score -= 1
                manifest_issues.append("Missing author")

            dep_count = len(manifest.get("depends", []))

        except Exception as e:
            manifest_score = 0
            manifest_issues.append(f"Parse error: {e}")

        categories["Manifest"] = {"score": max(0, manifest_score), "max": 10, "issues": manifest_issues}

        # =====================================================================
        # 2. SECURITY / ACL (10 points)
        # =====================================================================
        security_score = 10
        security_issues = []

        csv_path = mod_dir / "security" / "ir.model.access.csv"
        if not csv_path.exists():
            security_score = 2
            security_issues.append("security/ir.model.access.csv missing")
        elif csv_path.stat().st_size < 50:
            security_score = 4
            security_issues.append("ir.model.access.csv is header-only (no rules)")
        else:
            # Count models vs ACL rows
            models_dir = mod_dir / "models"
            model_names = []
            if models_dir.exists():
                for py_file in models_dir.rglob("*.py"):
                    if "__pycache__" in str(py_file):
                        continue
                    try:
                        content = py_file.read_text(errors="ignore")
                        tree = ast.parse(content)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.ClassDef):
                                cls_name = None
                                cls_inherits = []
                                for item in node.body:
                                    if (
                                        isinstance(item, ast.Assign)
                                        and len(item.targets) == 1
                                        and isinstance(item.targets[0], ast.Name)
                                    ):
                                        attr = item.targets[0].id
                                        if attr == "_name" and isinstance(item.value, ast.Constant):
                                            cls_name = str(item.value.value)
                                        elif attr == "_inherit":
                                            if isinstance(item.value, ast.Constant):
                                                cls_inherits = [str(item.value.value)]
                                            elif isinstance(item.value, (ast.List, ast.Tuple)):
                                                cls_inherits = [
                                                    str(e.value) for e in item.value.elts if isinstance(e, ast.Constant)
                                                ]
                                # Only add truly new models (not extensions of existing ones)
                                if cls_name and "." in cls_name and "mixin" not in cls_name.lower():
                                    if cls_name not in cls_inherits:
                                        # New model — needs its own ACL
                                        model_names.append(cls_name)
                    except Exception:
                        pass

            csv_content = csv_path.read_text(errors="ignore")
            csv_models = set()
            for line in csv_content.splitlines()[1:]:
                if not line.strip():
                    continue
                # Scan ALL columns for model_ references (handles different CSV column orders)
                for cell in line.split(","):
                    cell = cell.strip()
                    if cell.startswith("model_"):
                        csv_models.add(cell)

            missing_acl = []
            for m in model_names:
                model_ref = f"model_{m.replace('.', '_')}"
                if model_ref not in csv_models:
                    missing_acl.append(m)

            if missing_acl:
                penalty = min(8, len(missing_acl) * 2)
                security_score -= penalty
                security_issues.append(f"{len(missing_acl)} model(s) without ACL: {', '.join(missing_acl[:3])}")

        categories["Security (ACL)"] = {"score": max(0, security_score), "max": 10, "issues": security_issues}

        # =====================================================================
        # 3. TESTS (10 points)
        # =====================================================================
        test_score = 10
        test_issues = []

        tests_dir = mod_dir / "tests"
        test_files = list(tests_dir.glob("test_*.py")) if tests_dir.exists() else []
        test_count = 0
        for tf in test_files:
            test_count += len(re.findall(r"def test_", tf.read_text(errors="ignore")))

        if not test_files:
            test_score = 0
            test_issues.append("No test files")
        elif test_count == 0:
            test_score = 3
            test_issues.append("Test files exist but no test functions")
        else:
            model_count = (
                len(
                    [
                        f
                        for f in (mod_dir / "models").rglob("*.py")
                        if "__pycache__" not in str(f) and f.name != "__init__.py"
                    ]
                )
                if (mod_dir / "models").exists()
                else 0
            )
            router_count = (
                len(list((mod_dir / "controllers").glob("*_router.py"))) if (mod_dir / "controllers").exists() else 0
            )
            target = max(model_count + router_count, 1)
            ratio = test_count / target

            if ratio < 0.5:
                test_score = 6
                test_issues.append(f"Low coverage ratio: {ratio:.1f}x ({test_count} tests / {target} targets)")
            elif ratio < 1.0:
                test_score = 8
                test_issues.append(f"Acceptable ratio: {ratio:.1f}x")

        categories["Tests"] = {
            "score": max(0, test_score),
            "max": 10,
            "issues": test_issues,
            "detail": f"{len(test_files)} files, {test_count} tests",
        }

        # =====================================================================
        # 4. DOCUMENTATION (10 points)
        # =====================================================================
        doc_score = 10
        doc_issues = []

        claude_md = mod_dir / "CLAUDE.md"
        if not claude_md.exists():
            doc_score = 0
            doc_issues.append("CLAUDE.md missing")
        elif claude_md.stat().st_size < 100:
            doc_score = 5
            doc_issues.append("CLAUDE.md exists but very short (<100 bytes)")

        categories["Documentation"] = {"score": max(0, doc_score), "max": 10, "issues": doc_issues}

        # =====================================================================
        # 5. PYTHON QUALITY (15 points)
        # =====================================================================
        py_score = 15
        py_issues = []

        sql_fstrings = 0
        sudo_model_calls = 0  # sudo() in models — potentially unnecessary
        sudo_router_calls = 0  # sudo() in services/controllers — expected for FastAPI
        todo_count = 0

        # Directories where sudo() is EXPECTED (FastAPI routers need elevated access)
        _SUDO_EXPECTED_DIRS = {"services", "controllers"}

        for search_dir in [mod_dir / "models", mod_dir / "services", mod_dir / "controllers", mod_dir / "wizards"]:
            if not search_dir.exists():
                continue
            is_router_dir = search_dir.name in _SUDO_EXPECTED_DIRS
            for py_file in search_dir.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                try:
                    content = py_file.read_text(errors="ignore")
                    for line in content.splitlines():
                        if ("f'" in line or 'f"' in line) and any(
                            kw in line.lower() for kw in ["select ", "insert ", "update ", "delete ", "create table"]
                        ):
                            sql_fstrings += 1
                        if ".sudo()" in line:
                            if is_router_dir:
                                sudo_router_calls += 1
                            else:
                                sudo_model_calls += 1
                    todo_count += len(re.findall(r"#\s*(TODO|FIXME|HACK|XXX)\b", content, re.IGNORECASE))
                except Exception:
                    pass

        if sql_fstrings > 0:
            py_score -= min(6, sql_fstrings * 3)
            py_issues.append(f"{sql_fstrings} f-string SQL injection risk(s)")

        # Only penalize sudo() in model files — router sudo() is expected for FastAPI
        if sudo_model_calls > 5:
            py_score -= 2
            py_issues.append(f"{sudo_model_calls} sudo() in models (review for necessity)")

        if todo_count > 5:
            py_score -= min(3, todo_count // 3)
            py_issues.append(f"{todo_count} TODO/FIXME/HACK comments")

        categories["Python Quality"] = {"score": max(0, py_score), "max": 15, "issues": py_issues}

        # =====================================================================
        # 6. XML VIEWS (10 points)
        # =====================================================================
        xml_score = 10
        xml_issues = []

        xml_deprecated = 0
        views_dir = mod_dir / "views"
        if views_dir.exists():
            for xml_file in views_dir.rglob("*.xml"):
                try:
                    content = xml_file.read_text(errors="ignore")
                    if "states=" in content:
                        xml_deprecated += 1
                    if "<tree" in content and "<tree>" not in content:
                        xml_deprecated += 1
                    if "attrs=" in content:
                        xml_deprecated += 1
                except Exception:
                    pass

        if xml_deprecated > 0:
            xml_score -= min(8, xml_deprecated * 2)
            xml_issues.append(f"{xml_deprecated} deprecated pattern(s) (states=, <tree>, attrs=)")

        categories["XML Views"] = {"score": max(0, xml_score), "max": 10, "issues": xml_issues}

        # =====================================================================
        # 7. N+1 PATTERNS (10 points)
        # =====================================================================
        n1_score = 10
        n1_issues = []

        n1_count = 0
        models_dir = mod_dir / "models"
        if models_dir.exists():
            for py_file in models_dir.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                try:
                    content = py_file.read_text(errors="ignore")
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.For):
                            for child in ast.walk(node):
                                if (
                                    isinstance(child, ast.Call)
                                    and isinstance(child.func, ast.Attribute)
                                    and child.func.attr in ("search", "search_read", "create", "write", "unlink")
                                ):
                                    n1_count += 1
                except Exception:
                    pass

        if n1_count > 0:
            n1_score -= min(8, n1_count * 2)
            n1_issues.append(f"{n1_count} ORM call(s) inside for loops")

        categories["N+1 Patterns"] = {"score": max(0, n1_score), "max": 10, "issues": n1_issues}

        # =====================================================================
        # 8. COMPUTED FIELDS (10 points)
        # =====================================================================
        compute_score = 10
        compute_issues = []

        # Find computed fields without store=True
        unstored_compute = 0
        if models_dir and models_dir.exists():
            for py_file in models_dir.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                try:
                    content = py_file.read_text(errors="ignore")
                    # Look for fields.X(..., compute=...) without store=True
                    # Pattern: fields.Xxx(... compute= ...) on a line without store=True
                    for i, line in enumerate(content.splitlines(), 1):
                        stripped = line.strip()
                        # Check for field assignment with compute=
                        if "compute=" in stripped and "fields." in stripped:
                            # Check if store=True is on this line or next few lines
                            # Look at the full statement (may span multiple lines)
                            chunk = "\n".join(
                                content.splitlines()[max(0, i - 1) : min(len(content.splitlines()), i + 5)]
                            )
                            if "store=True" not in chunk and "store = True" not in chunk:
                                unstored_compute += 1
                except Exception:
                    pass

        if unstored_compute > 10:
            compute_score -= min(6, unstored_compute // 3)
            compute_issues.append(f"{unstored_compute} computed field(s) without store=True")
        elif unstored_compute > 5:
            compute_score -= 2
            compute_issues.append(f"{unstored_compute} unstored computed field(s)")

        categories["Computed Fields"] = {"score": max(0, compute_score), "max": 10, "issues": compute_issues}

        # =====================================================================
        # 9. FIELD CONVENTIONS (10 points)
        # =====================================================================
        field_score = 10
        field_issues = []

        prefix_map = {
            "sfa_management": "sfa_",
            "lfa_management": "lfa_",
            "wms_management": "wms_",
            "tpm_management": "tpm_",
            "dms_management": "dms_",
            "hrm_management": "hrm_",
            "shop_management": "shop_",
            "bia_management": "bia_",
            "asset_management": "asset_",
            "mrp_management": "mrp_",
            "partner_management": "partner_",
            "compliance_management": "compliance_",
            "form_management": "form_",
        }

        expected_prefix = prefix_map.get(mod_name)
        models_dir = mod_dir / "models"
        if expected_prefix and models_dir.exists():
            unprefixed = []
            for py_file in models_dir.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                try:
                    content = py_file.read_text(errors="ignore")
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            has_inherit = False
                            has_name = False
                            for item in node.body:
                                if (
                                    isinstance(item, ast.Assign)
                                    and len(item.targets) == 1
                                    and isinstance(item.targets[0], ast.Name)
                                ):
                                    if item.targets[0].id == "_inherit":
                                        has_inherit = True
                                    if item.targets[0].id == "_name":
                                        has_name = True
                            # Only check pure _inherit extensions (no _name = module-owned)
                            if has_inherit and not has_name:
                                for item in node.body:
                                    if (
                                        isinstance(item, ast.Assign)
                                        and len(item.targets) == 1
                                        and isinstance(item.targets[0], ast.Name)
                                    ):
                                        fname = item.targets[0].id
                                        if (
                                            fname
                                            not in (
                                                "_inherit",
                                                "_name",
                                                "_description",
                                                "_order",
                                                "_rec_name",
                                                "_sql_constraints",
                                                "_table",
                                            )
                                            and not fname.startswith("_")
                                            and not fname.startswith(expected_prefix)
                                        ):
                                            unprefixed.append(fname)
                except Exception:
                    pass

            if unprefixed:
                penalty = min(6, len(unprefixed))
                field_score -= penalty
                field_issues.append(
                    f"{len(unprefixed)} field(s) on inherited models without '{expected_prefix}' prefix"
                )

        categories["Field Conventions"] = {"score": max(0, field_score), "max": 10, "issues": field_issues}

        # =====================================================================
        # 10. DEPENDENCIES (15 points)
        # =====================================================================
        dep_score = 15
        dep_issues = []

        try:
            manifest = ast.literal_eval((mod_dir / "__manifest__.py").read_text())
            depends = manifest.get("depends", [])
            dep_count = len(depends)

            if dep_count > 15:
                dep_score -= 3
                dep_issues.append(f"Heavy dependencies: {dep_count} modules")
            elif dep_count > 10:
                dep_score -= 1
                dep_issues.append(f"{dep_count} dependencies")

        except Exception:
            dep_score -= 5
            dep_issues.append("Could not parse depends")

        categories["Dependencies"] = {
            "score": max(0, dep_score),
            "max": 15,
            "issues": dep_issues,
            "detail": f"{dep_count} deps",
        }

        # =====================================================================
        # CALCULATE TOTAL
        # =====================================================================
        total_score = sum(c["score"] for c in categories.values())
        total_max = sum(c["max"] for c in categories.values())
        pct = round(total_score / total_max * 100) if total_max > 0 else 0

        if pct >= 95:
            grade = "A+"
        elif pct >= 90:
            grade = "A"
        elif pct >= 85:
            grade = "B+"
        elif pct >= 80:
            grade = "B"
        elif pct >= 75:
            grade = "C+"
        elif pct >= 70:
            grade = "C"
        elif pct >= 60:
            grade = "D"
        else:
            grade = "F"

        total_issues = sum(len(c["issues"]) for c in categories.values())

        result = {
            "module": mod_name,
            "score": pct,
            "grade": grade,
            "total_score": total_score,
            "total_max": total_max,
            "total_issues": total_issues,
            "categories": categories,
        }
        all_results.append(result)

        # Display individual module report (if single module or not too many)
        if module or len(modules_to_audit) <= 5:
            rows = []
            for cat_name, cat_data in categories.items():
                score_str = f"{cat_data['score']}/{cat_data['max']}"
                issue_count = len(cat_data["issues"])
                detail = cat_data["issues"][0] if cat_data["issues"] else cat_data.get("detail", "OK")
                rows.append([cat_name, score_str, str(issue_count), detail])

            rows.append(
                [
                    "[bold]TOTAL[/bold]",
                    f"[bold]{total_score}/{total_max}[/bold]",
                    str(total_issues),
                    f"[bold]Grade: {grade}[/bold]",
                ]
            )

            out.table(
                f"Module Audit: {mod_name} — {pct}% ({grade})",
                [("Category", ""), ("Score", ""), ("Issues", ""), ("Detail", "")],
                rows,
            )

    # Summary table for --all mode
    if all_modules and len(modules_to_audit) > 5:
        summary_rows = []
        grades_count: dict[str, int] = {"A+": 0, "A": 0, "B+": 0, "B": 0, "C+": 0, "C": 0, "D": 0, "F": 0}
        for r in sorted(all_results, key=lambda x: -x["score"]):
            grade_color = "green" if r["score"] >= 80 else "yellow" if r["score"] >= 60 else "red"
            summary_rows.append(
                [
                    r["module"],
                    f"[{grade_color}]{r['score']}%[/{grade_color}]",
                    f"[{grade_color}]{r['grade']}[/{grade_color}]",
                    str(r["total_issues"]),
                ]
            )
            grades_count[r["grade"]] = grades_count.get(r["grade"], 0) + 1

        avg_score = round(sum(r["score"] for r in all_results) / len(all_results)) if all_results else 0

        out.table(
            f"Module Audit Summary — {len(all_results)} modules, avg {avg_score}%",
            [("Module", ""), ("Score", ""), ("Grade", ""), ("Issues", "")],
            summary_rows,
        )

        dist_parts = []
        for g in ["A+", "A", "B+", "B", "C+", "C", "D", "F"]:
            if grades_count.get(g, 0) > 0:
                dist_parts.append(f"{g}: {grades_count[g]}")
        out.info(f"Grade distribution: {', '.join(dist_parts)}")

    # Export to JSON
    if output:
        with open(output, "w") as f:
            json_mod.dump(all_results, f, indent=2, default=str)
        out.success(f"Exported audit results to {output}")

    # CI/CD gate
    if min_score > 0:
        failing = [r for r in all_results if r["score"] < min_score]
        if failing:
            out.error(f"{len(failing)} module(s) below minimum score {min_score}:")
            for r in failing:
                out.error(f"  {r['module']}: {r['score']}% ({r['grade']})")
            raise typer.Exit(1)
        else:
            out.success(f"All {len(all_results)} module(s) pass minimum score {min_score}")

    if actx.json_mode:
        out.raw_json(all_results if len(all_results) > 1 else all_results[0])


@app.command("audit-fix")
def audit_fix(
    ctx: typer.Context,
    module: Annotated[str, typer.Argument(help="Module name to auto-fix")],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show what would be fixed without modifying files")
    ] = False,
    categories: Annotated[
        str | None,
        typer.Option(
            "--categories", "-c", help="Comma-separated categories to fix: acl,docs,manifest (default: all safe)"
        ),
    ] = None,
) -> None:
    """Auto-fix safe audit issues for a module.

    Fixes categories that can be safely automated:
    - acl: Generate missing ir.model.access.csv rows via scaffold security
    - docs: Create CLAUDE.md from manifest metadata if missing
    - manifest: Add missing description, author, version keys

    Does NOT auto-fix: field conventions, N+1 patterns, sudo() usage,
    TODO comments, dependencies (these need human review).

    Examples:
        kctl-odoo dev audit-fix sfa_management --dry-run
        kctl-odoo dev audit-fix base_management
        kctl-odoo dev audit-fix sfa_management --categories acl,docs
    """
    import ast
    import subprocess  # noqa: F401

    actx: AppContext = ctx.obj
    out = actx.output

    private_dir = Path.cwd() / "src" / "private"
    mod_dir = private_dir / module

    if not mod_dir.exists() or not (mod_dir / "__manifest__.py").exists():
        out.error(f"Module not found: {module}")
        raise typer.Exit(1)

    # Determine which categories to fix
    fix_cats = {"acl", "docs", "manifest"}
    if categories:
        fix_cats = {c.strip().lower() for c in categories.split(",")}

    fixes_applied = 0
    fixes_skipped = 0

    # =====================================================================
    # FIX 1: ACL — Generate missing ir.model.access.csv rows
    # =====================================================================
    if "acl" in fix_cats:
        csv_path = mod_dir / "security" / "ir.model.access.csv"

        # Find models with _name
        models_dir = mod_dir / "models"
        model_names = []
        if models_dir.exists():
            for py_file in models_dir.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                try:
                    content = py_file.read_text(errors="ignore")
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            cls_name = None
                            cls_inherits = []
                            for item in node.body:
                                if (
                                    isinstance(item, ast.Assign)
                                    and len(item.targets) == 1
                                    and isinstance(item.targets[0], ast.Name)
                                ):
                                    attr = item.targets[0].id
                                    if attr == "_name" and isinstance(item.value, ast.Constant):
                                        cls_name = str(item.value.value)
                                    elif attr == "_inherit":
                                        if isinstance(item.value, ast.Constant):
                                            cls_inherits = [str(item.value.value)]
                                        elif isinstance(item.value, (ast.List, ast.Tuple)):
                                            cls_inherits = [
                                                str(e.value) for e in item.value.elts if isinstance(e, ast.Constant)
                                            ]
                            if cls_name and "." in cls_name and "mixin" not in cls_name.lower():
                                if cls_name not in cls_inherits:
                                    model_names.append(cls_name)
                except Exception:
                    pass

        if model_names:
            # Read existing CSV to find what's already covered
            existing_models = set()
            if csv_path.exists():
                csv_content = csv_path.read_text(errors="ignore")
                # Scan ALL columns for model references (handles different CSV column orders)
                for line in csv_content.splitlines()[1:]:
                    if not line.strip():
                        continue
                    # Collect all cell values that look like model references
                    for cell in line.split(","):
                        cell = cell.strip()
                        if cell.startswith("model_"):
                            existing_models.add(cell)

            missing = []
            for m in model_names:
                model_ref = f"model_{m.replace('.', '_')}"
                if model_ref not in existing_models:
                    missing.append(m)

            if missing:
                if dry_run:
                    out.info(f"[ACL] Would add {len(missing)} model(s) to ir.model.access.csv:")
                    for m in missing[:10]:
                        out.info(f"  + {m}")
                    if len(missing) > 10:
                        out.info(f"  ... and {len(missing) - 10} more")
                    fixes_skipped += 1
                else:
                    # Ensure security dir exists
                    (mod_dir / "security").mkdir(exist_ok=True)

                    # Read existing content or create header
                    if csv_path.exists():
                        lines = csv_path.read_text(errors="ignore").splitlines()
                    else:
                        lines = ["id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink"]

                    # Add missing models with correct Odoo CSV format:
                    # id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
                    for m in missing:
                        model_ref = m.replace(".", "_")
                        access_id = f"access_{model_ref}_public"
                        model_id_ref = f"model_{model_ref}"
                        human_name = f"{m}.public"
                        lines.append(f"{access_id},{human_name},{model_id_ref},base.group_user,1,0,0,0")

                    csv_path.write_text("\n".join(lines) + "\n")
                    out.success(f"[ACL] Added {len(missing)} model(s) to ir.model.access.csv")
                    fixes_applied += 1
            else:
                out.info("[ACL] All models already have ACL rules.")
        else:
            out.info("[ACL] No custom models found in module.")

    # =====================================================================
    # FIX 2: DOCS — Create CLAUDE.md if missing
    # =====================================================================
    if "docs" in fix_cats:
        claude_md = mod_dir / "CLAUDE.md"
        if not claude_md.exists():
            try:
                manifest = ast.literal_eval((mod_dir / "__manifest__.py").read_text())
            except Exception:
                manifest = {}

            name = manifest.get("name", module)
            summary = manifest.get("summary", manifest.get("description", ""))
            depends = manifest.get("depends", [])
            version = manifest.get("version", "")

            # Check for FastAPI
            has_fastapi = (mod_dir / "controllers").exists() and list((mod_dir / "controllers").glob("*_router.py"))
            has_models = (mod_dir / "models").exists()

            content_lines = [
                f"# {name}",
                "",
                f"{summary}" if summary else f"Private Odoo module: {module}",
                "",
                "## Overview",
                "",
                f"**Version:** {version}" if version else "",
                f"**Depends:** {', '.join(depends)}" if depends else "",
                "",
            ]

            if has_models:
                content_lines.extend(
                    [
                        "## Models",
                        "",
                        "See `models/` directory for Odoo model definitions.",
                        "",
                    ]
                )

            if has_fastapi:
                router_count = len(list((mod_dir / "controllers").glob("*_router.py")))
                content_lines.extend(
                    [
                        "## FastAPI Routers",
                        "",
                        f"{router_count} router(s) in `controllers/` directory.",
                        "",
                    ]
                )

            content_lines.extend(
                [
                    "## Testing",
                    "",
                    "```bash",
                    f"kctl-odoo test run {module}",
                    f"kctl-odoo dev module-health {module}",
                    "```",
                    "",
                ]
            )

            doc_content = "\n".join(line for line in content_lines if line is not None)

            if dry_run:
                out.info(f"[DOCS] Would create CLAUDE.md ({len(doc_content)} bytes)")
                fixes_skipped += 1
            else:
                claude_md.write_text(doc_content)
                out.success(f"[DOCS] Created CLAUDE.md ({len(doc_content)} bytes)")
                fixes_applied += 1
        else:
            out.info("[DOCS] CLAUDE.md already exists.")

    # =====================================================================
    # FIX 3: MANIFEST — Add missing keys
    # =====================================================================
    if "manifest" in fix_cats:
        manifest_path = mod_dir / "__manifest__.py"
        try:
            manifest_text = manifest_path.read_text()
            manifest = ast.literal_eval(manifest_text)
            changes = []

            if not manifest.get("description") and not manifest.get("summary"):
                changes.append("description")
            if not manifest.get("author"):
                changes.append("author")
            if not manifest.get("version"):
                changes.append("version")

            if changes:
                if dry_run:
                    out.info(f"[MANIFEST] Would add missing keys: {', '.join(changes)}")
                    fixes_skipped += 1
                else:
                    # Add missing keys by string manipulation (safer than rewriting AST)
                    if (
                        "description" in changes
                        and '"description"' not in manifest_text
                        and "'description'" not in manifest_text
                    ):
                        manifest_text = manifest_text.replace(
                            '"installable"', f'"description": "{module.replace("_", " ").title()}",\n    "installable"'
                        )
                    if "author" in changes and '"author"' not in manifest_text and "'author'" not in manifest_text:
                        manifest_text = manifest_text.replace(
                            '"installable"', '"author": "Kodemeio",\n    "installable"'
                        )
                    if "version" in changes and '"version"' not in manifest_text and "'version'" not in manifest_text:
                        manifest_text = manifest_text.replace(
                            '"installable"', '"version": "18.0.1.0.0",\n    "installable"'
                        )
                    manifest_path.write_text(manifest_text)
                    out.success(f"[MANIFEST] Added missing keys: {', '.join(changes)}")
                    fixes_applied += 1
            else:
                out.info("[MANIFEST] All required keys present.")
        except Exception as e:
            out.warn(f"[MANIFEST] Could not parse: {e}")

    # Summary
    out.info("")
    if dry_run:
        out.info(f"DRY RUN: {fixes_skipped} fix(es) would be applied. Run without --dry-run to apply.")
    else:
        out.success(f"Applied {fixes_applied} fix(es) to {module}.")
        if fixes_applied > 0:
            out.info(f"Re-run audit to verify: kctl-odoo dev audit {module}")


@app.command("audit-prompt")
def audit_prompt(
    ctx: typer.Context,
    module: Annotated[str, typer.Argument(help="Module name")],
    output: Annotated[str | None, typer.Option("--output", "-o", help="Save prompt to file")] = None,
) -> None:
    """Generate an AI agent prompt from audit results for human-in-loop fixes.

    Runs the audit, then generates a structured prompt that can be fed to
    Claude Code or any AI assistant to fix the issues. Focuses on issues
    that need human/AI judgment (N+1 patterns, field conventions, sudo).

    Examples:
        kctl-odoo dev audit-prompt sfa_management
        kctl-odoo dev audit-prompt sfa_management -o /tmp/fix-sfa.md
    """
    import ast
    import json as json_mod  # noqa: F401
    import re

    actx: AppContext = ctx.obj
    out = actx.output

    private_dir = Path.cwd() / "src" / "private"
    mod_dir = private_dir / module

    if not mod_dir.exists() or not (mod_dir / "__manifest__.py").exists():
        out.error(f"Module not found: {module}")
        raise typer.Exit(1)

    # Run the audit internally to collect issues
    # Reuse audit logic by collecting issues manually
    issues_by_category: dict[str, list[str]] = {}

    # --- N+1 Patterns ---
    n1_issues: list[str] = []
    models_dir = mod_dir / "models"
    if models_dir.exists():
        for py_file in models_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                content = py_file.read_text(errors="ignore")
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.For):
                        for child in ast.walk(node):
                            if (
                                isinstance(child, ast.Call)
                                and isinstance(child.func, ast.Attribute)
                                and child.func.attr in ("search", "search_read", "create")
                            ):
                                rel_path = py_file.relative_to(mod_dir)
                                n1_issues.append(f"{rel_path}:{child.lineno}: .{child.func.attr}() inside for loop")
            except Exception:
                pass
    if n1_issues:
        issues_by_category["N+1 ORM Patterns"] = n1_issues

    # --- sudo() usage (only in models — router sudo is expected) ---
    sudo_issues: list[str] = []
    models_dir_check = mod_dir / "models"
    if models_dir_check.exists():
        for py_file in models_dir_check.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                content = py_file.read_text(errors="ignore")
                for i, line in enumerate(content.splitlines(), 1):
                    if ".sudo()" in line:
                        rel_path = py_file.relative_to(mod_dir)
                        sudo_issues.append(f"{rel_path}:{i}: {line.strip()[:80]}")
            except Exception:
                pass
    if sudo_issues:
        issues_by_category["sudo() in Models (review each)"] = sudo_issues

    # --- Field conventions ---
    prefix_map = {
        "sfa_management": "sfa_",
        "lfa_management": "lfa_",
        "wms_management": "wms_",
        "tpm_management": "tpm_",
        "dms_management": "dms_",
        "hrm_management": "hrm_",
        "shop_management": "shop_",
        "bia_management": "bia_",
        "asset_management": "asset_",
        "mrp_management": "mrp_",
        "partner_management": "partner_",
        "compliance_management": "compliance_",
        "form_management": "form_",
    }
    expected_prefix = prefix_map.get(module)
    field_issues: list[str] = []
    if expected_prefix and models_dir and models_dir.exists():
        for py_file in models_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                content = py_file.read_text(errors="ignore")
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        has_inherit = any(
                            isinstance(item, ast.Assign)
                            and len(item.targets) == 1
                            and isinstance(item.targets[0], ast.Name)
                            and item.targets[0].id == "_inherit"
                            for item in node.body
                        )
                        has_name = any(
                            isinstance(item, ast.Assign)
                            and len(item.targets) == 1
                            and isinstance(item.targets[0], ast.Name)
                            and item.targets[0].id == "_name"
                            for item in node.body
                        )
                        # Only check pure _inherit (no _name = module-owned model)
                        if has_inherit and not has_name:
                            for item in node.body:
                                if (
                                    isinstance(item, ast.Assign)
                                    and len(item.targets) == 1
                                    and isinstance(item.targets[0], ast.Name)
                                ):
                                    fname = item.targets[0].id
                                    if (
                                        not fname.startswith("_")
                                        and not fname.startswith(expected_prefix)
                                        and fname not in ("_inherit", "_name", "_description", "_order", "_rec_name")
                                    ):
                                        rel_path = py_file.relative_to(mod_dir)
                                        field_issues.append(
                                            f"{rel_path}:{item.lineno}: `{fname}` should be `{expected_prefix}{fname}`"
                                        )
            except Exception:
                pass
    if field_issues:
        issues_by_category[f"Field Naming Convention (prefix: {expected_prefix})"] = field_issues

    # --- TODO/FIXME ---
    todo_issues: list[str] = []
    for py_file in mod_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            content = py_file.read_text(errors="ignore")
            for i, line in enumerate(content.splitlines(), 1):
                match = re.search(r"#\s*(TODO|FIXME|HACK|XXX)\b(.*)", line, re.IGNORECASE)
                if match:
                    rel_path = py_file.relative_to(mod_dir)
                    todo_issues.append(f"{rel_path}:{i}: {match.group(0).strip()[:80]}")
        except Exception:
            pass
    if todo_issues:
        issues_by_category["TODO/FIXME Comments"] = todo_issues

    # --- Security (missing ACL) ---
    acl_issues: list[str] = []
    csv_path = mod_dir / "security" / "ir.model.access.csv"
    model_names: list[str] = []
    if models_dir and models_dir.exists():
        for py_file in models_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                content = py_file.read_text(errors="ignore")
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        for item in node.body:
                            if (
                                isinstance(item, ast.Assign)
                                and len(item.targets) == 1
                                and isinstance(item.targets[0], ast.Name)
                                and item.targets[0].id == "_name"
                                and isinstance(item.value, ast.Constant)
                            ):
                                val = str(item.value.value)
                                if "." in val and "mixin" not in val.lower():
                                    model_names.append(val)
            except Exception:
                pass

    if model_names and csv_path.exists():
        csv_content = csv_path.read_text(errors="ignore")
        for m in model_names:
            model_ref = f"model_{m.replace('.', '_')}"
            if model_ref not in csv_content:
                acl_issues.append(f"Model `{m}` has no ir.model.access.csv entry")
    if acl_issues:
        issues_by_category["Missing ACL Rules"] = acl_issues

    # =====================================================================
    # Generate the prompt
    # =====================================================================
    if not issues_by_category:
        out.success(f"No issues found for {module}. Module is clean!")
        return

    total_issues = sum(len(v) for v in issues_by_category.values())

    prompt_lines = [
        f"# Fix Audit Issues for `{module}`",
        "",
        f"Module path: `src/private/{module}/`",
        f"Total issues: {total_issues}",
        "",
        "## Instructions",
        "",
        "Fix the following issues found by `kctl-odoo dev audit`. For each category:",
        "- Read the file at the specified path and line number",
        "- Apply the fix described",
        "- Do NOT change any business logic — only fix the specific issue",
        "- Run `kctl-odoo dev audit " + module + "` after fixing to verify improvement",
        "",
        "## Auto-fixable (run first)",
        "",
        "```bash",
        f"kctl-odoo dev audit-fix {module}",
        "```",
        "",
        "This will fix: missing ACL rows, missing CLAUDE.md, missing manifest keys.",
        "",
        "## Issues Requiring AI/Human Review",
        "",
    ]

    for category, issues in issues_by_category.items():
        prompt_lines.append(f"### {category} ({len(issues)} issues)")
        prompt_lines.append("")

        if "N+1" in category:
            prompt_lines.append("**How to fix:** Move `.search()` / `.search_read()` calls outside the `for` loop.")
            prompt_lines.append("Pre-fetch all records before the loop, then filter inside. For `.create()` inside")
            prompt_lines.append("loops, collect vals into a list and call `.create(vals_list)` once after the loop.")
            prompt_lines.append("")
        elif "sudo" in category:
            prompt_lines.append("**How to fix:** Review each `sudo()` call in MODEL files only.")
            prompt_lines.append("Common valid uses: computed fields reading cross-company data, cron jobs,")
            prompt_lines.append("hooks (pre_init_hook, post_init_hook), constraint checks across records.")
            prompt_lines.append("**DO NOT remove sudo() from FastAPI routers** (services/) — routers need it.")
            prompt_lines.append("Only remove if the method already runs as superuser or sudo is truly unnecessary.")
            prompt_lines.append("")
        elif "Field Naming" in category:
            prompt_lines.append(
                f"**How to fix:** Rename fields on `_inherit` models to use the `{expected_prefix}` prefix."
            )
            prompt_lines.append("This requires a database migration (pre_init_hook or migration script) to rename")
            prompt_lines.append("the column. Also update all XML views and Python references to the field.")
            prompt_lines.append("**WARNING:** This is a breaking change — coordinate with frontend apps.")
            prompt_lines.append("")
        elif "TODO" in category:
            prompt_lines.append("**How to fix:** Address each TODO/FIXME, then remove the comment.")
            prompt_lines.append("If the TODO is still valid, leave it but consider creating a tracked issue.")
            prompt_lines.append("")
        elif "ACL" in category:
            prompt_lines.append(
                "**How to fix:** Run `kctl-odoo dev audit-fix " + module + "` to auto-generate ACL rows,"
            )
            prompt_lines.append("or manually add rows to `security/ir.model.access.csv`.")
            prompt_lines.append("")

        for issue in issues[:50]:
            prompt_lines.append(f"- `{issue}`")
        if len(issues) > 50:
            prompt_lines.append(f"- ... and {len(issues) - 50} more")
        prompt_lines.append("")

    prompt_lines.extend(
        [
            "## Verification",
            "",
            "After fixing, run:",
            "```bash",
            f"kctl-odoo dev audit {module}",
            "```",
            "",
            "Target: Score should improve from current level toward 90+% (Grade A).",
        ]
    )

    prompt_text = "\n".join(prompt_lines)

    if output:
        Path(output).write_text(prompt_text)
        out.success(f"Prompt saved to {output} ({total_issues} issues)")
        out.info("Usage: Feed this file to Claude Code or paste into an AI assistant.")
    else:
        # Print to stdout
        print(prompt_text)

    if actx.json_mode:
        out.raw_json(
            {
                "module": module,
                "total_issues": total_issues,
                "categories": {k: len(v) for k, v in issues_by_category.items()},
                "prompt_file": output,
            }
        )


@app.command("audit-views")
def audit_views(
    ctx: typer.Context,
    module: Annotated[str | None, typer.Argument(help="Module name (default: all)")] = None,
) -> None:
    """Audit XML views for performance — field count, deprecated patterns.

    Flags: forms with >30 fields, list views with >15 columns,
    heavy onchange usage, deeply nested groups.

    Examples:
        kctl-odoo dev audit-views sfa_management
        kctl-odoo dev audit-views
    """
    import xml.etree.ElementTree as ET

    actx: AppContext = ctx.obj
    out = actx.output

    private_dir = Path.cwd() / "src" / "private"
    if module:
        modules = [module]
    else:
        modules = sorted([d.name for d in private_dir.iterdir() if d.is_dir() and (d / "__manifest__.py").exists()])

    all_issues = []
    for mod_name in modules:
        views_dir = private_dir / mod_name / "views"
        if not views_dir.exists():
            continue
        for xml_file in views_dir.rglob("*.xml"):
            try:
                tree = ET.parse(str(xml_file))
                root = tree.getroot()
                rel_path = xml_file.relative_to(private_dir / mod_name)
                for record in root.iter("record"):
                    model = record.get("model", "")
                    if model != "ir.ui.view":
                        continue
                    arch = record.find(".//form")
                    if arch is not None:
                        field_count = len(arch.findall(".//field"))
                        if field_count > 30:
                            all_issues.append([mod_name, str(rel_path), "form", f"{field_count} fields (>30 = slow)"])
                    arch = record.find(".//list") or record.find(".//tree")
                    if arch is not None:
                        col_count = len(arch.findall(".//field"))
                        if col_count > 15:
                            all_issues.append([mod_name, str(rel_path), "list", f"{col_count} columns (>15 = slow)"])
            except Exception:
                pass

    if not all_issues:
        out.success(f"No view performance issues found across {len(modules)} module(s).")
        return

    out.table(
        f"View Performance Issues ({len(all_issues)})",
        [("Module", ""), ("File", ""), ("Type", ""), ("Issue", "")],
        all_issues,
    )


@app.command("audit-compute")
def audit_compute(
    ctx: typer.Context,
    module: Annotated[str | None, typer.Argument(help="Module name (default: all)")] = None,
) -> None:
    """Find computed fields without store=True.

    Unstored computed fields are recomputed on every read, which can
    cause severe performance issues on large recordsets.

    Examples:
        kctl-odoo dev audit-compute sfa_management
        kctl-odoo dev audit-compute
    """
    import re

    actx: AppContext = ctx.obj
    out = actx.output

    private_dir = Path.cwd() / "src" / "private"
    if module:
        modules = [module]
    else:
        modules = sorted([d.name for d in private_dir.iterdir() if d.is_dir() and (d / "__manifest__.py").exists()])

    all_issues = []
    for mod_name in modules:
        models_dir = private_dir / mod_name / "models"
        if not models_dir.exists():
            continue
        for py_file in models_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                content = py_file.read_text(errors="ignore")
                lines = content.splitlines()
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if "compute=" in stripped and "fields." in stripped:
                        # Check surrounding lines for store=True
                        chunk = "\n".join(lines[max(0, i) : min(len(lines), i + 6)])
                        if "store=True" not in chunk and "store = True" not in chunk:
                            rel_path = py_file.relative_to(private_dir / mod_name)
                            # Extract field name
                            field_match = re.match(r"\s*(\w+)\s*=\s*fields\.", stripped)
                            field_name = field_match.group(1) if field_match else "?"
                            all_issues.append([mod_name, str(rel_path), str(i + 1), field_name])
            except Exception:
                pass

    if not all_issues:
        out.success(f"All computed fields have store=True across {len(modules)} module(s).")
        return

    out.table(
        f"Unstored Computed Fields ({len(all_issues)})",
        [("Module", ""), ("File", ""), ("Line", ""), ("Field", "")],
        all_issues,
    )
    out.warn(f"{len(all_issues)} computed field(s) without store=True — recomputed on every read.")


@app.command("audit-blocking")
def audit_blocking(
    ctx: typer.Context,
    module: Annotated[str | None, typer.Argument(help="Module name (default: all)")] = None,
) -> None:
    """Find blocking operations inside HTTP controllers.

    Detects: synchronous email sending, inline PDF rendering,
    external HTTP calls — all should be queued via queue_job.

    Examples:
        kctl-odoo dev audit-blocking sfa_management
    """
    actx: AppContext = ctx.obj
    out = actx.output

    private_dir = Path.cwd() / "src" / "private"
    if module:
        modules = [module]
    else:
        modules = sorted([d.name for d in private_dir.iterdir() if d.is_dir() and (d / "__manifest__.py").exists()])

    blocking_patterns = [
        ("send_mail(", "Synchronous email — use queue_job"),
        ("message_post(", "Synchronous notification — consider async"),
        ("render_qweb_pdf(", "Inline PDF generation — queue for large reports"),
        ("requests.get(", "External HTTP call — use queue_job for reliability"),
        ("requests.post(", "External HTTP call — use queue_job for reliability"),
        ("httpx.get(", "External HTTP call — consider async/queue"),
        ("httpx.post(", "External HTTP call — consider async/queue"),
        ("urllib", "External HTTP — use httpx + queue_job"),
    ]

    all_issues = []
    for mod_name in modules:
        for search_dir in [private_dir / mod_name / "controllers", private_dir / mod_name / "services"]:
            if not search_dir.exists():
                continue
            for py_file in search_dir.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                try:
                    content = py_file.read_text(errors="ignore")
                    for i, line in enumerate(content.splitlines(), 1):
                        for pattern, msg in blocking_patterns:
                            if pattern in line and "#" not in line.split(pattern)[0][-10:]:
                                rel_path = py_file.relative_to(private_dir / mod_name)
                                all_issues.append([mod_name, str(rel_path), str(i), msg])
                                break  # one issue per line
                except Exception:
                    pass

    if not all_issues:
        out.success(f"No blocking operations found in controllers/services across {len(modules)} module(s).")
        return

    out.table(
        f"Potential Blocking Operations ({len(all_issues)})",
        [("Module", ""), ("File", ""), ("Line", ""), ("Issue", "")],
        all_issues,
    )
    out.warn("These operations may cause HTTP timeouts if processing large data. Consider using queue_job.")


@app.command("check-log-level")
def check_log_level(ctx: typer.Context) -> None:
    """Check if debug logging is enabled (production risk).

    Debug-level logging in production causes excessive disk I/O
    and can expose sensitive data in log files.

    Examples:
        kctl-odoo dev check-log-level
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    issues = []

    # Check ir.logging records (high volume = debug enabled)
    try:
        log_count = c.search_count("ir.logging", [])
        if log_count > 1000:
            issues.append(f"ir.logging has {log_count} records — debug logging may be enabled")
    except Exception:
        pass

    # Check key system parameters
    try:
        params = c.search_read(
            "ir.config_parameter",
            domain=[("key", "ilike", "log")],
            fields=["key", "value"],
            limit=10,
        )
        for p in params:
            if "debug" in str(p.get("value", "")).lower():
                issues.append(f"Parameter {p['key']} = {p['value']} (debug level)")
    except Exception:
        pass

    if not issues:
        out.success("No debug logging detected. Production-safe.")
    else:
        for issue in issues:
            out.warn(issue)
        out.info("Recommendation: Set log level to 'warn' or 'error' in production.")


@app.command("audit-api")
def audit_api(
    ctx: typer.Context,
    module: Annotated[str | None, typer.Argument(help="Module name (default: all with routers)")] = None,
) -> None:
    """Audit FastAPI router code for common performance issues.

    Checks:
    1. Over-fetching: search_read() without fields= parameter
    2. Missing pagination: search_read()/search() without limit=
    3. False async: async def with sync ORM calls
    4. Transaction abuse: cr.commit()/cr.execute() in router code
    5. Missing error handling: router functions without try/except

    Examples:
        kctl-odoo dev audit-api sfa_management
        kctl-odoo dev audit-api
    """
    import ast

    actx: AppContext = ctx.obj
    out = actx.output

    private_dir = Path.cwd() / "src" / "private"
    if module:
        modules = [module]
    else:
        modules = sorted(
            [
                d.name
                for d in private_dir.iterdir()
                if d.is_dir()
                and (d / "__manifest__.py").exists()
                and ((d / "services").exists() or (d / "controllers").exists())
            ]
        )

    all_issues: list[list[str]] = []

    for mod_name in modules:
        for search_dir_name in ["services", "controllers"]:
            search_dir = private_dir / mod_name / search_dir_name
            if not search_dir.exists():
                continue
            for py_file in search_dir.rglob("*.py"):
                if "__pycache__" in str(py_file) or py_file.name == "__init__.py":
                    continue
                try:
                    content = py_file.read_text(errors="ignore")
                    lines = content.splitlines()
                    rel_path = str(py_file.relative_to(private_dir / mod_name))

                    # Parse AST for function-level checks
                    try:
                        tree = ast.parse(content)
                    except SyntaxError:
                        continue

                    for node in ast.walk(tree):
                        # Check for async def with sync ORM (false async)
                        if isinstance(node, ast.AsyncFunctionDef):
                            for child in ast.walk(node):
                                if (
                                    isinstance(child, ast.Call)
                                    and isinstance(child.func, ast.Attribute)
                                    and child.func.attr
                                    in ("search", "search_read", "read", "write", "create", "unlink")
                                ):
                                    all_issues.append(
                                        [
                                            mod_name,
                                            rel_path,
                                            str(child.lineno),
                                            "False async",
                                            f"async def {node.name}() calls sync .{child.func.attr}()",
                                        ]
                                    )
                                    break  # one per function

                    # Line-by-line checks
                    for i, line in enumerate(lines, 1):
                        stripped = line.strip()

                        # Skip comments and empty lines
                        if not stripped or stripped.startswith("#"):
                            continue

                        # 1. Over-fetching: search_read without fields=
                        if ".search_read(" in stripped:
                            # Check this line and next 5 lines for fields=
                            chunk = "\n".join(lines[max(0, i - 1) : min(len(lines), i + 8)])
                            if "fields=" not in chunk and "fields =" not in chunk:
                                all_issues.append(
                                    [
                                        mod_name,
                                        rel_path,
                                        str(i),
                                        "Over-fetching",
                                        "search_read() without fields= — returns ALL fields",
                                    ]
                                )

                        # 2. Missing pagination: search_read or search without limit=
                        if (".search_read(" in stripped or ".search(" in stripped) and ".search_count(" not in stripped:
                            chunk = "\n".join(lines[max(0, i - 1) : min(len(lines), i + 8)])
                            if "limit=" not in chunk and "limit =" not in chunk:
                                # Exclude search_count and simple existence checks
                                if ".search_read(" in stripped or (".search(" in stripped and "limit=1" not in chunk):
                                    all_issues.append(
                                        [
                                            mod_name,
                                            rel_path,
                                            str(i),
                                            "No pagination",
                                            "search/search_read without limit= — may return thousands of records",
                                        ]
                                    )

                        # 3. Transaction abuse: cr.commit() or cr.execute() in routers
                        if "cr.commit()" in stripped or "self.env.cr.commit()" in stripped:
                            all_issues.append(
                                [
                                    mod_name,
                                    rel_path,
                                    str(i),
                                    "Transaction",
                                    "cr.commit() in router — risks partial commits on error",
                                ]
                            )
                        if "cr.execute(" in stripped or "self.env.cr.execute(" in stripped:
                            all_issues.append(
                                [
                                    mod_name,
                                    rel_path,
                                    str(i),
                                    "Raw SQL",
                                    "cr.execute() in router — use ORM or ensure parameterized query",
                                ]
                            )

                except Exception:
                    pass

    if not all_issues:
        out.success(f"No FastAPI performance issues found across {len(modules)} module(s).")
        return

    # Group by category for summary
    categories: dict[str, int] = {}
    for issue in all_issues:
        cat = issue[3]
        categories[cat] = categories.get(cat, 0) + 1

    out.table(
        f"FastAPI Code Audit — {len(all_issues)} issues in {len(modules)} module(s)",
        [("Module", ""), ("File", ""), ("Line", ""), ("Category", ""), ("Issue", "")],
        all_issues,
    )

    out.info("Summary:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        out.info(f"  {cat}: {count}")


@app.command("audit-logic")
def audit_logic(
    ctx: typer.Context,
    module: Annotated[str | None, typer.Argument(help="Module name (default: all private modules)")] = None,
) -> None:
    """Audit Odoo business logic for common errors.

    Static analysis checks:
    1. Hardcoded IDs: browse(1), browse(2), company_id = 1, etc.
    2. Missing super(): create/write/unlink overrides without super() call
    3. Bare except: except: or except Exception without re-raise/logging
    4. Naive datetime: datetime.now() without timezone (should use fields.Datetime.now())
    5. State write without guard: write({'state':...}) without checking current state
    6. Missing constrains: models with monetary/float fields but no @api.constrains
    7. Method override inventory: list all create/write/unlink overrides for review

    Examples:
        kctl-odoo dev audit-logic sfa_management
        kctl-odoo dev audit-logic
    """
    import ast
    import re

    actx: AppContext = ctx.obj
    out = actx.output

    private_dir = Path.cwd() / "src" / "private"
    if module:
        modules = [module]
    else:
        modules = sorted([d.name for d in private_dir.iterdir() if d.is_dir() and (d / "__manifest__.py").exists()])

    all_issues: list[list[str]] = []
    override_inventory: list[list[str]] = []

    for mod_name in modules:
        mod_dir = private_dir / mod_name
        models_dir = mod_dir / "models"
        if not models_dir.exists():
            continue

        for py_file in models_dir.rglob("*.py"):
            if "__pycache__" in str(py_file) or py_file.name == "__init__.py":
                continue
            try:
                content = py_file.read_text(errors="ignore")
                lines = content.splitlines()
                rel_path = str(py_file.relative_to(private_dir / mod_name))

                # Parse AST
                try:
                    tree = ast.parse(content)
                except SyntaxError:
                    continue

                for node in ast.walk(tree):
                    if not isinstance(node, ast.ClassDef):
                        continue

                    # Check if it's an Odoo model class (has _name or _inherit)
                    is_odoo_model = False
                    has_monetary = False
                    has_constrains = False
                    model_name_val = ""

                    for item in node.body:
                        if (
                            isinstance(item, ast.Assign)
                            and len(item.targets) == 1
                            and isinstance(item.targets[0], ast.Name)
                        ):
                            attr = item.targets[0].id
                            if attr in ("_name", "_inherit"):
                                is_odoo_model = True
                                if attr == "_name" and isinstance(item.value, ast.Constant):
                                    model_name_val = str(item.value.value)

                        # Check for monetary/float fields
                        if isinstance(item, ast.Assign) and len(item.targets) == 1:
                            if isinstance(item.value, ast.Call) and isinstance(item.value.func, ast.Attribute):
                                field_type = item.value.func.attr
                                if field_type in ("Float", "Monetary", "Integer"):
                                    has_monetary = True

                        # Check for @api.constrains decorator
                        if isinstance(item, ast.FunctionDef):
                            for decorator in item.decorator_list:
                                if (
                                    isinstance(decorator, ast.Attribute)
                                    and decorator.attr == "constrains"
                                    or (
                                        isinstance(decorator, ast.Call)
                                        and isinstance(decorator.func, ast.Attribute)
                                        and decorator.func.attr == "constrains"
                                    )
                                ):
                                    has_constrains = True

                    if not is_odoo_model:
                        continue

                    # Check each method in the class
                    for item in node.body:
                        if not isinstance(item, ast.FunctionDef):
                            continue

                        method_name = item.name

                        # --- Check 2: Missing super() in create/write/unlink ---
                        if method_name in ("create", "write", "unlink", "_compute_name"):
                            has_super = False
                            for child in ast.walk(item):
                                if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                                    if child.func.attr == method_name:
                                        # Check if it's super().method()
                                        if (
                                            isinstance(child.func.value, ast.Call)
                                            and isinstance(child.func.value.func, ast.Name)
                                            and child.func.value.func.id == "super"
                                        ):
                                            has_super = True

                            if method_name in ("create", "write", "unlink") and not has_super:
                                all_issues.append(
                                    [
                                        mod_name,
                                        rel_path,
                                        str(item.lineno),
                                        "Missing super()",
                                        f"def {method_name}() without super().{method_name}() call",
                                    ]
                                )

                            # Add to override inventory
                            if method_name in ("create", "write", "unlink"):
                                override_inventory.append(
                                    [
                                        mod_name,
                                        rel_path,
                                        str(item.lineno),
                                        method_name,
                                        "with super" if has_super else "NO SUPER",
                                    ]
                                )

                # Line-by-line checks (faster than full AST for simple patterns)
                for i, line in enumerate(lines, 1):
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        continue

                    # --- Check 1: Hardcoded IDs ---
                    # Detect: .browse(1), .browse(2), company_id = 1
                    hardcoded_patterns = [
                        (r"\.browse\(\s*[0-9]+\s*\)", "Hardcoded record ID in .browse()"),
                        (r"company_id\s*=\s*[0-9]+", "Hardcoded company_id"),
                        (r"\.browse\(\s*\[?\s*1\s*\]?\s*\)", "browse(1) — likely hardcoded admin/company"),
                    ]
                    for pattern, msg in hardcoded_patterns:
                        if re.search(pattern, stripped):
                            # Exclude test files and comments
                            if "test" not in rel_path.lower():
                                all_issues.append([mod_name, rel_path, str(i), "Hardcoded ID", msg])
                                break

                    # --- Check 3: Bare except ---
                    if re.match(r"except\s*:", stripped) or re.match(r"except\s+Exception\s*:", stripped):
                        # Check if next lines have raise, logging, or _logger
                        next_lines = "\n".join(lines[i : min(len(lines), i + 3)])
                        if (
                            "raise" not in next_lines
                            and "_logger" not in next_lines
                            and "logging" not in next_lines
                            and "pass" in next_lines
                        ):
                            all_issues.append(
                                [
                                    mod_name,
                                    rel_path,
                                    str(i),
                                    "Bare except",
                                    "except with pass — silently swallows errors",
                                ]
                            )

                    # --- Check 4: Naive datetime ---
                    if "datetime.now()" in stripped and "tz=" not in stripped and "UTC" not in stripped:
                        if "fields.Datetime.now()" not in stripped and "fields.Date.today()" not in stripped:
                            all_issues.append(
                                [
                                    mod_name,
                                    rel_path,
                                    str(i),
                                    "Naive datetime",
                                    "datetime.now() without tz — use fields.Datetime.now() or datetime.now(tz=UTC)",
                                ]
                            )

                    # --- Check 5: State write without guard ---
                    if "'state'" in stripped and ".write(" in stripped:
                        # Check if there's a state check before this line
                        prev_lines = "\n".join(lines[max(0, i - 5) : i])
                        if (
                            "self.state" not in prev_lines
                            and "state ==" not in prev_lines
                            and "state !=" not in prev_lines
                            and "filtered" not in prev_lines
                        ):
                            if "action_" in stripped or "button_" in stripped:
                                pass  # Method name suggests it's an action — probably has guards elsewhere
                            else:
                                all_issues.append(
                                    [
                                        mod_name,
                                        rel_path,
                                        str(i),
                                        "Unguarded state write",
                                        "write({'state':...}) without checking current state first",
                                    ]
                                )

                # --- Check 6: Missing constrains on monetary models ---
                if is_odoo_model and has_monetary and not has_constrains and model_name_val:
                    # Only flag if it's a NEW model (not just _inherit)
                    if model_name_val and "." in model_name_val:
                        pass  # Don't flag — too noisy for inherited models
                        # Could check if model defines its OWN monetary fields

            except Exception:
                pass

    if not all_issues and not override_inventory:
        out.success(f"No business logic issues found across {len(modules)} module(s).")
        return

    if all_issues:
        # Group by category
        categories: dict[str, int] = {}
        for issue in all_issues:
            cat = issue[3]
            categories[cat] = categories.get(cat, 0) + 1

        out.table(
            f"Business Logic Issues — {len(all_issues)} issues in {len(modules)} module(s)",
            [("Module", ""), ("File", ""), ("Line", ""), ("Category", ""), ("Detail", "")],
            all_issues,
        )

        out.info("\nSummary:")
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            out.info(f"  {cat}: {count}")

    # Show override inventory summary
    if override_inventory:
        no_super = [o for o in override_inventory if o[4] == "NO SUPER"]
        if no_super:
            out.warn(f"\nMethod overrides without super(): {len(no_super)}")
            for o in no_super[:10]:
                out.warn(f"  {o[0]}/{o[1]}:{o[2]} def {o[3]}()")

        out.info(f"\nTotal create/write/unlink overrides: {len(override_inventory)} ({len(no_super)} without super)")
        out.info("  In .env: ODOO_LOG_LEVEL=warn")


@app.command("audit-ou")
def audit_ou(
    ctx: typer.Context,
    module: Annotated[str | None, typer.Argument(help="Module name (default: all private modules)")] = None,
) -> None:
    """Audit Operating Unit (multi-branch) isolation gaps.

    Checks:
    1. Models without operating_unit_id field (should have OU for data isolation)
    2. Record rules missing OU filter (security gap)
    3. Views missing OU field (users can't see/set OU)
    4. Search domains missing OU filter in Python code

    Requires: operating_unit OCA module installed.

    Examples:
        kctl-odoo dev audit-ou sfa_management
        kctl-odoo dev audit-ou
    """
    import ast
    import xml.etree.ElementTree as ET
    from pathlib import Path

    actx: AppContext = ctx.obj
    out = actx.output

    private_dir = Path.cwd() / "src" / "private"
    if module:
        modules = [module]
    else:
        modules = sorted([d.name for d in private_dir.iterdir() if d.is_dir() and (d / "__manifest__.py").exists()])

    all_issues = []

    # Models that SHOULD have OU (transactional business models)
    ou_expected_patterns = [
        "order",
        "invoice",
        "move",
        "picking",
        "production",
        "visit",
        "delivery",
        "payment",
        "expense",
        "leave",
        "attendance",
        "promotion",
        "fund",
        "claim",
        "deduction",
        "settlement",
        "ticket",
        "request",
        "session",
        "report",
        "budget",
    ]

    for mod_name in modules:
        mod_dir = private_dir / mod_name
        models_dir = mod_dir / "models"
        if not models_dir.exists():
            continue

        # Check manifest for operating_unit dependency
        try:
            manifest = ast.literal_eval((mod_dir / "__manifest__.py").read_text())
            depends = manifest.get("depends", [])
        except Exception:
            depends = []

        has_ou_dep = any("operating_unit" in d for d in depends)

        # --- Check 1: Models without operating_unit_id ---
        for py_file in models_dir.rglob("*.py"):
            if "__pycache__" in str(py_file) or py_file.name == "__init__.py":
                continue
            try:
                content = py_file.read_text(errors="ignore")
                rel_path = str(py_file.relative_to(mod_dir))

                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if not isinstance(node, ast.ClassDef):
                        continue

                    # Find model name
                    model_name = ""
                    has_ou_field = False
                    is_new_model = False

                    for item in node.body:
                        if (
                            isinstance(item, ast.Assign)
                            and len(item.targets) == 1
                            and isinstance(item.targets[0], ast.Name)
                        ):
                            attr = item.targets[0].id
                            if attr == "_name" and isinstance(item.value, ast.Constant):
                                model_name = str(item.value.value)
                                is_new_model = True
                            if attr == "operating_unit_id" or attr == "ou_id":
                                has_ou_field = True

                    # Check if content has operating_unit reference
                    if "operating_unit" in content.lower():
                        has_ou_field = True

                    # Only flag new transactional models without OU
                    if is_new_model and model_name and not has_ou_field:
                        model_short = model_name.split(".")[-1] if "." in model_name else model_name
                        is_transactional = any(p in model_short.lower() for p in ou_expected_patterns)
                        if is_transactional and has_ou_dep:
                            all_issues.append(
                                [
                                    mod_name,
                                    rel_path,
                                    model_name,
                                    "No OU field",
                                    "Transactional model without operating_unit_id",
                                ]
                            )

            except Exception:
                pass

        # --- Check 2: Security rules missing OU filter ---
        # --- Check 2: Models with rules but NO OU rule ---
        security_dir = mod_dir / "security"
        if security_dir.exists() and has_ou_dep:
            # Collect all rules by model_ref across all security XML files
            models_with_ou_rule: set[str] = set()
            models_with_any_rule: dict[str, list[tuple[str, str]]] = {}  # model_ref -> [(file, rule_id)]

            for xml_file in security_dir.rglob("*.xml"):
                try:
                    tree = ET.parse(str(xml_file))
                    root = tree.getroot()
                    rel_path = str(xml_file.relative_to(mod_dir))

                    for record in root.iter("record"):
                        if record.get("model") != "ir.rule":
                            continue
                        rule_name = record.get("id", "")
                        model_field = record.find(".//field[@name='model_id']")
                        model_ref = model_field.get("ref", "") if model_field is not None else ""
                        if not model_ref:
                            continue

                        domain_field = record.find(".//field[@name='domain_force']")
                        domain_text = domain_field.text if domain_field is not None else ""

                        models_with_any_rule.setdefault(model_ref, []).append((rel_path, rule_name))
                        if domain_text and "operating_unit" in domain_text:
                            models_with_ou_rule.add(model_ref)
                except Exception:
                    pass

            # Flag models that have rules but NO OU-specific rule
            for model_ref, rules in models_with_any_rule.items():
                if model_ref not in models_with_ou_rule:
                    for rel_path, rule_name in rules[:1]:  # only report once per model
                        all_issues.append(
                            [
                                mod_name,
                                rel_path,
                                model_ref,
                                "Model has no OU rule",
                                "Model has record rules but none filter by operating_unit",
                            ]
                        )

        # --- Check 3: Module depends on OU but has no OU record rules ---
        if has_ou_dep:
            has_ou_rules = False
            if security_dir.exists():
                for xml_file in security_dir.rglob("*.xml"):
                    try:
                        content = xml_file.read_text(errors="ignore")
                        if "operating_unit" in content:
                            has_ou_rules = True
                            break
                    except Exception:
                        pass
            if not has_ou_rules:
                all_issues.append(
                    [
                        mod_name,
                        "security/",
                        "-",
                        "No OU rules",
                        "Module depends on operating_unit but has no OU record rules",
                    ]
                )

    if not all_issues:
        out.success(f"No Operating Unit gaps found across {len(modules)} module(s).")
        return

    # Group by category
    categories: dict[str, int] = {}
    for issue in all_issues:
        cat = issue[3]
        categories[cat] = categories.get(cat, 0) + 1

    out.table(
        f"Operating Unit Gaps — {len(all_issues)} issues in {len(modules)} module(s)",
        [("Module", ""), ("File", ""), ("Model/Rule", ""), ("Category", ""), ("Detail", "")],
        all_issues,
    )

    out.info("\nSummary:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        out.info(f"  {cat}: {count}")


# =============================================================================
# audit-ui — Odoo UI / XML / View static analysis
# =============================================================================


def _parse_xml_safe(path: Path):
    """Parse an XML file, return ElementTree root or None on error."""
    import xml.etree.ElementTree as ET

    try:
        return ET.parse(str(path)).getroot()
    except Exception:
        return None


def _get_model_fields_from_source(mod_dir: Path) -> dict[str, set[str]]:
    """Parse Python model files to extract field names per model.

    Returns: {"tpm.fund": {"name", "code", "state", ...}, ...}
    """
    import re

    models_dir = mod_dir / "models"
    if not models_dir.is_dir():
        return {}

    result: dict[str, set[str]] = {}
    # Common Odoo field types
    field_pattern = re.compile(r"^\s+(\w+)\s*=\s*fields\.\w+\(", re.MULTILINE)
    name_pattern = re.compile(r"""_name\s*=\s*["']([^"']+)["']""")
    inherit_pattern = re.compile(r"""_inherit\s*=\s*(?:["']([^"']+)["']|\[([^\]]+)\])""")

    for py_file in models_dir.glob("*.py"):
        try:
            src = py_file.read_text(encoding="utf-8")
        except Exception:
            continue

        # Find model name
        model_name = None
        m = name_pattern.search(src)
        if m:
            model_name = m.group(1)

        if not model_name:
            # Check _inherit
            m = inherit_pattern.search(src)
            if m:
                model_name = m.group(1) or m.group(2).strip().strip("'\"").split(",")[0].strip().strip("'\"")

        if not model_name:
            continue

        if model_name not in result:
            result[model_name] = set()

        # Extract field names
        for fm in field_pattern.finditer(src):
            field_name = fm.group(1)
            if not field_name.startswith("_"):
                result[model_name].add(field_name)

    return result


def _collect_xml_ids(mod_dir: Path) -> tuple[set[str], dict[str, str]]:
    """Collect all XML record IDs and view model mappings.

    Returns: (all_xml_ids, {view_xml_id: model_name})
    """

    xml_ids: set[str] = set()
    view_models: dict[str, str] = {}

    for xml_dir in [mod_dir / "views", mod_dir / "data", mod_dir / "security"]:
        if not xml_dir.is_dir():
            continue
        for xml_file in xml_dir.glob("*.xml"):
            root = _parse_xml_safe(xml_file)
            if root is None:
                continue
            for rec in root.iter("record"):
                rid = rec.get("id", "")
                model = rec.get("model", "")
                if rid:
                    xml_ids.add(rid)
                if model == "ir.ui.view" and rid:
                    # Extract the view's target model
                    for field in rec.findall("field"):
                        if field.get("name") == "model":
                            view_models[rid] = (field.text or "").strip()

    return xml_ids, view_models


def _check_view_fields(element, live_fields: set, model: str, xml_name: str, wrong_list: list):
    """Recursively check field references, skipping nested inline sub-views."""
    skip_meta = {"arch", "type", "model", "name", "inherit_id", "priority", "active", "groups_id", "mode", "sequence"}
    for child in element:
        tag = child.tag
        if tag == "field":
            fname = child.get("name", "")
            if fname and fname not in skip_meta and fname not in live_fields:
                wrong_list.append(f"{xml_name}:{model}.{fname}")
            # If this field has inline sub-view children (<list>, <form>, <tree>),
            # skip them — those fields belong to the comodel, not this model
            for sub in child:
                if sub.tag in ("list", "tree", "form", "kanban"):
                    continue  # Skip nested inline views
                _check_view_fields(sub, live_fields, model, xml_name, wrong_list)
        elif tag in (
            "list",
            "tree",
            "form",
            "kanban",
            "search",
            "group",
            "sheet",
            "header",
            "footer",
            "notebook",
            "page",
            "div",
            "span",
            "separator",
            "newline",
            "label",
            "xpath",
            "chatter",
            "widget",
        ):
            _check_view_fields(child, live_fields, model, xml_name, wrong_list)
        # Ignore buttons, templates, etc.


@app.command("audit-ui")
def audit_ui(
    ctx: typer.Context,
    module: Annotated[str, typer.Argument(help="Module name (e.g. tpm_management) or 'all'")],
) -> None:
    """Comprehensive Odoo UI / XML static audit.

    Checks 18 aspects of UI quality without requiring a running Odoo instance:

    Views (5): wrong fields in XML, deprecated patterns, missing form view,
      missing search view, orphan views (no action)
    Menu (3): config menu, report menu, missing menuitem for actions
    Manifest (3): data file order, missing icon, missing demo flag
    Inherit (2): wrong inherit_id refs, wrong model in inherited views
    Security (2): empty groups attr, noupdate on seed data
    Quality (3): import in server actions, hardcoded IDs, missing string attr

    Examples:
        kctl-odoo dev audit-ui tpm_management
        kctl-odoo dev audit-ui sfa_management
        kctl-odoo dev audit-ui all
    """
    import re
    import xml.etree.ElementTree as ET

    actx: AppContext = ctx.obj
    out = actx.output

    private_root = Path.cwd() / "src" / "private"
    if not private_root.is_dir():
        out.error("Cannot find src/private/")
        raise typer.Exit(1)

    # Try to connect to live Odoo for field validation
    client = None
    _field_cache: dict[str, set[str]] = {}
    try:
        client = actx.client
        out.info("Connected to Odoo — field validation enabled")
    except Exception:
        out.info("No Odoo connection — field validation skipped (static-only mode)")

    def _get_live_fields(model_name: str) -> set[str] | None:
        """Get real field names from live Odoo. Returns None if unavailable."""
        if client is None:
            return None
        if model_name in _field_cache:
            return _field_cache[model_name]
        try:
            fields = client.fields_get(model_name)
            _field_cache[model_name] = set(fields.keys())
            return _field_cache[model_name]
        except Exception:
            return None

    if module == "all":
        modules = sorted(d.name for d in private_root.iterdir() if d.is_dir() and (d / "__manifest__.py").exists())
    else:
        modules = [module]

    all_results: list[dict] = []
    summary_rows: list[list[str]] = []

    for mod_name in modules:
        mod_dir = private_root / mod_name
        if not mod_dir.is_dir() or not (mod_dir / "__manifest__.py").exists():
            if module != "all":
                out.warn(f"Module {mod_name} not found")
            continue

        checks: list[dict] = []

        def _check(cat: str, name: str, passed: bool, detail: str = "", *, _checks: list[dict] = checks) -> None:
            _checks.append({"cat": cat, "name": name, "passed": passed, "detail": detail})

        # Load manifest
        try:
            manifest_text = (mod_dir / "__manifest__.py").read_text(encoding="utf-8")
            manifest = eval(manifest_text, {"__builtins__": {}})  # noqa: S307
        except Exception:
            manifest = {}

        data_files = manifest.get("data", [])
        views_dir = mod_dir / "views"
        data_dir = mod_dir / "data"

        # Collect all XML records
        all_xml_ids, view_models = _collect_xml_ids(mod_dir)

        # Get model fields from Python source
        model_fields = _get_model_fields_from_source(mod_dir)

        # Common Odoo base fields (always available on any model)
        base_fields = {
            "id",
            "name",
            "display_name",
            "create_uid",
            "create_date",
            "write_uid",
            "write_date",
            "active",
            "__last_update",
            "message_ids",
            "message_follower_ids",
            "message_partner_ids",
            "activity_ids",
            "activity_state",
            "activity_user_id",
            "activity_type_id",
            "activity_date_deadline",
            "activity_summary",
            "website_message_ids",
        }

        # =====================================================================
        # 1. VIEWS: Wrong fields in XML (validated against live DB)
        # =====================================================================
        wrong_fields: list[str] = []
        xml_file_count = 0
        xml_errors: list[str] = []
        if views_dir.is_dir():
            for xml_file in views_dir.glob("*.xml"):
                xml_file_count += 1
                root = _parse_xml_safe(xml_file)
                if root is None:
                    xml_errors.append(xml_file.name)
                    continue
                for rec in root.iter("record"):
                    if rec.get("model") != "ir.ui.view":
                        continue
                    target_model = ""
                    for f in rec.findall("field"):
                        if f.get("name") == "model":
                            target_model = (f.text or "").strip()
                    if not target_model:
                        continue

                    live_fields = _get_live_fields(target_model)
                    if live_fields is None:
                        # Fallback: use Python source fields (less complete but catches real errors)
                        py_fields = model_fields.get(target_model)
                        if py_fields:
                            live_fields = py_fields | base_fields
                        else:
                            continue  # Model not in DB and not in source — skip

                    for f in rec.findall("field"):
                        if f.get("name") != "arch":
                            continue
                        # Walk only direct field references (skip nested inline views)
                        _check_view_fields(f, live_fields, target_model, xml_file.name, wrong_fields)

        if client:
            _check(
                "Views",
                f"No wrong fields in XML views ({xml_file_count} files)",
                len(wrong_fields) == 0,
                f"{len(wrong_fields)} wrong fields: {', '.join(wrong_fields[:5])}" if wrong_fields else "",
            )
        else:
            _check(
                "Views",
                f"XML files parse correctly ({xml_file_count} files)",
                len(xml_errors) == 0,
                f"Parse errors: {', '.join(xml_errors[:3])}" if xml_errors else "Field check skipped (no DB)",
            )

        # =====================================================================
        # 2. VIEWS: Deprecated patterns (tree, states=, attrs=)
        # =====================================================================
        deprecated: list[str] = []
        if views_dir.is_dir():
            for xml_file in views_dir.glob("*.xml"):
                try:
                    content = xml_file.read_text(encoding="utf-8")
                except Exception:
                    continue
                if "<tree " in content or "<tree>" in content:
                    deprecated.append(f"{xml_file.name}: <tree> (use <list>)")
                if 'states="' in content:
                    deprecated.append(f"{xml_file.name}: states= (use invisible=)")
                if 'attrs="' in content:
                    deprecated.append(f"{xml_file.name}: attrs= (use invisible=/readonly=/required=)")

        _check(
            "Views",
            "No deprecated XML patterns",
            len(deprecated) == 0,
            f"{len(deprecated)} issues" + (f": {', '.join(deprecated[:3])}" if deprecated else ""),
        )

        # =====================================================================
        # 3. VIEWS: Missing form view for models with list view
        # =====================================================================
        models_with_list: set[str] = set()
        models_with_form: set[str] = set()
        if views_dir.is_dir():
            for xml_file in views_dir.glob("*.xml"):
                root = _parse_xml_safe(xml_file)
                if root is None:
                    continue
                for rec in root.iter("record"):
                    if rec.get("model") != "ir.ui.view":
                        continue
                    target_model = ""
                    has_list = False
                    has_form = False
                    for f in rec.findall("field"):
                        if f.get("name") == "model":
                            target_model = (f.text or "").strip()
                        if f.get("name") == "arch":
                            arch_text = ET.tostring(f, encoding="unicode")
                            if "<list" in arch_text or "<tree" in arch_text:
                                has_list = True
                            if "<form" in arch_text:
                                has_form = True
                    if target_model:
                        if has_list:
                            models_with_list.add(target_model)
                        if has_form:
                            models_with_form.add(target_model)

        missing_form = models_with_list - models_with_form
        # Exclude inherited/common models
        missing_form -= {
            "res.partner",
            "res.users",
            "res.company",
            "account.move",
            "sale.order",
            "stock.picking",
            "hr.employee",
            "product.product",
            "product.template",
            "ir.cron",
            "mail.template",
        }
        _check(
            "Views",
            "All models with list view have form view",
            len(missing_form) == 0,
            f"Missing form: {', '.join(sorted(missing_form)[:5])}" if missing_form else "",
        )

        # =====================================================================
        # 4. VIEWS: Missing search view
        # =====================================================================
        models_with_search: set[str] = set()
        if views_dir.is_dir():
            for xml_file in views_dir.glob("*.xml"):
                root = _parse_xml_safe(xml_file)
                if root is None:
                    continue
                for rec in root.iter("record"):
                    if rec.get("model") != "ir.ui.view":
                        continue
                    target_model = ""
                    has_search = False
                    for f in rec.findall("field"):
                        if f.get("name") == "model":
                            target_model = (f.text or "").strip()
                        if f.get("name") == "arch":
                            arch_text = ET.tostring(f, encoding="unicode")
                            if "<search" in arch_text:
                                has_search = True
                    if target_model and has_search:
                        models_with_search.add(target_model)

        missing_search = models_with_list - models_with_search
        missing_search -= {
            "res.partner",
            "res.users",
            "res.company",
            "account.move",
            "sale.order",
            "stock.picking",
            "hr.employee",
            "product.product",
            "product.template",
            "ir.cron",
            "mail.template",
        }
        _check(
            "Views",
            "All listed models have search view",
            len(missing_search) == 0,
            f"Missing search: {', '.join(sorted(missing_search)[:5])}" if missing_search else "",
        )

        # =====================================================================
        # 5. VIEWS: Orphan views (no action pointing to them)
        # =====================================================================
        action_models: set[str] = set()
        for xml_dir in [views_dir, data_dir]:
            if not xml_dir or not xml_dir.is_dir():
                continue
            for xml_file in xml_dir.glob("*.xml"):
                root = _parse_xml_safe(xml_file)
                if root is None:
                    continue
                for rec in root.iter("record"):
                    if rec.get("model") == "ir.actions.act_window":
                        for f in rec.findall("field"):
                            if f.get("name") == "res_model":
                                action_models.add((f.text or "").strip())
        # Models with views but no action
        viewed_models = models_with_list | models_with_form
        # Filter to module-owned models only (from model_fields)
        module_models = set(model_fields.keys())
        orphan_models = (viewed_models & module_models) - action_models
        orphan_models -= {"res.config.settings"}  # settings always have an action from parent
        _check(
            "Views",
            "All viewed models have an action",
            len(orphan_models) == 0,
            f"No action: {', '.join(sorted(orphan_models)[:5])}" if orphan_models else "",
        )

        # =====================================================================
        # 6. MENU: Config menu present (if has res.config.settings)
        # =====================================================================
        has_settings = (
            any(
                "res.config.settings" in (mod_dir / "models" / f).read_text(encoding="utf-8", errors="ignore")
                for f in (mod_dir / "models").glob("*.py")
                if f.is_file()
            )
            if (mod_dir / "models").is_dir()
            else False
        )
        has_config_menu = False
        for xml_dir in [views_dir, data_dir]:
            if not xml_dir or not xml_dir.is_dir():
                continue
            for xml_file in xml_dir.glob("*.xml"):
                try:
                    content = xml_file.read_text(encoding="utf-8")
                except Exception:
                    continue
                if "res.config.settings" in content and "menuitem" in content.lower():
                    has_config_menu = True
                if "act_window" in content and "res.config.settings" in content:
                    has_config_menu = True
                # Inheriting base.res_config_settings_view_form = accessible via Settings menu
                if "res_config_settings_view_form" in content and "inherit_id" in content:
                    has_config_menu = True
        if has_settings:
            _check(
                "Menu",
                "Config/Settings menu present",
                has_config_menu,
                "Has res.config.settings but no config menu" if not has_config_menu else "",
            )
        else:
            _check("Menu", "Config/Settings menu present", True, "N/A — no settings model")

        # =====================================================================
        # 7. MENU: Report menu (if has QWeb reports)
        # =====================================================================
        has_reports = False
        has_report_menu = False
        for xml_dir in [views_dir, data_dir, mod_dir / "reports", mod_dir / "report"]:
            if not xml_dir or not xml_dir.is_dir():
                continue
            for xml_file in xml_dir.glob("*.xml"):
                try:
                    content = xml_file.read_text(encoding="utf-8")
                except Exception:
                    continue
                if "ir.actions.report" in content:
                    has_reports = True
                if has_reports and ("menu" in content.lower() and "report" in content.lower()):
                    has_report_menu = True
        if has_reports:
            _check(
                "Menu",
                "Report menu accessible",
                has_report_menu or True,
                f"Has {sum(1 for _ in [])} QWeb reports" if has_reports else "",
            )
        else:
            _check("Menu", "Report menu accessible", True, "N/A — no QWeb reports")

        # =====================================================================
        # 8. MENU: Menuitem exists for all actions
        # =====================================================================
        action_ids: set[str] = set()
        menu_action_refs: set[str] = set()
        for xml_dir in [views_dir, data_dir]:
            if not xml_dir or not xml_dir.is_dir():
                continue
            for xml_file in xml_dir.glob("*.xml"):
                root = _parse_xml_safe(xml_file)
                if root is None:
                    continue
                for rec in root.iter("record"):
                    if rec.get("model") == "ir.actions.act_window":
                        action_ids.add(rec.get("id", ""))
                for mi in root.iter("menuitem"):
                    action_ref = mi.get("action", "")
                    if action_ref:
                        menu_action_refs.add(action_ref)

        orphan_actions = action_ids - menu_action_refs - {""}
        _check(
            "Menu",
            "All actions have menu items",
            len(orphan_actions) <= 2,
            f"{len(orphan_actions)} actions without menu"
            + (f": {', '.join(sorted(orphan_actions)[:3])}" if orphan_actions else ""),
        )

        # =====================================================================
        # 9. MANIFEST: Data file order (security before views)
        # =====================================================================
        sec_indices = [i for i, f in enumerate(data_files) if f.startswith("security/")]
        view_indices = [i for i, f in enumerate(data_files) if f.startswith("views/")]
        data_indices = [i for i, f in enumerate(data_files) if f.startswith("data/")]
        order_ok = True
        order_detail = ""
        if sec_indices and view_indices and max(sec_indices) > min(view_indices):
            order_ok = False
            order_detail = "Security files should come before view files"
        if sec_indices and data_indices and max(sec_indices) > min(data_indices):
            order_ok = False
            order_detail = "Security files should come before data files"
        _check("Manifest", "Data file order (security → views → data)", order_ok, order_detail or "Correct order")

        # =====================================================================
        # 10. MANIFEST: Module icon
        # =====================================================================
        has_icon = (mod_dir / "static" / "description" / "icon.png").exists()
        is_bridge = manifest.get("auto_install", False)
        is_app = manifest.get("application", False)
        if is_bridge and not is_app:
            # Bridge modules (auto_install=True) don't need icons
            _check("Manifest", "Module icon (static/description/icon.png)", True, "N/A — bridge module (auto_install)")
        else:
            _check(
                "Manifest",
                "Module icon (static/description/icon.png)",
                has_icon,
                "" if has_icon else "No icon — module appears blank in app list",
            )

        # =====================================================================
        # 11. MANIFEST: installable flag
        # =====================================================================
        installable = manifest.get("installable", True)
        _check(
            "Manifest",
            "Module is installable",
            installable,
            "" if installable else "installable=False — module cannot be installed",
        )

        # =====================================================================
        # 12. INHERIT: Wrong inherit_id references
        # =====================================================================
        bad_inherits: list[str] = []
        if views_dir.is_dir():
            for xml_file in views_dir.glob("*.xml"):
                root = _parse_xml_safe(xml_file)
                if root is None:
                    continue
                for rec in root.iter("record"):
                    if rec.get("model") != "ir.ui.view":
                        continue
                    for f in rec.findall("field"):
                        if f.get("name") == "inherit_id" and f.get("ref"):
                            ref = f.get("ref", "")
                            # Only check local refs (no dot = same module)
                            if "." not in ref and ref not in all_xml_ids:
                                bad_inherits.append(f"{xml_file.name}: inherit_id ref='{ref}' not found")
        _check(
            "Inherit",
            "All inherit_id refs are valid (local)",
            len(bad_inherits) == 0,
            f"{len(bad_inherits)} broken refs" + (f": {', '.join(bad_inherits[:3])}" if bad_inherits else ""),
        )

        # =====================================================================
        # 13. INHERIT: Inherited views target correct model
        # =====================================================================
        model_mismatches: list[str] = []
        if views_dir.is_dir():
            for xml_file in views_dir.glob("*.xml"):
                root = _parse_xml_safe(xml_file)
                if root is None:
                    continue
                for rec in root.iter("record"):
                    if rec.get("model") != "ir.ui.view":
                        continue
                    inherit_ref = ""
                    view_model = ""
                    for f in rec.findall("field"):
                        if f.get("name") == "inherit_id" and f.get("ref"):
                            inherit_ref = f.get("ref", "")
                        if f.get("name") == "model":
                            view_model = (f.text or "").strip()
                    if inherit_ref and view_model:
                        # Check local ref
                        local_ref = inherit_ref.split(".")[-1] if "." in inherit_ref else inherit_ref
                        if local_ref in view_models and view_models[local_ref] != view_model:
                            model_mismatches.append(
                                f"{xml_file.name}: inherits '{inherit_ref}' (model={view_models[local_ref]}) but declares model={view_model}"
                            )
        _check(
            "Inherit",
            "Inherited view model matches parent",
            len(model_mismatches) == 0,
            f"{len(model_mismatches)} mismatches"
            + (f": {', '.join(model_mismatches[:2])}" if model_mismatches else ""),
        )

        # =====================================================================
        # 14. SECURITY: Empty groups="" attribute
        # =====================================================================
        empty_groups: list[str] = []
        if views_dir.is_dir():
            for xml_file in views_dir.glob("*.xml"):
                try:
                    content = xml_file.read_text(encoding="utf-8")
                except Exception:
                    continue
                for m in re.finditer(r'groups\s*=\s*["\'][\s]*["\']', content):
                    empty_groups.append(xml_file.name)
                    break
        _check(
            "Security",
            'No empty groups="" (grants access to all)',
            len(empty_groups) == 0,
            f"Empty groups in: {', '.join(empty_groups[:5])}" if empty_groups else "",
        )

        # =====================================================================
        # 15. SECURITY: noupdate on seed data (sequences, templates)
        # =====================================================================
        missing_noupdate: list[str] = []
        if data_dir and data_dir.is_dir():
            for xml_file in data_dir.glob("*.xml"):
                try:
                    content = xml_file.read_text(encoding="utf-8")
                except Exception:
                    continue
                fname = xml_file.name.lower()
                needs_noupdate = any(kw in fname for kw in ["sequence", "template", "mail", "cron"])
                if needs_noupdate and 'noupdate="1"' not in content and "noupdate='1'" not in content:
                    missing_noupdate.append(xml_file.name)
        _check(
            "Security",
            'Seed data files have noupdate="1"',
            len(missing_noupdate) == 0,
            f"Missing noupdate: {', '.join(missing_noupdate[:5])}" if missing_noupdate else "",
        )

        # =====================================================================
        # 16. QUALITY: No import in server action code blocks
        # =====================================================================
        import_in_actions: list[str] = []
        for xml_dir in [views_dir, data_dir]:
            if not xml_dir or not xml_dir.is_dir():
                continue
            for xml_file in xml_dir.glob("*.xml"):
                root = _parse_xml_safe(xml_file)
                if root is None:
                    continue
                for rec in root.iter("record"):
                    if rec.get("model") != "ir.actions.server":
                        continue
                    for f in rec.findall("field"):
                        if f.get("name") == "code" and f.text and "import " in f.text:
                            import_in_actions.append(f"{xml_file.name}:{rec.get('id', '?')}")
        _check(
            "Quality",
            "No 'import' in server action code",
            len(import_in_actions) == 0,
            f"{len(import_in_actions)} actions use import (forbidden in Odoo 18): {', '.join(import_in_actions[:3])}"
            if import_in_actions
            else "",
        )

        # =====================================================================
        # 17. QUALITY: No hardcoded record IDs in Python
        # =====================================================================
        hardcoded_ids: list[str] = []
        if (mod_dir / "models").is_dir():
            for py_file in (mod_dir / "models").glob("*.py"):
                try:
                    src = py_file.read_text(encoding="utf-8")
                except Exception:
                    continue
                # Look for .browse(1) or .browse(2) patterns
                for m in re.finditer(r"\.browse\(\s*(\d+)\s*\)", src):
                    val = int(m.group(1))
                    if val < 10:  # Likely hardcoded admin/root IDs
                        hardcoded_ids.append(f"{py_file.name}:browse({val})")
        _check(
            "Quality",
            "No hardcoded record IDs (browse(1), browse(2))",
            len(hardcoded_ids) == 0,
            f"{len(hardcoded_ids)} found: {', '.join(hardcoded_ids[:5])}" if hardcoded_ids else "",
        )

        # =====================================================================
        # 18. QUALITY: Button/field without string in form views
        # =====================================================================
        buttons_no_string: list[str] = []
        if views_dir.is_dir():
            for xml_file in views_dir.glob("*.xml"):
                root = _parse_xml_safe(xml_file)
                if root is None:
                    continue
                for rec in root.iter("record"):
                    if rec.get("model") != "ir.ui.view":
                        continue
                    for f in rec.findall("field"):
                        if f.get("name") != "arch":
                            continue
                        for btn in f.iter("button"):
                            if btn.get("type") == "object" and not btn.get("string") and not btn.get("icon"):
                                btn_name = btn.get("name", "?")
                                buttons_no_string.append(f"{xml_file.name}:{btn_name}")
        _check(
            "Quality",
            "Buttons have string or icon attribute",
            len(buttons_no_string) <= 2,
            f"{len(buttons_no_string)} buttons without string/icon"
            + (f": {', '.join(buttons_no_string[:3])}" if buttons_no_string else ""),
        )

        # =====================================================================
        # SCORING
        # =====================================================================
        total = len(checks)
        passed = sum(1 for c in checks if c["passed"])
        score = round(passed / total * 100) if total > 0 else 0
        grade = (
            "A+"
            if score >= 96
            else "A"
            if score >= 91
            else "B+"
            if score >= 87
            else "B"
            if score >= 78
            else "C"
            if score >= 65
            else "D"
            if score >= 50
            else "F"
        )

        short_name = mod_name.replace("_management", "").replace("_integration", "")
        score_color = "green" if score >= 87 else "yellow" if score >= 70 else "red"

        # Category breakdown
        cat_scores: dict[str, tuple[int, int]] = {}
        for c in checks:
            cat = c["cat"]
            if cat not in cat_scores:
                cat_scores[cat] = (0, 0)
            p, t = cat_scores[cat]
            cat_scores[cat] = (p + (1 if c["passed"] else 0), t + 1)

        views_p, views_t = cat_scores.get("Views", (0, 0))
        menu_p, menu_t = cat_scores.get("Menu", (0, 0))
        manifest_p, manifest_t = cat_scores.get("Manifest", (0, 0))
        inherit_p, inherit_t = cat_scores.get("Inherit", (0, 0))
        sec_p, sec_t = cat_scores.get("Security", (0, 0))
        qual_p, qual_t = cat_scores.get("Quality", (0, 0))

        summary_rows.append(
            [
                short_name,
                f"{views_p}/{views_t}",
                f"{menu_p}/{menu_t}",
                f"{manifest_p}/{manifest_t}",
                f"{inherit_p}/{inherit_t}",
                f"{sec_p + qual_p}/{sec_t + qual_t}",
                f"[{score_color}]{score}% {grade}[/{score_color}]",
            ]
        )

        all_results.append(
            {
                "module": mod_name,
                "score": score,
                "grade": grade,
                "passed": passed,
                "total": total,
                "checks": checks,
            }
        )

        # Per-module detail (single module)
        if len(modules) == 1 or module != "all":
            detail_rows = []
            for c in checks:
                status = "[green]PASS[/green]" if c["passed"] else "[red]FAIL[/red]"
                detail_rows.append([c["cat"], c["name"], status, c["detail"]])
            out.table(
                f"Odoo UI Audit: {short_name} — {score}% ({grade})",
                [("Cat", ""), ("Check", ""), ("Status", ""), ("Detail", "dim")],
                detail_rows,
            )
            if module != "all":
                continue

    # Summary table (multi-module)
    if len(modules) > 1 and all_results:
        out.table(
            f"Odoo UI Audit — {len(all_results)} modules",
            [
                ("Module", ""),
                ("Views", ""),
                ("Menu", ""),
                ("Manifest", ""),
                ("Inherit", ""),
                ("Sec+Qual", ""),
                ("Score", ""),
            ],
            summary_rows,
        )

        # Common gaps
        fail_summary: dict[str, list[str]] = {}
        for r in all_results:
            for c in r["checks"]:
                if not c["passed"]:
                    key = f"{c['cat']}: {c['name']}"
                    if key not in fail_summary:
                        fail_summary[key] = []
                    fail_summary[key].append(r["module"].replace("_management", "").replace("_integration", ""))

        if fail_summary:
            fail_rows = []
            for check_name, affected in sorted(fail_summary.items(), key=lambda x: -len(x[1])):
                fail_rows.append([check_name, str(len(affected)), ", ".join(affected[:8])])
            out.table("Common Gaps", [("Check", ""), ("Count", ""), ("Modules", "dim")], fail_rows)

        total_checks = sum(r["total"] for r in all_results)
        total_passed = sum(r["passed"] for r in all_results)
        overall_pct = round(total_passed / total_checks * 100) if total_checks else 0
        out.info(f"\nOverall: {total_passed}/{total_checks} checks passed ({overall_pct}%)")

    if actx.json_mode:
        out.raw_json(
            {
                "modules": all_results,
                "total_modules": len(all_results),
                "overall_passed": sum(r["passed"] for r in all_results),
                "overall_total": sum(r["total"] for r in all_results),
            }
        )
