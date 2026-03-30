"""Tests for multi-channel notification dispatch."""

from __future__ import annotations

import pytest

from kctl_dokploy.core.notify_ops import (
    STATUS_COLORS,
    STATUS_ICONS,
    NotifyConfig,
)


class TestNotifyConfig:
    def test_defaults(self) -> None:
        cfg = NotifyConfig()
        assert cfg.mattermost_enabled is True
        assert cfg.telegram_enabled is True
        assert cfg.email_enabled is False

    def test_has_mattermost(self) -> None:
        cfg = NotifyConfig(mattermost_webhook_url="https://mm.example.com/hooks/abc")
        assert cfg.has_mattermost is True

    def test_has_mattermost_disabled(self) -> None:
        cfg = NotifyConfig(mattermost_enabled=False, mattermost_webhook_url="https://mm.example.com/hooks/abc")
        assert cfg.has_mattermost is False

    def test_has_telegram(self) -> None:
        cfg = NotifyConfig(telegram_bot_token="123:abc", telegram_chat_id="-100123")
        assert cfg.has_telegram is True

    def test_has_telegram_missing_token(self) -> None:
        cfg = NotifyConfig(telegram_chat_id="-100123")
        assert cfg.has_telegram is False

    def test_has_email(self) -> None:
        cfg = NotifyConfig(email_enabled=True, email_to="test@test.com", smtp_host="smtp.test.com")
        assert cfg.has_email is True

    def test_has_email_missing_host(self) -> None:
        cfg = NotifyConfig(email_enabled=True, email_to="test@test.com")
        assert cfg.has_email is False

    def test_channels_status(self) -> None:
        cfg = NotifyConfig(mattermost_webhook_url="https://mm.example.com/hooks/abc")
        status = cfg.channels_status
        assert status["mattermost"] is True
        assert status["telegram"] is False
        assert status["email"] is False


class TestFromEnv:
    def test_loads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MATTERMOST_WEBHOOK_URL", "https://mm.test.com/hooks/x")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100")
        monkeypatch.setenv("NOTIFY_EMAIL", "false")

        cfg = NotifyConfig.from_env()
        assert cfg.mattermost_webhook_url == "https://mm.test.com/hooks/x"
        assert cfg.telegram_bot_token == "123:abc"
        assert cfg.email_enabled is False


class TestFromProfile:
    def test_loads_from_profile_dict(self) -> None:
        profile_data = {
            "notify": {
                "mattermost_webhook_url": "https://mm.test.com/hooks/y",
                "telegram_bot_token": "456:def",
                "telegram_chat_id": "-200",
            }
        }
        cfg = NotifyConfig.from_profile(profile_data)
        assert cfg.mattermost_webhook_url == "https://mm.test.com/hooks/y"
        assert cfg.telegram_bot_token == "456:def"

    def test_empty_profile(self) -> None:
        cfg = NotifyConfig.from_profile({})
        assert cfg.mattermost_webhook_url == ""


class TestStatusMaps:
    def test_all_statuses_have_icons(self) -> None:
        for status in ("success", "failure", "warning", "info", "rollback"):
            assert status in STATUS_ICONS

    def test_all_statuses_have_colors(self) -> None:
        for status in ("success", "failure", "warning", "info", "rollback"):
            assert status in STATUS_COLORS
            assert STATUS_COLORS[status].startswith("#")
