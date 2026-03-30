"""Tests for notifications commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_dokploy.cli import app
from kctl_dokploy.core.callbacks import AppContext

runner = CliRunner()

SAMPLE_NOTIFICATIONS = [
    {
        "notificationId": "ntf-aaa-111",
        "name": "slack-alerts",
        "notificationType": "slack",
        "enabled": True,
        "slackWebhookUrl": "https://hooks.slack.com/services/test",
        "createdAt": "2026-01-01T00:00:00Z",
    },
    {
        "notificationId": "ntf-bbb-222",
        "name": "discord-deploys",
        "notificationType": "discord",
        "enabled": True,
        "discordWebhookUrl": "https://discord.com/api/webhooks/test",
        "createdAt": "2026-02-01T00:00:00Z",
    },
]


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


class TestNotificationsList:
    def test_list_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_NOTIFICATIONS
        result = runner.invoke(app, ["--json", "notifications", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "slack-alerts"

    def test_list_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        result = runner.invoke(app, ["--json", "notifications", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []


class TestNotificationsGet:
    def test_get_notification_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_NOTIFICATIONS[0]
        result = runner.invoke(app, ["--json", "notifications", "get", "ntf-aaa-111"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "slack-alerts"
        assert data["notificationType"] == "slack"

    def test_get_not_found_exits_1(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = "not a dict"
        result = runner.invoke(app, ["notifications", "get", "nonexistent"])
        assert result.exit_code == 1


class TestNotificationsCreate:
    def test_create_slack_channel(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"notificationId": "ntf-new-001"}
        result = runner.invoke(
            app,
            [
                "--json",
                "notifications",
                "create",
                "--name",
                "new-alerts",
                "--type",
                "slack",
                "--webhook-url",
                "https://hooks.slack.com/test",
            ],
        )
        assert result.exit_code == 0
        assert "new-alerts" in result.output


class TestNotificationsRemove:
    def test_remove_with_force(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["notifications", "remove", "ntf-bbb-222", "--force"])
        assert result.exit_code == 0

    def test_test_notification_channel(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["notifications", "test", "ntf-aaa-111"])
        assert result.exit_code == 0
