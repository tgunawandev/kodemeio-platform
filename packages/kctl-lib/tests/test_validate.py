"""Tests for kctl_lib.validate."""

from __future__ import annotations

from pathlib import Path

from kctl_lib.validate import Issue, dockerfile_lint, env_validate, json_lint, yaml_lint


class TestIssueDataclass:
    def test_fields(self) -> None:
        issue = Issue(file="foo.yaml", line=5, severity="error", message="bad syntax")
        assert issue.file == "foo.yaml"
        assert issue.line == 5
        assert issue.severity == "error"
        assert issue.message == "bad syntax"


class TestYamlLint:
    def test_valid_yaml_returns_no_issues(self, tmp_path: Path) -> None:
        f = tmp_path / "good.yaml"
        f.write_text("key: value\nlist:\n  - item1\n  - item2\n")
        result = yaml_lint(f)
        assert result == []

    def test_invalid_yaml_returns_error(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.yaml"
        f.write_text("key: [\nbad yaml\n")
        result = yaml_lint(f)
        assert len(result) == 1
        assert result[0].severity == "error"
        assert "YAML" in result[0].message

    def test_missing_file_returns_error(self, tmp_path: Path) -> None:
        f = tmp_path / "missing.yaml"
        result = yaml_lint(f)
        assert len(result) == 1
        assert result[0].severity == "error"
        assert "not found" in result[0].message.lower()

    def test_error_includes_file_path(self, tmp_path: Path) -> None:
        f = tmp_path / "missing.yaml"
        result = yaml_lint(f)
        assert result[0].file == str(f)

    def test_error_line_number_populated(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.yaml"
        f.write_text("key: [\nbad\n")
        result = yaml_lint(f)
        # line may be 0 (unknown) or > 0 depending on error location
        assert isinstance(result[0].line, int)


class TestJsonLint:
    def test_valid_json_returns_no_issues(self, tmp_path: Path) -> None:
        f = tmp_path / "good.json"
        f.write_text('{"key": "value", "number": 42}')
        result = json_lint(f)
        assert result == []

    def test_invalid_json_returns_error(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.json"
        f.write_text('{"key": "value"  "broken": true}')
        result = json_lint(f)
        assert len(result) == 1
        assert result[0].severity == "error"
        assert "JSON" in result[0].message

    def test_missing_file_returns_error(self, tmp_path: Path) -> None:
        f = tmp_path / "missing.json"
        result = json_lint(f)
        assert len(result) == 1
        assert result[0].severity == "error"
        assert "not found" in result[0].message.lower()

    def test_error_includes_line_number(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.json"
        f.write_text('{\n  "key": "value"\n  "oops"\n}')
        result = json_lint(f)
        assert result[0].line > 0

    def test_error_includes_file_path(self, tmp_path: Path) -> None:
        f = tmp_path / "missing.json"
        result = json_lint(f)
        assert result[0].file == str(f)


class TestEnvValidate:
    def _write(self, path: Path, content: str) -> None:
        path.write_text(content)

    def test_complete_env_no_issues(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        example = tmp_path / ".env.example"
        self._write(env, "DB_URL=postgres://localhost/db\nSECRET=abc123\n")
        self._write(example, "DB_URL=\nSECRET=\n")
        result = env_validate(env, example)
        assert result == []

    def test_missing_key_returns_error(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        example = tmp_path / ".env.example"
        self._write(env, "DB_URL=postgres://localhost/db\n")
        self._write(example, "DB_URL=\nSECRET=\n")
        result = env_validate(env, example)
        assert len(result) == 1
        assert result[0].severity == "error"
        assert "SECRET" in result[0].message

    def test_extra_key_returns_warn(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        example = tmp_path / ".env.example"
        self._write(env, "DB_URL=postgres://localhost/db\nEXTRA_KEY=something\n")
        self._write(example, "DB_URL=\n")
        result = env_validate(env, example)
        assert len(result) == 1
        assert result[0].severity == "warn"
        assert "EXTRA_KEY" in result[0].message

    def test_multiple_missing_keys_sorted(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        example = tmp_path / ".env.example"
        self._write(env, "A=1\n")
        self._write(example, "A=\nB=\nC=\n")
        result = env_validate(env, example)
        missing = [i for i in result if i.severity == "error"]
        assert [i.message for i in missing] == sorted(i.message for i in missing)

    def test_env_file_missing_returns_error(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        example = tmp_path / ".env.example"
        example.write_text("KEY=\n")
        result = env_validate(env, example)
        assert len(result) == 1
        assert result[0].severity == "error"
        assert "not found" in result[0].message.lower()

    def test_example_file_missing_returns_error(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        example = tmp_path / ".env.example"
        env.write_text("KEY=value\n")
        result = env_validate(env, example)
        assert len(result) == 1
        assert result[0].severity == "error"
        assert "not found" in result[0].message.lower()

    def test_comments_and_blanks_ignored(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        example = tmp_path / ".env.example"
        self._write(env, "# comment\n\nKEY=value\n")
        self._write(example, "# comment\n\nKEY=\n")
        result = env_validate(env, example)
        assert result == []


class TestDockerfileLint:
    def test_good_dockerfile_no_issues(self, tmp_path: Path) -> None:
        f = tmp_path / "Dockerfile"
        f.write_text("FROM python:3.12-slim\nWORKDIR /app\nUSER appuser\nHEALTHCHECK CMD curl -f http://localhost/\n")
        result = dockerfile_lint(f)
        assert result == []

    def test_latest_tag_returns_warn(self, tmp_path: Path) -> None:
        f = tmp_path / "Dockerfile"
        f.write_text("FROM python:latest\nUSER appuser\nHEALTHCHECK CMD curl -f http://localhost/\n")
        result = dockerfile_lint(f)
        warns = [i for i in result if "latest" in i.message]
        assert len(warns) == 1
        assert warns[0].severity == "warn"

    def test_no_user_returns_warn(self, tmp_path: Path) -> None:
        f = tmp_path / "Dockerfile"
        f.write_text("FROM python:3.12-slim\nWORKDIR /app\nHEALTHCHECK CMD curl -f http://localhost/\n")
        result = dockerfile_lint(f)
        warns = [i for i in result if "USER" in i.message or "root" in i.message]
        assert len(warns) == 1
        assert warns[0].severity == "warn"

    def test_no_healthcheck_returns_warn(self, tmp_path: Path) -> None:
        f = tmp_path / "Dockerfile"
        f.write_text("FROM python:3.12-slim\nWORKDIR /app\nUSER appuser\n")
        result = dockerfile_lint(f)
        warns = [i for i in result if "HEALTHCHECK" in i.message]
        assert len(warns) == 1
        assert warns[0].severity == "warn"

    def test_missing_file_returns_error(self, tmp_path: Path) -> None:
        f = tmp_path / "Dockerfile"
        result = dockerfile_lint(f)
        assert len(result) == 1
        assert result[0].severity == "error"
        assert "not found" in result[0].message.lower()

    def test_latest_tag_case_insensitive(self, tmp_path: Path) -> None:
        f = tmp_path / "Dockerfile"
        f.write_text("from PYTHON:latest\nUSER appuser\nHEALTHCHECK CMD curl -f http://localhost/\n")
        result = dockerfile_lint(f)
        warns = [i for i in result if "latest" in i.message]
        assert len(warns) == 1

    def test_latest_tag_line_number_reported(self, tmp_path: Path) -> None:
        f = tmp_path / "Dockerfile"
        f.write_text("FROM python:latest\nUSER appuser\nHEALTHCHECK CMD curl -f http://localhost/\n")
        result = dockerfile_lint(f)
        latest_issue = next(i for i in result if "latest" in i.message)
        assert latest_issue.line == 1

    def test_multiple_issues_accumulated(self, tmp_path: Path) -> None:
        f = tmp_path / "Dockerfile"
        f.write_text("FROM python:latest\nWORKDIR /app\n")
        result = dockerfile_lint(f)
        # latest tag + no USER + no HEALTHCHECK = 3 warnings
        assert len(result) == 3
