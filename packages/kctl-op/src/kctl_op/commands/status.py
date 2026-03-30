"""Sync status commands."""

from __future__ import annotations

import typer

from kctl_op.core.callbacks import AppContext

app = typer.Typer(help="Check sync status.")


@app.callback(invoke_without_command=True)
def status(ctx: typer.Context) -> None:
    """Check 1Password connection, vault access, and sync state for all files."""
    if ctx.invoked_subcommand is not None:
        return

    actx: AppContext = ctx.obj
    out = actx.output
    cfg = actx.service_config
    client = actx.client

    # Discover files
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
    synced = 0
    needs_attention = 0

    for f in files:
        try:
            st = client.file_status(f)
            local_ok = "[green]\u2713[/green]" if st.get("local_exists") else "[red]\u2717[/red]"
            remote_ok = "[green]\u2713[/green]" if st.get("remote_exists") else "[red]\u2717[/red]"

            if st.get("in_sync"):
                status_icon = "[green]\u2713 In sync[/green]"
                synced += 1
            elif not st.get("remote_exists"):
                status_icon = "[yellow]\u2191 Push needed[/yellow]"
                needs_attention += 1
            elif not st.get("local_exists"):
                status_icon = "[yellow]\u2193 Pull needed[/yellow]"
                needs_attention += 1
            else:
                status_icon = "[red]\u2260 Out of sync[/red]"
                needs_attention += 1

            rows.append([f.project, f.environment, local_ok, remote_ok, status_icon])
            json_data.append(
                {
                    "project": f.project,
                    "environment": f.environment,
                    "local_exists": st.get("local_exists"),
                    "remote_exists": st.get("remote_exists"),
                    "in_sync": st.get("in_sync"),
                    "local_vars": st.get("local_vars", 0),
                    "remote_vars": st.get("remote_vars", 0),
                }
            )
        except Exception as e:
            rows.append([f.project, f.environment, "?", "?", f"[red]Error: {e}[/red]"])
            needs_attention += 1
            json_data.append(
                {
                    "project": f.project,
                    "environment": f.environment,
                    "error": str(e),
                }
            )

    out.table(
        title="Sync Status",
        columns=[
            ("Project", "green"),
            ("Environment", "cyan"),
            ("Local", ""),
            ("Remote", ""),
            ("Status", ""),
        ],
        rows=rows,
        data_for_json=json_data,
    )

    out.text(f"\n[green]{synced} synced[/green], [yellow]{needs_attention} need attention[/yellow]")
