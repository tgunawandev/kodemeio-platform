"""Report instance format CRUD (7-tab Modify dialog backend).

Wraps the ``report.instance.format`` model — the per-instance format override
that drives columns/typography/numbers/header/footer/page/rows in every
renderer (HTML viewer, PDF, XLSX, CSV, fixed-width Text). Lets operators
customize a report instance's layout via CLI without opening the Modify
Format dialog in the web UI.

Mounted under ``kctl-odoo report format``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Per-instance report format (Modify dialog) CRUD.")


_LEAF_FIELDS = (
    "show_header",
    "show_company_name",
    "company_name_override",
    "show_report_title",
    "report_title_override",
    "show_subtitle",
    "subtitle_override",
    "show_filter_bar",
    "show_column_title",
    "show_footer",
    "show_system_name",
    "show_print_date",
    "show_page_number",
    "show_footer_company_name",
    "additional_footer",
    "paper_format",
    "orientation",
    "flexible_height",
    "margin_top",
    "margin_right",
    "margin_bottom",
    "margin_left",
    "date_format",
    "decimal_digits",
    "decimal_separator",
    "thousand_separator",
    "negative_style",
    "negative_red",
)
_JSON_FIELDS = ("columns_json", "extra_filter_json", "typography_json", "rows_json")
_ALL_WRITABLE = (*_LEAF_FIELDS, *_JSON_FIELDS)


def _require_module(c, out) -> bool:
    if not model_available(c, "report.instance.format"):
        out.warn("report.instance.format model not available. Install: kctl-odoo modules install report_management")
        return False
    return True


def _format_id_for_instance(c, instance_id: int, create: bool = False) -> int | None:
    ids = c.search("report.instance.format", [("instance_id", "=", instance_id)], limit=1)
    if ids:
        return ids[0]
    if not create:
        return None
    res = c.execute_kw("report.instance.format", "create", [{"instance_id": instance_id}])
    return res[0] if isinstance(res, list) else res


def _parse_kv(pairs: list[str] | None) -> dict:
    out: dict = {}
    if not pairs:
        return out
    for raw in pairs:
        if "=" not in raw:
            raise typer.BadParameter(f"Expected key=value, got {raw!r}")
        key, _, val = raw.partition("=")
        key = key.strip()
        if key not in _ALL_WRITABLE:
            raise typer.BadParameter(f"Unknown field {key!r}. Writable: {', '.join(_ALL_WRITABLE)}")
        val = val.strip()
        if key in _JSON_FIELDS:
            try:
                json.loads(val)
            except ValueError as exc:
                raise typer.BadParameter(f"{key} must be valid JSON: {exc}") from exc
            out[key] = val
        else:
            try:
                out[key] = json.loads(val)
            except ValueError:
                out[key] = val
    return out


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------
@app.command("get")
def get_format(
    ctx: typer.Context,
    instance_id: Annotated[int, typer.Argument(help="report.instance id")],
    merged: Annotated[
        bool,
        typer.Option("--merged/--raw", help="Return as_dict() merged config (default) vs raw leaf fields"),
    ] = True,
) -> None:
    """Read the format override for a report instance.

    Without a format override, returns the defaults (every tenant has
    baseline values wired in the model).
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_module(c, out):
        raise typer.Exit(1)

    fmt_id = _format_id_for_instance(c, instance_id, create=False)
    if fmt_id is None:
        out.info(f"No format override for instance {instance_id}. Defaults apply.")
        if actx.json_mode:
            out.raw_json({"instance_id": instance_id, "has_override": False})
        return

    if merged:
        # as_dict() is ensure_one() on the server, returns a single dict
        # (not a list). Don't unpack.
        data = c.execute_kw("report.instance.format", "as_dict", [[fmt_id]])
        payload = {"instance_id": instance_id, "format_id": fmt_id, "config": data}
    else:
        (rec,) = c.read("report.instance.format", [fmt_id], list(_ALL_WRITABLE))
        payload = {"instance_id": instance_id, "format_id": fmt_id, "fields": rec}

    if actx.json_mode:
        out.raw_json(payload)
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


