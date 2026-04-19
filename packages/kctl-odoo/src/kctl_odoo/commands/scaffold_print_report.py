"""`kctl-odoo scaffold print-report` - end-to-end new printable report type."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

console = Console()

_TEMPLATES = {
    "register_print_report.py": '''\
# Copyright 2026 PT Trisumber Makmur Indah
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Register {MODULE}'s print report type with report_layout."""

from odoo.addons.report_layout.models.report_format_registry import (
    PrintReportRegistry,
)

PrintReportRegistry.register(
    "{KEY}",
    label="{LABEL}",
    model="{MODEL}",
    default_arch_xmlid="{MODULE}.report_format_{KEY}_default",
    report_action_xmlid="{MODULE}.action_report_{KEY}",
    supports_operating_unit=True,
)
''',
    "report_actions.xml": """\
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="action_report_{KEY}" model="ir.actions.report">
        <field name="name">{LABEL}</field>
        <field name="model">{MODEL}</field>
        <field name="report_type">qweb-pdf</field>
        <field name="report_name">{MODULE}.report_{KEY}_document</field>
        <field name="report_file">{MODULE}.report_{KEY}_document</field>
        <field name="binding_model_id" ref="{BINDING_MODEL_XMLID}"/>
        <field name="binding_type">report</field>
    </record>
</odoo>
""",
    "report_{KEY}.xml": """\
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <template id="report_{KEY}_document">
        <t t-call="web.html_container">
            <t t-foreach="docs" t-as="doc">
                <t t-set="fmt" t-value="doc.company_id._get_report_format(
                    '{KEY}', operating_unit=doc.operating_unit_id if 'operating_unit_id' in doc else False)"/>
                <t t-call="web.external_layout">
                    <div class="page">
                        <t t-call="report_layout.fmt_document_header"/>
                        <t t-call="report_layout.fmt_product_lines"/>
                        <t t-call="report_layout.fmt_totals_section"/>
                        <t t-call="report_layout.fmt_notes_section"/>
                        <t t-call="report_layout.fmt_bank_info"/>
                        <t t-call="report_layout.fmt_signature_section"/>
                        <t t-call="report_layout.fmt_watermark"/>
                    </div>
                </t>
            </t>
        </t>
    </template>
</odoo>
""",
    "report_format_{KEY}_default.xml": """\
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <record id="report_format_{KEY}_default" model="report.format">
        <field name="name">Default {LABEL}</field>
        <field name="report_type">{KEY}</field>
        <field name="theme_preset">{THEME}</field>
        <field name="is_default" eval="False"/>
        <field name="active" eval="True"/>
    </record>
</odoo>
""",
    "migrations/post-register.py": '''\
# Copyright 2026 PT Trisumber Makmur Indah
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Sanity-check {KEY} registration after install/upgrade."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo.addons.report_layout.models.report_format_registry import (
        PrintReportRegistry,
    )
    if "{KEY}" not in PrintReportRegistry._registry:
        _logger.warning("{MODULE}: print report type {KEY!r} not registered after upgrade")
