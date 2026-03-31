"""Git workflow helpers for kctl-* CLI tools."""

from __future__ import annotations

import re
from pathlib import Path

from kctl_lib.runner import run, run_quiet


def branch_status(cwd: Path | None = None) -> dict:  # type: ignore[type-arg]
    branch = run_quiet(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    branch_name = branch.stdout.strip() if branch.returncode == 0 else "unknown"
    ahead_behind = run_quiet(["git", "rev-list", "--left-right", "--count", f"HEAD...origin/{branch_name}"], cwd=cwd)
    ahead, behind = 0, 0
    if ahead_behind.returncode == 0 and "\t" in ahead_behind.stdout:
        parts = ahead_behind.stdout.strip().split("\t")
        ahead, behind = int(parts[0]), int(parts[1])
    status = run_quiet(["git", "status", "--porcelain"], cwd=cwd)
    dirty_files = [line for line in status.stdout.splitlines() if line.strip()] if status.returncode == 0 else []
    stash = run_quiet(["git", "stash", "list"], cwd=cwd)
    stash_count = len(stash.stdout.strip().splitlines()) if stash.returncode == 0 and stash.stdout.strip() else 0
    return {
        "branch": branch_name,
        "ahead": ahead,
        "behind": behind,
        "dirty_count": len(dirty_files),
        "dirty_files": dirty_files,
        "stash_count": stash_count,
    }


def pr_create(title: str, body: str, base: str = "main", cwd: Path | None = None) -> str:
    result = run(["gh", "pr", "create", "--title", title, "--body", body, "--base", base], cwd=cwd)
    return result.stdout.strip()


def release_tag(version: str, message: str, cwd: Path | None = None) -> None:
    run(["git", "tag", "-a", version, "-m", message], cwd=cwd)
    run(["git", "push", "origin", version], cwd=cwd)


def changelog_generate(since_tag: str | None = None, cwd: Path | None = None) -> str:
    cmd = ["git", "log", "--oneline", "--no-merges"]
    if since_tag:
        cmd.append(f"{since_tag}..HEAD")
    else:
        cmd.extend(["-50"])
    result = run_quiet(cmd, cwd=cwd)
    if result.returncode != 0:
        return ""
    features, fixes, others = [], [], []
    for line in result.stdout.strip().splitlines():
        msg = re.sub(r"^[a-f0-9]+ ", "", line)
        if msg.startswith("feat"):
            features.append(f"- {msg}")
        elif msg.startswith("fix"):
            fixes.append(f"- {msg}")
        else:
            others.append(f"- {msg}")
    sections = []
    if features:
        sections.append("### Features\n" + "\n".join(features))
    if fixes:
        sections.append("### Fixes\n" + "\n".join(fixes))
    if others:
        sections.append("### Other\n" + "\n".join(others))
    return "\n\n".join(sections)


def diff_summary(base: str = "main", cwd: Path | None = None) -> dict:  # type: ignore[type-arg]
    result = run_quiet(["git", "diff", "--stat", base], cwd=cwd)
    if result.returncode != 0:
        return {"files_changed": 0, "insertions": 0, "deletions": 0, "raw": ""}
    raw = result.stdout.strip()
    match = re.search(r"(\d+) files? changed", raw)
    files = int(match.group(1)) if match else 0
    ins = re.search(r"(\d+) insertion", raw)
    insertions = int(ins.group(1)) if ins else 0
    dels = re.search(r"(\d+) deletion", raw)
    deletions = int(dels.group(1)) if dels else 0
    return {"files_changed": files, "insertions": insertions, "deletions": deletions, "raw": raw}
