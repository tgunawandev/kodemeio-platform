"""Tests for config show masking behavior (--reveal flag).

Verifies that kctl-odoo config show masks api_key by default,
and shows it in plaintext when --reveal is passed.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from kctl_odoo.core.output import Output


PLAINTEXT_KEY = "supersecretapikey123456"


def _write_config(config_file: Path, api_key: str) -> None:
    """Write a minimal config with a known api_key to the temp config file."""
    data = {
        "default_profile": "test-profile",
        "profiles": {
            "test-profile": {
                "odoo": {
                    "url": "https://odoo.example.com",
                    "database": "test_db",
                    "username": "admin",
                    "api_key": api_key,
                }
            }
        },
    }
    config_file.write_text(yaml.dump(data))


def _make_actx(*, json_mode: bool = False) -> MagicMock:
    actx = MagicMock()
    actx.json_mode = json_mode
    actx.output = Output(json_mode=json_mode)
    actx.profile = None
    actx.url_override = None
    actx.api_key_override = None
    actx.database_override = None
    actx.username_override = None
    return actx


def _make_ctx(actx: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.obj = actx
    return ctx


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Write a temp config file and monkeypatch CONFIG_FILE in both the
    config module and config_cmd (which imports CONFIG_FILE at module load time)."""
    config_file = tmp_path / "config.yaml"
    _write_config(config_file, PLAINTEXT_KEY)

    import kctl_odoo.core.config as _config_mod
    import kctl_odoo.commands.config_cmd as _cmd_mod

    monkeypatch.setattr(_config_mod, "CONFIG_FILE", config_file)
    monkeypatch.setattr(_config_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(_cmd_mod, "CONFIG_FILE", config_file)
    return config_file


class TestConfigShowMasking:
    """config show masks secrets by default; --reveal shows them."""

    def test_show_masks_api_key_by_default_json(
        self,
        isolated_config: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Without --reveal (JSON mode), api_key must be masked in output."""
        actx = _make_actx(json_mode=True)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.config_cmd import show

        show(ctx, reveal=False)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        odoo_cfg = data["profiles"]["test-profile"]["odoo"]
        assert PLAINTEXT_KEY not in odoo_cfg["api_key"], "Plaintext key must not appear when --reveal is not set"
        assert "****" in odoo_cfg["api_key"], "Masked key must contain ****"

    def test_show_reveal_exposes_api_key_json(
        self,
        isolated_config: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """With --reveal (JSON mode), api_key must appear in plaintext."""
        actx = _make_actx(json_mode=True)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.config_cmd import show

        show(ctx, reveal=True)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        odoo_cfg = data["profiles"]["test-profile"]["odoo"]
        assert odoo_cfg["api_key"] == PLAINTEXT_KEY, "Plaintext key must appear with --reveal"

    def test_show_pretty_masks_api_key_by_default(
        self,
        isolated_config: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Without --reveal in pretty mode, api_key must not appear in output."""
        actx = _make_actx(json_mode=False)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.config_cmd import show

        show(ctx, reveal=False)

        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert PLAINTEXT_KEY not in combined, "Plaintext key must not appear when --reveal is not set"
        assert "****" in combined, "Masked key must appear in output"

    def test_show_pretty_reveal_exposes_api_key(
        self,
        isolated_config: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """With --reveal in pretty mode, api_key must appear in plaintext."""
        actx = _make_actx(json_mode=False)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.config_cmd import show

        show(ctx, reveal=True)

        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert PLAINTEXT_KEY in combined, "Plaintext key must appear with --reveal"