''',
    "test_report_{KEY}.py": """\
# Copyright 2026 PT Trisumber Makmur Indah
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "{MODULE}_report_{KEY}")
class TestReport{KEY_PASCAL}(TransactionCase):
    def test_registry_has_key(self):
        from odoo.addons.report_layout.models.report_format_registry import (
            PrintReportRegistry,
        )
        self.assertIn("{KEY}", PrintReportRegistry._registry)

    def test_seeded_default_exists(self):
        fmt = self.env.ref("{MODULE}.report_format_{KEY}_default", raise_if_not_found=False)
        self.assertTrue(fmt, "Seeded default format missing")
        self.assertEqual(fmt.report_type, "{KEY}")
""",
}


def _write(path: Path, content: str, *, overwrite: bool) -> bool:
    if path.exists() and not overwrite:
        console.print(f"[yellow]SKIP[/yellow] {path}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    console.print(f"[green]CREATE[/green] {path}")
    return True


def _append_manifest_dep(manifest_path: Path, new_dep: str) -> None:
    text = manifest_path.read_text(encoding="utf-8")
    if f'"{new_dep}"' in text:
        return
    pattern = re.compile(r'("depends"\s*:\s*\[)([^\]]*)(\])', re.DOTALL)
    m = pattern.search(text)
    if not m:
        console.print(f"[red]Could not locate `depends` list in {manifest_path}[/red]")
        return
    existing = m.group(2).rstrip().rstrip(",")
    if existing.strip():
        replacement = f'{m.group(1)}{existing},\n        "{new_dep}",\n    {m.group(3)}'
    else:
        replacement = f'{m.group(1)}"{new_dep}"{m.group(3)}'
    new_text = text[: m.start()] + replacement + text[m.end() :]
    manifest_path.write_text(new_text, encoding="utf-8")
    console.print(f"[blue]UPDATE[/blue] {manifest_path} (added '{new_dep}' to depends)")


def _append_manifest_data(manifest_path: Path, entries: list[str]) -> None:
    text = manifest_path.read_text(encoding="utf-8")
    pattern = re.compile(r'("data"\s*:\s*\[)([^\]]*)(\])', re.DOTALL)
    m = pattern.search(text)
    if not m:
        console.print(f"[red]Could not locate `data` list in {manifest_path}[/red]")
        return
    existing = m.group(2)
    additions = [f'        "{e}",' for e in entries if f'"{e}"' not in existing]
    if not additions:
        return
    replacement = f"{m.group(1)}{existing.rstrip().rstrip(',')},\n" + "\n".join(additions) + f"\n    {m.group(3)}"
    new_text = text[: m.start()] + replacement + text[m.end() :]
    manifest_path.write_text(new_text, encoding="utf-8")
    console.print(f"[blue]UPDATE[/blue] {manifest_path} (added {len(additions)} data entries)")


def print_report(
    ctx: typer.Context,
    module: Annotated[str, typer.Option("--module", help="Target Odoo module name (e.g. payroll_management)")],
    key: Annotated[str, typer.Option("--key", help="Registry key (snake_case, e.g. payroll_slip)")],
    label: Annotated[str, typer.Option("--label", help="Human-readable label (e.g. 'Payroll Slip')")],
    model: Annotated[str, typer.Option("--model", help="Odoo model for docs (e.g. hr.payslip)")],
    binding_model_xmlid: Annotated[str, typer.Option("--binding", help="xmlid of the binding_model_id record")],
    theme: Annotated[
        str, typer.Option("--theme", help="Default preset: pro|matrix|minimal|executive|compact|id_classic")
    ] = "pro",
    dest: Annotated[Path | None, typer.Option("--dest", help="Destination module directory")] = None,
    version_dir: Annotated[
        str, typer.Option("--version-dir", help="Migration subdirectory (e.g. 18.0.1.0.0)")
    ] = "18.0.1.0.0",
    overwrite: Annotated[bool, typer.Option("--overwrite", help="Overwrite existing files")] = False,
) -> None:
    """Scaffold a new printable report type end-to-end.

    Generates 6 files (register, QWeb template, action record, seeded default,
    migration hook, test) and patches the target module's __manifest__.py.
    """
    from kctl_odoo.core.utils import find_project_root

    if not dest:
        root = find_project_root()
        for bucket in ("apps", "ext", "integrations", "reports"):
            candidate = root / "src" / "private" / bucket / module
            if candidate.exists():
                dest = candidate
                break
        if not dest:
            dest = root / "src" / "private" / "ext" / module
    dest = Path(dest).resolve()
    if not dest.exists():
        raise typer.BadParameter(f"Module directory not found: {dest}")

    key_pascal = "".join(p.capitalize() for p in key.split("_"))
    subs = {
        "{MODULE}": module,
        "{KEY}": key,
        "{KEY_PASCAL}": key_pascal,
        "{LABEL}": label,
        "{MODEL}": model,
        "{THEME}": theme,
        "{BINDING_MODEL_XMLID}": binding_model_xmlid,
    }

    def render(tpl_name: str) -> tuple[Path, str]:
        tpl = _TEMPLATES[tpl_name]
        for placeholder, value in subs.items():
            tpl = tpl.replace(placeholder, value)
        file_name = tpl_name
        for placeholder, value in subs.items():
            file_name = file_name.replace(placeholder, value)
        return Path(file_name), tpl

    # 1. models/register_print_report.py
    rel, content = render("register_print_report.py")
    _write(dest / "models" / rel.name, content, overwrite=overwrite)

    init = dest / "models" / "__init__.py"
    init.parent.mkdir(parents=True, exist_ok=True)
    existing = init.read_text(encoding="utf-8") if init.exists() else ""
    line = "from . import register_print_report"
    if line not in existing:
        trailer = "\n" if existing and not existing.endswith("\n") else ""
        init.write_text(existing + trailer + line + "\n", encoding="utf-8")
        console.print(f"[blue]UPDATE[/blue] {init}")

    # 2. reports/report_<key>.xml
    rel, content = render("report_{KEY}.xml")
    _write(dest / "reports" / rel.name, content, overwrite=overwrite)

    # 3. data/report_actions.xml (append-or-create)
    actions_path = dest / "data" / "report_actions.xml"
    if actions_path.exists():
        existing = actions_path.read_text(encoding="utf-8")
        _, content = render("report_actions.xml")
        m = re.search(r"<record[\s\S]*?</record>", content)
        if m and m.group(0) not in existing:
            injected = existing.replace("</odoo>", m.group(0) + "\n</odoo>")
            actions_path.write_text(injected, encoding="utf-8")
            console.print(f"[blue]UPDATE[/blue] {actions_path}")
    else:
        _, content = render("report_actions.xml")
        _write(actions_path, content, overwrite=overwrite)

    # 4. data/report_format_<key>_default.xml
    rel, content = render("report_format_{KEY}_default.xml")
    _write(dest / "data" / rel.name, content, overwrite=overwrite)

    # 5. migrations/<version>/post-migration.py
    rel, content = render("migrations/post-register.py")
    mig_dir = dest / "migrations" / version_dir
    _write(mig_dir / "post-migration.py", content, overwrite=overwrite)

    # 6. tests/test_report_<key>.py
    rel, content = render("test_report_{KEY}.py")
    _write(dest / "tests" / rel.name, content, overwrite=overwrite)

    test_init = dest / "tests" / "__init__.py"
    existing = test_init.read_text(encoding="utf-8") if test_init.exists() else ""
    test_line = f"from . import test_report_{key}"
    if test_line not in existing:
        trailer = "\n" if existing and not existing.endswith("\n") else ""
        test_init.write_text(existing + trailer + test_line + "\n", encoding="utf-8")
        console.print(f"[blue]UPDATE[/blue] {test_init}")

    # 7. __manifest__.py
    manifest = dest / "__manifest__.py"
    if manifest.exists():
        _append_manifest_dep(manifest, "report_layout")
        _append_manifest_data(
            manifest,
            [
                "data/report_actions.xml",
                f"data/report_format_{key}_default.xml",
                f"reports/report_{key}.xml",
            ],
        )

    console.print(f"\n[bold green]Scaffolded {label} ({key}) in {dest}[/bold green]")
    console.print(f"\nNext steps:")
    console.print(f"  1. cd {find_project_root()}")
    console.print(f"  2. ./run mod update {module}")
    console.print(f"  3. Test: ./run test {module} --tag {module}_report_{key}")
