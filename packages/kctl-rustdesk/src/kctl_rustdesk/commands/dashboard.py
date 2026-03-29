"""Dashboard overview commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_rustdesk.core.callbacks import AppContext

app = typer.Typer(help="System overview dashboard.")


@app.command("show")
def show(
    ctx: typer.Context,
    compact: Annotated[bool, typer.Option("--compact", help="Compact output")] = False,
) -> None:
    """Show system overview dashboard."""
    c: AppContext = ctx.obj
    out = c.output
    ex = c.executor

    hbbs_running = ex.container_running("hbbs")
    hbbr_running = ex.container_running("hbbr")

    hbbs_status = "[green]running[/green]" if hbbs_running else "[red]stopped[/red]"
    hbbr_status = "[green]running[/green]" if hbbr_running else "[red]stopped[/red]"

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Services",
            [
                ("hbbs (ID server)", hbbs_status),
                ("hbbr (Relay)", hbbr_status),
            ],
        ),
    ]

    if not compact:
        hbbs_stats = ex.get_container_stats("hbbs")
        hbbr_stats = ex.get_container_stats("hbbr")
        sections.append(
            (
                "Resources",
                [
                    ("hbbs CPU", hbbs_stats["cpu"]),
                    ("hbbs Memory", f"{hbbs_stats['mem_usage']} ({hbbs_stats['mem_pct']})"),
                    ("hbbr CPU", hbbr_stats["cpu"]),
                    ("hbbr Memory", f"{hbbr_stats['mem_usage']} ({hbbr_stats['mem_pct']})"),
                ],
            )
        )

    try:
        public_key = ex.get_public_key()
    except Exception:
        public_key = "(unavailable)"

    key_display = public_key[:20] + "..." if len(public_key) > 20 else public_key
    sections.append(
        (
            "Configuration",
            [
                ("Domain", ex.config.domain),
                ("ID Server", f"{ex.config.domain}:21116"),
                ("Relay Server", f"{ex.config.domain}:21117"),
                ("Public Key", key_display),
            ],
        )
    )

    if not compact:
        try:
            peer_count = ex.query_db_scalar("SELECT count(*) FROM peer;")
            user_count = ex.query_db_scalar("SELECT count(*) FROM user;")
            group_count = ex.query_db_scalar("SELECT count(*) FROM grp;")
            sections.append(
                (
                    "Database",
                    [
                        ("Peers", peer_count),
                        ("Users", user_count),
                        ("Groups", group_count),
                    ],
                )
            )
        except Exception:
            sections.append(("Database", [("Status", "[yellow]unavailable[/yellow]")]))

    out.detail(
        "RustDesk Dashboard",
        sections,
        data_for_json={
            "services": {"hbbs": hbbs_running, "hbbr": hbbr_running},
            "config": {"domain": ex.config.domain, "public_key": public_key},
        },
    )
