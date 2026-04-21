"""Report Format commands - banded PDF layout CRUD + preview + import/export.

Wraps the JSON-RPC API shipped by the `report_layout` Odoo module (v18.0.9+).
"""

from __future__ import annotations

import base64
import difflib
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext

app = typer.Typer(help="Report format configuration - banded PDF layouts.")


def _resolve_format(c, fmt_ref: str) -> int:
    """Resolve ``fmt_ref`` (numeric id, xmlid, or name substring) to an int id."""
    if fmt_ref.isdigit():
        rows = c.read("report.format", [int(fmt_ref)], ["id"])
        if rows:
            return rows[0]["id"]
        raise typer.BadParameter(f"No report.format with id {fmt_ref}")
    if "." in fmt_ref and " " not in fmt_ref:
        module, _, name = fmt_ref.partition(".")
        xmlid_rec = c.search_read(
            "ir.model.data",
            [("module", "=", module), ("name", "=", name), ("model", "=", "report.format")],
            ["res_id"],
            limit=1,
        )
        if xmlid_rec:
            return xmlid_rec[0]["res_id"]
    rows = c.search_read(
        "report.format",
        [("name", "ilike", fmt_ref)],
        ["id", "name"],
        limit=5,
    )
    if not rows:
        raise typer.BadParameter(f"No report.format matches {fmt_ref!r}")
    if len(rows) > 1:
        names = ", ".join(f"{r['id']}:{r['name']}" for r in rows)
        raise typer.BadParameter(f"Ambiguous {fmt_ref!r}; matches: {names}")
    return rows[0]["id"]


def _strip_pdf_noise(pdf_bytes: bytes) -> bytes:
    """Remove volatile bytes (CreationDate, ModDate, trailer ID) so SHA-256 is stable."""
    out = pdf_bytes
    out = re.sub(rb"/CreationDate \(D:\d{14}[^)]*\)", b"/CreationDate (D:GOLDEN)", out)
    out = re.sub(rb"/ModDate \(D:\d{14}[^)]*\)", b"/ModDate (D:GOLDEN)", out)
    out = re.sub(rb"/ID \[<[0-9a-fA-F]+>\s*<[0-9a-fA-F]+>\]", b"/ID [<GOLDEN><GOLDEN>]", out)
    return out


# ---------------------------------------------------------------------------
# Inspection commands
# ---------------------------------------------------------------------------


