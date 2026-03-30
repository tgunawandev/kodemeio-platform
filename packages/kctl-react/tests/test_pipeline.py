"""Tests for pipeline commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from kctl_react.cli import app

runner = CliRunner()


class TestPipelineGate:
    def test_gate_help(self) -> None:
        result = runner.invoke(app, ["pipeline", "gate", "--help"])
        assert result.exit_code == 0
        assert "lint" in result.output.lower() or "gate" in result.output.lower()

    def test_gate_all_pass(self, mock_monorepo: Path) -> None:
        """Gate with all steps mocked to succeed."""
        with patch("kctl_react.commands.pipeline.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""
            result = runner.invoke(app, ["--root", str(mock_monorepo), "pipeline", "gate", "--skip-build"])
            assert result.exit_code == 0
            assert "PASS" in result.output or "passed" in result.output

    def test_gate_single_app(self, mock_monorepo: Path) -> None:
        """Gate for a single app with mocked success."""
        with patch("kctl_react.commands.pipeline.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""
            result = runner.invoke(app, ["--root", str(mock_monorepo), "pipeline", "gate", "sfa", "--skip-build"])
            assert result.exit_code == 0

    def test_gate_failing_step(self, mock_monorepo: Path) -> None:
        """Gate with a failing step should exit 1."""
        from kctl_react.core.exceptions import CommandError

        def side_effect(cmd, **kwargs):
            if "lint" in cmd:
                raise CommandError("lint", 1, "lint errors found")
            result_mock = type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            return result_mock

        with patch("kctl_react.commands.pipeline.run", side_effect=side_effect):
            result = runner.invoke(app, ["--root", str(mock_monorepo), "pipeline", "gate", "--skip-build"])
            assert result.exit_code == 1
            assert "FAIL" in result.output or "failed" in result.output

    def test_gate_invalid_app(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "pipeline", "gate", "nonexistent"])
        assert result.exit_code == 1

    def test_gate_json(self, mock_monorepo: Path) -> None:
        """Gate with JSON output."""
        with patch("kctl_react.commands.pipeline.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""
            result = runner.invoke(app, ["--json", "--root", str(mock_monorepo), "pipeline", "gate", "--skip-build"])
            assert result.exit_code == 0
            # Find JSON in output
            for i, ch in enumerate(result.output):
                if ch == "[":
                    try:
                        data = json.loads(result.output[i:])
                        assert len(data) >= 3  # lint, type-check, test:ci, audit
                        assert data[0]["step"] == "lint"
                        break
                    except json.JSONDecodeError:
                        continue


class TestPipelineAffectedGate:
    def test_affected_gate_no_changes(self, mock_monorepo: Path) -> None:
        """No affected apps should exit 0."""
        with patch("kctl_react.core.git.get_affected_apps", return_value=[]):
            result = runner.invoke(app, ["--root", str(mock_monorepo), "pipeline", "affected-gate"])
            assert result.exit_code == 0
            assert "No apps affected" in result.output or "nothing" in result.output.lower()

    def test_affected_gate_with_affected(self, mock_monorepo: Path) -> None:
        """Affected apps should run gate for each."""
        with (
            patch("kctl_react.core.git.get_affected_apps", return_value=["sfa"]),
            patch("kctl_react.commands.pipeline.run") as mock_run,
        ):
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""
            result = runner.invoke(app, ["--root", str(mock_monorepo), "pipeline", "affected-gate"])
            assert result.exit_code == 0
            assert "sfa" in result.output


class TestPipelineRelease:
    def test_release_help(self) -> None:
        result = runner.invoke(app, ["pipeline", "release", "--help"])
        assert result.exit_code == 0
        assert "docker" in result.output.lower() or "tag" in result.output.lower()

    def test_release_builds_correct_command(self, mock_monorepo: Path) -> None:
        """Release should build docker image with correct args."""
        with (
            patch("kctl_react.commands.pipeline.run") as mock_run,
            patch("kctl_react.core.git.get_last_commit_hash", return_value="abc1234"),
        ):
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "12345678"
            mock_run.return_value.stderr = ""
            result = runner.invoke(app, ["--root", str(mock_monorepo), "pipeline", "release", "sfa"])
            assert result.exit_code == 0
            # Check docker build was called with correct image name
            calls = mock_run.call_args_list
            build_call = calls[0]
            cmd = build_call[0][0]
            assert "docker" in cmd
            assert "build" in cmd
            assert "APP_NAME=sfa" in cmd

    def test_release_custom_tag(self, mock_monorepo: Path) -> None:
        """Release with custom tag."""
        with (
            patch("kctl_react.commands.pipeline.run") as mock_run,
            patch("kctl_react.core.git.get_last_commit_hash", return_value="abc1234"),
        ):
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "12345678"
            mock_run.return_value.stderr = ""
            result = runner.invoke(app, ["--root", str(mock_monorepo), "pipeline", "release", "sfa", "--tag", "v1.0.0"])
            assert result.exit_code == 0
            assert "v1.0.0" in result.output

    def test_release_invalid_app(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "pipeline", "release", "nonexistent"])
        assert result.exit_code == 1
