"""Tests for identifier resolution (core/resolve.py)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kctl_ak.core.exceptions import NotFoundError
from kctl_ak.core.resolve import resolve_group, resolve_user, resolve_user_username


@pytest.fixture()
def mock_client() -> MagicMock:
    return MagicMock()


class TestResolveUser:
    def test_numeric_id(self, mock_client: MagicMock) -> None:
        assert resolve_user(mock_client, "42") == 42
        mock_client.get.assert_not_called()

    def test_by_username(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"results": [{"pk": 7}]}
        assert resolve_user(mock_client, "admin") == 7
        mock_client.get.assert_called_once_with("core/users/", params={"username": "admin"})

    def test_by_email(self, mock_client: MagicMock) -> None:
        # First call (username search) returns empty, second call (email search) returns match
        mock_client.get.side_effect = [
            {"results": []},
            {"results": [{"pk": 10}]},
        ]
        assert resolve_user(mock_client, "alice@example.com") == 10
        calls = mock_client.get.call_args_list
        assert calls[0].args == ("core/users/",)
        assert calls[0].kwargs == {"params": {"username": "alice@example.com"}}
        assert calls[1].kwargs == {"params": {"email": "alice@example.com"}}

    def test_fallback_to_search(self, mock_client: MagicMock) -> None:
        mock_client.get.side_effect = [
            {"results": []},
            {"results": []},
            {"results": [{"pk": 99}]},
        ]
        assert resolve_user(mock_client, "some-term") == 99
        assert mock_client.get.call_count == 3

    def test_not_found(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"results": []}
        with pytest.raises(NotFoundError, match="User"):
            resolve_user(mock_client, "nonexistent")

    def test_empty_results_key(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {}
        with pytest.raises(NotFoundError):
            resolve_user(mock_client, "ghost")


class TestResolveGroup:
    def test_uuid_format(self, mock_client: MagicMock) -> None:
        uuid = "78d0f3e0-a9c2-4f50-9c36-fb8799dbf123"
        assert resolve_group(mock_client, uuid) == uuid
        mock_client.get.assert_not_called()

    def test_numeric_id(self, mock_client: MagicMock) -> None:
        assert resolve_group(mock_client, "5") == "5"
        mock_client.get.assert_not_called()

    def test_by_name(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"results": [{"pk": "abc-uuid"}]}
        assert resolve_group(mock_client, "ak-role-devops") == "abc-uuid"
        mock_client.get.assert_called_once_with("core/groups/", params={"name": "ak-role-devops"})

    def test_fallback_to_search(self, mock_client: MagicMock) -> None:
        mock_client.get.side_effect = [
            {"results": []},
            {"results": [{"pk": "found-uuid"}]},
        ]
        assert resolve_group(mock_client, "devops") == "found-uuid"
        assert mock_client.get.call_count == 2

    def test_not_found(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"results": []}
        with pytest.raises(NotFoundError, match="Group"):
            resolve_group(mock_client, "nonexistent-group")

    def test_short_uuid_not_treated_as_uuid(self, mock_client: MagicMock) -> None:
        """UUIDs must be exactly 36 chars with 4 dashes."""
        mock_client.get.return_value = {"results": [{"pk": "result-uuid"}]}
        resolve_group(mock_client, "abc-def")
        mock_client.get.assert_called_once()


class TestResolveUserUsername:
    def test_returns_username(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"username": "alice"}
        assert resolve_user_username(mock_client, 42) == "alice"
        mock_client.get.assert_called_once_with("core/users/42/")

    def test_fallback_to_pk(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {}
        assert resolve_user_username(mock_client, 99) == "99"