@app.command(name="list")
def list_formats(
    ctx: typer.Context,
    report_type: Annotated[str | None, typer.Option("--type", help="Filter by report type key")] = None,
    company: Annotated[str | None, typer.Option("--company", help="Filter by company name")] = None,
    ou: Annotated[str | None, typer.Option("--ou", help="Filter by operating unit name")] = None,
    default_only: Annotated[bool, typer.Option("--default-only", help="Show only defaults")] = False,
    limit: Annotated[int, typer.Option("--limit", "-l")] = 100,
) -> None:
    """List report formats."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = []
    if report_type:
        domain.append(("report_type", "=", report_type))
    if default_only:
        domain.append(("is_default", "=", True))
    if company:
        co = c.search_read("res.company", [("name", "ilike", company)], ["id"], limit=1)
        if not co:
            raise typer.BadParameter(f"Company not found: {company}")
        domain.append(("company_id", "=", co[0]["id"]))
    if ou:
        ou_rec = c.search_read("operating.unit", [("name", "ilike", ou)], ["id"], limit=1)
        if not ou_rec:
            raise typer.BadParameter(f"Operating unit not found: {ou}")
        domain.append(("operating_unit_id", "=", ou_rec[0]["id"]))

    records = c.search_read(
        "report.format",
        domain,
        ["id", "name", "report_type", "theme_preset", "company_id", "operating_unit_id", "is_default"],
        limit=limit,
        order="report_type, name",
    )

    rows: list[list[str]] = []
    json_rows: list[dict] = []
    for r in records:
        company_name = r["company_id"][1] if r.get("company_id") else ""
        ou_name = r["operating_unit_id"][1] if r.get("operating_unit_id") else ""
        rows.append(
            [
                str(r["id"]),
                r.get("name") or "",
                r.get("report_type") or "",
                r.get("theme_preset") or "",
                company_name,
                ou_name,
                "Y" if r.get("is_default") else "",
            ]
        )
        json_rows.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "report_type": r.get("report_type"),
                "theme_preset": r.get("theme_preset"),
                "company": company_name,
                "operating_unit": ou_name,
                "is_default": bool(r.get("is_default")),
            }
        )

    out.table(
        f"Report Formats ({len(rows)})",
        [
            ("ID", "cyan"),
            ("Name", ""),
            ("Type", ""),
            ("Theme", ""),
            ("Company", ""),
            ("OU", ""),
            ("Default", "green"),
        ],
        rows,
        data_for_json=json_rows,
    )


@app.command()
def show(
    ctx: typer.Context,
    fmt_ref: Annotated[str, typer.Argument(help="id, xmlid, or name substring")],
) -> None:
    """Show a single format with its bands."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    fmt_id = _resolve_format(c, fmt_ref)
    rec = c.read(
        "report.format",
        [fmt_id],
        [
            "id",
            "name",
            "report_type",
            "theme_preset",
            "company_id",
            "operating_unit_id",
            "is_default",
            "parent_format_id",
            "paperformat_id",
            "notes",
        ],
    )[0]

    out.header(f"Report Format #{fmt_id}")
    out.kv("ID", str(rec["id"]))
    out.kv("Name", rec.get("name") or "")
    out.kv("Type", rec.get("report_type") or "")
    out.kv("Theme", rec.get("theme_preset") or "")
    out.kv("Company", rec["company_id"][1] if rec.get("company_id") else "")
    out.kv("Operating Unit", rec["operating_unit_id"][1] if rec.get("operating_unit_id") else "")
    out.kv("Default", "Yes" if rec.get("is_default") else "No")
    out.kv("Parent", rec["parent_format_id"][1] if rec.get("parent_format_id") else "")
    out.kv("Paper Format", rec["paperformat_id"][1] if rec.get("paperformat_id") else "")
    if rec.get("notes"):
        out.kv("Notes", rec["notes"])

    bands = c.search_read(
        "report.format.band",
        [("format_id", "=", fmt_id)],
        ["id", "kind", "sequence", "active", "visible_if", "blocks_json"],
        order="sequence, kind",
    )

    rows: list[list[str]] = []
    json_rows: list[dict] = []
    for b in bands:
        blocks = b.get("blocks_json") or []
        blocks_count = len(blocks) if isinstance(blocks, list) else 0
        rows.append(
            [
                str(b["id"]),
                b.get("kind") or "",
                str(b.get("sequence") or 0),
                "Y" if b.get("active") else "",
                (b.get("visible_if") or "")[:40],
                str(blocks_count),
            ]
        )
        json_rows.append(
            {
                "id": b["id"],
                "kind": b.get("kind"),
                "sequence": b.get("sequence"),
                "active": bool(b.get("active")),
                "visible_if": b.get("visible_if"),
                "blocks_count": blocks_count,
            }
        )
    out.table(
        f"Bands ({len(rows)})",
        [
            ("ID", "cyan"),
            ("Kind", ""),
            ("Seq", ""),
            ("Active", "green"),
            ("visible_if", "dim"),
            ("Blocks", ""),
        ],
        rows,
        data_for_json=json_rows,
    )


