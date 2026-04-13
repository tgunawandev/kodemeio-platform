"""Shell completions command for kctl-mm."""

from __future__ import annotations

from typing import Annotated

import typer

app = typer.Typer(help="Generate or install shell completions.", no_args_is_help=False, invoke_without_command=True)


@app.callback(invoke_without_command=True)
def completions(
    ctx: typer.Context,
    shell: Annotated[str, typer.Argument(help="Shell type: zsh, bash, fish")] = "zsh",
    install: Annotated[bool, typer.Option("--install", help="Install completions")] = False,
) -> None:
    """Generate or install shell completions."""
    if ctx.invoked_subcommand is not None:
        return
    from kctl_lib.completions import get_completion_script, install_completions

    if install:
        path = install_completions("kctl-mm", shell)
        if path:
            typer.echo(f"Completions installed to {path}")
        else:
            typer.echo(f"Could not install completions for {shell}", err=True)
            raise typer.Exit(code=1)
    else:
        script = get_completion_script("kctl-mm", shell)
        typer.echo(script)
