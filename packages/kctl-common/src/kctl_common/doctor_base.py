"""Standardized doctor/health check framework for kctl-* CLI tools."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Protocol

from kctl_common.output import Output
from kctl_common.runner import run_quiet


@dataclass
class CheckResult:
    name: str
    status: str  # "ok", "warn", "fail"
    message: str
    fix_command: str | None = None


class DoctorCheck(Protocol):
    name: str

    def run(self) -> CheckResult: ...


def run_doctor(checks: list[DoctorCheck], output: Output) -> bool:
    results: list[CheckResult] = []
    for check in checks:
        try:
            result = check.run()
        except Exception as e:
            result = CheckResult(name=check.name, status="fail", message=f"Check crashed: {e}")
        results.append(result)

    rows: list[list[str]] = []
    json_data: list[dict] = []  # type: ignore[type-arg]
    for r in results:
        if r.status == "ok":
            icon = "[green]PASS[/green]"
        elif r.status == "warn":
            icon = "[yellow]WARN[/yellow]"
        else:
            icon = "[red]FAIL[/red]"
        fix_info = f" (fix: {r.fix_command})" if r.fix_command else ""
        rows.append([r.name, icon, f"{r.message}{fix_info}"])
        json_data.append({"name": r.name, "status": r.status, "message": r.message, "fix_command": r.fix_command})

    output.table(
        "Doctor Check",
        [("Check", "cyan"), ("Status", ""), ("Details", "dim")],
        rows,
        data_for_json=json_data,
    )
    has_fail = any(r.status == "fail" for r in results)
    if has_fail:
        output.error("Some checks failed")
    else:
        output.success("All checks passed")
    return not has_fail


class PythonVersionCheck:
    name = "Python version"

    def run(self) -> CheckResult:
        version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        if sys.version_info >= (3, 12):
            return CheckResult(name=self.name, status="ok", message=f"Python {version}")
        return CheckResult(
            name=self.name,
            status="fail",
            message=f"Python {version} (need >= 3.12)",
            fix_command="uv python install 3.12",
        )


class UvCheck:
    name = "uv"

    def run(self) -> CheckResult:
        result = run_quiet(["uv", "--version"])
        if result.returncode == 0:
            return CheckResult(name=self.name, status="ok", message=result.stdout.strip())
        return CheckResult(
            name=self.name,
            status="fail",
            message="uv not found",
            fix_command="curl -LsSf https://astral.sh/uv/install.sh | sh",
        )


class GitCheck:
    name = "git"

    def run(self) -> CheckResult:
        result = run_quiet(["git", "--version"])
        if result.returncode == 0:
            return CheckResult(name=self.name, status="ok", message=result.stdout.strip())
        return CheckResult(name=self.name, status="fail", message="git not found")


class DockerCheck:
    name = "Docker"

    def run(self) -> CheckResult:
        result = run_quiet(["docker", "info", "--format", "{{.ServerVersion}}"])
        if result.returncode == 0:
            return CheckResult(name=self.name, status="ok", message=f"Docker {result.stdout.strip()}")
        return CheckResult(
            name=self.name,
            status="fail",
            message="Docker not available",
            fix_command="sudo systemctl start docker",
        )
