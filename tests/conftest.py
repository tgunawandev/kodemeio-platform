"""Shared fixtures for workspace-level integration tests."""

from __future__ import annotations

import pytest

# All 21 downstream CLI packages in the workspace (excludes kctl-lib itself).
ALL_PACKAGES = [
    "kctl_ak",
    "kctl_api",
    "kctl_cf",
    "kctl_claude",
    "kctl_claw",
    "kctl_dokploy",
    "kctl_github",
    "kctl_glitchtip",
    "kctl_grafana",
    "kctl_hz",
    "kctl_linear",
    "kctl_notion",
    "kctl_odoo",
    "kctl_op",
    "kctl_pg",
    "kctl_react",
    "kctl_rmm",
    "kctl_rustdesk",
    "kctl_sentry",
    "kctl_telegram",
    "kctl_waha",
]

# Packages that have a core/exceptions.py module.
# kctl_rustdesk and kctl_rmm import directly from kctl_lib rather than
# providing a local re-export module, so they are excluded here.
PACKAGES_WITH_CORE_EXCEPTIONS = [
    p for p in ALL_PACKAGES if p not in {"kctl_rustdesk", "kctl_rmm"}
]


@pytest.fixture(params=ALL_PACKAGES)
def package(request: pytest.FixtureRequest) -> str:
    """Parametrized fixture yielding every CLI package name."""
    return request.param  # type: ignore[return-value]


@pytest.fixture(params=PACKAGES_WITH_CORE_EXCEPTIONS)
def package_with_exceptions(request: pytest.FixtureRequest) -> str:
    """Parametrized fixture for packages that expose core.exceptions."""
    return request.param  # type: ignore[return-value]
