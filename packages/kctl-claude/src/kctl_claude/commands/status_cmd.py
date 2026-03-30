"""kctl-claude status — one-page dashboard."""

from __future__ import annotations

import typer

from kctl_claude.core.callbacks import AppContext
from kctl_claude.core.checks import collect_status

app = typer.Typer(help="Status dashboard and health checks.")


@app.callback(invoke_without_command=True)
def status(ctx: typer.Context) -> None:
    """Show one-page Claude Code status dashboard."""
    if ctx.invoked_subcommand is not None:
        return
    actx: AppContext = ctx.obj
    out = actx.output
    data = collect_status(actx.claude_dir, actx.config_dir)

    if actx.json_mode:
        out.raw_json(data)
        return

    _render_dashboard(out, data)


@app.command()
def health(ctx: typer.Context) -> None:
    """Quick health check (exit code 0=ok, 1=issues)."""
    actx: AppContext = ctx.obj
    out = actx.output
    data = collect_status(actx.claude_dir, actx.config_dir)

    if actx.json_mode:
        out.raw_json(data)
        return

    issues = 0
    c = data["claude"]
    if c["installed"]:
        out.success(f"Claude Code: {c['version']}")
    else:
        out.error("Claude Code: not installed")
        issues += 1

    if data["auth"]["credentials"]:
        out.success("Auth: credentials found")
    else:
        out.warn("Auth: no credentials (run: claude login)")
        issues += 1

    cfg = data["config"]
    if cfg.get("sync_status") == "synced":
        out.success("Config: in sync")
    elif cfg.get("sync_status") == "out-of-sync":
        out.warn("Config: out of sync")
        issues += 1
    else:
        out.info("Config: no repo found")

    s = data["settings"]
    if s["exists"] and s["hooks"]:
        out.success("Settings: configured")
    elif not s["exists"]:
        out.error("Settings: missing")
        issues += 1
    else:
        out.warn("Settings: hooks not configured")

    srv = data["server"]
    if srv["sdk_api_up"]:
        out.success(f"SDK API: up ({srv['sdk_in_flight']}/{srv['sdk_max_concurrent']} tasks)")
    else:
        out.info("SDK API: not running")

    upd = data["updates"]
    if upd["up_to_date"]:
        out.success(f"Updates: current ({upd['latest_npm']})")
    elif upd["latest_npm"]:
        out.warn(f"Updates: {upd['current']} -> {upd['latest_npm']} available")
    else:
        out.info("Updates: could not check")

    if issues:
        raise typer.Exit(code=1)


@app.command()
def updates(ctx: typer.Context) -> None:
    """Check for Claude Code updates and show changelog link."""
    actx: AppContext = ctx.obj
    out = actx.output
    data = collect_status(actx.claude_dir, actx.config_dir)
    upd = data["updates"]

    if actx.json_mode:
        out.raw_json(upd)
        return

    out.header("CLAUDE CODE UPDATES")
    out.text(f"  Installed: [bold]{upd['current'] or 'not found'}[/bold]")
    out.text(f"  Latest:    [bold]{upd['latest_npm'] or 'unknown'}[/bold]")

    if upd["up_to_date"]:
        out.success("You are up to date")
    elif upd["latest_npm"]:
        out.warn(f"Update available: {upd['latest_npm']}")
        out.text("  Run: [bold]npm update -g @anthropic-ai/claude-code[/bold]")
    else:
        out.info("Could not check (npm not available)")

    out.text("")
    out.text("  [dim]Changelog: https://github.com/anthropics/claude-code/releases[/dim]")
    out.text("  [dim]Docs:      https://docs.anthropic.com/en/docs/claude-code[/dim]")
    out.text("  [dim]What's new: https://claude.ai/code[/dim]")