@app.command()
def types(ctx: typer.Context) -> None:
    """List all registered report types (from PrintReportRegistry)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    selection = c.execute_kw("report.format", "registry_selection", [])
    rows = [[key, label] for key, label in selection]
    out.table(
        f"Registered Report Types ({len(rows)})",
        [("Key", "cyan"), ("Label", "")],
        rows,
        data_for_json=[{"key": k, "label": v} for k, v in selection],
    )


@app.command()
def versions(
    ctx: typer.Context,
    fmt_ref: Annotated[str, typer.Argument(help="id, xmlid, or name substring")],
    revert: Annotated[int | None, typer.Option("--revert", help="Revert to this version id")] = None,
) -> None:
    """List versions of a format. Optionally revert with --revert <id>."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    fmt_id = _resolve_format(c, fmt_ref)

    if revert is not None:
        c.execute_kw("report.format", "action_revert_to_version", [[fmt_id], revert])
        out.success(f"Reverted format {fmt_id} to version {revert}.")
        return

    records = c.search_read(
        "report.format.version",
        [("format_id", "=", fmt_id)],
        ["id", "create_date", "create_uid", "comment", "is_current"],
        limit=100,
        order="create_date desc, id desc",
    )
    rows: list[list[str]] = []
    json_rows: list[dict] = []
    for r in records:
        user_name = r["create_uid"][1] if r.get("create_uid") else ""
        rows.append(
            [
                str(r["id"]),
                r.get("create_date") or "",
                user_name,
                (r.get("comment") or "")[:60],
                "Y" if r.get("is_current") else "",
            ]
        )
        json_rows.append(
            {
                "id": r["id"],
                "create_date": r.get("create_date"),
                "user": user_name,
                "comment": r.get("comment"),
                "is_current": bool(r.get("is_current")),
            }
        )
    out.table(
        f"Versions of format {fmt_id}",
        [
            ("ID", "cyan"),
            ("Created", ""),
            ("User", ""),
            ("Comment", "dim"),
            ("Current", "green"),
        ],
        rows,
        data_for_json=json_rows,
    )


# ---------------------------------------------------------------------------
# Portability commands
# ---------------------------------------------------------------------------


