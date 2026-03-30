"""CI/CD pipeline automation and observability commands."""

from __future__ import annotations

import contextlib
import re
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.client import OdooClient
from kctl_odoo.core.config import resolve_connection
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="CI/CD pipeline automation and observability.")

# Safe git ref pattern — letters, digits, and common ref chars
_REF_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/~^@{}\-]*$")

# Conventional Commit parser: type(scope)!: description
_CC_RE = re.compile(r"^(\w+)(?:\(([^)]+)\))?[!]?:\s*(.+)$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_client_for_profile(profile_name: str) -> OdooClient:
    """Build an OdooClient from a named config profile."""
    url, db, user, key = resolve_connection(
        profile_name=profile_name,
        url_override=None,
        api_key_override=None,
        database_override=None,
        username_override=None,
    )
    return OdooClient(base_url=url, database=db, username=user, api_key=key)


def _fetch_installed_modules(client: OdooClient) -> dict[str, dict]:
    """Return {technical_name: {version, state}} for installed modules."""
    records = client.search_read(
        "ir.module.module",
        domain=[("state", "!=", "uninstalled")],
        fields=["name", "installed_version", "state"],
        limit=0,
        order="name",
    )
    return {r["name"]: {"version": r.get("installed_version") or "", "state": r.get("state", "")} for r in records}


def _fetch_config_params(client: OdooClient) -> dict[str, str]:
    """Return {key: value} for system parameters."""
    records = client.search_read(
        "ir.config_parameter",
        domain=[],
        fields=["key", "value"],
        limit=0,
        order="key",
    )
    return {r["key"]: str(r.get("value", "")) for r in records}


def _validate_git_ref(ref: str, name: str) -> None:
    """Validate a git ref string to prevent argument injection."""
    if not _REF_RE.match(ref):
        raise typer.BadParameter(f"Invalid git ref for {name}: {ref!r}")


def _run_step(name: str, cmd: list[str], cwd: str | None = None) -> dict:
    """Run a subprocess step and return result dict."""
    start = time.monotonic()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=cwd)
        elapsed = round(time.monotonic() - start, 2)
        return {
            "name": name,
            "passed": result.returncode == 0,
            "exit_code": result.returncode,
            "duration_s": elapsed,
            "stdout": result.stdout[-2000:] if result.stdout else "",
            "stderr": result.stderr[-2000:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = round(time.monotonic() - start, 2)
        partial_out = ""
        if exc.stdout:
            partial_out = (
                exc.stdout.decode(errors="replace")[-500:] if isinstance(exc.stdout, bytes) else exc.stdout[-500:]
            )
        return {
            "name": name,
            "passed": False,
            "exit_code": -1,
            "duration_s": elapsed,
            "stdout": partial_out,
            "stderr": "Timed out after 600s",
        }
    except FileNotFoundError:
        return {
            "name": name,
            "passed": False,
            "exit_code": -1,
            "duration_s": 0,
            "stdout": "",
            "stderr": f"Command not found: {cmd[0]}",
        }


def _truncate(value: str, max_len: int = 60) -> str:
    """Truncate a string for display."""
    if len(value) > max_len:
        return value[: max_len - 3] + "..."
    return value


# ---------------------------------------------------------------------------
# 1. pipeline validate
# ---------------------------------------------------------------------------


@app.command()
def validate(
    ctx: typer.Context,
    skip_lint: Annotated[bool, typer.Option("--skip-lint", help="Skip lint step")] = False,
    skip_test: Annotated[bool, typer.Option("--skip-test", help="Skip test step")] = False,
) -> None:
    """Run lint + test + preflight + smoke-test as a single CI gate.

    Runs each step sequentially. Exit code 0 if all pass, 1 if any fail.
    Use --json for CI-parseable output. Use the top-level --profile flag
    to target a specific instance for preflight and smoke-test steps.

    Examples:
        kctl-odoo --profile staging pipeline validate
        kctl-odoo pipeline validate --json
        kctl-odoo pipeline validate --skip-lint
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Resolve repo root for subprocess calls
    from kctl_odoo.core.utils import find_project_root

    repo_root_path = find_project_root()
    if not (repo_root_path / "src").is_dir():
        out.warn(f"Cannot locate repo root at {repo_root_path}, lint/test steps may fail")
    repo_root = str(repo_root_path)

    steps: list[dict] = []

    # Step 1: Lint
    if not skip_lint:
        out.info("Running lint-all...")
        steps.append(_run_step("lint", [sys.executable, "-m", "kctl_odoo", "lint", "all"], cwd=repo_root))
    else:
        out.info("Skipping lint (--skip-lint)")

    # Step 2: Test
    if not skip_test:
        out.info("Running tests...")
        cli_dir = str(Path(__file__).resolve().parents[3])
        steps.append(_run_step("test", [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short"], cwd=cli_dir))
    else:
        out.info("Skipping test (--skip-test)")

    # Step 3: Preflight — health check + module state verification
    out.info("Running preflight checks...")
    preflight_start = time.monotonic()
    preflight_passed = True
    preflight_details: list[str] = []

    try:
        ok, version = c.check_health()
        if ok:
            preflight_details.append(f"Health: OK (v{version})")
        else:
            preflight_passed = False
            preflight_details.append(f"Health: FAIL ({version})")
    except Exception as exc:
        preflight_passed = False
        preflight_details.append(f"Health: FAIL ({exc})")

    # Check for broken modules
    try:
        broken = c.search_read(
            "ir.module.module",
            domain=[("state", "in", ["to upgrade", "to install", "to remove"])],
            fields=["name", "state"],
            limit=20,
        )
        if broken:
            preflight_passed = False
            names = ", ".join(f"{m['name']}({m['state']})" for m in broken)
            preflight_details.append(f"Broken modules: {names}")
        else:
            preflight_details.append("Module states: clean")
    except RPCError as exc:
        preflight_passed = False
        preflight_details.append(f"Module check failed: {exc}")

    preflight_elapsed = round(time.monotonic() - preflight_start, 2)
    steps.append(
        {
            "name": "preflight",
            "passed": preflight_passed,
            "exit_code": 0 if preflight_passed else 1,
            "duration_s": preflight_elapsed,
            "stdout": "\n".join(preflight_details),
            "stderr": "",
        }
    )

    # Step 4: Smoke test — verify critical endpoints/models are accessible
    out.info("Running smoke test...")
    smoke_start = time.monotonic()
    smoke_passed = True
    smoke_details: list[str] = []

    critical_models = ["res.users", "res.partner", "ir.module.module", "ir.cron"]
    for model in critical_models:
        try:
            count = c.search_count(model, [])
            smoke_details.append(f"{model}: {count} records")
        except RPCError:
            smoke_passed = False
            smoke_details.append(f"{model}: INACCESSIBLE")

    smoke_elapsed = round(time.monotonic() - smoke_start, 2)
    steps.append(
        {
            "name": "smoke_test",
            "passed": smoke_passed,
            "exit_code": 0 if smoke_passed else 1,
            "duration_s": smoke_elapsed,
            "stdout": "\n".join(smoke_details),
            "stderr": "",
        }
    )

    # Results
    all_passed = all(s["passed"] for s in steps)
    total_time = sum(s["duration_s"] for s in steps)

    if actx.json_mode:
        out.raw_json(
            {
                "passed": all_passed,
                "total_duration_s": total_time,
                "steps": steps,
            }
        )
    else:
        rows = []
        for s in steps:
            status = "[green]PASS[/green]" if s["passed"] else "[red]FAIL[/red]"
            rows.append([s["name"], status, f"{s['duration_s']}s"])
        out.table(
            f"Pipeline Validation ({'[green]PASSED[/green]' if all_passed else '[red]FAILED[/red]'})",
            [("Step", ""), ("Status", ""), ("Duration", "dim")],
            rows,
        )

        # Show failure details
        for s in steps:
            if not s["passed"]:
                stderr = s.get("stderr", "").strip()
                stdout = s.get("stdout", "").strip()
                detail = stderr or stdout
                if detail:
                    out.error(f"{s['name']}: {_truncate(detail, 200)}")

    if not all_passed:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# 2. pipeline promote
# ---------------------------------------------------------------------------


@app.command()
def promote(
    ctx: typer.Context,
    source: Annotated[str, typer.Argument(help="Source profile name (e.g., staging)")],
    target: Annotated[str, typer.Argument(help="Target profile name (e.g., production)")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show diff only, do not sync anything")] = False,
    sync_modules: Annotated[bool, typer.Option("--sync-modules", help="Install missing modules on target")] = False,
    sync_params: Annotated[bool, typer.Option("--sync-params", help="Sync config params to target")] = False,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Compare and promote modules/config from source to target instance.

    Generates a diff report showing modules and config parameter differences.
    With --dry-run (default behavior without --sync-* flags), only the diff is
    shown. Use --sync-modules and/or --sync-params to apply changes.

    Examples:
        kctl-odoo pipeline promote staging production
        kctl-odoo pipeline promote staging production --dry-run
        kctl-odoo pipeline promote staging production --sync-modules --sync-params -y
        kctl-odoo pipeline promote staging production --json
    """
    actx: AppContext = ctx.obj
    out = actx.output

    # Connect to both instances
    out.info(f"Connecting to source '{source}'...")
    client_src = _get_client_for_profile(source)
    try:
        out.info(f"Connecting to target '{target}'...")
        client_tgt = _get_client_for_profile(target)
    except Exception:
        client_src.close()
        raise

    try:
        # Fetch modules
        mods_src = _fetch_installed_modules(client_src)
        mods_tgt = _fetch_installed_modules(client_tgt)

        keys_src = set(mods_src.keys())
        keys_tgt = set(mods_tgt.keys())

        only_src = sorted(keys_src - keys_tgt)
        only_tgt = sorted(keys_tgt - keys_src)

        version_diff: list[tuple[str, str, str]] = []
        for name in sorted(keys_src & keys_tgt):
            src_ver = mods_src[name]["version"]
            tgt_ver = mods_tgt[name]["version"]
            if src_ver != tgt_ver:
                version_diff.append((name, src_ver, tgt_ver))

        # Fetch config params
        params_src = _fetch_config_params(client_src)
        params_tgt = _fetch_config_params(client_tgt)

        pkeys_src = set(params_src.keys())
        pkeys_tgt = set(params_tgt.keys())

        params_only_src = sorted(pkeys_src - pkeys_tgt)
        param_diff: list[tuple[str, str, str]] = []
        for k in sorted(pkeys_src & pkeys_tgt):
            if params_src[k] != params_tgt[k]:
                param_diff.append((k, params_src[k], params_tgt[k]))

        # Output diff report
        if actx.json_mode:
            out.raw_json(
                {
                    "source": source,
                    "target": target,
                    "modules": {
                        "source_total": len(mods_src),
                        "target_total": len(mods_tgt),
                        "only_in_source": only_src,
                        "only_in_target": only_tgt,
                        "version_diff": [{"name": n, "source": sv, "target": tv} for n, sv, tv in version_diff],
                    },
                    "config_params": {
                        "only_in_source": params_only_src,
                        "value_diff": [{"key": k, "source": sv, "target": tv} for k, sv, tv in param_diff],
                    },
                }
            )
        else:
            out.detail(
                f"Promotion: {source} -> {target}",
                [
                    (
                        "Module Summary",
                        [
                            (f"{source} modules", str(len(mods_src))),
                            (f"{target} modules", str(len(mods_tgt))),
                            ("Missing on target", str(len(only_src))),
                            ("Extra on target", str(len(only_tgt))),
                            ("Version differs", str(len(version_diff))),
                        ],
                    ),
                    (
                        "Config Summary",
                        [
                            ("Missing params on target", str(len(params_only_src))),
                            ("Value differs", str(len(param_diff))),
                        ],
                    ),
                ],
            )

            if only_src:
                rows = [[name, mods_src[name]["version"]] for name in only_src]
                out.table(
                    f"Modules to Install on {target} ({len(only_src)})",
                    [("Module", ""), ("Version", "dim")],
                    rows,
                )

            if version_diff:
                rows = [[n, sv, tv] for n, sv, tv in version_diff]
                out.table(
                    f"Version Differences ({len(version_diff)})",
                    [("Module", ""), (f"{source}", "cyan"), (f"{target}", "yellow")],
                    rows,
                )

            if param_diff:
                rows = [[k, _truncate(sv), _truncate(tv)] for k, sv, tv in param_diff]
                out.table(
                    f"Config Param Differences ({len(param_diff)})",
                    [("Key", ""), (f"{source}", "cyan"), (f"{target}", "yellow")],
                    rows,
                )

        # Sync if requested (each sync is independent — declining one does not skip the other)
        if dry_run:
            if sync_modules or sync_params:
                out.warn("--dry-run is set, ignoring --sync-modules/--sync-params.")
            out.info("Dry run complete. No changes applied.")
            return

        if sync_modules and only_src:
            if force or typer.confirm(f"Install {len(only_src)} missing module(s) on {target}?"):
                ids = client_tgt.search("ir.module.module", [("name", "in", only_src)])
                if ids:
                    try:
                        client_tgt.execute_kw(
                            "ir.module.module",
                            "button_immediate_install",
                            [ids],
                        )
                        out.success(f"Installed {len(only_src)} module(s) on {target}")
                    except RPCError as exc:
                        out.error(f"Module install failed: {exc}")
                else:
                    out.warn(f"No matching module records found on {target} for: {', '.join(only_src)}")
        elif sync_modules:
            out.info("No missing modules to install on target.")

        if sync_params and params_only_src:
            if force or typer.confirm(f"Copy {len(params_only_src)} missing config param(s) to {target}?"):
                for key in params_only_src:
                    try:
                        client_tgt.execute_kw(
                            "ir.config_parameter",
                            "set_param",
                            [key, params_src[key]],
                        )
                    except RPCError as exc:
                        out.error(f"Failed to set param '{key}': {exc}")
                        continue
                out.success(f"Synced {len(params_only_src)} config param(s) to {target}")
        elif sync_params:
            out.info("No missing config params to sync to target.")

        if not sync_modules and not sync_params and only_src:
            out.info("Use --sync-modules and/or --sync-params to apply changes.")

    finally:
        client_src.close()
        client_tgt.close()


# ---------------------------------------------------------------------------
# 3. pipeline rollback
# ---------------------------------------------------------------------------


@app.command()
def rollback(
    ctx: typer.Context,
    profile: Annotated[str, typer.Argument(help="Target profile (e.g., production)")],
    backup_file: Annotated[str, typer.Option("--to", help="Backup file path to restore from")],
    database: Annotated[str | None, typer.Option("--database", "-d", help="Target database name override")] = None,
    copy: Annotated[bool, typer.Option("--copy/--move", help="Neutralize restored database (copy mode)")] = True,
    skip_pre_backup: Annotated[
        bool, typer.Option("--skip-pre-backup", help="Skip safety backup before restore")
    ] = False,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Restore from backup with pre/post verification.

    Creates a safety backup of the current database before restoring, then
    performs health checks before and after restore to verify success.
    Use --skip-pre-backup to skip the safety backup.

    Examples:
        kctl-odoo pipeline rollback production --to /backups/prod_2026-03-27.zip
        kctl-odoo pipeline rollback production --to backup.zip --database odoo_prod -y
        kctl-odoo pipeline rollback production --to backup.zip --skip-pre-backup
    """
    actx: AppContext = ctx.obj
    out = actx.output

    path = Path(backup_file).resolve()
    if not path.exists():
        out.error(f"Backup file not found: {backup_file}")
        raise typer.Exit(1)

    client = _get_client_for_profile(profile)
    try:
        db_name = database or client.database
        if not db_name:
            out.error("No database specified and no default configured.")
            raise typer.Exit(1)

        size_mb = path.stat().st_size / (1024 * 1024)
        mode = "copy" if copy else "move"

        if size_mb > 500:
            out.warn(f"Backup file is large ({size_mb:.0f} MB). This may consume significant memory during restore.")

        # Pre-restore verification
        out.info("Pre-restore verification...")
        pre_health: dict = {}
        try:
            ok, version = client.check_health()
            pre_health = {"healthy": ok, "version": version}
            if ok:
                pre_health["module_count"] = client.search_count("ir.module.module", [("state", "=", "installed")])
                pre_health["user_count"] = client.search_count("res.users", [("active", "=", True)])
        except Exception as exc:
            pre_health = {"healthy": False, "error": str(exc)}

        out.info(f"Pre-restore: {'healthy' if pre_health.get('healthy') else 'unhealthy'}")

        if not force and not typer.confirm(
            f"Restore '{path.name}' ({size_mb:.1f} MB) as '{db_name}' on {profile} ({mode} mode)?\n"
            f"This will OVERWRITE the current database."
        ):
            raise typer.Exit(0)

        # Safety backup before restore
        pre_backup_file: str | None = None
        if not skip_pre_backup and pre_health.get("healthy"):
            out.info(f"Creating safety backup of '{db_name}' before restore...")
            try:
                backup_data = client.db_backup(db_name, backup_format="zip")
                ts = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
                pre_backup_path = path.parent / f"{db_name}_pre_rollback_{ts}.zip"
                pre_backup_path.write_bytes(backup_data)
                pre_backup_file = str(pre_backup_path)
                pre_backup_mb = len(backup_data) / (1024 * 1024)
                out.success(f"Safety backup saved: {pre_backup_path.name} ({pre_backup_mb:.1f} MB)")
            except Exception as exc:
                out.warn(f"Safety backup failed: {exc}. Proceeding with restore anyway.")
        elif skip_pre_backup:
            out.info("Skipping safety backup (--skip-pre-backup)")

        # Perform restore
        out.info(f"Restoring '{path.name}' -> '{db_name}' ({mode} mode)...")
        try:
            data = path.read_bytes()
            client.db_restore(db_name, data, copy=copy)
        except Exception as exc:
            out.error(f"Restore failed: {exc}")
            if actx.json_mode:
                out.raw_json(
                    {
                        "success": False,
                        "error": str(exc),
                        "pre_backup": pre_backup_file,
                        "pre_health": pre_health,
                    }
                )
            raise typer.Exit(1) from exc

        # Post-restore verification
        out.info("Post-restore verification...")
        post_health: dict = {}
        try:
            ok, version = client.check_health()
            post_health = {"healthy": ok, "version": version}
            if ok:
                post_health["module_count"] = client.search_count("ir.module.module", [("state", "=", "installed")])
                post_health["user_count"] = client.search_count("res.users", [("active", "=", True)])
        except Exception as exc:
            post_health = {"healthy": False, "error": str(exc)}

        if actx.json_mode:
            out.raw_json(
                {
                    "success": True,
                    "database": db_name,
                    "profile": profile,
                    "backup": str(path),
                    "size_mb": round(size_mb, 2),
                    "copy_mode": copy,
                    "pre_backup": pre_backup_file,
                    "pre_restore": pre_health,
                    "post_restore": post_health,
                }
            )
        else:
            sections = [
                (
                    "Restore Result",
                    [
                        (
                            "Status",
                            "[green]SUCCESS[/green]"
                            if post_health.get("healthy")
                            else "[yellow]RESTORED (verify manually)[/yellow]",
                        ),
                        ("Database", db_name),
                        ("Profile", profile),
                        ("Backup", path.name),
                        ("Size", f"{size_mb:.1f} MB"),
                        ("Mode", mode),
                        ("Safety Backup", pre_backup_file or "skipped"),
                    ],
                ),
                (
                    "Pre-Restore",
                    [
                        ("Healthy", str(pre_health.get("healthy", "?"))),
                        ("Modules", str(pre_health.get("module_count", "?"))),
                        ("Users", str(pre_health.get("user_count", "?"))),
                    ],
                ),
                (
                    "Post-Restore",
                    [
                        ("Healthy", str(post_health.get("healthy", "?"))),
                        ("Modules", str(post_health.get("module_count", "?"))),
                        ("Users", str(post_health.get("user_count", "?"))),
                    ],
                ),
            ]
            out.detail(f"Rollback Complete — {db_name}", sections)

    finally:
        client.close()


# ---------------------------------------------------------------------------
# 4. pipeline changelog
# ---------------------------------------------------------------------------


@app.command()
def changelog(
    ctx: typer.Context,
    from_ref: Annotated[str, typer.Option("--from", help="Start git ref (tag, commit, branch)")],
    to_ref: Annotated[str, typer.Option("--to", help="End git ref (tag, commit, branch)")] = "HEAD",
    path_filter: Annotated[
        str | None, typer.Option("--path", help="Filter commits by path (e.g., src/private/)")
    ] = None,
) -> None:
    """Generate release notes from git commits and module changes.

    Parses Conventional Commits between two refs to produce categorized
    release notes.

    Examples:
        kctl-odoo pipeline changelog --from v1.0.0 --to v1.1.0
        kctl-odoo pipeline changelog --from v1.0.0 --path src/private/
        kctl-odoo pipeline changelog --from HEAD~20 --json
    """
    actx: AppContext = ctx.obj
    out = actx.output

    # Validate refs to prevent argument injection
    _validate_git_ref(from_ref, "--from")
    _validate_git_ref(to_ref, "--to")

    # Get git log between refs
    git_cmd = ["git", "log", f"{from_ref}..{to_ref}", "--pretty=format:%H|%s|%an|%ai", "--no-merges"]
    if path_filter:
        git_cmd.extend(["--", path_filter])

    try:
        result = subprocess.run(git_cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            out.error(f"Git log failed: {result.stderr.strip()}")
            raise typer.Exit(1)
    except FileNotFoundError:
        out.error("git command not found")
        raise typer.Exit(1) from None

    commits_raw = result.stdout.strip()
    if not commits_raw:
        out.info(f"No commits found between {from_ref} and {to_ref}")
        if actx.json_mode:
            out.raw_json({"from": from_ref, "to": to_ref, "commits": [], "categories": {}})
        return

    # Parse commits
    categories: dict[str, list[dict]] = {
        "feat": [],
        "fix": [],
        "refactor": [],
        "docs": [],
        "test": [],
        "chore": [],
        "ci": [],
        "other": [],
    }

    all_commits: list[dict] = []
    for line in commits_raw.splitlines():
        parts = line.split("|", 3)
        if len(parts) < 4:
            continue
        sha, subject, author, date = parts
        commit: dict = {"sha": sha[:8], "subject": subject, "author": author, "date": date.strip()}

        # Parse Conventional Commit type and scope
        cc_match = _CC_RE.match(subject)
        if cc_match:
            cc_type = cc_match.group(1).lower()
            cc_scope = cc_match.group(2) or ""
            cc_desc = cc_match.group(3)
            commit["type"] = cc_type
            commit["scope"] = cc_scope
            commit["description"] = cc_desc
        else:
            commit["type"] = "other"
            commit["scope"] = ""
            commit["description"] = subject

        all_commits.append(commit)

        # Categorize
        if commit["type"] in categories:
            categories[commit["type"]].append(commit)
        else:
            categories["other"].append(commit)

    # Detect changed modules from file paths
    diff_cmd = ["git", "diff", "--name-only", f"{from_ref}..{to_ref}"]
    if path_filter:
        diff_cmd.extend(["--", path_filter])

    changed_modules: set[str] = set()
    try:
        diff_result = subprocess.run(diff_cmd, capture_output=True, text=True, timeout=30)
        if diff_result.returncode == 0:
            for fpath in diff_result.stdout.strip().splitlines():
                # Extract module name from src/private/<module>/... or src/external/<module>/...
                parts_path = fpath.split("/")
                if len(parts_path) >= 3 and parts_path[0] == "src" and parts_path[1] in ("private", "external"):
                    changed_modules.add(parts_path[2])
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # JSON output
    if actx.json_mode:
        json_categories = {k: v for k, v in categories.items() if v}
        out.raw_json(
            {
                "from": from_ref,
                "to": to_ref,
                "total_commits": len(all_commits),
                "categories": json_categories,
                "changed_modules": sorted(changed_modules),
            }
        )
        return

    # Pretty output
    out.header(f"Release Notes: {from_ref} -> {to_ref}")
    out.info(f"Total commits: {len(all_commits)}")

    if changed_modules:
        out.info(f"Changed modules: {', '.join(sorted(changed_modules))}")

    category_labels = {
        "feat": "Features",
        "fix": "Bug Fixes",
        "refactor": "Refactoring",
        "docs": "Documentation",
        "test": "Tests",
        "chore": "Chores",
        "ci": "CI/CD",
        "other": "Other",
    }

    for cat_key, label in category_labels.items():
        commits = categories[cat_key]
        if not commits:
            continue
        rows = [
            [c["sha"], c.get("scope", ""), c.get("description", c["subject"]), c["author"], c["date"][:10]]
            for c in commits
        ]
        out.table(
            f"{label} ({len(commits)})",
            [("SHA", "cyan"), ("Scope", "yellow"), ("Description", ""), ("Author", "dim"), ("Date", "dim")],
            rows,
        )


# ---------------------------------------------------------------------------
# 5. pipeline metrics
# ---------------------------------------------------------------------------


@app.command()
def metrics(
    ctx: typer.Context,
    prefix: Annotated[str, typer.Option("--prefix", help="Prometheus metric prefix")] = "odoo",
    warn: Annotated[bool, typer.Option("--warn", help="Show threshold alerts for unhealthy metrics")] = False,
) -> None:
    """Export Prometheus-format metrics for Grafana dashboards.

    Collects key operational metrics: module count, cron health, mail queue,
    queue job stats, and response time. Use --warn to highlight metrics that
    exceed healthy thresholds.

    Examples:
        kctl-odoo pipeline metrics
        kctl-odoo pipeline metrics --warn
        kctl-odoo pipeline metrics --prefix kodemeio_odoo
        kctl-odoo pipeline metrics --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    collected: dict[str, float | int] = {}

    # Response time (measure RPC round-trip)
    start = time.monotonic()
    try:
        c.version_info()
        rpc_time = round(time.monotonic() - start, 4)
        collected[f"{prefix}_rpc_response_seconds"] = rpc_time
    except Exception:
        collected[f"{prefix}_rpc_response_seconds"] = -1

    # Module counts
    try:
        collected[f"{prefix}_modules_installed"] = c.search_count("ir.module.module", [("state", "=", "installed")])
        collected[f"{prefix}_modules_to_upgrade"] = c.search_count("ir.module.module", [("state", "=", "to upgrade")])
        collected[f"{prefix}_modules_to_install"] = c.search_count("ir.module.module", [("state", "=", "to install")])
    except RPCError:
        pass

    # Cron health
    try:
        collected[f"{prefix}_cron_total"] = c.search_count("ir.cron", [])
        collected[f"{prefix}_cron_active"] = c.search_count("ir.cron", [("active", "=", True)])
        cutoff = (datetime.now(tz=UTC) - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
        collected[f"{prefix}_cron_stale"] = c.search_count(
            "ir.cron",
            [("active", "=", True), ("lastcall", "<", cutoff)],
        )
    except RPCError:
        pass

    # Mail queue
    try:
        collected[f"{prefix}_mail_outgoing"] = c.search_count("mail.mail", [("state", "=", "outgoing")])
        collected[f"{prefix}_mail_exception"] = c.search_count("mail.mail", [("state", "=", "exception")])
    except RPCError:
        pass

    # Queue jobs (OCA queue_job module)
    try:
        for state in ["pending", "enqueued", "started", "failed", "done"]:
            collected[f"{prefix}_queue_jobs_{state}"] = c.search_count("queue.job", [("state", "=", state)])
    except RPCError:
        # queue_job module not installed — skip silently
        pass

    # Active users
    with contextlib.suppress(RPCError):
        collected[f"{prefix}_users_active"] = c.search_count(
            "res.users", [("active", "=", True), ("share", "=", False)]
        )

    # Threshold alerts
    alerts: list[dict] = []
    thresholds = {
        f"{prefix}_modules_to_upgrade": ("modules pending upgrade", 0),
        f"{prefix}_modules_to_install": ("modules pending install", 0),
        f"{prefix}_cron_stale": ("stale crons (>48h since last run)", 0),
        f"{prefix}_mail_exception": ("failed emails in queue", 0),
        f"{prefix}_mail_outgoing": ("emails stuck in outgoing queue", 100),
        f"{prefix}_queue_jobs_failed": ("failed queue jobs", 0),
        f"{prefix}_rpc_response_seconds": ("RPC response time (seconds)", 2.0),
    }
    for metric_key, (label, threshold) in thresholds.items():
        value = collected.get(metric_key)
        if value is not None and value > threshold:
            alerts.append({"metric": metric_key, "label": label, "value": value, "threshold": threshold})

    # JSON output
    if actx.json_mode:
        result: dict = {"metrics": collected}
        if warn:
            result["alerts"] = alerts
        out.raw_json(result)
        return

    # Table output for human readability
    rows = []
    json_data = []
    for key, value in sorted(collected.items()):
        short_key = key.replace(f"{prefix}_", "")
        rows.append([short_key, str(value)])
        json_data.append({"metric": key, "value": value})
    out.table(
        f"Odoo Metrics ({len(collected)})",
        [("Metric", ""), ("Value", "cyan")],
        rows,
        data_for_json=json_data,
    )

    # Show alerts
    if warn and alerts:
        alert_rows = []
        for a in alerts:
            alert_rows.append([a["label"], str(a["value"]), f"> {a['threshold']}"])
        out.table(
            f"[yellow]Alerts ({len(alerts)})[/yellow]",
            [("Issue", ""), ("Value", "red"), ("Threshold", "dim")],
            alert_rows,
        )
    elif warn:
        out.success("All metrics within healthy thresholds.")
