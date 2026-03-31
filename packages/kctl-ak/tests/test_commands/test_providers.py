"""Tests for providers commands."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_ak.cli import app

runner = CliRunner()


class TestProvidersHelp:
    def test_providers_list_help(self) -> None:
        result = runner.invoke(app, ["providers", "list", "--help"])
        assert result.exit_code == 0

    def test_providers_oauth2_help(self) -> None:
        result = runner.invoke(app, ["providers", "oauth2", "--help"])
        assert result.exit_code == 0

    def test_providers_ldap_help(self) -> None:
        result = runner.invoke(app, ["providers", "ldap", "--help"])
        assert result.exit_code == 0

    def test_providers_saml_help(self) -> None:
        result = runner.invoke(app, ["providers", "saml", "--help"])
        assert result.exit_code == 0

    def test_providers_proxy_help(self) -> None:
        result = runner.invoke(app, ["providers", "proxy", "--help"])
        assert result.exit_code == 0
