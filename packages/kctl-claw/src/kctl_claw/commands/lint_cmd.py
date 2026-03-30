"""Configuration linting commands."""

from __future__ import annotations

import json

import typer
from croniter import croniter  # type: ignore[import-untyped]

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.config_manager import ConfigFile

app = typer.Typer(help="Lint configs, MCP servers, skills, and cron expressions.")

_REQUIRED_OPENCLAW_KEYS = ["agents", "channels", "tools", "bindings"]
_REQUIRED_MCP_KEYS = ["mcpServers"]
_REQUIRED_CRON_JOB_KEYS = ["id", "schedule", "agent", "prompt"]
_REQUIRED_SKILL_FRONTMATTER = ["name", "version", "description"]


def _collect_errors(label: str, errors: list[str], warnings: list[str]) -> list[tuple[str, str, str]]:
    rows = []
    for e in errors:
        rows.append((label, "ERROR", e))
    for w in warnings:
        rows.append((label, "WARN", w))
    if not errors and not warnings:
        rows.append((label, "OK", "All checks passed"))
    return rows


@app.command()
def config(ctx: typer.Context) -> None:
    """Validate openclaw.json schema structure."""
    actx: AppContext = ctx.obj
    out = actx.output

    errors: list[str] = []
    warnings: list[str] = []

    try:
        data = actx.config_mgr.read(ConfigFile.OPENCLAW)
    except FileNotFoundError as err:
        out.error("openclaw.json not found")
        raise typer.Exit(1) from err
    except json.JSONDecodeError as e:
        out.error(f"Invalid JSON in openclaw.json: {e}")
        raise typer.Exit(1) from e

    # Structural checks
    for key in _REQUIRED_OPENCLAW_KEYS:
        if key not in data:
            errors.append(f"Missing required key: {key!r}")

    # Agents checks
    agents = data.get("agents", {}).get("list", [])
    if not agents:
        warnings.append("No agents defined in agents.list")
    for i, agent in enumerate(agents):
        if not agent.get("name"):
            errors.append(f"agents.list[{i}]: missing 'name'")
        if not agent.get("model"):
            warnings.append(f"agents.list[{i}] ({agent.get('name', '?')}): missing 'model'")

    # Bindings checks
    bindings = data.get("bindings", [])
    for i, b in enumerate(bindings):
        if not b.get("channel"):
            errors.append(f"bindings[{i}]: missing 'channel'")
        if not b.get("agent"):
            errors.append(f"bindings[{i}]: missing 'agent'")

    # Also run built-in validation
    builtin_errors = actx.config_mgr.validate_json(ConfigFile.OPENCLAW)
    errors.extend(builtin_errors)

    rows = _collect_errors("openclaw.json", errors, warnings)
    out.table(
        f"Config Lint ({len(errors)} errors, {len(warnings)} warnings)",
        [("File", "cyan"), ("Level", ""), ("Message", "dim")],
        [[r[0], r[1], r[2]] for r in rows],
        data_for_json=[{"file": r[0], "level": r[1], "message": r[2]} for r in rows],
    )
    if errors:
        raise typer.Exit(1)


@app.command()
def mcp(ctx: typer.Context) -> None:
    """Validate MCP server configs in config.json."""
    actx: AppContext = ctx.obj
    out = actx.output

    errors: list[str] = []
    warnings: list[str] = []

    try:
        data = actx.config_mgr.read(ConfigFile.MCP_REGISTRY)
    except FileNotFoundError as err:
        out.error("config.json not found")
        raise typer.Exit(1) from err
    except json.JSONDecodeError as e:
        out.error(f"Invalid JSON in config.json: {e}")
        raise typer.Exit(1) from e

    servers = data.get("mcpServers", {})
    if not servers:
        errors.append("No mcpServers defined")

    for name, cfg in servers.items():
        if not cfg.get("command"):
            errors.append(f"{name}: missing 'command'")
        if "args" not in cfg:
            warnings.append(f"{name}: no 'args' defined")
        env = cfg.get("env", {})
        for env_key, env_val in env.items():
            if env_val and env_val.startswith("${") and not env_val.endswith("}"):
                errors.append(f"{name}.env.{env_key}: malformed env var reference: {env_val!r}")

    rows = _collect_errors("config.json", errors, warnings)
    out.table(
        f"MCP Lint ({len(servers)} servers, {len(errors)} errors, {len(warnings)} warnings)",
        [("File", "cyan"), ("Level", ""), ("Message", "dim")],
        [[r[0], r[1], r[2]] for r in rows],
        data_for_json=[{"file": r[0], "level": r[1], "message": r[2]} for r in rows],
    )
    if errors:
        raise typer.Exit(1)
    else:
        out.success(f"All {len(servers)} MCP server configs are valid.")


