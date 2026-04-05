"""Tests for skills command group."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from kctl_claw.cli import app

runner = CliRunner()


class TestSkillsList:
    def test_skills_list(self, project_root) -> None:
        result = runner.invoke(app, ["--root", str(project_root), "skills", "list"])
        assert result.exit_code == 0
        assert "kodemeio-dev" in result.output
        assert "tilawah" in result.output

    def test_skills_list_json(self, project_root) -> None:
        result = runner.invoke(app, ["--root", str(project_root), "--json", "skills", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        names = [d["name"] for d in data]
        assert "kodemeio-dev" in names

    def test_skills_list_help(self) -> None:
        result = runner.invoke(app, ["skills", "list", "--help"])
        assert result.exit_code == 0


class TestSkillsGet:
    def test_skills_get_existing(self, project_root) -> None:
        result = runner.invoke(app, ["--root", str(project_root), "skills", "get", "kodemeio-dev"])
        assert result.exit_code == 0
        assert "Kodemeio Dev" in result.output

    def test_skills_get_not_found(self, project_root) -> None:
        result = runner.invoke(app, ["--root", str(project_root), "skills", "get", "nonexistent-skill"])
        assert result.exit_code == 1

    def test_skills_get_help(self) -> None:
        result = runner.invoke(app, ["skills", "get", "--help"])
        assert result.exit_code == 0


class TestSkillsCreate:
    def test_skills_create_new(self, project_root) -> None:
        result = runner.invoke(app, ["--root", str(project_root), "skills", "create", "new-skill"])
        assert result.exit_code == 0
        skill_dir = project_root / "config" / "skills" / "new-skill"
        assert skill_dir.is_dir()
        assert (skill_dir / "SKILL.md").exists()

    def test_skills_create_help(self) -> None:
        result = runner.invoke(app, ["skills", "create", "--help"])
        assert result.exit_code == 0


class TestSkillsDelete:
    def test_skills_delete_with_force(self, project_root) -> None:
        result = runner.invoke(app, ["--root", str(project_root), "skills", "delete", "tilawah", "--force"])
        assert result.exit_code == 0
        skill_dir = project_root / "config" / "skills" / "tilawah"
        assert not skill_dir.exists()

    def test_skills_delete_not_found(self, project_root) -> None:
        result = runner.invoke(app, ["--root", str(project_root), "skills", "delete", "nonexistent", "--force"])
        assert result.exit_code == 1

    def test_skills_delete_help(self) -> None:
        result = runner.invoke(app, ["skills", "delete", "--help"])
        assert result.exit_code == 0
        assert "--force" in result.output


class TestSkillsSecurity:
    def test_security_credentials_missing_env(self, project_root) -> None:
        # Remove .env.prod so it's missing
        env_prod = project_root / ".env.prod"
        env_prod.unlink(missing_ok=True)
        result = runner.invoke(app, ["--root", str(project_root), "security", "credentials"])
        assert result.exit_code == 1

    def test_security_credentials_with_env(self, project_root) -> None:
        result = runner.invoke(app, ["--root", str(project_root), "security", "credentials"])
        assert result.exit_code == 0

    def test_security_audit_no_script(self, project_root) -> None:
        result = runner.invoke(app, ["--root", str(project_root), "security", "audit"])
        assert result.exit_code == 0
        assert "not found" in result.output.lower() or "manually" in result.output.lower()
