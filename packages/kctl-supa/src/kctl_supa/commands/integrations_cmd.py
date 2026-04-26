"""Integration management commands for kctl-supa."""

from __future__ import annotations

import typer
from rich import print as rprint
from rich.table import Table

from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.docker import DockerOps
from kctl_supa.core.exceptions import DockerError

app = typer.Typer(help="Manage integrations (Cron, Wrappers, GraphQL).")


def _get_docker(actx: AppContext) -> DockerOps:
    return DockerOps(actx.config)


def _run_psql(actx: AppContext, query: str) -> str:
    out = actx.output
    try:
        docker = _get_docker(actx)
        result = docker.psql(query)
        docker.close()
        return result
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc


@app.command()
def status(ctx: typer.Context) -> None:
    """Show status of available integrations."""
    actx: AppContext = ctx.obj

    docker = _get_docker(actx)
    integrations: list[tuple[str, str, str]] = []

    extensions_to_check = [
        ("pg_cron", "Cron", "Scheduled jobs"),
        ("pg_net", "HTTP/Webhooks", "HTTP requests from SQL"),
        ("pg_graphql", "GraphQL", "GraphQL API"),
        ("pgsodium", "Vault", "Encrypted secrets"),
        ("wrappers", "Wrappers", "Foreign data wrappers"),
        ("pgmq", "Queues", "Message queues"),
    ]

    for ext_name, label, desc in extensions_to_check:
        try:
            result = docker.psql(
                f"SELECT 1 FROM pg_extension WHERE extname = '{ext_name}'",
            )
            installed = any(line.strip() == "1" for line in result.splitlines())
            status_str = "[green]installed[/green]" if installed else "[dim]not installed[/dim]"
        except DockerError:
            status_str = "[red]error[/red]"
        integrations.append((label, desc, status_str))

    docker.close()

    table = Table(title="Integrations", show_header=True, header_style="bold cyan")
    table.add_column("Integration", style="cyan")
    table.add_column("Description")
    table.add_column("Status")
    for label, desc, status_str in integrations:
        table.add_row(label, desc, status_str)
    rprint(table)


@app.command()
def graphql(ctx: typer.Context) -> None:
    """Show GraphQL schema statistics."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("GraphQL types in graphql_public schema:")
    result = _run_psql(
        actx,
        "SELECT routine_name, routine_type "
        "FROM information_schema.routines "
        "WHERE routine_schema = 'graphql_public' "
        "ORDER BY routine_name",
    )
    typer.echo(result)
