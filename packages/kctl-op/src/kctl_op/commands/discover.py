"""Discover .env files across scan roots."""

from __future__ import annotations

import typer

from kctl_op.core.callbacks import AppContext

app = typer.Typer(help="Discover .env files.")


@app.callback(invoke_without_command=True)
def discover(ctx: typer.Context) -> None:
    """Find all .env files across configured scan roots."""
    if ctx.invoked_subcommand is not None:
        return

    actx: AppContext = ctx.obj
    out = actx.output
    cfg = actx.service_config
    client = actx.client

    if not cfg.scan_roots:
        out.error("No scan roots configured. Run: kctl-op config init")
        raise typer.Exit(code=1)

    files = client.discover_files(
        cfg.scan_roots,
        cfg.exclude_patterns,
        cfg.env_mappings,
        cfg.custom_env_pattern,
    )

    if not files:
        out.warn("No .env files found.")
        return

    rows = []
    json_data = []
    for f in files:
        rows.append(
            [
                f.project,
                f.environment,
                str(f.path),
                f.item_title,
            ]
        )
        json_data.append(
            {
                "project": f.project,
                "environment": f.environment,
                "path": str(f.path),
                "item_title": f.item_title,
                "scan_root": str(f.scan_root),
            }
        )

    out.table(
        title=f"Discovered .env Files ({len(files)})",
        columns=[
            ("Project", "green"),
            ("Environment", "cyan"),
            ("Path", ""),
            ("1Password Item", "yellow"),
        ],
        rows=rows,
        data_for_json=json_data,
    )
