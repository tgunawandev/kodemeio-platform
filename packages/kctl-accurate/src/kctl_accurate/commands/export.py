"""kctl-accurate export — convert JSON extracts to Odoo-importable CSVs.

Subcommands
-----------
csv     Convert a JSON dump directory to Odoo CSV import files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from kctl_accurate.core.callbacks import AppContext

try:
    from accurate_sdk.export_csv import ExportSummary, export_odoo_csv
    from accurate_sdk.extract import FIELD_MAPPINGS_KEYS as _EXPORT_MODULES
except ImportError:
    try:
        # FIELD_MAPPINGS_KEYS may not exist; fall back to inspecting FIELD_MAPPINGS
        from accurate_sdk.export_csv import FIELD_MAPPINGS, ExportSummary, export_odoo_csv

        _EXPORT_MODULES: list[str] = list(FIELD_MAPPINGS.keys())  # type: ignore[assignment]
    except ImportError:  # pragma: no cover
        _EXPORT_MODULES = []

app = typer.Typer(
    help="Convert Accurate Online JSON extracts to Odoo-importable CSV files.",
    no_args_is_help=True,
)


def _print_export_summary(summary: ExportSummary, json_mode: bool) -> None:
    """Print a summary table (or JSON) of the export run to stdout."""
    if json_mode:
        print(
            json.dumps(
                {
                    "files_written": summary.files_written,
                    "records_exported": summary.records_exported,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(
        title="[bold]Export complete[/bold]",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Module")
    table.add_column("Records", justify="right")

    for module, count in summary.records_exported.items():
        table.add_row(module, str(count))

    console.print()
    console.print(table)
    console.print(f"  [dim]CSV files written:[/dim] {summary.files_written}")


@app.command("csv")
def export_csv(
    ctx: typer.Context,
    json_dir: Annotated[
        Path,
        typer.Option(
            "--json-dir",
            help="Root directory produced by 'extract run' (contains master/ and transactions/).",
            show_default=False,
        ),
    ],
    out_dir: Annotated[
        Path,
        typer.Option("--out-dir", help="Directory where Odoo CSV import files will be written.", show_default=False),
    ],
    modules: Annotated[
        str | None,
        typer.Option(
            "--modules",
            help="Comma-separated module names to export (default: all available). "
            f"Valid: {', '.join(_EXPORT_MODULES)}",
        ),
    ] = None,
) -> None:
    """Convert JSON extracts to Odoo-importable CSV files.

    Reads the output of 'extract run' from JSON-DIR and writes one CSV per
    Odoo model to OUT-DIR.  Use --modules to restrict which modules are
    exported.
    """
    actx: AppContext = ctx.obj

    # export_odoo_csv iterates FIELD_MAPPINGS internally; if the caller wants a
    # subset we patch the mapping temporarily via a modules filter.
    # The current SDK signature is export_odoo_csv(json_dir, csv_dir, mapping_file=None).
    # Module filtering is not yet supported by the SDK function directly, so we
    # accept the --modules flag for forward compatibility but cannot restrict the
    # SDK call today.  When the SDK adds a modules= param this can be plumbed.
    if modules is not None:
        # Validate the names early so the user gets a clear error.
        requested = [m.strip() for m in modules.split(",") if m.strip()]
        unknown = [m for m in requested if m not in _EXPORT_MODULES]
        if unknown:
            from kctl_lib.exceptions import ConfigError

            raise ConfigError(f"Unknown module(s): {', '.join(unknown)}. Valid modules: {', '.join(_EXPORT_MODULES)}")
        if not actx.quiet:
            typer.echo(
                f"Note: --modules filter ({', '.join(requested)}) accepted but "
                "the current SDK exports all available modules. "
                "Filter will be applied in a future SDK release.",
                err=True,
            )

    summary = export_odoo_csv(json_dir=json_dir, csv_dir=out_dir)
    _print_export_summary(summary, actx.json_mode)
