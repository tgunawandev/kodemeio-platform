"""Tests for kctl_lib.skill_generator."""

from __future__ import annotations

from pathlib import Path

import typer

from kctl_lib.skill_generator import check_stale, generate_skill


def _make_test_app() -> typer.Typer:
    app = typer.Typer(name="kctl-test", help="Test CLI")
    sub = typer.Typer(help="Sub group help.")

    @sub.command()
    def cmd1(name: str) -> None:
        """Do something.

        Examples:
            kctl-test sub cmd1 myname
        """

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


class TestRegistryHash:
    def test_hash_in_frontmatter(self) -> None:
        app = _make_test_app()
        content = generate_skill(app, "kctl-test", "test-admin", "Test")
        assert "registry_hash:" in content

    def test_hash_is_deterministic(self) -> None:
        app = _make_test_app()
        content1 = generate_skill(app, "kctl-test", "test-admin", "Test")
        content2 = generate_skill(app, "kctl-test", "test-admin", "Test")
        # Extract hash from both
        hash1 = [l for l in content1.splitlines() if "registry_hash:" in l][0]
        hash2 = [l for l in content2.splitlines() if "registry_hash:" in l][0]
        assert hash1 == hash2


class TestCheckStale:
    def test_stale_when_missing(self, tmp_path: Path) -> None:
        app = _make_test_app()
        is_stale, reason = check_stale(app, tmp_path / "nonexistent.md")
        assert is_stale
        assert "does not exist" in reason

    def test_not_stale_when_fresh(self, tmp_path: Path) -> None:
        app = _make_test_app()
        out_dir = tmp_path / "skill"
        generate_skill(app, "kctl-test", "test-admin", "Test", output_dir=out_dir)
        is_stale, reason = check_stale(app, out_dir / "SKILL.md")
        assert not is_stale
        assert "Up to date" in reason

    def test_stale_when_commands_change(self, tmp_path: Path) -> None:
        app = _make_test_app()
        out_dir = tmp_path / "skill"
        generate_skill(app, "kctl-test", "test-admin", "Test", output_dir=out_dir)

        # Add a new command to the app
        sub = typer.Typer(help="New group.")

        @sub.command()
        def new_cmd() -> None:
            """New command."""

        app.add_typer(sub, name="new-group")

        is_stale, reason = check_stale(app, out_dir / "SKILL.md")
        assert is_stale
        assert "mismatch" in reason


class TestExampleExtraction:
    def test_extracts_examples_from_docstring(self) -> None:
        app = _make_test_app()
        content = generate_skill(app, "kctl-test", "test-admin", "Test")
        # cmd1 has an example in its docstring
        assert "kctl-test sub cmd1 myname" in content

    def test_examples_in_code_block(self) -> None:
        app = _make_test_app()
        content = generate_skill(app, "kctl-test", "test-admin", "Test")
        # Examples should be wrapped in ```bash blocks
        assert "**Examples:**" in content


class TestDomainTriggers:
    def test_subcommand_triggers(self) -> None:
        app = _make_test_app()
        content = generate_skill(app, "kctl-test", "test-admin", "Test")
        # "cmd1" is >3 chars and not in skip list, so should be a trigger
        assert '"cmd1"' in content

    def test_generic_subcommands_skipped(self) -> None:
        app = typer.Typer(name="kctl-test", help="Test")
        sub = typer.Typer(help="Group.")

        @sub.command()
        def list() -> None:  # noqa: A001
            """List items."""

        @sub.command()
        def get() -> None:
            """Get item."""

        app.add_typer(sub, name="items")
        content = generate_skill(app, "kctl-test", "test-admin", "Test")
        # Generic names like "list" and "get" should NOT be triggers
        triggers_line = [l for l in content.splitlines() if "Triggers on:" in l][0]
        assert '"list"' not in triggers_line
        assert '"get"' not in triggers_line
