"""Tests for env command group."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from kctl_claw.cli import app

runner = CliRunner()


def test_env_check_all_present(project_root):
    """check passes when all example vars exist in prod."""
    # Ensure prod has all vars from example (add ODOO_API_KEY which is in example)
    (project_root / ".env.prod").write_text("OPENCLAW_GATEWAY_TOKEN=test\nODOO_API_KEY=realkey\n")
    result = runner.invoke(app, ["--root", str(project_root), "env", "check"])
    assert result.exit_code == 0
    assert "OPENCLAW_GATEWAY_TOKEN" in result.output


def test_env_check_missing_var(project_root):
    """check exits 1 when a variable is missing from .env.prod."""
    # Add a new var to .env.example that's not in .env.prod
    example = project_root / ".env.example"
    example.write_text("OPENCLAW_GATEWAY_TOKEN=\nODOO_API_KEY=\nNEW_SECRET=\n")
    result = runner.invoke(app, ["--root", str(project_root), "env", "check"])
    assert result.exit_code == 1
    assert "NEW_SECRET" in result.output
    assert "MISSING" in result.output


def test_env_check_no_example(project_root):
    """check exits 1 if .env.example is missing."""
    (project_root / ".env.example").unlink()
    result = runner.invoke(app, ["--root", str(project_root), "env", "check"])
    assert result.exit_code == 1


def test_env_check_json(project_root):
    """check outputs JSON table and exits 1 when vars missing."""
    result = runner.invoke(app, ["--root", str(project_root), "--json", "env", "check"])
    # Fixture has ODOO_API_KEY in example but not in prod, so exits 1
    assert result.exit_code == 1
    # JSON is embedded in output — find the JSON array
    output = result.output
    start = output.index("[")
    data = json.loads(output[start:])
    assert isinstance(data, list)
    assert any(item["key"] == "ODOO_API_KEY" for item in data)


def test_env_list(project_root):
    """list shows redacted vars from .env.prod."""
    # Add a value to .env.prod so we can check redaction
    (project_root / ".env.prod").write_text("OPENCLAW_GATEWAY_TOKEN=mysecrettoken\nODOO_API_KEY=abc\n")
    result = runner.invoke(app, ["--root", str(project_root), "env", "list"])
    assert result.exit_code == 0
    assert "OPENCLAW_GATEWAY_TOKEN" in result.output
    # Value should be redacted (first 3 chars + ***)
    assert "mys***" in result.output
    # Full token should NOT appear
    assert "mysecrettoken" not in result.output


def test_env_list_empty_value(project_root):
    """list shows (empty) for vars without values."""
    (project_root / ".env.prod").write_text("OPENCLAW_GATEWAY_TOKEN=\n")
    result = runner.invoke(app, ["--root", str(project_root), "env", "list"])
    assert result.exit_code == 0
    assert "(empty)" in result.output


def test_env_list_no_prod(project_root):
    """list exits 1 if .env.prod is missing."""
    (project_root / ".env.prod").unlink()
    result = runner.invoke(app, ["--root", str(project_root), "env", "list"])
    assert result.exit_code == 1


def test_env_list_json(project_root):
    """list outputs valid JSON."""
    result = runner.invoke(app, ["--root", str(project_root), "--json", "env", "list"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert "key" in data[0]
    assert "value" in data[0]


def test_env_diff_no_differences(project_root):
    """diff reports no differences when prod has all example vars."""
    # .env.prod has OPENCLAW_GATEWAY_TOKEN=test (set), example has it empty
    result = runner.invoke(app, ["--root", str(project_root), "env", "diff"])
    assert result.exit_code == 0


def test_env_diff_shows_missing(project_root):
    """diff shows MISSING status for vars not in prod."""
    example = project_root / ".env.example"
    example.write_text("OPENCLAW_GATEWAY_TOKEN=\nODOO_API_KEY=\nMISSING_VAR=\n")
    result = runner.invoke(app, ["--root", str(project_root), "env", "diff"])
    assert result.exit_code == 0
    assert "MISSING_VAR" in result.output
    assert "MISSING" in result.output


def test_env_diff_no_example(project_root):
    """diff exits 1 if .env.example is missing."""
    (project_root / ".env.example").unlink()
    result = runner.invoke(app, ["--root", str(project_root), "env", "diff"])
    assert result.exit_code == 1
