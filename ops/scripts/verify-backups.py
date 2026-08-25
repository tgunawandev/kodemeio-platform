#!/usr/bin/env python3
"""Verify backup freshness for all deployed Kodemeio instances.

Scans deploy manifests in deploys/instances/ to find backup configurations,
then checks backup recency via kctl-dokploy CLI. Flags STALE or MISSING backups.

Usage:
    uv run python ops/scripts/verify-backups.py --profile <profile>
    uv run python ops/scripts/verify-backups.py --profile <profile> --json
    uv run python ops/scripts/verify-backups.py --profile <profile> --dry-run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
INSTANCES_DIR = ROOT / "deploys" / "instances"
BASES_DIR = ROOT / "deploys" / "bases"

# Staleness threshold: backup older than 2x expected interval
STALENESS_MULTIPLIER = 2


@dataclass
class BackupConfig:
    """Parsed backup configuration for a single instance."""

    instance_name: str
    manifest_path: Path
    schedule: str
    prefix: str
    keep_latest: int
    destination: str
    backup_type: str
    base_type: str


@dataclass
class BackupStatus:
    """Result of checking a single instance's backup."""

    config: BackupConfig
    last_backup: datetime | None = None
    age: timedelta | None = None
    status: str = "UNKNOWN"  # OK, STALE, MISSING, ERROR
    error: str | None = None


def parse_cron_interval_hours(cron_expr: str) -> float:
    """Estimate the interval in hours from a cron expression.

    Attempts to use croniter if available; falls back to heuristic parsing.
    """
    try:
        from croniter import croniter

        now = datetime.now(UTC)
        cron = croniter(cron_expr, now)
        t1 = cron.get_next(datetime)
        t2 = cron.get_next(datetime)
        return (t2 - t1).total_seconds() / 3600
    except ImportError:
        pass

    # Heuristic fallback: parse standard cron fields
    parts = cron_expr.strip().split()
    if len(parts) < 5:
        return 24.0

    minute, hour, dom, month, dow = parts[:5]

    # Every N minutes: */5 * * * *
    if minute.startswith("*/") and hour == "*" and dom == "*":
        try:
            return int(minute[2:]) / 60
        except ValueError:
            return 24.0

    # Every N hours: 0 */N * * *
    if hour.startswith("*/") and dom == "*":
        try:
            return int(hour[2:])
        except ValueError:
            return 24.0

    # Daily: specific hour, * day of month
    if dom == "*" and month == "*" and dow == "*":
        return 24.0

    # Weekly: specific day of week
    if dom == "*" and month == "*" and dow != "*":
        return 168.0  # 7 days

    # Monthly: specific day of month
    if dom != "*" and month == "*":
        return 720.0  # ~30 days

    return 24.0


def load_base(extends_path: str, manifest_dir: Path) -> dict:
    """Load a base manifest YAML file."""
    base_path = (manifest_dir / extends_path).resolve()
    if not base_path.exists():
        return {}
    with open(base_path) as f:
        return yaml.safe_load(f) or {}


def discover_instances() -> list[BackupConfig]:
    """Scan all instance manifests and return those with backup configs."""
    results: list[BackupConfig] = []

    for manifest_path in sorted(INSTANCES_DIR.glob("*.yaml")):
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f) or {}

        if manifest.get("kind") != "instance":
            continue

        # Load base to get inherited backup config
        extends = manifest.get("extends", "")
        base = load_base(extends, manifest_path.parent) if extends else {}
        base_type = base.get("type", "unknown")

        # Merge backup config: instance overrides base
        backup = {**base.get("backup", {}), **manifest.get("backup", {})}
        if not backup:
            continue

        instance = manifest.get("instance", {})
        instance_name = instance.get("name", manifest_path.stem)

        # Resolve template variables in prefix
        prefix_template = backup.get("prefix_template", instance_name)
        prefix = prefix_template.replace("{instance_name}", instance_name)

        results.append(
            BackupConfig(
                instance_name=instance_name,
                manifest_path=manifest_path,
                schedule=backup.get("schedule", "0 2 * * *"),
                prefix=prefix,
                keep_latest=backup.get("keep_latest", 14),
                destination=backup.get("destination", "kodemeio-s3-backups"),
                backup_type=backup.get("type", "postgres"),
                base_type=base_type,
            )
        )

    return results