@app.command()
def export(
    ctx: typer.Context,
    fmt_ref: Annotated[str, typer.Argument(help="id, xmlid, or name")],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Path to write JSON")] = None,
) -> None:
    """Export a format as JSON (portable across companies / instances)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    fmt_id = _resolve_format(c, fmt_ref)
    payload = c.execute_kw("report.format", "action_export_json", [[fmt_id]])
    if output:
        data = json.dumps(payload, indent=2)
        output.write_text(data, encoding="utf-8")
        out.success(f"Wrote {len(data)} bytes to {output}")
    else:
        out.raw_json(payload)


@app.command(name="import")
def import_format(
    ctx: typer.Context,
    path: Annotated[Path, typer.Argument(help="Path to JSON file")],
    company: Annotated[str | None, typer.Option("--company", help="Target company name")] = None,
    ou: Annotated[str | None, typer.Option("--ou", help="Target operating unit name")] = None,
    set_default: Annotated[bool, typer.Option("--set-default", help="Mark as default")] = False,
) -> None:
    """Import a report format from a JSON file."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not path.exists():
        raise typer.BadParameter(f"File not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))

    company_id = None
    if company:
        co = c.search_read("res.company", [("name", "ilike", company)], ["id"], limit=1)
        if not co:
            raise typer.BadParameter(f"Company not found: {company}")
        company_id = co[0]["id"]

    ou_id = None
    if ou:
        ou_rec = c.search_read("operating.unit", [("name", "ilike", ou)], ["id"], limit=1)
        if not ou_rec:
            raise typer.BadParameter(f"Operating unit not found: {ou}")
        ou_id = ou_rec[0]["id"]

    new_id = c.execute_kw(
        "report.format",
        "action_import_json",
        [payload, company_id, ou_id, set_default],
    )
    out.success(f"Created report.format #{new_id}")


@app.command()
def clone(
    ctx: typer.Context,
    fmt_ref: Annotated[str, typer.Argument(help="id, xmlid, or name")],
    name: Annotated[str, typer.Option("--name", help="Name for the new format")],
    inherit: Annotated[bool, typer.Option("--inherit", help="Link as child via parent_format_id")] = False,
) -> None:
    """Clone a format. With --inherit, the new record inherits from the source."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    fmt_id = _resolve_format(c, fmt_ref)
    new_id = c.execute_kw("report.format", "action_clone", [[fmt_id], name, inherit])
    out.success(f"Cloned -> report.format #{new_id} ({'inherits' if inherit else 'standalone'})")


@app.command(name="set-default")
def set_default(
    ctx: typer.Context,
    fmt_ref: Annotated[str, typer.Argument(help="id, xmlid, or name")],
) -> None:
    """Mark a format as the default for its (type, company, OU) triple."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    fmt_id = _resolve_format(c, fmt_ref)
    c.write("report.format", [fmt_id], {"is_default": True})
    out.success(f"Report format #{fmt_id} is now default for its scope.")


# ---------------------------------------------------------------------------
# Preview / bench / golden
# ---------------------------------------------------------------------------


@app.command()
def preview(
    ctx: typer.Context,
    fmt_ref: Annotated[str, typer.Argument(help="id, xmlid, or name")],
    record_id: Annotated[int, typer.Option("--record-id", help="Sample record id")],
    as_html: Annotated[bool, typer.Option("--html/--pdf", help="Render HTML instead of PDF")] = False,
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Path to write output")] = None,
) -> None:
    """Render a preview of the format against a sample record."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    fmt_id = _resolve_format(c, fmt_ref)
    if as_html:
        html = c.execute_kw("report.format", "render_preview_html", [[fmt_id], record_id])
        if output:
            output.write_text(html, encoding="utf-8")
            out.success(f"Wrote HTML preview to {output}")
        else:
            typer.echo(html)
    else:
        res = c.execute_kw("report.format", "render_preview_pdf", [[fmt_id], record_id])
        pdf = base64.b64decode(res["content_base64"])
        target = output or Path(res["filename"])
        target.write_bytes(pdf)
        out.success(f"Wrote {len(pdf)} bytes to {target}")


@app.command(name="render-bench")
def render_bench(
    ctx: typer.Context,
    fmt_ref: Annotated[str, typer.Argument(help="id, xmlid, or name")],
    record_id: Annotated[int, typer.Option("--record-id", help="Sample record id")],
    iterations: Annotated[int, typer.Option("--iterations", help="Runs to average")] = 5,
) -> None:
    """Benchmark render time across N iterations."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    fmt_id = _resolve_format(c, fmt_ref)
    durations: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        c.execute_kw("report.format", "render_preview_pdf", [[fmt_id], record_id])
        durations.append(time.perf_counter() - t0)

    stats = {
        "iterations": iterations,
        "min_ms": round(min(durations) * 1000, 1),
        "max_ms": round(max(durations) * 1000, 1),
        "avg_ms": round(sum(durations) / len(durations) * 1000, 1),
    }
    if actx.json_mode:
        out.raw_json(stats)
        return
    out.header(f"render-bench for format {fmt_id}")
    for k, v in stats.items():
        out.kv(k, str(v))


@app.command(name="golden-snapshot")
def golden_snapshot(
    ctx: typer.Context,
    fmt_ref: Annotated[str, typer.Argument(help="id, xmlid, or name")],
    record_id: Annotated[int, typer.Option("--record-id", help="Sample record id")],
    golden_dir: Annotated[Path | None, typer.Option("--dir", help="Directory for the .sha256 file")] = None,
) -> None:
    """Render the format to PDF, strip timestamps, write SHA-256 as a golden file."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    fmt_id = _resolve_format(c, fmt_ref)
    fmt = c.read("report.format", [fmt_id], ["name", "report_type", "theme_preset"])[0]
    res = c.execute_kw("report.format", "render_preview_pdf", [[fmt_id], record_id])
    pdf = base64.b64decode(res["content_base64"])
    normalized = _strip_pdf_noise(pdf)
    digest = hashlib.sha256(normalized).hexdigest()

    golden_dir = golden_dir or Path.cwd()
    golden_dir.mkdir(parents=True, exist_ok=True)
    theme = fmt.get("theme_preset") or "default"
    out_path = golden_dir / f"{theme}_{fmt['report_type']}.sha256"
    out_path.write_text(f"{digest}\n", encoding="utf-8")
    out.success(f"Wrote {digest} to {out_path}")


# ---------------------------------------------------------------------------
# Validation / scaffold
# ---------------------------------------------------------------------------


@app.command()
def diff(
    ctx: typer.Context,
    fmt_ref_a: Annotated[str, typer.Argument(help="First format")],
    fmt_ref_b: Annotated[str, typer.Argument(help="Second format")],
) -> None:
    """Show semantic differences between two formats (arch-level)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    id_a = _resolve_format(c, fmt_ref_a)
    id_b = _resolve_format(c, fmt_ref_b)
    payload_a = c.execute_kw("report.format", "action_export_json", [[id_a]])
    payload_b = c.execute_kw("report.format", "action_export_json", [[id_b]])
    text_a = json.dumps(payload_a["arch"], indent=2, sort_keys=True).splitlines(keepends=True)
    text_b = json.dumps(payload_b["arch"], indent=2, sort_keys=True).splitlines(keepends=True)
    diff_lines = list(
        difflib.unified_diff(
            text_a,
            text_b,
            fromfile=f"format {id_a}",
            tofile=f"format {id_b}",
            lineterm="",
        )
    )
    if not diff_lines:
        out.success("Formats are identical at arch level.")
    else:
        typer.echo("\n".join(diff_lines))


@app.command()
def lint(
    ctx: typer.Context,
    fmt_ref: Annotated[str | None, typer.Argument(help="Format to lint; omit with --all")] = None,
    all_formats: Annotated[bool, typer.Option("--all", help="Lint every format")] = False,
) -> None:
    """Validate one format's arch (or all). Reports errors + warnings."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if all_formats:
        ids = [r["id"] for r in c.search_read("report.format", [], ["id"], limit=1000)]
    else:
        if not fmt_ref:
            raise typer.BadParameter("Provide a format reference or pass --all.")
        ids = [_resolve_format(c, fmt_ref)]

    bad = 0
    for fmt_id in ids:
        issues = c.execute_kw("report.format", "validate_arch", [[fmt_id]])
        if issues:
            name = c.read("report.format", [fmt_id], ["name"])[0]["name"]
            out.info(f"#{fmt_id} ({name}) - {len(issues)} issue(s):")
            for i in issues:
                typer.echo(f"  [{i['severity']}] {i['path']}: {i['msg']}")
            if any(i["severity"] == "error" for i in issues):
                bad += 1

    if bad:
        out.error(f"{bad} format(s) have errors.")
        raise typer.Exit(code=1)
    out.success("All formats pass.")


_THEME_SKELETON = {
    "pro",
    "matrix",
    "minimal",
    "executive",
    "compact",
    "id_classic",
}


@app.command()
def scaffold(
    ctx: typer.Context,
    report_type: Annotated[str, typer.Option("--type", help="Registry key, e.g. 'invoice'")],
    theme: Annotated[
        str, typer.Option("--theme", help="Preset: pro|matrix|minimal|executive|compact|id_classic")
    ] = "pro",
    name: Annotated[str, typer.Option("--name", help="Display name")] = "Scaffolded Format",
    output: Annotated[Path, typer.Option("--output", "-o", help="Path to write the starter JSON")] = Path(
        "new_format.json"
    ),
) -> None:
    """Generate a starter JSON for a new format (not yet submitted to Odoo)."""
    actx: AppContext = ctx.obj
    out = actx.output

    if theme not in _THEME_SKELETON:
        raise typer.BadParameter(f"Unknown theme {theme!r}; choose one of {sorted(_THEME_SKELETON)}")

    starter = {
        "name": name,
        "report_type": report_type,
        "theme_preset": theme,
        "paperformat_id": False,
        "arch_version": "1",
        "arch": {
            "arch_version": "1",
            "theme_preset": theme,
            "bands": [
                {
                    "kind": "header",
                    "sequence": 10,
                    "visible_if": "",
                    "blocks": [
                        {
                            "type": "image",
                            "id": "logo",
                            "props": {
                                "field_path": "company.logo",
                                "max_height_px": 60,
                                "align": "left",
                            },
                        },
                        {
                            "type": "text",
                            "id": "co",
                            "props": {
                                "html_i18n": {
                                    "en_US": "<strong>{{ company.name }}</strong>",
                                    "id_ID": "<strong>{{ company.name }}</strong>",
                                }
                            },
                        },
                    ],
                },
                {"kind": "doc_info", "sequence": 20, "visible_if": "", "blocks": []},
                {"kind": "body", "sequence": 30, "visible_if": "", "blocks": []},
                {"kind": "totals", "sequence": 40, "visible_if": "", "blocks": []},
                {"kind": "notes", "sequence": 50, "visible_if": "", "blocks": []},
                {
                    "kind": "signature",
                    "sequence": 60,
                    "visible_if": "",
                    "blocks": [{"type": "signature", "id": "sig", "props": {}}],
                },
                {"kind": "footer", "sequence": 70, "visible_if": "", "blocks": []},
                {"kind": "watermark", "sequence": 80, "visible_if": "", "blocks": []},
            ],
        },
        "signature_lines": [],
    }
    output.write_text(json.dumps(starter, indent=2), encoding="utf-8")
    out.success(f"Wrote starter JSON to {output}")
    out.info(f"Import with: kctl-odoo report-formats import {output}")


@app.command(name="seed-samples")
def seed_samples(
    ctx: typer.Context,
    company_id: Annotated[
        int | None,
        typer.Option("--company-id", help="res.company id to seed into. Defaults to env.company."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a table.")] = False,
) -> None:
    """Create one sample record per registered report type, so Preview PDF works.

    Wraps ``report.format.seed_sample_records`` — idempotent (skips if a record
    already exists on the target company). Each failed type is reported with
    the exception type + short message; the rest still proceed. Run this after
    a fresh install / upgrade to unblock the Preview PDF button for every
    registered type.
    """
    actx = ctx.obj
    assert isinstance(actx, AppContext)
    out = actx.output
    c = actx.client

    out.info("Seeding sample records...")
    results = c.execute_kw(
        "report.format",
        "seed_sample_records",
        [],
        {"company_id": company_id} if company_id else {},
    )

    if as_json:
        out.raw_json(results)
        return

    status_glyph = {"created": "[NEW]", "exists": "[OK ]", "skip": "[SKP]", "error": "[ERR]"}
    rows = []
    for r in results:
        glyph = status_glyph.get(r["status"], "[?? ]")
        rid = str(r.get("record_id")) if r.get("record_id") else "—"
        rows.append(
            [
                glyph,
                r["report_type"],
                r.get("model") or "—",
                rid,
                (r.get("note") or "")[:60],
            ]
        )
    out.table(
        "Sample record seed results",
        [("Status", "green"), ("Report type", "cyan"), ("Model", ""), ("Record id", ""), ("Note", "dim")],
        rows,
    )

    n_created = sum(1 for r in results if r["status"] == "created")
    n_exists = sum(1 for r in results if r["status"] == "exists")
    n_skip = sum(1 for r in results if r["status"] == "skip")
    n_error = sum(1 for r in results if r["status"] == "error")
    total = len(results)
    out.text(
        f"Summary: {n_created} created, {n_exists} already existed, "
        f"{n_skip} skipped, {n_error} errors (of {total} registered types)."
    )
    if n_error:
        out.warn("Errors above usually mean multi-company warehouse mismatch or missing journal.")
    out.success("Seed complete. Try: kctl-odoo report-formats preview <fmt-id> --record-id <id>")
