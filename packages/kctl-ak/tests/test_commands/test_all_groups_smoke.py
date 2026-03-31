"""Smoke tests for ALL command groups — verify --help works for every group."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from kctl_ak.cli import app

runner = CliRunner()

ALL_GROUPS = [
    "users",
    "groups",
    "apps",
    "providers",
    "flows",
    "audit",
    "sessions",
    "tokens",
    "blueprints",
    "maintenance",
    "setup",
    "health",
    "dashboard",
    "config",
    "mail",
    "policies",
    "stages",
    "property-mappings",
    "certificates",
    "outposts",
    "brands",
    "notifications",
    "system",
]


@pytest.mark.parametrize("group", ALL_GROUPS)
def test_group_help(group: str) -> None:
    """Every command group must respond to --help with exit code 0."""
    result = runner.invoke(app, [group, "--help"])
    assert result.exit_code == 0, f"{group} --help failed: {result.output}"
