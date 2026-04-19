"""Typer entry point for kctl-profiles."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="kctl-profiles",
    help="Inspect and manage kctl-* profiles in ~/.config/kodemeio/config.yaml.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Inspect and manage kctl-* profiles in ~/.config/kodemeio/config.yaml."""


if __name__ == "__main__":
    app()
