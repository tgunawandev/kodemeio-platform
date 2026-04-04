"""Smoke tests — verify CLI loads and help works."""

from typer.testing import CliRunner

from kctl_mailcow.cli import app

runner = CliRunner()


class TestCLIHelp:
    def test_main_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "kctl-mailcow" in result.output.lower() or "mailcow" in result.output.lower()

    def test_version(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestCommandGroupsRegistered:
    """Verify all 31 command groups appear in help."""

    GROUPS = [
        # Original 16
        "domains",
        "mailboxes",
        "aliases",
        "dkim",
        "queue",
        "logs",
        "ratelimits",
        "quarantine",
        "status",
        "health",
        "dashboard",
        "sync-jobs",
        "fwdhost",
        "config",
        "tls",
        "resources",
        # Phase 1: Authentik integration
        "identity-provider",
        "oauth2-clients",
        "provision",
        # Phase 2: Security & compliance
        "fail2ban",
        "policies",
        "app-passwords",
        "password-policy",
        "domain-admins",
        "filters",
        # Phase 3: Routing & advanced
        "transports",
        "relay-hosts",
        "bcc-maps",
        "alias-domains",
        "recipient-maps",
        "rspamd",
    ]

    def test_all_groups_in_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for group in self.GROUPS:
            assert group in result.output, f"Command group '{group}' not found in help output"


class TestSubcommandHelp:
    """Spot-check a few subcommands load without error."""

    def test_domains_list_help(self) -> None:
        result = runner.invoke(app, ["domains", "list", "--help"])
        assert result.exit_code == 0

    def test_config_init_help(self) -> None:
        result = runner.invoke(app, ["config", "init", "--help"])
        assert result.exit_code == 0

    def test_mailboxes_list_help(self) -> None:
        result = runner.invoke(app, ["mailboxes", "list", "--help"])
        assert result.exit_code == 0

    def test_health_help(self) -> None:
        result = runner.invoke(app, ["health", "--help"])
        assert result.exit_code == 0
