"""Tests for kctl_op.core.op_config module."""

import pytest
from pathlib import Path

from kctl_op.core.op_config import Config


class TestConfigDefaults:
    """Tests for Config default values."""

    def test_default_vault(self, tmp_path):
        """Default vault is 'kodemeio-secrets'."""
        config_file = tmp_path / "nonexistent.yaml"
        config = Config(config_path=config_file)
        assert config.vault == "kodemeio-secrets"

    def test_default_scan_root(self, tmp_path):
        """Default scan_root is the expected path."""
        config_file = tmp_path / "nonexistent.yaml"
        config = Config(config_path=config_file)
        assert isinstance(config.scan_root, Path)

    def test_default_exclude_patterns(self, tmp_path):
        """Default exclude_patterns contains expected patterns."""
        config_file = tmp_path / "nonexistent.yaml"
        config = Config(config_path=config_file)
        patterns = config.exclude_patterns
        assert "**/.env.example" in patterns
        assert "**/node_modules/**" in patterns
        assert "**/archived/**" in patterns

    def test_default_env_mappings(self, tmp_path):
        """Default env_mappings contains standard mappings."""
        config_file = tmp_path / "nonexistent.yaml"
        config = Config(config_path=config_file)
        mappings = config.env_mappings
        assert mappings[".env"] == "dev"
        assert mappings[".env.prod"] == "production"
        assert mappings[".env.staging"] == "staging"
        assert mappings[".env.local"] == "local"
        assert mappings[".env.production"] == "production"
        assert mappings[".env.development"] == "dev"

    def test_default_custom_env_pattern(self, tmp_path):
        """Default custom_env_pattern is set."""
        config_file = tmp_path / "nonexistent.yaml"
        config = Config(config_path=config_file)
        assert config.custom_env_pattern == r"\.env\.(?P<prefix>[a-z]+)\.(?P<env>[a-z]+)"

    def test_default_backup_enabled(self, tmp_path):
        """Default backup_enabled is True."""
        config_file = tmp_path / "nonexistent.yaml"
        config = Config(config_path=config_file)
        assert config.backup_enabled is True

    def test_default_max_backups(self, tmp_path):
        """Default max_backups is 10."""
        config_file = tmp_path / "nonexistent.yaml"
        config = Config(config_path=config_file)
        assert config.max_backups == 10


class TestConfigFromYaml:
    """Tests for loading Config from a YAML file."""

    def test_loads_vault_from_yaml(self, tmp_path):
        """Vault name is loaded from YAML config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("op:\n  vault: my-custom-vault\n")
        config = Config(config_path=config_file)
        assert config.vault == "my-custom-vault"

    def test_loads_scan_root_from_yaml(self, tmp_path):
        """scan_root is loaded from YAML config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("scan_root: /custom/path/to/projects\n")
        config = Config(config_path=config_file)
        assert config.scan_root == Path("/custom/path/to/projects")

    def test_loads_exclude_patterns_from_yaml(self, tmp_path):
        """exclude_patterns are loaded from YAML config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("exclude_patterns:\n  - '**/.env.test'\n  - '**/vendor/**'\n")
        config = Config(config_path=config_file)
        patterns = config.exclude_patterns
        assert len(patterns) == 2
        assert "**/.env.test" in patterns
        assert "**/vendor/**" in patterns

    def test_loads_env_mappings_from_yaml(self, tmp_path):
        """env_mappings are loaded from YAML config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("env_mappings:\n  .env: development\n  .env.live: live\n")
        config = Config(config_path=config_file)
        mappings = config.env_mappings
        assert mappings[".env"] == "development"
        assert mappings[".env.live"] == "live"

    def test_loads_backup_settings_from_yaml(self, tmp_path):
        """Backup settings are loaded from YAML config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("backup:\n  enabled: false\n  directory: /tmp/backups\n  max_backups: 5\n")
        config = Config(config_path=config_file)
        assert config.backup_enabled is False
        assert config.backup_directory == Path("/tmp/backups")
        assert config.max_backups == 5

    def test_missing_file_uses_defaults(self, tmp_path):
        """A missing config file does not raise an error and uses defaults."""
        config_file = tmp_path / "missing.yaml"
        config = Config(config_path=config_file)
        # Should not raise, and should have defaults
        assert config.vault == "kodemeio-secrets"
        assert isinstance(config.exclude_patterns, list)
        assert isinstance(config.env_mappings, dict)

    def test_empty_yaml_uses_defaults(self, tmp_path):
        """An empty YAML file uses defaults."""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")
        config = Config(config_path=config_file)
        assert config.vault == "kodemeio-secrets"

    def test_partial_yaml_merges_with_defaults(self, tmp_path):
        """A partial YAML file uses defaults for missing keys."""
        config_file = tmp_path / "partial.yaml"
        config_file.write_text("op:\n  vault: partial-vault\n")
        config = Config(config_path=config_file)
        assert config.vault == "partial-vault"
        # Other properties should use defaults
        assert isinstance(config.exclude_patterns, list)
        assert len(config.exclude_patterns) > 0
