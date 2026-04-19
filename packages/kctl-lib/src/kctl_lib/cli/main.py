"""Typer entry point for kctl-profiles."""

from __future__ import annotations

import typer

from kctl_lib.cli.commands.current import current_profile
from kctl_lib.cli.commands.list_cmd import list_profiles
from kctl_lib.cli.commands.migrate import migrate
from kctl_lib.cli.commands.show import show_profile

app = typer.Typer(
    name="kctl-profiles",
    help="Inspect and manage kctl-* profiles in ~/.config/kodemeio/config.yaml.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Inspect and manage kctl-* profiles in ~/.config/kodemeio/config.yaml."""


app.command("list")(list_profiles)
app.command("show")(show_profile)
app.command("current")(current_profile)
app.command("migrate")(migrate)


if __name__ == "__main__":
    app()
