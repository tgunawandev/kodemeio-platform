"""Unit tests for gen_hermes in generate.py."""

from __future__ import annotations

import pytest


def test_gen_hermes_kod_telegram_only():
    """kod-shape tenant (Telegram only, no Honcho) → kod-infra-hermes.yaml + env example."""
    from generate import gen_hermes

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
    assert "MATTERMOST_URL=" not in e_content  # mattermost block omitted
    assert "HONCHO_API_KEY=" not in e_content  # honcho block omitted
    assert (
        "GATEWAY_ALLOW_ALL_USERS=true" not in e_content
    )  # only set when Mattermost-only
