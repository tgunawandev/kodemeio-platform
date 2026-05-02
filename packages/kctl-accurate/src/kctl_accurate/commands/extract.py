"""kctl-accurate extract — bulk JSON extraction from Accurate Online.

Subcommands
-----------
run     Extract one or more modules to a JSON dump directory.
resume  Re-run extraction with resume=True (skips already-fetched files).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from kctl_lib.exceptions import ConfigError

from kctl_accurate.core.callbacks import AppContext

# Lazy imports from accurate_sdk so the module loads even if the SDK is absent
# at import-time (avoids hard failures in tests that don't need the SDK).
try:
    from accurate_sdk.extract import (
        MASTER_MODULES,
        TRANSACTION_MODULES,
        ExtractManifest,
        extract_company,
    )

    _ALL_MODULES: list[str] = list(MASTER_MODULES) + list(TRANSACTION_MODULES)
except ImportError:  # pragma: no cover
    _ALL_MODULES = []

app = typer.Typer(
    help="Bulk-extract Accurate Online data to JSON files on disk.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_modules(raw: str) -> list[str]:
    """Parse a comma-separated module list and reject unknowns."""
    names = [m.strip() for m in raw.split(",") if m.strip()]
    unknown = [m for m in names if m not in _ALL_MODULES]
    if unknown:
        raise ConfigError(f"Unknown module(s): {', '.join(unknown)}. Valid modules: {', '.join(_ALL_MODULES)}")
    return names


def _make_progress_callback(quiet: bool) -> object:
    """Return a Rich Progress-based callback, or None when quiet/non-TTY."""
    is_tty = sys.stderr.isatty()
    if quiet or not is_tty:
        return None

    from rich.progress import Progress, SpinnerColumn, TextColumn

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=__import__("rich.console", fromlist=["Console"]).Console(stderr=True),
    )
    task_id = progress.add_task("Extracting…", total=None)
    progress.start()

    def _callback(msg: str) -> None:
        progress.update(task_id, description=msg)

    # Attach progress to callback so caller can stop it
    _callback._progress = progress  # type: ignore[attr-defined]
    return _callback


def _stop_progress(callback: object) -> None:
    """Stop the Rich Progress attached to *callback* if present."""
    prog = getattr(callback, "_progress", None)
    if prog is not None:
        prog.stop()


def _print_manifest_summary(manifest: ExtractManifest, json_mode: bool) -> None:
    """Print a per-module summary table (or JSON) to stdout."""
    if json_mode:
        print(json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False))
        return

    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(
        title=f"[bold]Extract complete — {manifest.company}[/bold]",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Module")
    table.add_column("Records", justify="right")
    table.add_column("Details fetched", justify="right")
    table.add_column("Skipped", justify="right")

    for mod, stats in manifest.modules.items():
        table.add_row(
            mod,
            str(stats.get("records", "—")),
            str(stats.get("details_fetched", "—")),
            str(stats.get("details_skipped", "—")),
        )

    console.print()
    console.print(table)
    console.print(f"  [dim]Duration:[/dim] {manifest.duration_seconds:.1f}s  [dim]Written to:[/dim] {manifest.host}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("run")
def extract_run(
    ctx: typer.Context,
    out_dir: Annotated[
        Path,
        typer.Option("--out-dir", help="Root directory for the JSON dump.", show_default=False),
    ],
    modules: Annotated[
        str | None,
        typer.Option(
            "--modules",
            help=f"Comma-separated module names (default: all). Valid: {', '.join(_ALL_MODULES)}",
        ),
    ] = None,
    no_detail: Annotated[
        bool,
        typer.Option("--no-detail", help="Skip per-record detail fetching."),
    ] = False,
    resume: Annotated[
        bool,
        typer.Option("--resume", help="Skip files already present on disk."),
    ] = False,
) -> None:
    """Extract Accurate Online data to JSON files.

    By default all modules (master + transaction) are extracted with
    per-record detail calls.  Use --modules to restrict the run.
    """
    actx: AppContext = ctx.obj

    module_list: list[str] | None = None
    if modules is not None:
        module_list = _validate_modules(modules)

    progress_cb = _make_progress_callback(actx.quiet)

    try:
        manifest = extract_company(
            client=actx.client.raw,
            output_dir=out_dir,
            modules=module_list,
            include_detail=not no_detail,
            resume=resume,
            progress=progress_cb,  # type: ignore[arg-type]
        )
    finally:
        _stop_progress(progress_cb)

    _print_manifest_summary(manifest, actx.json_mode)


@app.command("resume")
def extract_resume(
    ctx: typer.Context,
    out_dir: Annotated[
        Path,
        typer.Option("--out-dir", help="Root directory of the existing JSON dump.", show_default=False),
    ],
) -> None:
    """Resume a previous extraction run, skipping already-fetched files."""
    actx: AppContext = ctx.obj

    progress_cb = _make_progress_callback(actx.quiet)

    try:
        manifest = extract_company(
            client=actx.client.raw,
            output_dir=out_dir,
            modules=None,
            include_detail=True,
            resume=True,
            progress=progress_cb,  # type: ignore[arg-type]
        )
    finally:
        _stop_progress(progress_cb)

    _print_manifest_summary(manifest, actx.json_mode)
