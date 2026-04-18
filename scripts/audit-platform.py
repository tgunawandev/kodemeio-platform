"""Per-package quality audit for kctl-* CLIs.

Outputs a scored table (1-10) based on objective metrics. Intended to be the
source of truth for "what needs work" — not a one-shot snapshot.

Usage: python scripts/audit-platform.py [--json] [--fix-list]
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKGS = sorted(p for p in (ROOT / "packages").iterdir() if p.name.startswith("kctl-"))


@dataclass
class PkgReport:
    name: str
    lint_clean: bool = False
    format_clean: bool = False
    tests_pass: bool = False
    test_count: int = 0
    cmd_count: int = 0
    readme_lines: int = 0
    has_skill: bool = False
    has_conftest: bool = False
    has_doctor: bool = False
    has_self_update: bool = False
    has_completions: bool = False
    has_config_init: bool = False
    has_skill_generate: bool = False
    mypy_clean: bool = False
    in_ci: bool = False
    notes: list[str] = field(default_factory=list)
    score: int = 0


def _run(
    cmd: list[str], cwd: Path | None = None, timeout: int = 120
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, check=False, timeout=timeout
    )


def _count_commands(pkg_dir: Path) -> int:
    """Count @app.command() decorators across the package's src/ directory."""
    count = 0
    src = pkg_dir / "src"
    if not src.exists():
        return 0
    for py in src.rglob("*.py"):
        try:
            tree = ast.parse(py.read_text())
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                for dec in node.decorator_list:
                    if _is_command_decorator(dec):
                        count += 1
                        break
    return count


def _is_command_decorator(dec: ast.expr) -> bool:
    if isinstance(dec, ast.Call):
        dec = dec.func
    if isinstance(dec, ast.Attribute):
        return dec.attr == "command"
    return False


def _count_tests(pkg_dir: Path) -> int:
    """Count test functions (test_*) in tests/ dir."""
    count = 0
    tests = pkg_dir / "tests"
    if not tests.exists():
        return 0
    for py in tests.rglob("test_*.py"):
        try:
            tree = ast.parse(py.read_text())
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(
                node, ast.FunctionDef | ast.AsyncFunctionDef
            ) and node.name.startswith("test_"):
                count += 1
    return count


def _grep(path: Path, pattern: str) -> bool:
    """Return True if any .py file under path contains pattern."""
    if not path.exists():
        return False
    for py in path.rglob("*.py"):
        try:
            if pattern in py.read_text():
                return True
        except Exception:
            continue
    return False


def _in_ci_matrix(name: str) -> bool:
    """Check CI matrix for an exact package-name entry.

    Uses a newline-anchored match so `kctl-op` doesn't falsely match
    `kctl-opencloud`, and `kctl-pg` doesn't match a hypothetical `kctl-pg-x`.
    """
    ci = ROOT / ".github" / "workflows" / "ci.yml"
    if not ci.exists():
        return False
    text = ci.read_text()
    return f"- {name}\n" in text or f"- {name} " in text


def audit_package(pkg_dir: Path) -> PkgReport:
    name = pkg_dir.name
    r = PkgReport(name=name)

    # Lint
    lint = _run(["uv", "run", "ruff", "check", str(pkg_dir / "src")], cwd=ROOT)
    r.lint_clean = lint.returncode == 0

    # Format
    fmt = _run(
        ["uv", "run", "ruff", "format", "--check", str(pkg_dir / "src")], cwd=ROOT
    )
    r.format_clean = fmt.returncode == 0

    # Tests — count + pass status
    r.test_count = _count_tests(pkg_dir)
    if r.test_count > 0:
        test_run = _run(
            ["uv", "run", "pytest", str(pkg_dir / "tests"), "-q", "--tb=no"],
            cwd=ROOT,
            timeout=300,
        )
        r.tests_pass = test_run.returncode == 0
    else:
        r.tests_pass = True  # no tests to fail

    # Commands
    r.cmd_count = _count_commands(pkg_dir)

    # README
    readme = pkg_dir / "README.md"
    r.readme_lines = len(readme.read_text().splitlines()) if readme.exists() else 0

    # SKILL
    r.has_skill = (
        any((pkg_dir / "skills").glob("*/SKILL.md"))
        if (pkg_dir / "skills").exists()
        else False
    )

    # conftest
    r.has_conftest = (pkg_dir / "tests" / "conftest.py").exists()

    # Standard commands
    src = pkg_dir / "src"
    r.has_doctor = (
        _grep(src, '@app.command("doctor")')
        or _grep(src, 'name="doctor"')
        or _grep(src, "doctor_app")
        or _grep(src, '("doctor",')
        or _grep(src, "commands.doctor")
    )
    r.has_self_update = _grep(src, "self-update") or _grep(src, "self_update")
    r.has_completions = _grep(src, "completions")
    r.has_config_init = (
        _grep(src, "config_init")
        or _grep(src, "init_config")
        or _grep(src, "commands.config")
    )
    r.has_skill_generate = _grep(src, "skill_generator") or _grep(src, "generate_skill")

    # Mypy (strict)
    if name != "kctl-lib":  # kctl-lib has its own test suite we handle separately
        mypy = _run(["uv", "run", "mypy", str(pkg_dir / "src")], cwd=ROOT, timeout=180)
        r.mypy_clean = mypy.returncode == 0
    else:
        r.mypy_clean = True

    # CI inclusion
    r.in_ci = _in_ci_matrix(name) if name != "kctl-lib" else True  # lib has its own job

    r.score = _score(r)
    return r


