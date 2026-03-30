"""PO file management and translation coverage commands."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Manage PO translation files for Odoo modules.")
console = Console()


def _get_private_dir() -> Path:
    from kctl_odoo.core.utils import find_project_root

    return find_project_root() / "src" / "private"


def _iter_po_files(module: str | None = None):
    """Yield (po_path, module_name, lang) for all PO files."""
    private_dir = _get_private_dir()
    if module:
        mod_dirs = [private_dir / module]
    else:
        mod_dirs = [d for d in private_dir.iterdir() if d.is_dir() and (d / "__manifest__.py").exists()]

    for mod_dir in mod_dirs:
        i18n_dir = mod_dir / "i18n"
        if not i18n_dir.exists():
            continue
        for po_file in i18n_dir.glob("*.po"):
            lang = po_file.stem
            yield po_file, mod_dir.name, lang


def _parse_po(po_path: Path) -> list[dict]:
    """Parse a PO file and return list of {msgid, msgstr, fuzzy} dicts."""
    entries = []
    try:
        content = po_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return entries

    current: dict = {}
    fuzzy = False

    for line in content.splitlines():
        line = line.rstrip()
        if line.startswith("#,") and "fuzzy" in line:
            fuzzy = True
        elif line.startswith("msgid "):
            m = re.match(r'msgid "(.*)"', line)
            if m:
                current = {"msgid": m.group(1), "msgstr": "", "fuzzy": fuzzy}
                fuzzy = False
        elif line.startswith("msgstr ") and current:
            m = re.match(r'msgstr "(.*)"', line)
            if m:
                current["msgstr"] = m.group(1)
                if current["msgid"]:  # Skip header entry (empty msgid)
                    entries.append(current)
                current = {}

    return entries


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("coverage")
def translation_coverage(
    module: Annotated[str | None, typer.Argument(help="Module name (default: all)")] = None,
) -> None:
    """Show translation coverage per module per language."""
    # Collect data: {module: {lang: (translated, total)}}
    coverage: dict[str, dict[str, tuple[int, int]]] = {}

    for po_path, mod_name, lang in _iter_po_files(module):
        entries = _parse_po(po_path)
        total = len(entries)
        translated = sum(1 for e in entries if e["msgstr"].strip())
        coverage.setdefault(mod_name, {})[lang] = (translated, total)

    if not coverage:
        console.print("[yellow]No PO files found.[/yellow]")
        return

    table = Table(title="Translation Coverage", show_header=True)
    table.add_column("Module", style="cyan")
    table.add_column("Language")
    table.add_column("Translated", justify="right")
    table.add_column("Total", justify="right")
    table.add_column("Coverage")
    table.add_column("Status")

    for mod_name in sorted(coverage.keys()):
        for lang in sorted(coverage[mod_name].keys()):
            translated, total = coverage[mod_name][lang]
            pct = 0 if total == 0 else int(translated / total * 100)
            bar = f"[{'green' if pct >= 80 else 'yellow' if pct >= 50 else 'red'}]{pct}%[/]"
            status = "[green]OK[/green]" if pct >= 80 else "[yellow]partial[/yellow]" if pct >= 50 else "[red]low[/red]"
            table.add_row(mod_name, lang, str(translated), str(total), bar, status)

    console.print(table)


@app.command("validate")
def validate_po(
    module: Annotated[str | None, typer.Argument(help="Module name (default: all)")] = None,
) -> None:
    """Validate PO syntax and format string consistency."""
    errors = 0
    files_checked = 0

    for po_path, mod_name, _lang in _iter_po_files(module):
        files_checked += 1
        rel = f"{mod_name}/i18n/{po_path.name}"
        file_ok = True

        try:
            content = po_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            console.print(f"  [red]E[/red] {rel}: Cannot read: {e}")
            errors += 1
            continue

        # Check encoding declaration
        if "Content-Type" in content and "charset=UTF-8" not in content and "charset=utf-8" not in content:
            console.print(f"  [yellow]W[/yellow] {rel}: Non-UTF-8 charset declared")
            file_ok = False

        # Check format string consistency (%s, %d, %(name)s)
        entries = _parse_po(po_path)
        for entry in entries:
            if not entry["msgstr"]:
                continue
            src_fmts = set(re.findall(r"%(?:\(\w+\))?[sdfrg%]", entry["msgid"]))
            tgt_fmts = set(re.findall(r"%(?:\(\w+\))?[sdfrg%]", entry["msgstr"]))
            if src_fmts != tgt_fmts:
                console.print(f"  [yellow]W[/yellow] {rel}: Format string mismatch: '{entry['msgid'][:40]}...'")
                console.print(f"    source: {src_fmts}, translation: {tgt_fmts}")
                errors += 1
                file_ok = False

        if file_ok:
            console.print(f"  [green]OK[/green] {rel}")

    console.print(f"\n[bold]Checked {files_checked} PO files, {errors} issues.[/bold]")
    if errors:
        raise typer.Exit(1)


@app.command("missing")
def show_missing(
    module: Annotated[str | None, typer.Argument(help="Module name (default: all)")] = None,
    lang: Annotated[str | None, typer.Option("--lang", help="Language code to check (e.g. id_ID)")] = None,
) -> None:
    """Show untranslated strings in PO files."""
    total_missing = 0

    for po_path, mod_name, po_lang in _iter_po_files(module):
        if lang and po_lang != lang:
            continue

        entries = _parse_po(po_path)
        missing = [e for e in entries if not e["msgstr"].strip() and not e.get("fuzzy")]

        if missing:
            total_missing += len(missing)
            console.print(f"\n[bold]{mod_name}/{po_lang}[/bold] — {len(missing)} untranslated:")
            for entry in missing[:20]:
                console.print(f'  [dim]msgid[/dim] "{entry["msgid"][:80]}"')
            if len(missing) > 20:
                console.print(f"  [dim]... and {len(missing) - 20} more[/dim]")

    if total_missing == 0:
        console.print("[green]All strings translated.[/green]")
    else:
        console.print(f"\n[bold]Total missing translations: {total_missing}[/bold]")


@app.command("export-all")
def export_all(
    ctx: typer.Context,
    lang: Annotated[str, typer.Option("--lang", help="Language code to export (e.g. id_ID)")] = "id_ID",
    output_dir: Annotated[str | None, typer.Option("--output-dir", "-o", help="Output directory")] = None,
) -> None:
    """Batch export PO files for all installed private modules via Odoo."""
    import base64

    from kctl_odoo.core.callbacks import AppContext
    from kctl_odoo.core.exceptions import RPCError

    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    private_dir = _get_private_dir()
    modules = [d.name for d in private_dir.iterdir() if d.is_dir() and (d / "__manifest__.py").exists()]

    out_path = Path(output_dir) if output_dir else private_dir
    exported = 0
    failed = 0

    for mod_name in sorted(modules):
        try:
            mod_ids = c.search("ir.module.module", [("name", "=", mod_name), ("state", "=", "installed")])
            if not mod_ids:
                continue

            wizard_id = c.create(
                "base.language.export",
                {
                    "lang": lang,
                    "format": "po",
                    "modules": [(6, 0, mod_ids)],
                },
            )
            c.execute_kw("base.language.export", "act_getfile", [[wizard_id]])
            wizard_data = c.read("base.language.export", [wizard_id], ["data", "name"])
            if wizard_data and wizard_data[0].get("data"):
                file_data = base64.b64decode(wizard_data[0]["data"])
                dest = out_path / mod_name / "i18n" / f"{lang}.po"
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(file_data)
                out.info(f"Exported {mod_name}/{lang}.po ({len(file_data)} bytes)")
                exported += 1
        except (RPCError, Exception) as e:
            out.info(f"Skipped {mod_name}: {e}")
            failed += 1

    out.info(f"Exported {exported} PO files, {failed} skipped.")


@app.command("import-all")
def import_all(
    ctx: typer.Context,
    lang: Annotated[str, typer.Option("--lang", help="Language code to import (e.g. id_ID)")] = "id_ID",
    overwrite: Annotated[bool, typer.Option("--overwrite", help="Overwrite existing translations")] = False,
) -> None:
    """Batch import PO files for all private modules from i18n/ directories."""
    import base64

    from kctl_odoo.core.callbacks import AppContext
    from kctl_odoo.core.exceptions import RPCError

    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    imported = 0
    failed = 0

    for po_path, mod_name, po_lang in _iter_po_files():
        if po_lang != lang:
            continue
        try:
            file_content = base64.b64encode(po_path.read_bytes()).decode("ascii")
            wizard_id = c.create(
                "base.language.import",
                {
                    "name": po_path.name,
                    "code": lang,
                    "data": file_content,
                    "filename": po_path.name,
                    "overwrite": overwrite,
                },
            )
            c.execute_kw("base.language.import", "import_lang", [[wizard_id]])
            out.info(f"Imported {mod_name}/{po_lang}.po")
            imported += 1
        except (RPCError, Exception) as e:
            out.info(f"Failed {mod_name}/{po_lang}: {e}")
            failed += 1

    out.info(f"Imported {imported} PO files, {failed} failed.")
