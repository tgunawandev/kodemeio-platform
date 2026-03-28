"""kctl-common: shared core library for kctl-* CLI tools.

Public API:
    - exceptions: KctlError hierarchy
    - output: Output class (pretty/json/csv/yaml)
    - config: Profile/config framework
    - callbacks: AppContextBase
    - runner: run(), run_quiet(), git helpers
    - plugins: KctlPlugin protocol + discovery
    - history: HistoryStore
    - testing: Test fixtures (optional dependency)
"""

__version__ = "0.1.0"

from kctl_common.callbacks import AppContextBase
from kctl_common.exceptions import (
    APIError,
    AppNotFoundError,
    AuthenticationError,
    CommandError,
    ConfigError,
    ConnectionError,
    DockerError,
    KctlError,
    NotFoundError,
    ValidationError,
)
from kctl_common.output import Output

__all__ = [
    "APIError",
    "AppContextBase",
    "AppNotFoundError",
    "AuthenticationError",
    "CommandError",
    "ConfigError",
    "ConnectionError",
    "DockerError",
    "KctlError",
    "NotFoundError",
    "Output",
    "ValidationError",
]


def handle_cli_error(e: KctlError) -> None:
    """Standardized error handler for CLI _run() entry points.

    Usage in each CLI's cli.py:
        try:
            app()
        except KctlError as e:
            handle_cli_error(e)
    """
    import typer

    typer.echo(f"Error: {e}", err=True)
    raise typer.Exit(1) from e
