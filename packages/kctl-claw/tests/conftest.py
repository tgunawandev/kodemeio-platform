"""Shared test fixtures for kctl-claw tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kctl_claw.core.config_manager import ConfigManager


@pytest.fixture
def sample_openclaw_config() -> dict:
    """Minimal openclaw.json for testing."""
    return {
        "agents": {
            "defaults": {"model": "claude-opus-4-6", "thinking": "adaptive"},
            "list": [
                {"name": "kodemeiodev", "model": "claude-opus-4-6", "profile": "default"},
                {"name": "kontenosdev", "model": "claude-sonnet-4-20250514", "profile": "content"},
                {"name": "journaltxdev", "model": "claude-sonnet-4-20250514", "profile": "trading"},
                {"name": "kidneurodev", "model": "claude-sonnet-4-20250514", "profile": "kidneuro"},
                {"name": "kodemeioteam", "model": "claude-sonnet-4-20250514", "profile": "team"},
            ],
        },
        "tools": {
            "profiles": {
                "default": {"servers": ["kodemeio-mcp-odoo", "kodemeio-mcp-prometheus"]},
                "content": {"servers": ["kontenos-mcp-content", "brave-search"]},
                "trading": {"servers": ["journaltx-mcp-trading"]},
                "kidneuro": {"servers": ["kidneuro-mcp-platform"]},
                "team": {"servers": ["kodemeio-mcp-odoo"], "denied_tools": ["write_file"]},
            }
        },
        "gateway": {"port": 18789, "auth": {"mode": "token"}},
        "security": {"auditOnStart": True, "redactSensitive": True},
        "channels": {
            "telegram": {
                "accounts": [
                    {"name": "kodemeiodev", "tokenEnv": "TELEGRAM_KODEMEIODEV_BOT_TOKEN"},
                    {"name": "kontenosdev", "tokenEnv": "TELEGRAM_KONTENOSDEV_BOT_TOKEN"},
                ],
                "allowFrom": {"dm": [634688702], "groups": [634688702]},
            }
        },
        "bindings": [
            {"channel": "telegram:kodemeiodev", "agent": "kodemeiodev"},
            {"channel": "telegram:kontenosdev", "agent": "kontenosdev"},
        ],
    }


@pytest.fixture
def sample_mcp_config() -> dict:
    """Minimal config.json for testing."""
    return {
        "mcpServers": {
            "kodemeio-mcp-odoo": {
                "command": "node",
                "args": ["/opt/mcp-servers/kodemeio-mcp-odoo.mjs"],
                "env": {"ODOO_URL": "https://erp.kodeme.io"},
            },
            "kodemeio-mcp-prometheus": {
                "command": "node",
                "args": ["/opt/mcp-servers/kodemeio-mcp-prometheus.mjs"],
            },
            "brave-search": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-brave-search"],
            },
        }
    }


@pytest.fixture
def sample_cron_config() -> dict:
    """Minimal cron/jobs.json for testing."""
    return {
        "jobs": [
            {
                "id": "morning-briefing",
                "name": "Morning Briefing",
                "schedule": "0 7 * * *",
                "agent": "kodemeiodev",
                "enabled": True,
                "prompt": "Run morning briefing",
            },
            {
                "id": "system-health-check",
                "name": "System Health Check",
                "schedule": "0 */6 * * *",
                "agent": "kodemeiodev",
                "enabled": True,
                "silent": True,
                "prompt": "Check system health",
            },
            {
                "id": "weekly-content-plan",
                "name": "Weekly Content Plan",
                "schedule": "0 8 * * 1",
                "agent": "kontenosdev",
                "enabled": False,
                "prompt": "Create content plan",
            },
        ]
    }


@pytest.fixture
def project_root(tmp_path, sample_openclaw_config, sample_mcp_config, sample_cron_config) -> Path:
    """Create a complete mock project directory."""
    (tmp_path / "config" / "cron").mkdir(parents=True)
    (tmp_path / "config" / "skills" / "kodemeio-dev").mkdir(parents=True)
    (tmp_path / "config" / "skills" / "tilawah").mkdir(parents=True)
    (tmp_path / "config" / "agents" / "kontenosdev" / "workspace").mkdir(parents=True)
    (tmp_path / "config" / "workspace" / "memory").mkdir(parents=True)

    (tmp_path / "config" / "openclaw.json").write_text(json.dumps(sample_openclaw_config, indent=2))
    (tmp_path / "config" / "config.json").write_text(json.dumps(sample_mcp_config, indent=2))
    (tmp_path / "config" / "cron" / "jobs.json").write_text(json.dumps(sample_cron_config, indent=2))
    (tmp_path / "config" / "skills" / "kodemeio-dev" / "SKILL.md").write_text("# Kodemeio Dev\n")
    (tmp_path / "config" / "skills" / "tilawah" / "SKILL.md").write_text("# Tilawah\n")

    (tmp_path / "docker-compose.prod.yml").write_text("version: '3'\n")
    (tmp_path / ".env.prod").write_text("OPENCLAW_GATEWAY_TOKEN=test\n")
    (tmp_path / ".env.example").write_text("OPENCLAW_GATEWAY_TOKEN=\nODOO_API_KEY=\n")

    return tmp_path


@pytest.fixture
def config_mgr(project_root) -> ConfigManager:
    """ConfigManager pointed at mock project."""
    return ConfigManager(project_root)
