"""Tests for GitHubClient."""

from __future__ import annotations

import pytest
from kctl_common.exceptions import ConfigError

from kctl_github.core.client import GitHubClient, _parse_next_link


class TestGitHubClient:
    def test_requires_credential(self):
        with pytest.raises(ConfigError, match="credential"):
            GitHubClient(credential="")

    def test_init_sets_headers(self):
        client = GitHubClient(credential="ghp_test123")
        assert client._client.headers["Authorization"] == "Bearer ghp_test123"
        assert "application/vnd.github+json" in client._client.headers["Accept"]
        client.close()

    def test_default_organization(self):
        client = GitHubClient(credential="ghp_test123")
        assert client.organization == "tgunawandev"
        assert client.repo_prefix == "kodemeio-"
        client.close()

    def test_custom_organization(self):
        client = GitHubClient(credential="ghp_test123", organization="myorg", repo_prefix="myapp-")
        assert client.organization == "myorg"
        assert client.repo_prefix == "myapp-"
        client.close()


class TestParseNextLink:
    def test_parses_next_url(self):
        header = (
            '<https://api.github.com/user/repos?page=2>; rel="next", '
            '<https://api.github.com/user/repos?page=5>; rel="last"'
        )
        assert _parse_next_link(header) == "https://api.github.com/user/repos?page=2"

    def test_returns_none_without_next(self):
        header = '<https://api.github.com/user/repos?page=5>; rel="last"'
        assert _parse_next_link(header) is None

    def test_returns_none_for_empty(self):
        assert _parse_next_link("") is None
