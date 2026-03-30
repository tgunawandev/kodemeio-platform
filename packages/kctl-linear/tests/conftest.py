"""Shared test configuration and fixtures."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from kctl_linear.core.client import LinearClient


@pytest.fixture
def mock_client() -> MagicMock:
    """Return a mock LinearClient."""
    client = MagicMock(spec=LinearClient)
    client.viewer.return_value = {
        "id": "user-123",
        "name": "Test User",
        "email": "test@kodeme.io",
        "admin": False,
        "active": True,
    }
    return client


@pytest.fixture
def mock_query(mock_client: MagicMock):
    """Convenience fixture to set up query return values."""

    def _set_query_response(response: dict[str, Any]) -> MagicMock:
        mock_client.query.return_value = response
        return mock_client

    return _set_query_response


SAMPLE_ISSUE = {
    "id": "issue-1",
    "identifier": "KOD-1",
    "title": "Test issue",
    "priority": 2,
    "state": {"name": "In Progress", "color": "#f00"},
    "assignee": {"name": "Test User", "email": "test@kodeme.io"},
    "createdAt": "2026-03-01T00:00:00Z",
    "updatedAt": "2026-03-28T00:00:00Z",
}

SAMPLE_CYCLE = {
    "id": "cycle-1",
    "number": 5,
    "name": "Sprint 5",
    "startsAt": "2026-03-25T00:00:00Z",
    "endsAt": "2026-04-07T00:00:00Z",
    "progress": 0.6,
    "issues": {"nodes": [SAMPLE_ISSUE]},
}
