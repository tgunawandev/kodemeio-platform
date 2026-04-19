"""Config subcommand tests."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from kctl_gsc.cli import app


def test_config_add_then_show(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / "kodemeio" / "config.yaml"
    cfg.parent.mkdir(parents=True)
    monkeypatch.setattr("kctl_gsc.core.config.CONFIG_FILE", cfg)
    monkeypatch.setattr("kctl_gsc.core.config.CONFIG_DIR", cfg.parent)

    sa = tmp_path / "sa.json"
    sa.write_text("{}")

    r = CliRunner()
    res = r.invoke(
        app,
        [
            "config",
            "add",
            "kodemeio-kod-infra-gsc",
            "--credentials-file",
            str(sa),
            "--default-property",
            "sc-domain:kodeme.io",
        ],
    )
    assert res.exit_code == 0, res.stdout

    res = r.invoke(app, ["-p", "kodemeio-kod-infra-gsc", "config", "show"])
    assert res.exit_code == 0
    assert "sc-domain:kodeme.io" in res.stdout
    # Secret-like value is the file path; no API key to mask, so full path is fine.


def test_config_profiles_and_current(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / "kodemeio" / "config.yaml"
    cfg.parent.mkdir(parents=True)
    monkeypatch.setattr("kctl_gsc.core.config.CONFIG_FILE", cfg)
    monkeypatch.setattr("kctl_gsc.core.config.CONFIG_DIR", cfg.parent)

    sa = tmp_path / "sa.json"
    sa.write_text("{}")

    r = CliRunner()
    r.invoke(app, ["config", "add", "a", "--credentials-file", str(sa), "--default-property", "sc-domain:a"])
    r.invoke(app, ["config", "add", "b", "--credentials-file", str(sa), "--default-property", "sc-domain:b"])
    res = r.invoke(app, ["config", "profiles"])
    assert res.exit_code == 0
    assert "a" in res.stdout and "b" in res.stdout
