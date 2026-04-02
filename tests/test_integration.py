"""Cross-package integration tests for the kodemeio-platform workspace.

Verifies that kctl-lib works correctly when imported by all 22 downstream CLI
packages. These tests run at the workspace root and exercise the real installed
packages — they do not mock imports.

Test groups
-----------
1. Import tests          — every package can be imported without errors.
2. Version consistency   — every package exports __version__ as a string.
3. CLI app loadable      — every package's cli.py has an `app` that serves --help.
4. kctl-lib re-exports   — core.exceptions re-exports KctlError + ConfigError.
5. SERVICE_KEY defined   — core.config has a non-empty SERVICE_KEY string.
"""

from __future__ import annotations

import importlib

import pytest
from typer.testing import CliRunner

from tests.conftest import ALL_PACKAGES, PACKAGES_WITH_CORE_EXCEPTIONS

# ---------------------------------------------------------------------------
# 1. Import tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("package", ALL_PACKAGES)
def test_package_importable(package: str) -> None:
    """Every CLI package can be imported without raising an exception.

    A failure here typically means a missing dependency, a broken __init__.py,
    or an import-time side-effect error.
    """
    importlib.import_module(package)


# ---------------------------------------------------------------------------
# 2. Version consistency
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("package", ALL_PACKAGES)
def test_package_has_version(package: str) -> None:
    """Every CLI package exports __version__ as a non-empty string.

    This ensures the package is properly built and its version metadata is
    accessible at runtime, which kctl-lib's self_update module depends on.
    """
    mod = importlib.import_module(package)
    assert hasattr(mod, "__version__"), f"{package} is missing __version__"
    assert isinstance(mod.__version__, str), (
        f"{package}.__version__ must be str, got {type(mod.__version__)}"
    )
    assert mod.__version__, f"{package}.__version__ must not be empty"


# ---------------------------------------------------------------------------
# 3. CLI app loadable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("package", ALL_PACKAGES)
def test_cli_help(package: str) -> None:
    """Every package's cli.py exposes a Typer `app` that returns exit code 0
    for --help.

    This exercises the full Typer command tree construction without needing a
    real server connection. A non-zero exit code or missing `app` attribute
    indicates a broken command registration or import-time crash in a command
    module.
    """
    cli_mod = importlib.import_module(f"{package}.cli")
    assert hasattr(cli_mod, "app"), f"{package}.cli is missing `app`"

    runner = CliRunner()
    result = runner.invoke(cli_mod.app, ["--help"])
    assert result.exit_code == 0, (
        f"{package}.cli --help exited with {result.exit_code}.\n"
        f"Output:\n{result.output}\n"
        f"Exception: {result.exception}"
    )


# ---------------------------------------------------------------------------
# 4. kctl-lib re-exports
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("package", PACKAGES_WITH_CORE_EXCEPTIONS)
def test_exceptions_reexport(package: str) -> None:
    """Every package that provides core.exceptions re-exports KctlError and
    ConfigError so that downstream callers can catch them via the package's
    own namespace rather than importing kctl_lib directly.

    kctl_rustdesk and kctl_rmm import directly from kctl_lib and therefore do
    not have a core/exceptions module — they are excluded from this test via
    PACKAGES_WITH_CORE_EXCEPTIONS.
    """
    exc_mod = importlib.import_module(f"{package}.core.exceptions")

    assert hasattr(exc_mod, "KctlError"), (
        f"{package}.core.exceptions does not export KctlError"
    )
    assert hasattr(exc_mod, "ConfigError"), (
        f"{package}.core.exceptions does not export ConfigError"
    )

    # The exported names must be actual exception classes.
    assert issubclass(exc_mod.KctlError, BaseException), (
        f"{package}.core.exceptions.KctlError is not an exception class"
    )
    assert issubclass(exc_mod.ConfigError, exc_mod.KctlError), (
        f"{package}.core.exceptions.ConfigError must be a subclass of KctlError"
    )


# ---------------------------------------------------------------------------
# 5. Config SERVICE_KEY defined
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("package", ALL_PACKAGES)
def test_service_key(package: str) -> None:
    """Every package's core.config declares a non-empty SERVICE_KEY string.

    SERVICE_KEY is the profile namespace under which each CLI stores its
    config (e.g. 'grafana', 'dokploy'). An absent or empty key would silently
    corrupt the shared ~/.config/kodemeio/config.yaml.
    """
    config_mod = importlib.import_module(f"{package}.core.config")

    assert hasattr(config_mod, "SERVICE_KEY"), (
        f"{package}.core.config is missing SERVICE_KEY"
    )
    assert isinstance(config_mod.SERVICE_KEY, str), (
        f"{package}.core.config.SERVICE_KEY must be str, "
        f"got {type(config_mod.SERVICE_KEY)}"
    )
    assert config_mod.SERVICE_KEY, (
        f"{package}.core.config.SERVICE_KEY must not be empty"
    )
