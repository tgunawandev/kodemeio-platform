"""Tests for name-to-ID resolution helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kctl_dokploy.core.exceptions import NotFoundError
from kctl_dokploy.core.resolve import (
    clear_cache,
    resolve_application,
    resolve_compose,
    resolve_project,
    resolve_server,
)


@pytest.fixture(autouse=True)
def _clear_resolve_cache() -> None:
    """Clear the resolve cache before each test."""
    clear_cache()


@pytest.fixture
def client(sample_projects: list[dict], sample_servers: list[dict]) -> MagicMock:
    mock = MagicMock()

    def get_side_effect(endpoint: str, **kwargs: object) -> list[dict]:
        if "project" in endpoint:
            return sample_projects
        if "server" in endpoint:
            return sample_servers
        return []

    mock.get.side_effect = get_side_effect
    return mock


class TestResolveProject:
    def test_resolve_by_name(self, client: MagicMock) -> None:
        result = resolve_project(client, "kodemeio")
        assert result == "proj-abc-123"

    def test_resolve_by_name_case_insensitive(self, client: MagicMock) -> None:
        result = resolve_project(client, "Kodemeio")
        assert result == "proj-abc-123"

    def test_resolve_by_id(self, client: MagicMock) -> None:
        result = resolve_project(client, "proj-abc-123")
        assert result == "proj-abc-123"

    def test_resolve_by_partial_id(self, client: MagicMock) -> None:
        result = resolve_project(client, "proj-abc")
        assert result == "proj-abc-123"

    def test_not_found_raises(self, client: MagicMock) -> None:
        with pytest.raises(NotFoundError, match="project"):
            resolve_project(client, "nonexistent")

    def test_caches_result(self, client: MagicMock) -> None:
        resolve_project(client, "kodemeio")
        resolve_project(client, "kodemeio")
        # Should only call API once due to cache
        assert client.get.call_count == 1


class TestResolveCompose:
    def test_resolve_by_name(self, client: MagicMock) -> None:
        result = resolve_compose(client, "web-app")
        assert result == "comp-xyz-789"

    def test_resolve_by_id(self, client: MagicMock) -> None:
        result = resolve_compose(client, "comp-xyz-789")
        assert result == "comp-xyz-789"

    def test_resolve_with_project_filter(self, client: MagicMock) -> None:
        result = resolve_compose(client, "web-app", project="kodemeio")
        assert result == "comp-xyz-789"

    def test_not_found_raises(self, client: MagicMock) -> None:
        with pytest.raises(NotFoundError, match="compose"):
            resolve_compose(client, "no-such-service")


class TestResolveApplication:
    def test_resolve_by_name(self, client: MagicMock) -> None:
        result = resolve_application(client, "frontend")
        assert result == "app-111-222"

    def test_not_found_raises(self, client: MagicMock) -> None:
        with pytest.raises(NotFoundError, match="application"):
            resolve_application(client, "nonexistent")


class TestResolveServer:
    def test_resolve_by_name(self, client: MagicMock) -> None:
        result = resolve_server(client, "hetzner-main")
        assert result == "srv-001"

    def test_resolve_by_id(self, client: MagicMock) -> None:
        result = resolve_server(client, "srv-002")
        assert result == "srv-002"

    def test_not_found_raises(self, client: MagicMock) -> None:
        with pytest.raises(NotFoundError, match="server"):
            resolve_server(client, "nonexistent")
