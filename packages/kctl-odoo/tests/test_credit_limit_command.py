"""Tests for the credit-limit-proposal subcommand."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_odoo.commands.partners import app as partners_app


def test_credit_limit_proposal_command_registered() -> None:
    """The credit-limit-proposal command is registered on the partners group."""
    runner = CliRunner()
    result = runner.invoke(partners_app, ["credit-limit-proposal", "--help"])
    assert result.exit_code == 0
    assert "credit-limit-proposal" in result.stdout.lower() or "Propose credit limits" in result.stdout
