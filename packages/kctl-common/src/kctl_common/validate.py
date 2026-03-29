"""File validation utilities for kctl-* CLI tools."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Issue:
    file: str
    line: int
    severity: str  # "error", "warn", "info"
    message: str


def yaml_lint(path: Path) -> list[Issue]:
    if not path.exists():
        return [Issue(str(path), 0, "error", f"File not found: {path}")]
    try:
        with open(path) as f:
            yaml.safe_load(f)
        return []
    except yaml.YAMLError as e:
        line = getattr(e, "problem_mark", None)
        return [Issue(str(path), line.line + 1 if line else 0, "error", f"YAML syntax error: {e}")]


def json_lint(path: Path) -> list[Issue]:
    if not path.exists():
        return [Issue(str(path), 0, "error", f"File not found: {path}")]
    try:
        with open(path) as f:
            json.load(f)
        return []
    except json.JSONDecodeError as e:
        return [Issue(str(path), e.lineno, "error", f"JSON syntax error: {e.msg}")]


def _parse_env_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


def env_validate(env_file: Path, example_file: Path) -> list[Issue]:
    if not env_file.exists():
        return [Issue(str(env_file), 0, "error", f"File not found: {env_file}")]
    if not example_file.exists():
        return [Issue(str(example_file), 0, "error", f"File not found: {example_file}")]
    env_keys = set(_parse_env_file(env_file).keys())
    example_keys = set(_parse_env_file(example_file).keys())
    issues: list[Issue] = []
    for key in sorted(example_keys - env_keys):
        issues.append(Issue(str(env_file), 0, "error", f"Missing key: {key} (defined in {example_file.name})"))
    for key in sorted(env_keys - example_keys):
        issues.append(Issue(str(env_file), 0, "warn", f"Extra key: {key} (not in {example_file.name})"))
    return issues


def dockerfile_lint(path: Path) -> list[Issue]:
    if not path.exists():
        return [Issue(str(path), 0, "error", f"File not found: {path}")]
    content = path.read_text()
    lines = content.splitlines()
    issues: list[Issue] = []
    for i, line in enumerate(lines, 1):
        if re.match(r"^FROM\s+\S+:latest", line, re.IGNORECASE):
            issues.append(Issue(str(path), i, "warn", "Avoid :latest tag - use specific version"))
    if not any(line.strip().upper().startswith("USER ") for line in lines):
        issues.append(Issue(str(path), 0, "warn", "No USER instruction - container runs as root"))
    if not any(line.strip().upper().startswith("HEALTHCHECK ") for line in lines):
        issues.append(Issue(str(path), 0, "warn", "No HEALTHCHECK instruction"))
    return issues
