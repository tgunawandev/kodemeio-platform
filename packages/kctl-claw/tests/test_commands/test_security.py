"""Tests for security command group."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from kctl_claw.cli import app

runner = CliRunner()


def test_security_audit_missing_script(project_root):
    """audit warns gracefully when script is missing."""
    # scripts/security-audit.sh doesn't exist in the test project_root
    result = runner.invoke(app, ["--root", str(project_root), "security", "audit"])
    assert result.exit_code == 0
    assert "not found" in result.output or "not found" in result.output


def test_security_audit_with_script(project_root):
    """audit runs the script when it exists."""
    scripts_dir = project_root / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    script = scripts_dir / "security-audit.sh"
    script.write_text("#!/bin/bash\necho 'Audit complete'\nexit 0\n")
    script.chmod(0o755)
    result = runner.invoke(app, ["--root", str(project_root), "security", "audit"])
    assert result.exit_code == 0


def test_security_credentials_all_set(project_root):
    """credentials passes when all vars have real values."""
    (project_root / ".env.prod").write_text("OPENCLAW_GATEWAY_TOKEN=realtoken123\nODOO_API_KEY=realkey456\n")
    result = runner.invoke(app, ["--root", str(project_root), "security", "credentials"])
    assert result.exit_code == 0
    assert "All credentials are set" in result.output


def test_security_credentials_empty_value(project_root):
    """credentials exits 1 when a var is empty."""
    (project_root / ".env.prod").write_text("OPENCLAW_GATEWAY_TOKEN=\nODOO_API_KEY=realkey\n")
    result = runner.invoke(app, ["--root", str(project_root), "security", "credentials"])
    assert result.exit_code == 1
    assert "EMPTY" in result.output
    assert "OPENCLAW_GATEWAY_TOKEN" in result.output


def test_security_credentials_placeholder(project_root):
    """credentials exits 1 for placeholder values."""
    (project_root / ".env.prod").write_text("OPENCLAW_GATEWAY_TOKEN=your_token_here\n")
    result = runner.invoke(app, ["--root", str(project_root), "security", "credentials"])
    assert result.exit_code == 1
    assert "PLACEHOLDER" in result.output


def test_security_credentials_json(project_root):
    """credentials outputs valid JSON (may have info messages mixed in)."""
    (project_root / ".env.prod").write_text("OPENCLAW_GATEWAY_TOKEN=realtoken\n")
    result = runner.invoke(app, ["--root", str(project_root), "--json", "security", "credentials"])
    assert result.exit_code == 0
    output = result.output
    start = output.index("[")
    data = json.loads(output[start:])
    assert isinstance(data, list)
    assert data[0]["key"] == "OPENCLAW_GATEWAY_TOKEN"
    assert data[0]["status"] == "OK"


def test_security_credentials_no_prod(project_root):
    """credentials exits 1 if .env.prod is missing."""
    (project_root / ".env.prod").unlink()
    result = runner.invoke(app, ["--root", str(project_root), "security", "credentials"])
    assert result.exit_code == 1


def test_security_allowlist(project_root):
    """allowlist shows telegram allowed IDs."""
    result = runner.invoke(app, ["--root", str(project_root), "security", "allowlist"])
    assert result.exit_code == 0
    assert "634688702" in result.output


def test_security_allowlist_json(project_root):
    """allowlist outputs valid JSON."""
    result = runner.invoke(app, ["--root", str(project_root), "--json", "security", "allowlist"])
    assert result.exit_code == 0
    output = result.output
    start = output.index("[")
    data = json.loads(output[start:])
    assert isinstance(data, list)
    assert any(e["id"] == 634688702 for e in data)


def test_security_sandbox(project_root):
    """sandbox shows agent sandbox settings."""
    result = runner.invoke(app, ["--root", str(project_root), "security", "sandbox"])
    assert result.exit_code == 0
    assert "kodemeiodev" in result.output


def test_security_sandbox_json(project_root):
    """sandbox outputs valid JSON."""
    result = runner.invoke(app, ["--root", str(project_root), "--json", "security", "sandbox"])
    assert result.exit_code == 0
    output = result.output
    start = output.index("[")
    data = json.loads(output[start:])
    assert isinstance(data, list)
    assert "name" in data[0]
    assert "sandbox" in data[0]