@app.command()
def skills(ctx: typer.Context) -> None:
    """Validate skill markdown files for required frontmatter and structure."""
    actx: AppContext = ctx.obj
    out = actx.output

    skills_dir = actx.project_root / "config" / "skills"
    if not skills_dir.exists():
        out.warn("Skills directory not found: config/skills/")
        return

    all_rows = []
    json_data = []
    total_errors = 0

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        skill_name = skill_dir.name
        skill_md = skill_dir / "SKILL.md"

        if not skill_md.exists():
            all_rows.append([skill_name, "ERROR", "Missing SKILL.md"])
            json_data.append({"skill": skill_name, "level": "ERROR", "message": "Missing SKILL.md"})
            total_errors += 1
            continue

        content = skill_md.read_text()
        # Parse frontmatter
        meta: dict[str, str] = {}
        if content.startswith("---"):
            lines = content.splitlines()
            for _i, line in enumerate(lines[1:], 1):
                if line.strip() == "---":
                    break
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip().strip('"').strip("'")

        for field in _REQUIRED_SKILL_FRONTMATTER:
            if field not in meta:
                all_rows.append([skill_name, "WARN", f"Missing frontmatter: {field!r}"])
                json_data.append({"skill": skill_name, "level": "WARN", "message": f"Missing frontmatter: {field!r}"})
            elif not meta[field]:
                all_rows.append([skill_name, "WARN", f"Empty frontmatter: {field!r}"])
                json_data.append({"skill": skill_name, "level": "WARN", "message": f"Empty frontmatter: {field!r}"})

        if not any(r[0] == skill_name for r in all_rows):
            trigger = meta.get("trigger", "")
            all_rows.append([skill_name, "OK", f"v{meta.get('version', '?')} trigger={trigger!r}"])
            json_data.append({"skill": skill_name, "level": "OK", "message": f"v{meta.get('version', '?')}"})

    out.table(
        f"Skills Lint ({len(skills_dir.glob('*')) if skills_dir.exists() else 0} skills, {total_errors} errors)",
        [("Skill", "cyan"), ("Level", ""), ("Message", "dim")],
        all_rows,
        data_for_json=json_data,
    )
    if total_errors:
        raise typer.Exit(1)
    else:
        out.success("All skill configs are valid.")


@app.command()
def cron(ctx: typer.Context) -> None:
    """Check cron expressions, agent references, and model references."""
    actx: AppContext = ctx.obj
    out = actx.output

    errors: list[str] = []
    warnings: list[str] = []

    try:
        cron_data = actx.config_mgr.read(ConfigFile.CRON_JOBS)
    except FileNotFoundError as err:
        out.error("cron/jobs.json not found")
        raise typer.Exit(1) from err
    except json.JSONDecodeError as e:
        out.error(f"Invalid JSON in cron/jobs.json: {e}")
        raise typer.Exit(1) from e

    # Load known agents for reference validation
    known_agents: set[str] = set()
    try:
        openclaw = actx.config_mgr.read(ConfigFile.OPENCLAW)
        known_agents = {a.get("name", "") for a in openclaw.get("agents", {}).get("list", [])}
    except Exception:
        pass

    jobs = cron_data.get("jobs", [])
    ids_seen: set[str] = set()

    for i, job in enumerate(jobs):
        job_id = job.get("id", f"jobs[{i}]")

        # Duplicate ID check
        if job_id in ids_seen:
            errors.append(f"{job_id}: duplicate job ID")
        ids_seen.add(job_id)

        # Required fields
        for field in _REQUIRED_CRON_JOB_KEYS:
            if field not in job:
                errors.append(f"{job_id}: missing required field {field!r}")

        # Cron expression validation
        schedule = job.get("schedule", "")
        if schedule and not croniter.is_valid(schedule):
            errors.append(f"{job_id}: invalid cron expression: {schedule!r}")

        # Agent reference
        agent = job.get("agent", "")
        if agent and known_agents and agent not in known_agents:
            warnings.append(f"{job_id}: references unknown agent {agent!r} (known: {', '.join(sorted(known_agents))})")

        # Prompt check
        prompt = job.get("prompt", "")
        if not prompt:
            warnings.append(f"{job_id}: empty prompt")
        elif len(prompt) < 10:
            warnings.append(f"{job_id}: very short prompt ({len(prompt)} chars)")

    rows = _collect_errors("cron/jobs.json", errors, warnings)
    out.table(
        f"Cron Lint ({len(jobs)} jobs, {len(errors)} errors, {len(warnings)} warnings)",
        [("File", "cyan"), ("Level", ""), ("Message", "dim")],
        [[r[0], r[1], r[2]] for r in rows],
        data_for_json=[{"file": r[0], "level": r[1], "message": r[2]} for r in rows],
    )
    if errors:
        raise typer.Exit(1)
    elif not warnings:
        out.success(f"All {len(jobs)} cron job configs are valid.")
