"""Tests for provision CLI commands."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_ak.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def provision_config_file(tmp_path: Path) -> Path:
    config = tmp_path / "provision-config.yaml"
    config.write_text(
        textwrap.dedent("""\
        mailcow:
          api_url: https://mail.kodeme.io
        defaults:
          mailbox_quota: 1073741824
        companies:
          mac:
            domain: mandiriagro.com
            hrms: mac-odoo-hrms.mandiriagro.com
            odoo_targets:
              - mac-odoo-dist.mandiriagro.com
    """)
    )
    return config


def test_provision_onboard_dry_run(runner: CliRunner, provision_config_file: Path) -> None:
    with (
        patch("kctl_ak.commands.provision._resolve_config_path", return_value=provision_config_file),
        patch("kctl_ak.commands.provision.ProvisionChain") as MockChain,
    ):
        from kctl_ak.models.provision import ChainResult, StepStatus

        mock_result = ChainResult(email="john@mandiriagro.com", action="onboard")
        mock_result.add("Authentik user", StepStatus.SKIPPED, "dry-run")
        MockChain.return_value.onboard.return_value = mock_result

        result = runner.invoke(
            app,
            [
                "--profile",
                "default",
                "--token",
                "test",
                "--url",
                "http://localhost:9000",
                "provision",
                "onboard",
                "john@mandiriagro.com",
                "--name",
                "John Doe",
                "--company",
                "mac",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0


def test_provision_offboard_dry_run(runner: CliRunner, provision_config_file: Path) -> None:
    with (
        patch("kctl_ak.commands.provision._resolve_config_path", return_value=provision_config_file),
        patch("kctl_ak.commands.provision.ProvisionChain") as MockChain,
    ):
        from kctl_ak.models.provision import ChainResult

        mock_result = ChainResult(email="john@mandiriagro.com", action="offboard")
        MockChain.return_value.offboard.return_value = mock_result

        result = runner.invoke(
            app,
            [
                "--profile",
                "default",
                "--token",
                "test",
                "--url",
                "http://localhost:9000",
                "provision",
                "offboard",
                "john@mandiriagro.com",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
