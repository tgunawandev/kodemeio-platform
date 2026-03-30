"""XML view validation and analysis commands."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

app = typer.Typer(help="XML view validation and xpath analysis.")
console = Console()


def _get_private_dir() -> Path:
    from kctl_odoo.core.utils import find_project_root

    return find_project_root() / "src" / "private"


def _iter_xml_files(module: str | None = None):
    """Yield (xml_path, module_name) for all XML files in views/ directories."""
    private_dir = _get_private_dir()
    if module:
        mod_dirs = [private_dir / module]
    else:
        mod_dirs = [d for d in private_dir.iterdir() if d.is_dir() and (d / "__manifest__.py").exists()]

    for mod_dir in mod_dirs:
        views_dir = mod_dir / "views"
        if not views_dir.exists():
            continue
        for xml_file in views_dir.glob("*.xml"):
            yield xml_file, mod_dir.name


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("validate")
def validate_views(
    module: Annotated[str | None, typer.Argument(help="Module name to validate (default: all)")] = None,
) -> None:
    """Parse all XML view files, check syntax, deprecated patterns (states=, tree vs list)."""
    files = list(_iter_xml_files(module))
    if not files:
        console.print("[yellow]No XML view files found.[/yellow]")
        raise typer.Exit(0)

    errors = 0
    warnings = 0

    for xml_path, mod_name in sorted(files, key=lambda x: (x[1], x[0].name)):
        rel = f"{mod_name}/views/{xml_path.name}"
        try:
            content = xml_path.read_text(encoding="utf-8")
        except Exception as e:
            console.print(f"  [red]E[/red] {rel}: Cannot read file: {e}")
            errors += 1
            continue

        # Parse XML
        try:
            ET.fromstring(content)
        except ET.ParseError as e:
            console.print(f"  [red]E[/red] {rel}: XML parse error: {e}")
            errors += 1
            continue

        file_ok = True

        # Check deprecated <tree> → <list>
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()

            if "<tree" in stripped and "string=" in stripped or stripped.startswith("<tree"):
                console.print(f"  [red]E[/red] {rel}:{i}: <tree> is deprecated in Odoo 18 — use <list>")
                errors += 1
                file_ok = False

            # states= attribute removed in Odoo 18
            if "states=" in stripped and not stripped.startswith("#") and not stripped.startswith("<!--"):
                console.print(f"  [red]E[/red] {rel}:{i}: states= attribute removed in Odoo 18 — use invisible=")
                errors += 1
                file_ok = False

            # Check for groups attribute with old-style comma-separated (should still work but warn)
            if 'attrs="' in stripped:
                console.print(
                    f"  [yellow]W[/yellow] {rel}:{i}: attrs= removed in Odoo 17+ — use invisible=, required=, readonly="
                )
                warnings += 1
                file_ok = False

        if file_ok:
            console.print(f"  [green]OK[/green] {rel}")

    console.print(f"\n[bold]Result:[/bold] {errors} errors, {warnings} warnings across {len(files)} files")
    if errors:
        raise typer.Exit(1)


@app.command("parse")
def parse_view(
    file: Annotated[str, typer.Argument(help="Path to XML file to parse")],
) -> None:
    """Parse a single XML file and show the element tree structure."""
    xml_path = Path(file)
    if not xml_path.exists():
        console.print(f"[red]ERROR[/red] File not found: {file}")
        raise typer.Exit(1)

    try:
        content = xml_path.read_text(encoding="utf-8")
        tree = ET.fromstring(content)
    except ET.ParseError as e:
        console.print(f"[red]ERROR[/red] XML parse error: {e}")
        raise typer.Exit(1) from e

    console.print(f"\n[bold]XML structure:[/bold] {xml_path.name}\n")

    def _print_tree(elem: ET.Element, indent: int = 0) -> None:
        prefix = "  " * indent
        attrs = ""
        if elem.attrib:
            attr_pairs = [f'{k}="{v}"' for k, v in list(elem.attrib.items())[:3]]
            if len(elem.attrib) > 3:
                attr_pairs.append(f"...+{len(elem.attrib) - 3}")
            attrs = " " + " ".join(attr_pairs)
        tag = f"[cyan]{elem.tag}[/cyan]"
        console.print(f"{prefix}<{tag}{attrs}>")
        for child in elem:
            _print_tree(child, indent + 1)

    _print_tree(tree)
    console.print("\n[green]OK[/green] Valid XML")


@app.command("xpath-test")
def xpath_test(
    ctx: typer.Context,
    view_id: Annotated[str, typer.Argument(help="View XML ID (e.g. module.view_name)")],
    xpath: Annotated[str, typer.Argument(help="XPath expression to test")],
) -> None:
    """Test an XPath expression against a view definition in running Odoo."""
    from kctl_odoo.core.callbacks import AppContext
    from kctl_odoo.core.exceptions import RPCError

    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        # Resolve XML ID to ir.ui.view record
        view_ids = c.search("ir.ui.view", [("xml_id", "=", view_id)])
        if not view_ids:
            # Try name match
            view_ids = c.search("ir.ui.view", [("name", "=", view_id)])
        if not view_ids:
            out.error(f"View not found: {view_id}")
            raise typer.Exit(1)

        views = c.read("ir.ui.view", [view_ids[0]], ["name", "model", "arch", "xml_id"])
        if not views:
            out.error("Could not read view data")
            raise typer.Exit(1)

        view = views[0]
        arch = view.get("arch", "")

        try:
            root = ET.fromstring(arch)
        except ET.ParseError as e:
            out.error(f"View arch is not valid XML: {e}")
            raise typer.Exit(1) from e

        matches = root.findall(xpath)
        console.print(f"\n[bold]XPath test:[/bold] {xpath}")
        console.print(f"[dim]View:[/dim] {view.get('name')} ({view.get('model')})\n")

        if not matches:
            console.print("[yellow]No elements matched.[/yellow]")
        else:
            console.print(f"[green]{len(matches)} element(s) matched:[/green]\n")
            for elem in matches:
                tag = elem.tag
                attrs = dict(elem.attrib)
                console.print(f"  <[cyan]{tag}[/cyan] {attrs}>")

    except RPCError as e:
        out.error(f"RPC error: {e.detail}")
        raise typer.Exit(1) from e


@app.command("inheritance")
def view_inheritance(
    ctx: typer.Context,
    view_id: Annotated[str, typer.Argument(help="View XML ID or name")],
) -> None:
    """Show the inheritance chain for a view from ir.ui.view."""
    from kctl_odoo.core.callbacks import AppContext
    from kctl_odoo.core.exceptions import RPCError

    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        # Find view
        views = c.search_read(
            "ir.ui.view",
            domain=["|", ("name", "=", view_id), ("key", "=", view_id)],
            fields=["id", "name", "model", "inherit_id", "mode", "priority", "active", "xml_id"],
            limit=1,
        )
        if not views:
            out.error(f"View not found: {view_id}")
            raise typer.Exit(1)

        root_view = views[0]

        # Get all views that inherit from this view (recursively)
        all_views = c.search_read(
            "ir.ui.view",
            domain=[("model", "=", root_view.get("model", ""))],
            fields=["id", "name", "inherit_id", "mode", "priority", "active", "xml_id"],
            limit=200,
        )

        by_id = {v["id"]: v for v in all_views}

        # Build tree
        def _find_root(view):
            inh = view.get("inherit_id")
            if inh and isinstance(inh, list) and inh[0] in by_id:
                return _find_root(by_id[inh[0]])
            return view

        def _children(vid):
            return [v for v in all_views if isinstance(v.get("inherit_id"), list) and v["inherit_id"][0] == vid]

        def _print_chain(view, indent=0):
            prefix = "  " * indent
            active = "" if view.get("active", True) else " [dim](inactive)[/dim]"
            mode = f" [{view.get('mode', '')}]" if view.get("mode") != "primary" else ""
            prio = f" prio={view.get('priority', 16)}"
            xid = f" ({view.get('xml_id', '')})" if view.get("xml_id") else ""
            console.print(f"{prefix}[cyan]{view.get('name', '')}[/cyan]{xid}{mode}{prio}{active}")
            for child in sorted(_children(view["id"]), key=lambda v: v.get("priority", 16)):
                _print_chain(child, indent + 1)

        top = _find_root(root_view)
        console.print(f"\n[bold]Inheritance chain for:[/bold] {view_id}\n")
        _print_chain(top)

    except RPCError as e:
        out.error(f"RPC error: {e.detail}")
        raise typer.Exit(1) from e


@app.command("duplicates")
def find_duplicates() -> None:
    """Find duplicate view IDs (record id=) across all private modules."""
    _get_private_dir()
    id_locations: dict[str, list[str]] = defaultdict(list)

    for xml_path, mod_name in _iter_xml_files():
        try:
            content = xml_path.read_text(encoding="utf-8")
            root = ET.fromstring(content)
        except Exception:
            continue

        for elem in root.iter():
            record_id = elem.get("id")
            if record_id:
                loc = f"{mod_name}/views/{xml_path.name}"
                id_locations[record_id].append(loc)

    duplicates = {k: v for k, v in id_locations.items() if len(v) > 1}

    if not duplicates:
        console.print("[green]No duplicate view IDs found.[/green]")
        return

    console.print(f"\n[bold]Duplicate IDs found:[/bold] {len(duplicates)}\n")
    for record_id, locations in sorted(duplicates.items()):
        console.print(f"  [red]{record_id}[/red]")
        for loc in locations:
            console.print(f"    - {loc}")

    raise typer.Exit(1)


@app.command("render")
def render_template(
    ctx: typer.Context,
    template: Annotated[str, typer.Argument(help="QWeb template XML ID or name")],
) -> None:
    """Show QWeb template structure from running Odoo."""
    from kctl_odoo.core.callbacks import AppContext
    from kctl_odoo.core.exceptions import RPCError

    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        views = c.search_read(
            "ir.ui.view",
            domain=["|", ("key", "=", template), ("name", "=", template)],
            fields=["id", "name", "key", "arch", "type"],
            limit=1,
        )
        if not views:
            out.error(f"Template not found: {template}")
            raise typer.Exit(1)

        view = views[0]
        arch = view.get("arch", "")

        console.print(f"\n[bold]Template:[/bold] {view.get('key') or view.get('name')}")
        console.print(f"[dim]Type:[/dim] {view.get('type', 'qweb')}\n")
        console.print(arch[:4000])

        if len(arch) > 4000:
            console.print(f"\n[dim]... ({len(arch) - 4000} more characters)[/dim]")

    except RPCError as e:
        out.error(f"RPC error: {e.detail}")
        raise typer.Exit(1) from e