def check_backup(config: BackupConfig, profile: str) -> BackupStatus:
    """Check the most recent backup for a given instance via kctl-dokploy."""
    status = BackupStatus(config=config)

    try:
        result = subprocess.run(
            [
                "kctl-dokploy",
                "-p",
                profile,
                "--json",
                "backups",
                "list-files",
                "--destination",
                config.destination,
                "--prefix",
                config.prefix,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "not found" in stderr.lower() or "no backups" in stderr.lower():
                status.status = "MISSING"
                return status
            status.status = "ERROR"
            status.error = stderr[:200] if stderr else f"exit code {result.returncode}"
            return status

        output = result.stdout.strip()
        if not output:
            status.status = "MISSING"
            return status

        backups = json.loads(output)
        if not backups:
            status.status = "MISSING"
            return status

        # Find the most recent backup by timestamp
        latest = None
        for backup in backups:
            ts_str = backup.get("created_at") or backup.get("timestamp") or backup.get("date")
            if not ts_str:
                continue
            # Try common ISO formats
            for fmt in (
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S",
            ):
                try:
                    ts = datetime.strptime(ts_str, fmt)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=UTC)
                    if latest is None or ts > latest:
                        latest = ts
                    break
                except ValueError:
                    continue

        if latest is None:
            status.status = "MISSING"
            return status

        now = datetime.now(UTC)
        status.last_backup = latest
        status.age = now - latest

        # Check staleness
        expected_hours = parse_cron_interval_hours(config.schedule)
        max_age = timedelta(hours=expected_hours * STALENESS_MULTIPLIER)

        if status.age > max_age:
            status.status = "STALE"
        else:
            status.status = "OK"

    except subprocess.TimeoutExpired:
        status.status = "ERROR"
        status.error = "kctl-dokploy timed out after 30s"
    except json.JSONDecodeError as exc:
        status.status = "ERROR"
        status.error = f"Invalid JSON from kctl-dokploy: {exc}"
    except FileNotFoundError:
        status.status = "ERROR"
        status.error = "kctl-dokploy not found in PATH"
    except Exception as exc:
        status.status = "ERROR"
        status.error = str(exc)[:200]

    return status


def format_age(td: timedelta | None) -> str:
    """Format a timedelta as a human-readable string."""
    if td is None:
        return "\u2014"
    total_seconds = int(td.total_seconds())
    if total_seconds < 0:
        return "future?"

    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60

    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def format_last_backup(dt: datetime | None) -> str:
    """Format a datetime for display."""
    if dt is None:
        return "\u2014"
    return dt.strftime("%Y-%m-%d %H:%M")


def print_table(statuses: list[BackupStatus]) -> None:
    """Print a plain-text summary table."""
    # Column widths
    name_w = max(len("Instance"), max(len(s.config.instance_name) for s in statuses))
    sched_w = max(len("Schedule"), max(len(s.config.schedule) for s in statuses))
    last_w = max(len("Last Backup"), 16)
    age_w = max(len("Age"), 8)
    status_w = max(len("Status"), 7)

    header = (
        f"{'Instance':<{name_w}}  "
        f"{'Schedule':<{sched_w}}  "
        f"{'Last Backup':<{last_w}}  "
        f"{'Age':>{age_w}}  "
        f"{'Status':<{status_w}}"
    )
    separator = "-" * len(header)

    print()
    print(header)
    print(separator)

    for s in statuses:
        status_display = s.status
        if s.error:
            status_display = f"ERROR: {s.error[:40]}"

        line = (
            f"{s.config.instance_name:<{name_w}}  "
            f"{s.config.schedule:<{sched_w}}  "
            f"{format_last_backup(s.last_backup):<{last_w}}  "
            f"{format_age(s.age):>{age_w}}  "
            f"{status_display}"
        )
        print(line)

    print()

    # Summary
    ok = sum(1 for s in statuses if s.status == "OK")
    stale = sum(1 for s in statuses if s.status == "STALE")
    missing = sum(1 for s in statuses if s.status == "MISSING")
    errors = sum(1 for s in statuses if s.status == "ERROR")

    print(f"Total: {len(statuses)} instances with backup configs")
    print(f"  OK: {ok}  |  STALE: {stale}  |  MISSING: {missing}  |  ERROR: {errors}")
    print()


def to_json(statuses: list[BackupStatus]) -> str:
    """Serialize results to JSON."""
    records = []
    for s in statuses:
        records.append(
            {
                "instance_name": s.config.instance_name,
                "base_type": s.config.base_type,
                "schedule": s.config.schedule,
                "prefix": s.config.prefix,
                "destination": s.config.destination,
                "keep_latest": s.config.keep_latest,
                "last_backup": format_last_backup(s.last_backup),
                "age_seconds": int(s.age.total_seconds()) if s.age else None,
                "age_human": format_age(s.age),
                "status": s.status,
                "error": s.error,
            }
        )

    summary = {
        "total": len(records),
        "ok": sum(1 for r in records if r["status"] == "OK"),
        "stale": sum(1 for r in records if r["status"] == "STALE"),
        "missing": sum(1 for r in records if r["status"] == "MISSING"),
        "errors": sum(1 for r in records if r["status"] == "ERROR"),
        "checked_at": datetime.now(UTC).isoformat(),
    }

    return json.dumps({"summary": summary, "instances": records}, indent=2)


def print_dry_run(configs: list[BackupConfig], profile: str) -> None:
    """Print what would be checked without running kctl commands."""
    print()
    print(f"DRY RUN: Found {len(configs)} instances with backup configurations")
    print()

    name_w = max(len("Instance"), max(len(c.instance_name) for c in configs))
    type_w = max(len("Type"), max(len(c.base_type) for c in configs))
    sched_w = max(len("Schedule"), max(len(c.schedule) for c in configs))

    header = f"{'Instance':<{name_w}}  {'Type':<{type_w}}  {'Schedule':<{sched_w}}  {'Interval':>10}  {'Prefix'}"
    print(header)
    print("-" * len(header))

    for c in configs:
        interval_h = parse_cron_interval_hours(c.schedule)
        interval_str = f"{interval_h:.0f}h" if interval_h >= 1 else f"{interval_h * 60:.0f}m"
        stale_h = interval_h * STALENESS_MULTIPLIER
        stale_str = f"{stale_h:.0f}h" if stale_h >= 1 else f"{stale_h * 60:.0f}m"

        line = (
            f"{c.instance_name:<{name_w}}  "
            f"{c.base_type:<{type_w}}  "
            f"{c.schedule:<{sched_w}}  "
            f"{interval_str + ' (>' + stale_str + ')':>10}  "
            f"{c.prefix}"
        )
        print(line)

    print()
    print("Commands that would run:")
    for c in configs:
        print(
            f"  kctl-dokploy -p {profile} --json backups list-files --destination {c.destination} --prefix {c.prefix}"
        )
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify backup freshness for all deployed Kodemeio instances.",
    )
    parser.add_argument(
        "--profile",
        "-p",
        required=True,
        help="Explicit kctl-dokploy profile",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List instances and commands without running kctl checks",
    )
    args = parser.parse_args()

    if not INSTANCES_DIR.exists():
        print(f"ERROR: Instances directory not found: {INSTANCES_DIR}", file=sys.stderr)
        return 1

    configs = discover_instances()

    if not configs:
        print("No instances with backup configurations found.", file=sys.stderr)
        return 0

    if args.dry_run:
        if args.json_output:
            records = [
                {
                    "instance_name": c.instance_name,
                    "base_type": c.base_type,
                    "schedule": c.schedule,
                    "interval_hours": parse_cron_interval_hours(c.schedule),
                    "stale_after_hours": parse_cron_interval_hours(c.schedule) * STALENESS_MULTIPLIER,
                    "prefix": c.prefix,
                    "destination": c.destination,
                    "keep_latest": c.keep_latest,
                }
                for c in configs
            ]
            print(json.dumps({"dry_run": True, "instances": records}, indent=2))
        else:
            print_dry_run(configs, args.profile)
        return 0

    # Check each instance
    statuses: list[BackupStatus] = []
    for config in configs:
        if not args.json_output:
            print(f"  Checking {config.instance_name}...", end=" ", flush=True)
        status = check_backup(config, args.profile)
        if not args.json_output:
            print(status.status)
        statuses.append(status)

    # Output
    if args.json_output:
        print(to_json(statuses))
    else:
        print_table(statuses)

    # Exit code
    has_issues = any(s.status in ("STALE", "MISSING") for s in statuses)
    return 1 if has_issues else 0


if __name__ == "__main__":
    sys.exit(main())
