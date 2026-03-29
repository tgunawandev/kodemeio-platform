"""Tests for kctl_common.skill_generator."""

from __future__ import annotations

from pathlib import Path

import typer

from kctl_common.skill_generator import generate_skill


def _make_test_app() -> typer.Typer:
    app = typer.Typer(name="kctl-test", help="Test CLI")
    sub = typer.Typer(help="Sub group help.")

    @sub.command()
    def cmd1(name: str) -> None:
        """Do something."""

    @sub.command()
    def cmd2() -> None:
        """Do other thing."""

    app.add_typer(sub, name="sub")
    return app


class TestGenerateSkill:
    def test_generates_content(self) -> None:
        app = _make_test_app()
        content = generate_skill(app, "kctl-test", "test-admin", "Test CLI admin")
        assert "test-admin" in content
        assert "kctl-test" in content
        assert "## Command Reference" in content
        assert "sub" in content
        assert "cmd1" in content
        assert "cmd2" in content

    def test_frontmatter(self) -> None:
        app = _make_test_app()
        content = generate_skill(app, "kctl-test", "test-admin", "Test CLI admin")
        assert content.startswith("---")
        assert "name: test-admin" in content
        assert "Triggers on:" in content

    def test_writes_file(self, tmp_path: Path) -> None:
        app = _make_test_app()
        generate_skill(app, "kctl-test", "test-admin", "Test CLI admin", output_dir=tmp_path / "test-admin")
        skill_file = tmp_path / "test-admin" / "SKILL.md"
        assert skill_file.exists()
        content = skill_file.read_text()
        assert "## Command Reference" in content

    def test_extra_file(self, tmp_path: Path) -> None:
        app = _make_test_app()
        extra = tmp_path / "SKILL.extra.md"
        extra.write_text("## Custom Examples\n\nHere are examples.")
        content = generate_skill(app, "kctl-test", "test-admin", "Test", extra_file=extra)
        assert "Custom Examples" in content

    def test_command_count(self) -> None:
        app = _make_test_app()
        content = generate_skill(app, "kctl-test", "test-admin", "Test")
        assert "~2 commands" in content

    def test_global_options(self) -> None:
        app = _make_test_app()
        content = generate_skill(app, "kctl-test", "test-admin", "Test")
        assert "--json" in content
        assert "--format" in content
