"""kctl-claude doctor — scored diagnostics using kctl-common doctor_base."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer
from kctl_common.doctor_base import (
    CheckResult,
    DockerCheck,
    GitCheck,
    PythonVersionCheck,
    UvCheck,
    run_doctor,
)
from kctl_common.runner import run_quiet

from kctl_claude.core.callbacks import AppContext

app = typer.Typer(help="Diagnostics and health checks.")


class ClaudeCodeCheck:
    """Check if Claude Code CLI is installed and working."""

    name = "Claude Code"

    def run(self) -> CheckResult:
        result = run_quiet(["claude", "--version"])
        if result.returncode == 0:
            return CheckResult(name=self.name, status="ok", message=f"Installed: {result.stdout.strip()}")
        return CheckResult(
            name=self.name,
            status="fail",
            message="Claude Code not found",
            fix_command="npm install -g @anthropic-ai/claude-code",
        )


class AuthCheck:
    """Check for Claude Code credentials."""

    name = "Authentication"

    def run(self) -> CheckResult:
        claude_dir = Path.home() / ".claude"
        if (claude_dir / ".credentials.json").is_file():
            return CheckResult(name=self.name, status="ok", message="Credentials found")
        if (Path.home() / ".claude.json").is_file():
            return CheckResult(name=self.name, status="ok", message="OAuth token found")
        return CheckResult(
            name=self.name,
            status="warn",
            message="No credentials found",
            fix_command="claude login",
        )


class ConfigSyncCheck:
    """Check if config is in sync with repo."""

    name = "Config Sync"

    def run(self) -> CheckResult:
        claude_dir = Path.home() / ".claude"
        # Look for the repo
        for path in [
            Path.home() / "project" / "00-new-projects" / "kodemeio-app" / "kodemeio-claude",
            Path("/opt/dev/kodemeio-claude"),
        ]:
            config_dir = path / "config" / ".claude"
            if config_dir.is_dir():
                for name in ("agents", "skills", "rules"):
                    local = claude_dir / name
                    repo = config_dir / name
                    if local.is_dir() and repo.is_dir():
                        r = run_quiet(["diff", "-rq", str(local), str(repo)])
                        if r.stdout.strip():
                            return CheckResult(
                                name=self.name,
                                status="warn",
                                message="Config out of sync with repo",
                                fix_command="kctl-claude sync push",
                            )
                return CheckResult(name=self.name, status="ok", message="In sync")
        return CheckResult(name=self.name, status="warn", message="Repo not found for sync check")


class SettingsCheck:
    """Check settings.json configuration."""

    name = "Settings"

    def run(self) -> CheckResult:
        sf = Path.home() / ".claude" / "settings.json"
        if not sf.is_file():
            return CheckResult(name=self.name, status="fail", message="settings.json not found")
        text = sf.read_text()
        issues = []
        if '"PreToolUse"' not in text:
            issues.append("no hooks")
        if '"enabledPlugins"' not in text:
            issues.append("no plugins")
        if issues:
            return CheckResult(
                name=self.name,
                status="warn",
                message=f"settings.json: {', '.join(issues)}",
            )
        return CheckResult(name=self.name, status="ok", message="Configured with hooks and plugins")


class NodeCheck:
    """Check Node.js version."""

    name = "Node.js"

    def run(self) -> CheckResult:
        result = run_quiet(["node", "--version"])
        if result.returncode == 0:
            return CheckResult(name=self.name, status="ok", message=f"Node {result.stdout.strip()}")
        return CheckResult(
            name=self.name,
            status="fail",
            message="Node.js not found",
            fix_command="nvm install 22",
        )


class KctlConfigCheck:
    """Check kctl shared config."""

    name = "Kctl Config"

    def run(self) -> CheckResult:
        config = Path.home() / ".config" / "kodemeio" / "config.yaml"
        if config.is_file():
            return CheckResult(name=self.name, status="ok", message=f"Found: {config}")
        return CheckResult(
            name=self.name,
            status="warn",
            message="No shared kctl config",
            fix_command="kctl-claude config init",
        )


class SdkApiCheck:
    """Check SDK API reachability."""

    name = "SDK API"

    def run(self) -> CheckResult:
        import httpx

        for url in ("http://localhost:3100/health", "http://127.0.0.1:3100/health"):
            try:
                resp = httpx.get(url, timeout=3)
                if resp.status_code == 200:
                    return CheckResult(name=self.name, status="ok", message=f"Reachable at {url}")
            except Exception:
                pass
        return CheckResult(name=self.name, status="warn", message="Not running (optional)")


class GhCliCheck:
    """Check GitHub CLI."""

    name = "GitHub CLI"

    def run(self) -> CheckResult:
        if shutil.which("gh"):
            return CheckResult(name=self.name, status="ok", message="gh available")
        return CheckResult(
            name=self.name,
            status="warn",
            message="gh CLI not found",
            fix_command="brew install gh",
        )


@app.callback(invoke_without_command=True)
def doctor(ctx: typer.Context) -> None:
    """Run all diagnostic checks with scored output."""
    if ctx.invoked_subcommand is not None:
        return
    actx: AppContext = ctx.obj
    out = actx.output

    checks = [
        PythonVersionCheck(),
        UvCheck(),
        GitCheck(),
        DockerCheck(),
        NodeCheck(),
        GhCliCheck(),
        ClaudeCodeCheck(),
        AuthCheck(),
        SettingsCheck(),
        ConfigSyncCheck(),
        KctlConfigCheck(),
        SdkApiCheck(),
    ]

    all_passed = run_doctor(checks, out)  # type: ignore[arg-type]
    if not all_passed:
        raise typer.Exit(code=1)
