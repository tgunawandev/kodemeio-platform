"""kctl-claude verify — 14-point config audit."""

from __future__ import annotations

import typer
from kctl_common.exceptions import CommandError

from kctl_claude.core.callbacks import AppContext
from kctl_claude.core.runner import run_script

app = typer.Typer(help="Verify Claude Code config completeness.")


@app.callback(invoke_without_command=True)
def verify(ctx: typer.Context) -> None:
    """Run 14-point config verification."""
    if ctx.invoked_subcommand is not None:
        return
    actx: AppContext = ctx.obj
    out = actx.output
    repo = actx.repo_dir
    if repo:
        script = repo / "scripts" / "verify-scores.sh"
        if script.is_file():
            try:
                run_script(script, capture=False)
                out.success("Verification passed")
            except CommandError as e:
                out.error(f"Verification failed (exit {e.returncode})")
                raise typer.Exit(code=1) from None
            return
    # Fallback: run against local dir
    out.warn("Repo not found — checking local ~/.claude/ only")
    _verify_local(actx)


def _verify_local(actx: AppContext) -> None:
    """Basic local verification without the repo script."""
    out = actx.output
    d = actx.claude_dir
    results: list[dict[str, object]] = []
    issues = 0

    # Rules
    rules = list((d / "rules").glob("*.md")) if (d / "rules").is_dir() else []
    passed = len(rules) >= 3
    results.append({"check": "Rules", "count": len(rules), "status": "ok" if passed else "warn"})
    if not passed:
        issues += 1

    # Agents
    agents = list((d / "agents").glob("*.md")) if (d / "agents").is_dir() else []
    passed = len(agents) >= 2
    results.append({"check": "Agents", "count": len(agents), "status": "ok" if passed else "warn"})
    if not passed:
        issues += 1

    # Skills
    skills = [p for p in (d / "skills").iterdir() if p.is_dir()] if (d / "skills").is_dir() else []
    passed = len(skills) >= 10
    results.append({"check": "Skills", "count": len(skills), "status": "ok" if passed else "warn"})
    if not passed:
        issues += 1

    # Settings
    sf = d / "settings.json"
    if sf.is_file():
        text = sf.read_text()
        results.append({"check": "settings.json", "status": "ok"})
        has_hooks = '"PreToolUse"' in text
        results.append({"check": "Hooks", "status": "ok" if has_hooks else "warn"})
        if not has_hooks:
            issues += 1
        has_plugins = '"enabledPlugins"' in text
        results.append({"check": "Plugins", "status": "ok" if has_plugins else "warn"})
        if not has_plugins:
            issues += 1
    else:
        results.append({"check": "settings.json", "status": "fail"})
        issues += 1

    # Auth
    has_creds = (d / ".credentials.json").is_file()
    results.append({"check": "Credentials", "status": "ok" if has_creds else "warn"})
    if not has_creds:
        issues += 1

    # Output
    if actx.json_mode:
        out.raw_json({"checks": results, "issues": issues, "passed": issues == 0})
        if issues:
            raise typer.Exit(code=1)
        return

    out.header("LOCAL CONFIG VERIFICATION")
    for r in results:
        msg = f"{r['check']}"
        if "count" in r:
            msg += f": {r['count']} files"
        if r["status"] == "ok":
            out.success(msg)
        elif r["status"] == "warn":
            out.warn(msg)
        else:
            out.error(msg)

    out.text("")
    if issues:
        out.warn(f"{issues} issue(s) found")
        raise typer.Exit(code=1)
    out.success("All checks passed")