# ---------------------------------------------------------------------------
# set
# ---------------------------------------------------------------------------
@app.command("set")
def set_format(
    ctx: typer.Context,
    instance_id: Annotated[int, typer.Argument(help="report.instance id")],
    set_: Annotated[
        list[str],
        typer.Option("--set", "-s", help="field=value (repeatable). JSON fields take a JSON string."),
    ],
) -> None:
    """Create or update a format override for a report instance.

    Examples:

    \b
        # Hide filter bar + switch to landscape
        kctl-odoo report format set 613 \\
            --set show_filter_bar=false --set orientation=landscape

    \b
        # Set custom column order via JSON
        kctl-odoo report format set 613 \\
            --set 'columns_json=[{"key":"actual","visible":true,"header_override":"Current"}]'
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_module(c, out):
        raise typer.Exit(1)

    vals = _parse_kv(set_)
    if not vals:
        out.error("No fields to set — pass at least one --set key=value.")
        raise typer.Exit(1)

    fmt_id = _format_id_for_instance(c, instance_id, create=True)
    try:
        c.execute_kw("report.instance.format", "write", [[fmt_id], vals])
    except RPCError as exc:
        out.error(f"Set failed: {exc}")
        raise typer.Exit(1) from exc

    out.success(
        f"Updated report.instance.format (instance_id={instance_id} format_id={fmt_id}): {', '.join(vals.keys())}"
    )
    if actx.json_mode:
        out.raw_json({"instance_id": instance_id, "format_id": fmt_id, "updated": list(vals.keys())})


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------
@app.command("reset")
def reset_format(
    ctx: typer.Context,
    instance_id: Annotated[int, typer.Argument(help="report.instance id")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
) -> None:
    """Drop the format override for a report instance — renderer falls back to defaults."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_module(c, out):
        raise typer.Exit(1)

    fmt_id = _format_id_for_instance(c, instance_id, create=False)
    if fmt_id is None:
        out.info(f"Instance {instance_id} has no override; nothing to reset.")
        return

    if not yes and not typer.confirm(f"Delete format override for instance {instance_id}?"):
        raise typer.Exit(0)

    c.execute_kw("report.instance.format", "unlink", [[fmt_id]])
    out.success(f"Reset report.instance.format for instance {instance_id} (was id={fmt_id})")
    if actx.json_mode:
        out.raw_json({"instance_id": instance_id, "reset": True})


# ---------------------------------------------------------------------------
# export-json / import-json
# ---------------------------------------------------------------------------
@app.command("export-json")
def export_json(
    ctx: typer.Context,
    instance_id: Annotated[int, typer.Argument(help="report.instance id")],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output file path (stdout if omitted)"),
    ] = None,
) -> None:
    """Dump the raw leaf-field values of a format override as JSON.

    The output is round-trippable via ``import-json`` to clone format
    presets across instances or tenants.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_module(c, out):
        raise typer.Exit(1)

    fmt_id = _format_id_for_instance(c, instance_id, create=False)
    if fmt_id is None:
        out.error(f"No format override for instance {instance_id}.")
        raise typer.Exit(1)

    (rec,) = c.read("report.instance.format", [fmt_id], list(_ALL_WRITABLE))
    # Drop id/relation fields; keep only the writable leaf + JSON fields.
    payload = {k: rec.get(k) for k in _ALL_WRITABLE}
    text = json.dumps(payload, indent=2, ensure_ascii=False, default=str)

    if output:
        output.write_text(text, encoding="utf-8")
        out.success(f"Wrote {output}")
        if actx.json_mode:
            out.raw_json({"instance_id": instance_id, "file": str(output)})
    else:
        print(text)


@app.command("import-json")
def import_json_cmd(
    ctx: typer.Context,
    instance_id: Annotated[int, typer.Argument(help="Target report.instance id")],
    file: Annotated[Path, typer.Argument(help="JSON file produced by export-json")],
) -> None:
    """Load a format preset JSON onto a report instance (creates or updates the override)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_module(c, out):
        raise typer.Exit(1)

    if not file.exists():
        out.error(f"File not found: {file}")
        raise typer.Exit(1)

    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except ValueError as exc:
        out.error(f"Invalid JSON: {exc}")
        raise typer.Exit(1) from exc

    if not isinstance(data, dict):
        out.error("JSON payload must be an object (produced by `report format export-json`).")
        raise typer.Exit(1)

    # Filter to known writable fields; drop id/instance_id so the payload
    # is instance-agnostic.
    vals = {k: data[k] for k in _ALL_WRITABLE if k in data}
    if not vals:
        out.error("Payload has no recognized format fields.")
        raise typer.Exit(1)

    fmt_id = _format_id_for_instance(c, instance_id, create=True)
    try:
        c.execute_kw("report.instance.format", "write", [[fmt_id], vals])
    except RPCError as exc:
        out.error(f"Import failed: {exc}")
        raise typer.Exit(1) from exc

    out.success(f"Applied format preset to instance {instance_id} (format_id={fmt_id}): {len(vals)} field(s)")
    if actx.json_mode:
        out.raw_json({"instance_id": instance_id, "format_id": fmt_id, "applied": list(vals.keys())})