def _score(r: PkgReport) -> int:
    """Compute a 1-10 score by subtracting 1 per missed check from 10.

    Checks (9 total, max -9 → floor of 1):
    1. Lint clean
    2. Format clean
    3. Tests pass
    4. Test ratio ≥ 0.3 tests/cmd  (or lib: any tests)
    5. README ≥ 60 lines
    6. SKILL.md present  (CLIs only — lib exempt)
    7. Has doctor command  (CLIs only)
    8. Has config init command  (CLIs only)
    9. In CI matrix

    Mypy is tracked but NOT in the score — it's a cross-cutting debt area
    to be eliminated separately via a ratchet.
    """
    is_lib = r.name == "kctl-lib"
    score = 10
    misses: list[str] = []

    if not r.lint_clean:
        score -= 1
        misses.append("lint")
    if not r.format_clean:
        score -= 1
        misses.append("format")
    if not r.tests_pass:
        score -= 1
        misses.append("tests")

    if r.cmd_count > 0:
        ratio = r.test_count / r.cmd_count
        if ratio < 0.3:
            score -= 1
            misses.append(f"coverage({r.test_count}/{r.cmd_count})")
    elif not is_lib and r.test_count == 0:
        score -= 1
        misses.append("no-tests")

    if r.readme_lines < 60:
        score -= 1
        misses.append(f"readme({r.readme_lines}L<60)")
    if not is_lib and not r.has_skill:
        score -= 1
        misses.append("no-skill")
    if not is_lib and not r.has_doctor:
        score -= 1
        misses.append("no-doctor")
    if not is_lib and not r.has_config_init:
        score -= 1
        misses.append("no-config-init")
    if not r.in_ci:
        score -= 1
        misses.append("not-in-ci")

    r.notes = misses
    return max(1, score)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="Emit JSON")
    ap.add_argument("--fix-list", action="store_true", help="List packages below 9")
    args = ap.parse_args()

    reports: list[PkgReport] = []
    for pkg in PKGS:
        print(f"Auditing {pkg.name}...", file=sys.stderr)
        reports.append(audit_package(pkg))

    reports.sort(key=lambda r: (r.score, r.name))

    if args.json:
        print(json.dumps([r.__dict__ for r in reports], indent=2, default=str))
        return 0

    if args.fix_list:
        # Reuse the score's own missed-checks list (`notes`) so thresholds stay
        # in sync. Adds mypy as a diagnostic suggestion (not deducted from score).
        below = [r for r in reports if r.score < 9]
        for r in below:
            notes = list(r.notes)
            if not r.mypy_clean and r.name != "kctl-lib":
                notes.append("mypy (advisory)")
            print(f"{r.name} ({r.score}/10): {', '.join(notes)}")
        return 0

    # Default: pretty table
    print(
        f"{'Package':<20} {'Score':>5} {'Lint':>5} {'Fmt':>4} {'Test':>5} {'Cmds':>5} {'Tests':>6} {'Doc':>4} {'CI':>3} {'Mypy':>5} {'README':>7}"
    )
    print("-" * 90)
    for r in reports:
        print(
            f"{r.name:<20} {r.score:>4}/10 "
            f"{'OK' if r.lint_clean else 'FAIL':>5} "
            f"{'OK' if r.format_clean else 'FAIL':>4} "
            f"{'OK' if r.tests_pass else 'FAIL':>5} "
            f"{r.cmd_count:>5} "
            f"{r.test_count:>6} "
            f"{'Y' if r.has_doctor else '-':>4} "
            f"{'Y' if r.in_ci else '-':>3} "
            f"{'OK' if r.mypy_clean else 'FAIL':>5} "
            f"{r.readme_lines:>4}L"
        )
    avg = sum(r.score for r in reports) / len(reports)
    print("-" * 90)
    print(
        f"Average: {avg:.1f}/10   |   9+ packages: {sum(1 for r in reports if r.score >= 9)}/{len(reports)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
