"""Health and status checks — the core data collector."""

from __future__ import annotations

import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import httpx


def collect_status(claude_dir: Path, config_dir: Path | None) -> dict:
    """Collect comprehensive status data. Returns a JSON-serializable dict."""
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "claude": _claude_info(),
        "auth": _auth_info(claude_dir),
        "config": _config_info(claude_dir, config_dir),
        "settings": _settings_info(claude_dir),
        "tools": _tools_info(),
        "server": _server_info(),
        "git": _git_info(),
        "updates": _update_info(),
    }


def _claude_info() -> dict:
    installed = shutil.which("claude") is not None
    version = ""
    if installed:
        try:
            r = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=5)
            version = r.stdout.strip() if r.returncode == 0 else "unknown"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            version = "unknown"
    return {"installed": installed, "version": version}


def _auth_info(claude_dir: Path) -> dict:
    return {
        "credentials": (claude_dir / ".credentials.json").is_file(),
        "oauth": (Path.home() / ".claude.json").is_file(),
    }


def _config_info(claude_dir: Path, config_dir: Path | None) -> dict:
    local = _count_config(claude_dir)
    repo = _count_config(config_dir) if config_dir else {}
    sync = _sync_status(claude_dir, config_dir)
    return {"local": local, "repo": repo, **sync}


def _count_config(base: Path | None) -> dict:
    if not base or not base.is_dir():
        return {"agents": 0, "skills": 0, "commands": 0, "rules": 0}
    return {
        "agents": len(list((base / "agents").glob("*.md"))) if (base / "agents").is_dir() else 0,
        "skills": len([d for d in (base / "skills").iterdir() if d.is_dir()]) if (base / "skills").is_dir() else 0,
        "commands": len(list((base / "commands").glob("*.md"))) if (base / "commands").is_dir() else 0,
        "rules": len(list((base / "rules").glob("*.md"))) if (base / "rules").is_dir() else 0,
    }


def _sync_status(claude_dir: Path, config_dir: Path | None) -> dict:
    if not config_dir or not config_dir.is_dir():
        return {"sync_status": "no-repo", "sync_details": []}
    details = []
    for name in ("agents", "skills", "commands", "rules"):
        local = claude_dir / name
        repo = config_dir / name
        if local.is_dir() and repo.is_dir():
            try:
                r = subprocess.run(
                    ["diff", "-rq", str(local), str(repo)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if r.stdout.strip():
                    count = len(r.stdout.strip().splitlines())
                    details.append({"dir": name, "diffs": count})
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
    status = "synced" if not details else "out-of-sync"
    return {"sync_status": status, "sync_details": details}


def _settings_info(claude_dir: Path) -> dict:
    sf = claude_dir / "settings.json"
    if not sf.is_file():
        return {"exists": False, "hooks": False, "plugins": False, "thinking": False, "mcp": 0}
    try:
        text = sf.read_text()
    except OSError:
        return {"exists": True, "hooks": False, "plugins": False, "thinking": False, "mcp": 0}
    return {
        "exists": True,
        "hooks": '"PreToolUse"' in text,
        "plugins": '"enabledPlugins"' in text,
        "thinking": '"alwaysThinkingEnabled": true' in text or '"alwaysThinkingEnabled":true' in text,
        "mcp": _count_mcp(),
    }


def _count_mcp() -> int:
    mcp_file = Path.home() / ".mcp.json"
    if not mcp_file.is_file():
        return 0
    try:
        return mcp_file.read_text().count('"command"')
    except OSError:
        return 0


def _tools_info() -> dict:
    tools = {}
    for name in ("ruff", "prettier", "pnpm", "uv", "gh", "docker", "terraform", "tmux"):
        tools[name] = shutil.which(name) is not None
    # kctl tools
    kctl_names = [
        "kctl-ak",
        "kctl-glitchtip",
        "kctl-mailcow",
        "kctl-mdm",
        "kctl-outline",
        "kctl-pg",
        "kctl-plane",
        "kctl-rmm",
        "kctl-zulip",
        "kctl-odoo",
        "kctl-1password",
        "kctl-dokploy",
        "kctl-cloudflare",
        "kctl-hetzner",
    ]
    kctl_installed = sum(1 for t in kctl_names if shutil.which(t))
    kctl_config = (Path.home() / ".config" / "kodemeio" / "config.yaml").is_file()
    return {
        **tools,
        "kctl_installed": kctl_installed,
        "kctl_total": len(kctl_names),
        "kctl_config": kctl_config,
    }


def _server_info() -> dict:
    container_running = False
    container_healthy = False
    sdk_api_up = False
    sdk_data: dict = {}

    # Docker container
    if shutil.which("docker"):
        try:
            r = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if "kodemeio-claude" in (r.stdout or ""):
                container_running = True
                h = subprocess.run(
                    [
                        "docker",
                        "inspect",
                        "--format",
                        "{{.State.Health.Status}}",
                        "kodemeio-claude",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                container_healthy = h.stdout.strip() == "healthy"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # SDK API
    for url in ("http://localhost:3100/health", "http://127.0.0.1:3100/health"):
        try:
            resp = httpx.get(url, timeout=3)
            if resp.status_code == 200:
                sdk_api_up = True
                try:
                    sdk_data = resp.json()
                except Exception:
                    sdk_data = {}
                break
        except (httpx.ConnectError, httpx.TimeoutException, Exception):
            pass

    return {
        "container_running": container_running,
        "container_healthy": container_healthy,
        "sdk_api_up": sdk_api_up,
        "sdk_in_flight": sdk_data.get("inFlight"),
        "sdk_max_concurrent": sdk_data.get("maxConcurrent"),
    }


def _git_info() -> dict:
    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return {
            "branch": branch.stdout.strip() if branch.returncode == 0 else "",
            "clean": not bool(status.stdout.strip()) if status.returncode == 0 else True,
        }
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"branch": "", "clean": True}


def _update_info() -> dict:
    """Check for Claude Code updates."""
    current = ""
    latest = ""
    try:
        r = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            current = r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    try:
        r = subprocess.run(
            ["npm", "view", "@anthropic-ai/claude-code", "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            latest = r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    up_to_date = bool(current and latest and latest in current)
    return {"current": current, "latest_npm": latest, "up_to_date": up_to_date}
