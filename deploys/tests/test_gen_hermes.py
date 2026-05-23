"""Unit tests for gen_hermes in generate.py."""

from __future__ import annotations

import pytest

from generate import gen_hermes


def test_gen_hermes_kod_telegram_only():
    """kod-shape tenant (Telegram only, no Honcho) → kod-infra-hermes.yaml + env example."""
    tenant = {
        "code": "kod",
        "name": "Kodemeio",
        "short_name": "KOD",
        "domain": "kodeme.io",
    }
    hermes = {
        "enabled": True,
        "server": "kod-prod-04-claude",
        "inbound": {
            "telegram": {"enabled": True},
            "mattermost": {"enabled": False},
        },
        "memory": {"honcho": {"enabled": False}},
    }

    y_name, y_content, e_name, e_content = gen_hermes(tenant, hermes, "production")

    # Filenames
    assert y_name == "kod-infra-hermes.yaml"
    assert e_name == ".env.kod-infra-hermes.example"

    # Manifest content
    assert "server: kod-prod-04-claude" in y_content
    assert "project: kod" in y_content
    assert "extends: ../../bases/hermes.yaml" in y_content
    assert "Telegram inbound" in y_content  # description

    # Env example content
    assert "TELEGRAM_BOT_TOKEN=CHANGE_ME" in e_content
    assert (
        "MATTERMOST_TOKEN=CHANGE_ME" not in e_content
    )  # mattermost inbound block omitted
    assert "HONCHO_API_KEY=" not in e_content  # honcho block omitted
    assert (
        "GATEWAY_ALLOW_ALL_USERS=true" not in e_content
    )  # only set when Mattermost-only


def test_gen_hermes_tpp_mattermost_only():
    """tpp-shape (Mattermost only) → GATEWAY_ALLOW_ALL_USERS=true present."""
    tenant = {
        "code": "tpp",
        "name": "TPP",
        "short_name": "TPP",
        "domain": "idtpp.com",
    }
    hermes = {
        "enabled": True,
        "server": "tpp-prod-01",
        "inbound": {
            "telegram": {"enabled": False},
            "mattermost": {
                "enabled": True,
                "url": "https://mm.idtpp.com",
                "reply_mode": "thread",
                "require_mention": True,
                "allowed_channels": ["nxe8gt7xyfbp9rxqdqso5m17dr"],
            },
        },
        "memory": {"honcho": {"enabled": False}},
    }

    y_name, y_content, e_name, e_content = gen_hermes(tenant, hermes, "production")

    assert y_name == "tpp-infra-hermes.yaml"
    assert "server: tpp-prod-01" in y_content
    assert "Mattermost inbound (mm.idtpp.com)" in y_content
    assert "MCP outbound" in y_content

    # env.example: Mattermost block present
    assert "MATTERMOST_URL=https://mm.idtpp.com" in e_content
    assert "MATTERMOST_TOKEN=CHANGE_ME" in e_content
    assert "MATTERMOST_REPLY_MODE=thread" in e_content
    assert "MATTERMOST_REQUIRE_MENTION=true" in e_content
    assert "MATTERMOST_ALLOWED_CHANNELS=nxe8gt7xyfbp9rxqdqso5m17dr" in e_content

    # Telegram and Honcho blocks omitted
    assert "TELEGRAM_BOT_TOKEN" not in e_content
    assert "HONCHO_API_KEY" not in e_content

    # GATEWAY_ALLOW_ALL_USERS set because Mattermost is the ONLY inbound
    assert "GATEWAY_ALLOW_ALL_USERS=true" in e_content


def test_gen_hermes_mac_with_honcho():
    """mac shape + honcho.enabled: true → workspace defaults to mac-hermes."""
    tenant = {
        "code": "mac",
        "name": "Mandiri Agro",
        "short_name": "MAC",
        "domain": "idtpp.com",
    }
    hermes = {
        "enabled": True,
        "server": "tpp-prod-05",
        "inbound": {
            "telegram": {"enabled": False},
            "mattermost": {
                "enabled": True,
                "url": "https://mac-mm.idtpp.com",
                "allowed_channels": ["bnms3rw37iya5b8g1fdyg3edph"],
            },
        },
        "memory": {"honcho": {"enabled": True}},  # workspace not set → default
    }

    _, y_content, _, e_content = gen_hermes(tenant, hermes, "production")

    assert "Honcho memory (mac-hermes)" in y_content
    assert "HONCHO_API_KEY=CHANGE_ME" in e_content
    assert "HONCHO_BASE_URL=https://honcho.kodeme.io" in e_content
    assert "HONCHO_WORKSPACE=mac-hermes" in e_content


def test_gen_hermes_requires_server():
    tenant = {"code": "tpp", "short_name": "TPP", "domain": "idtpp.com"}
    hermes = {
        "enabled": True,
        # server missing
        "inbound": {"mattermost": {"enabled": True, "url": "https://mm.idtpp.com"}},
        "memory": {"honcho": {"enabled": False}},
    }

    with pytest.raises(ValueError, match="hermes.server is required"):
        gen_hermes(tenant, hermes, "production")


def test_gen_hermes_requires_at_least_one_inbound():
    tenant = {"code": "tpp", "short_name": "TPP", "domain": "idtpp.com"}
    hermes = {
        "enabled": True,
        "server": "tpp-prod-01",
        "inbound": {
            "telegram": {"enabled": False},
            "mattermost": {"enabled": False},
        },
        "memory": {"honcho": {"enabled": False}},
    }

    with pytest.raises(ValueError, match="no inbound adapter is enabled"):
        gen_hermes(tenant, hermes, "production")


def test_gen_hermes_mattermost_requires_url():
    tenant = {"code": "tpp", "short_name": "TPP", "domain": "idtpp.com"}
    hermes = {
        "enabled": True,
        "server": "tpp-prod-01",
        "inbound": {
            "mattermost": {"enabled": True},  # url missing
        },
        "memory": {"honcho": {"enabled": False}},
    }

    with pytest.raises(ValueError, match="mattermost.url is required"):
        gen_hermes(tenant, hermes, "production")


def test_gen_hermes_backup_gap_comment_on_tpp_prod():
    """Servers matching ^tpp-prod-\\d+$ → backup-gap comment appended."""
    tenant = {"code": "tpp", "short_name": "TPP", "domain": "idtpp.com"}
    hermes = {
        "enabled": True,
        "server": "tpp-prod-01",
        "inbound": {"mattermost": {"enabled": True, "url": "https://mm.idtpp.com"}},
        "memory": {"honcho": {"enabled": False}},
    }
    _, y_content, _, _ = gen_hermes(tenant, hermes, "production")

    assert "kodemeio-s3-backups" in y_content
    assert "dokploy.idtpp.com" in y_content


def test_gen_hermes_no_backup_gap_comment_on_kod_prod():
    tenant = {"code": "kod", "short_name": "KOD", "domain": "kodeme.io"}
    hermes = {
        "enabled": True,
        "server": "kod-prod-04-claude",
        "inbound": {"telegram": {"enabled": True}},
        "memory": {"honcho": {"enabled": False}},
    }
    _, y_content, _, _ = gen_hermes(tenant, hermes, "production")

    assert "kodemeio-s3-backups" not in y_content