def _render_dashboard(out, data: dict) -> None:
    """Render the full dashboard."""
    from datetime import datetime

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    out.console.print(f"\n[bold]{'═' * 58}[/bold]")
    out.console.print(f"[bold]  Claude Code Status Dashboard[/bold]         {now}")
    out.console.print(f"[bold]{'═' * 58}[/bold]")

    # Claude Code
    out.header("CLAUDE CODE")
    c = data["claude"]
    if c["installed"]:
        out.ok(f"Installed: [bold]{c['version']}[/bold]")
    else:
        out.fail("Not installed — run: npm i -g @anthropic-ai/claude-code")
    a = data["auth"]
    out.ok("Credentials: found") if a["credentials"] else out.warn("Credentials: missing")
    out.ok("OAuth: configured") if a["oauth"] else out.dim("OAuth: not set")

    # Config
    out.header("CONFIG (local / repo)")
    cfg = data["config"]
    local = cfg.get("local", {})
    repo = cfg.get("repo", {})
    out.console.print(f"  {'':12} [bold]{'Local':8}[/bold] │ [dim]{'Repo':8}[/dim]")
    for key in ("agents", "skills", "commands", "rules"):
        lv = str(local.get(key, "-"))
        rv = str(repo.get(key, "-"))
        out.console.print(f"  {key:12} {lv:8} │ {rv:8}")
    out.print("")
    if cfg["sync_status"] == "synced":
        out.ok("Sync: [green]in sync[/green]")
    elif cfg["sync_status"] == "out-of-sync":
        out.warn("Sync: [yellow]out of sync[/yellow] — run: kctl-claude sync push")
        for d in cfg.get("sync_details", []):
            out.dim(f"  {d['dir']}: {d['diffs']} file(s) differ")
    else:
        out.dim("Sync: no repo found")

    # Settings
    out.header("SETTINGS")
    s = data["settings"]
    out.ok("settings.json: found") if s["exists"] else out.fail("settings.json: missing")
    out.ok("Hooks: configured") if s["hooks"] else out.warn("Hooks: not configured")
    out.ok("Plugins: enabled") if s["plugins"] else out.warn("Plugins: not configured")
    out.ok("Extended thinking: on") if s["thinking"] else out.dim("Extended thinking: off")
    out.ok(f"MCP servers: {s['mcp']}") if s["mcp"] else out.dim("MCP: not configured")

    # Tools
    out.header("DEV TOOLS")
    t = data["tools"]
    tool_line = ""
    for name in ("ruff", "prettier", "pnpm", "uv", "gh", "docker", "terraform", "tmux"):
        color = "green" if t.get(name) else "red"
        tool_line += f"[{color}]●[/{color}]{name}  "
    out.console.print(f"  {tool_line}")
    ki, kt = t["kctl_installed"], t["kctl_total"]
    if ki == kt:
        out.ok(f"kctl tools: [bold]{ki}/{kt}[/bold] installed")
    elif ki > 0:
        out.warn(f"kctl tools: [bold]{ki}/{kt}[/bold] installed")
    else:
        out.dim(f"kctl tools: 0/{kt}")
    out.ok("kctl config: found") if t["kctl_config"] else out.warn("kctl config: missing")

    # Server
    out.header("SERVER")
    srv = data["server"]
    if srv["container_running"]:
        out.ok("Container: [green]running[/green]")
        if srv["container_healthy"]:
            out.ok("Health: [green]healthy[/green]")
        else:
            out.warn("Health: [yellow]not healthy[/yellow]")
    else:
        out.dim("Container: not running locally")
    if srv["sdk_api_up"]:
        inf = srv.get("sdk_in_flight", 0)
        mx = srv.get("sdk_max_concurrent", 3)
        out.ok(f"SDK API: [green]up[/green] — {inf}/{mx} tasks in flight")
    else:
        out.dim("SDK API: not reachable")

    # Updates
    out.header("UPDATES")
    upd = data["updates"]
    if upd["up_to_date"]:
        out.ok(f"Claude Code: [green]up to date[/green] ({upd['latest_npm']})")
    elif upd["latest_npm"]:
        out.warn(f"Claude Code: [yellow]{upd['current']} → {upd['latest_npm']}[/yellow]")
        out.dim("Run: npm update -g @anthropic-ai/claude-code")
    else:
        out.dim("Could not check for updates")

    # Git
    out.header("GIT")
    g = data["git"]
    if g["branch"]:
        out.ok(f"Branch: [bold]{g['branch']}[/bold]")
    out.ok("Working tree: [green]clean[/green]") if g["clean"] else out.warn(
        "Working tree: [yellow]uncommitted changes[/yellow]"
    )

    # Summary
    issues = 0
    if not c["installed"]:
        issues += 1
    if not a["credentials"]:
        issues += 1
    if not s["exists"]:
        issues += 1
    if cfg["sync_status"] == "out-of-sync":
        issues += 1
    if not g["clean"]:
        issues += 1
    if upd.get("latest_npm") and not upd["up_to_date"]:
        issues += 1

    out.console.print(f"\n[bold]{'═' * 58}[/bold]")
    if issues == 0:
        out.console.print("  [green bold]All clear[/green bold] — no issues found")
    else:
        out.console.print(f"  [yellow bold]{issues} issue(s)[/yellow bold] need attention")
    out.console.print(f"[bold]{'═' * 58}[/bold]\n")
