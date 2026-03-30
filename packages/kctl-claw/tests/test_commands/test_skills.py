"""Tests for skills command group."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_claw.cli import app

runner = CliRunner()


def test_skills_list(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "skills", "list"])
    assert result.exit_code == 0
    assert "kodemeio-dev" in result.output
    assert "tilawah" in result.output


def test_skills_list_shows_skill_md(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "skills", "list"])
    assert result.exit_code == 0
    assert "yes" in result.output.lower()


def test_skills_get(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "skills", "get", "kodemeio-dev"])
    assert result.exit_code == 0
    assert "Kodemeio Dev" in result.output


def test_skills_get_not_found(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "skills", "get", "nonexistent"])
    assert result.exit_code == 1


def test_skills_create(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "skills", "create", "my-new-skill"])
    assert result.exit_code == 0
    assert "Created" in result.output
    skill_md = project_root / "config" / "skills" / "my-new-skill" / "SKILL.md"
    assert skill_md.exists()
    content = skill_md.read_text()
    assert "my-new-skill" in content


def test_skills_create_duplicate(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "skills", "create", "kodemeio-dev"])
    assert result.exit_code == 1
    assert "already exists" in result.output.lower()


def test_skills_delete_with_yes_flag(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "skills", "delete", "--yes", "tilawah"])
    assert result.exit_code == 0
    assert "Deleted" in result.output
    assert not (project_root / "config" / "skills" / "tilawah").exists()


def test_skills_delete_not_found(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "skills", "delete", "nonexistent"])
    assert result.exit_code == 1


def test_skills_delete_aborted(project_root):
    # Provide 'n' as input so confirm() returns False
    result = runner.invoke(app, ["--root", str(project_root), "skills", "delete", "tilawah"], input="n\n")
    assert result.exit_code == 0
    assert (project_root / "config" / "skills" / "tilawah").exists()
