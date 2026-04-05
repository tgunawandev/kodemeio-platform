"""Shared test configuration and fixtures."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from kctl_lib.output import Output
from typer.testing import CliRunner

from kctl_notion.core.callbacks import AppContext
from kctl_notion.core.client import NotionClient
from kctl_notion.core.config import ServiceConfig


@pytest.fixture(autouse=True)
def _mock_config():
    """Auto-mock config layer so CLI commands get a valid token."""
    with (
        patch(
            "kctl_notion.core.callbacks.get_service_config",
            return_value=ServiceConfig(token="ntn_test_token_123"),
        ),
        patch(
            "kctl_notion.core.callbacks.resolve_active_profile_name",
            return_value="default",
        ),
    ):
        yield


@pytest.fixture
def mock_client(httpx_mock):
    """Create a NotionClient pointing at the mock."""
    client = NotionClient(credential="ntn_test_token_123")
    yield client
    client.close()


@pytest.fixture
def mock_app_context(mock_client):
    """Create an AppContext with a mocked client."""
    ctx = AppContext(json_mode=False, quiet=False)
    ctx._client = mock_client
    return ctx


@pytest.fixture
def json_app_context(mock_client):
    """Create an AppContext with JSON output mode."""
    ctx = AppContext(json_mode=True, quiet=False)
    ctx._client = mock_client
    return ctx


@pytest.fixture
def mock_notion_me():
    """Standard /users/me response."""
    return {
        "object": "user",
        "id": "bot-user-id-1234",
        "type": "bot",
        "name": "Test Integration",
        "bot": {
            "owner": {"type": "workspace"},
            "workspace_name": "Test Workspace",
        },
    }


@pytest.fixture
def mock_search_results():
    """Standard search results."""
    return {
        "object": "list",
        "results": [
            {
                "object": "page",
                "id": "page-1234-5678",
                "created_time": "2026-01-15T10:00:00.000Z",
                "last_edited_time": "2026-03-20T14:30:00.000Z",
                "parent": {"type": "workspace", "workspace": True},
                "properties": {
                    "title": {
                        "id": "title",
                        "type": "title",
                        "title": [{"type": "text", "plain_text": "Meeting Notes"}],
                    }
                },
                "url": "https://www.notion.so/Meeting-Notes-page1234",
            },
        ],
        "has_more": False,
        "next_cursor": None,
    }


@pytest.fixture
def mock_database():
    """Standard database object."""
    return {
        "object": "database",
        "id": "db-1234-5678",
        "title": [{"type": "text", "plain_text": "Project Tracker"}],
        "created_time": "2026-01-01T00:00:00.000Z",
        "last_edited_time": "2026-03-25T12:00:00.000Z",
        "url": "https://www.notion.so/db1234",
        "properties": {
            "Name": {"id": "title", "type": "title", "title": {}},
            "Status": {"id": "status", "type": "select", "select": {"options": []}},
            "Priority": {"id": "priority", "type": "number", "number": {"format": "number"}},
        },
    }


@pytest.fixture
def mock_database_query_results():
    """Standard database query results."""
    return {
        "object": "list",
        "results": [
            {
                "object": "page",
                "id": "row-1234-5678",
                "properties": {
                    "Name": {"type": "title", "title": [{"plain_text": "Task Alpha"}]},
                    "Status": {"type": "select", "select": {"name": "In Progress"}},
                    "Priority": {"type": "number", "number": 1},
                },
            },
            {
                "object": "page",
                "id": "row-abcd-efgh",
                "properties": {
                    "Name": {"type": "title", "title": [{"plain_text": "Task Beta"}]},
                    "Status": {"type": "select", "select": {"name": "Done"}},
                    "Priority": {"type": "number", "number": 2},
                },
            },
        ],
        "has_more": False,
        "next_cursor": None,
    }


@pytest.fixture
def mock_blocks():
    """Standard block children response."""
    return {
        "object": "list",
        "results": [
            {
                "object": "block",
                "id": "block-1111",
                "type": "heading_1",
                "has_children": False,
                "heading_1": {
                    "rich_text": [{"type": "text", "plain_text": "Introduction"}],
                },
            },
            {
                "object": "block",
                "id": "block-2222",
                "type": "paragraph",
                "has_children": False,
                "paragraph": {
                    "rich_text": [{"type": "text", "plain_text": "This is a test paragraph."}],
                },
            },
        ],
        "has_more": False,
        "next_cursor": None,
    }


@pytest.fixture
def mock_users_list():
    """Standard users list response."""
    return {
        "object": "list",
        "results": [
            {
                "object": "user",
                "id": "user-1111",
                "type": "person",
                "name": "Alice Smith",
                "person": {"email": "alice@example.com"},
            },
            {
                "object": "user",
                "id": "user-2222",
                "type": "bot",
                "name": "Test Bot",
                "bot": {"owner": {"type": "workspace"}, "workspace_name": "Test"},
            },
        ],
        "has_more": False,
        "next_cursor": None,
    }


@pytest.fixture
def runner() -> CliRunner:
    """Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect config loading to a temporary directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    monkeypatch.setenv("KCTL_CONFIG_DIR", str(config_dir))
    return config_file


@pytest.fixture
def mock_output() -> Output:
    """Output instance with quiet mode for testing."""
    return Output(json_mode=False, quiet=True, format="pretty")


@pytest.fixture
def mock_context(mock_client):
    """Alias for mock_app_context — AppContext with mocked client."""
    ctx = AppContext(json_mode=False, quiet=True)
    ctx._client = mock_client
    return ctx
