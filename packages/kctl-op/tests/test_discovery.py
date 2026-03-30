"""Tests for kctl_op.core.discovery module."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from kctl_op.core.discovery import (
    EnvFile,
    discover_env_files,
    get_environment_name,
    get_project_name,
    is_excluded,
)


class TestEnvFile:
    """Tests for the EnvFile dataclass."""

    def test_item_title(self):
        """item_title returns 'project/environment' format."""
        env_file = EnvFile(path=Path("/tmp/myproject/.env.prod"), project="myproject", environment="production")
        assert env_file.item_title == "myproject/production"

    def test_item_title_dev(self):
        """item_title works for dev environment."""
        env_file = EnvFile(path=Path("/tmp/webapp/.env"), project="webapp", environment="dev")
        assert env_file.item_title == "webapp/dev"

    def test_tags(self):
        """tags returns list with project: and env: prefixed tags."""
        env_file = EnvFile(path=Path("/tmp/api/.env.staging"), project="api", environment="staging")
        tags = env_file.tags
        assert len(tags) == 2
        assert "project:api" in tags
        assert "env:staging" in tags

    def test_tags_content(self):
        """Tags contain correct project and environment values."""
        env_file = EnvFile(path=Path("/x"), project="frontend", environment="production")
        assert env_file.tags == ["project:frontend", "env:production"]


class TestGetProjectName:
    """Tests for get_project_name."""

    def test_extracts_first_directory(self, tmp_path):
        """Returns the first directory component relative to scan_root."""
        file_path = tmp_path / "myproject" / "subdir" / ".env"
        assert get_project_name(file_path, tmp_path) == "myproject"

    def test_single_level(self, tmp_path):
        """Returns directory name when file is one level deep."""
        file_path = tmp_path / "webapp" / ".env"
        assert get_project_name(file_path, tmp_path) == "webapp"

    def test_deeply_nested(self, tmp_path):
        """Returns the first directory even for deeply nested files."""
        file_path = tmp_path / "project" / "a" / "b" / "c" / ".env"
        assert get_project_name(file_path, tmp_path) == "project"

    def test_file_not_under_scan_root(self):
        """Falls back to parent directory name when not under scan_root."""
        file_path = Path("/other/location/myapp/.env")
        scan_root = Path("/projects")
        assert get_project_name(file_path, scan_root) == "myapp"


class TestGetEnvironmentName:
    """Tests for get_environment_name."""

    def _make_config(self, env_mappings=None, custom_env_pattern=None):
        """Create a mock config object."""
        config = MagicMock()
        config.env_mappings = env_mappings or {
            ".env": "dev",
            ".env.development": "dev",
            ".env.staging": "staging",
            ".env.production": "production",
            ".env.prod": "production",
            ".env.local": "local",
        }
        config.custom_env_pattern = custom_env_pattern or r'\.env\.(?P<prefix>[a-z]+)\.(?P<env>[a-z]+)'
        return config

    def test_env_maps_to_dev(self):
        """'.env' maps to 'dev'."""
        config = self._make_config()
        assert get_environment_name(".env", config) == "dev"

    def test_env_prod_maps_to_production(self):
        """'.env.prod' maps to 'production' via direct mapping."""
        config = self._make_config()
        assert get_environment_name(".env.prod", config) == "production"

    def test_env_staging_maps_to_staging(self):
        """'.env.staging' maps to 'staging' via direct mapping."""
        config = self._make_config()
        assert get_environment_name(".env.staging", config) == "staging"

    def test_env_local_maps_to_local(self):
        """'.env.local' maps to 'local' via direct mapping."""
        config = self._make_config()
        assert get_environment_name(".env.local", config) == "local"

    def test_unmapped_suffix_uses_suffix(self):
        """'.env.test' (not in mappings) returns the suffix 'test'."""
        config = self._make_config()
        assert get_environment_name(".env.test", config) == "test"

    def test_custom_pattern_match(self):
        """Custom pattern '.env.hz.staging' extracts prefix and env."""
        config = self._make_config()
        result = get_environment_name(".env.hz.staging", config)
        assert result == "hz-staging"

    def test_compound_suffix(self):
        """Compound suffix '.env.prod.replica' returns 'prod-replica'."""
        config = self._make_config()
        # Remove .env.prod from mappings so it falls through to suffix logic
        config.env_mappings = {".env": "dev"}
        # Set a pattern that won't match to test the suffix fallback
        config.custom_env_pattern = r'\.env\.(?P<prefix>xx)\.(?P<env>[a-z]+)'
        result = get_environment_name(".env.prod.replica", config)
        assert result == "prod-replica"

    def test_custom_mappings(self):
        """Custom env_mappings override defaults."""
        config = self._make_config(env_mappings={".env.custom": "my-custom-env"})
        assert get_environment_name(".env.custom", config) == "my-custom-env"


class TestIsExcluded:
    """Tests for is_excluded."""

    def test_matches_example_pattern(self, tmp_path):
        """Files matching '**/.env.example' are excluded."""
        file_path = tmp_path / "project" / ".env.example"
        assert is_excluded(file_path, tmp_path, ["**/.env.example"]) is True

    def test_matches_node_modules_pattern(self, tmp_path):
        """Files under node_modules are excluded."""
        file_path = tmp_path / "project" / "node_modules" / "pkg" / ".env"
        assert is_excluded(file_path, tmp_path, ["**/node_modules/**"]) is True

    def test_matches_archived_pattern(self, tmp_path):
        """Files under archived directory are excluded."""
        file_path = tmp_path / "archived" / "old-project" / ".env"
        assert is_excluded(file_path, tmp_path, ["**/archived/**"]) is True

    def test_no_match_normal_env(self, tmp_path):
        """Normal .env files are not excluded by standard patterns."""
        file_path = tmp_path / "project" / ".env"
        patterns = ["**/.env.example", "**/node_modules/**"]
        assert is_excluded(file_path, tmp_path, patterns) is False

    def test_no_match_env_prod(self, tmp_path):
        """Normal .env.prod files are not excluded by standard patterns."""
        file_path = tmp_path / "project" / ".env.prod"
        patterns = ["**/.env.example", "**/.env.*.example"]
        assert is_excluded(file_path, tmp_path, patterns) is False

    def test_matches_directory_pattern(self, tmp_path):
        """Directory/** patterns exclude all files under that directory."""
        file_path = tmp_path / "kodemeio-1password" / "sub" / ".env"
        assert is_excluded(file_path, tmp_path, ["kodemeio-1password/**"]) is True

    def test_empty_patterns_excludes_nothing(self, tmp_path):
        """An empty exclusion list excludes nothing."""
        file_path = tmp_path / "project" / ".env"
        assert is_excluded(file_path, tmp_path, []) is False

    def test_file_not_under_scan_root(self):
        """Files not under scan_root use absolute path for matching."""
        file_path = Path("/other/path/.env.example")
        scan_root = Path("/projects")
        # Should not crash, uses str(file_path) as fallback
        result = is_excluded(file_path, scan_root, [".env.example"])
        assert isinstance(result, bool)


class TestDiscoverEnvFiles:
    """Tests for discover_env_files."""

    def test_finds_env_files(self, tmp_path):
        """Discovers .env files in the scan root directory."""
        # Create project structure
        project_dir = tmp_path / "myproject"
        project_dir.mkdir()
        (project_dir / ".env").write_text("KEY=value\n")
        (project_dir / ".env.prod").write_text("KEY=prod_value\n")

        mock_config = MagicMock()
        mock_config.scan_root = tmp_path
        mock_config.exclude_patterns = []
        mock_config.env_mappings = {".env": "dev", ".env.prod": "production"}
        mock_config.custom_env_pattern = r'\.env\.(?P<prefix>[a-z]+)\.(?P<env>[a-z]+)'

        with patch("kctl_op.core.discovery.get_config", return_value=mock_config):
            result = discover_env_files(tmp_path)

        assert len(result) == 2
        projects = {f.project for f in result}
        assert "myproject" in projects

    def test_excludes_example_files(self, tmp_path):
        """Files with 'example' in the name are excluded."""
        project_dir = tmp_path / "myproject"
        project_dir.mkdir()
        (project_dir / ".env").write_text("KEY=value\n")
        (project_dir / ".env.example").write_text("KEY=example\n")

        mock_config = MagicMock()
        mock_config.scan_root = tmp_path
        mock_config.exclude_patterns = []
        mock_config.env_mappings = {".env": "dev"}
        mock_config.custom_env_pattern = r'\.env\.(?P<prefix>[a-z]+)\.(?P<env>[a-z]+)'

        with patch("kctl_op.core.discovery.get_config", return_value=mock_config):
            result = discover_env_files(tmp_path)

        assert len(result) == 1
        assert result[0].path.name == ".env"

    def test_excludes_tmp_files(self, tmp_path):
        """Files ending with .tmp are excluded."""
        project_dir = tmp_path / "myproject"
        project_dir.mkdir()
        (project_dir / ".env").write_text("KEY=value\n")
        (project_dir / ".env.tmp").write_text("KEY=tmp\n")

        mock_config = MagicMock()
        mock_config.scan_root = tmp_path
        mock_config.exclude_patterns = []
        mock_config.env_mappings = {".env": "dev"}
        mock_config.custom_env_pattern = r'\.env\.(?P<prefix>[a-z]+)\.(?P<env>[a-z]+)'

        with patch("kctl_op.core.discovery.get_config", return_value=mock_config):
            result = discover_env_files(tmp_path)

        assert len(result) == 1

    def test_nonexistent_scan_root_returns_empty(self, tmp_path):
        """A nonexistent scan root returns an empty list."""
        nonexistent = tmp_path / "does_not_exist"

        mock_config = MagicMock()
        mock_config.scan_root = nonexistent
        mock_config.exclude_patterns = []

        with patch("kctl_op.core.discovery.get_config", return_value=mock_config):
            result = discover_env_files(nonexistent)

        assert result == []

    def test_sorted_by_project_and_environment(self, tmp_path):
        """Results are sorted by project name then environment."""
        for name in ["zebra", "alpha"]:
            d = tmp_path / name
            d.mkdir()
            (d / ".env").write_text("X=1\n")

        mock_config = MagicMock()
        mock_config.scan_root = tmp_path
        mock_config.exclude_patterns = []
        mock_config.env_mappings = {".env": "dev"}
        mock_config.custom_env_pattern = r'\.env\.(?P<prefix>[a-z]+)\.(?P<env>[a-z]+)'

        with patch("kctl_op.core.discovery.get_config", return_value=mock_config):
            result = discover_env_files(tmp_path)

        projects = [f.project for f in result]
        assert projects == sorted(projects)
