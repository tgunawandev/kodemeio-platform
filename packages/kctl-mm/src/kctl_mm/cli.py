"""kctl-mm main CLI entry point."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import handle_cli_error
from kctl_lib.exceptions import KctlError

from kctl_mm import __version__
from kctl_mm.core.callbacks import AppContext

app = typer.Typer(
    name="kctl-mm",
    help="Kodemeio Mattermost CLI - manage Mattermost Team Edition.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-mm {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q")] = False,
    output_format: Annotated[str, typer.Option("--format", "-f")] = "pretty",
    no_header: Annotated[bool, typer.Option("--no-header")] = False,
    profile: Annotated[str | None, typer.Option("--profile", "-p")] = None,
    version: Annotated[bool | None, typer.Option("--version", "-V", callback=version_callback, is_eager=True)] = None,
) -> None:
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        format="json" if json_output else output_format,
        no_header=no_header,
    )


def _register() -> None:
    from kctl_mm.commands import (
        audit,
        bots,
        channels,
        completions,
        config_cmd,
        dashboard,
        deploy,
        doctor,
        health,
        import_export,
        integrations,
        jobs,
        logs,
        maintenance,
        mm_config,
        permissions,
        plugins,
        posts,
        self_update,
        skill_cmd,
        status,
        teams,
        users,
        webhooks,
    )

    mapping = [
        ("config", config_cmd),
        ("doctor", doctor),
        ("self-update", self_update),
        ("completions", completions),
        ("skill", skill_cmd),
        ("status", status),
        ("logs", logs),
        ("deploy", deploy),
        ("health", health),
        ("dashboard", dashboard),
        ("users", users),
        ("teams", teams),
        ("channels", channels),
        ("permissions", permissions),
        ("posts", posts),
        ("mm-config", mm_config),
        ("maintenance", maintenance),
        ("webhooks", webhooks),
        ("bots", bots),
        ("plugins", plugins),
        ("integrations", integrations),
        ("jobs", jobs),
        ("audit", audit),
        ("import-export", import_export),
    ]
    for name, module in mapping:
        app.add_typer(module.app, name=name)


_register()


def _run() -> None:
    try:
        app()
    except KctlError as exc:
        handle_cli_error(exc)


if __name__ == "__main__":
    _run()
