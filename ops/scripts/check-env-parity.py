#!/usr/bin/env python3
"""Check environment variable parity across deploy instances of the same type.

Scans deploys/env/<environment>/.env.* files, groups them by base type (odoo, react-pwa,
nextjs, fastapi, infra) using the corresponding instance manifest's `extends`
field, and reports drift (missing vars, differing values) within each group.

Usage:
    uv run python ops/scripts/check-env-parity.py
    uv run python ops/scripts/check-env-parity.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
INSTANCES_DIR = ROOT / "deploys" / "instances"
ENV_DIR = ROOT / "deploys" / "env"

# Patterns for values that should be masked in output
SECRET_PATTERNS = re.compile(
    r"(key|token|secret|password|passwd|credential|dsn|jwt)",
    re.IGNORECASE,
)


def mask_value(key: str, value: str) -> str:
    """Mask secret values, showing first 4 and last 4 chars."""
    if SECRET_PATTERNS.search(key):
        if len(value) <= 8:
            return "****"
        return f"{value[:4]}****{value[-4:]}"
    return value


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file into a dict, ignoring comments and blank lines."""
    env: dict[str, str] = {}
    if not path.exists():
        return env

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Handle KEY=VALUE (value may contain = signs)
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        # Strip surrounding quotes from value
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        env[key] = value

    return env


def resolve_base_type(manifest_path: Path) -> str | None:
    """Read an instance manifest and resolve its base type."""
    if not manifest_path.exists():
        return None

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f) or {}

    extends = manifest.get("extends", "")
    if not extends:
        return None

    base_path = (manifest_path.parent / extends).resolve()
    if not base_path.exists():
        return None

    with open(base_path) as f:
        base = yaml.safe_load(f) or {}

    return base.get("type")


def discover_env_groups() -> dict[str, list[tuple[str, Path]]]:
    """Group env files by base type.

    Returns: {base_type: [(instance_name, env_path), ...]}
    """
    groups: dict[str, list[tuple[str, Path]]] = defaultdict(list)

    env_paths = (path for path in ENV_DIR.rglob(".env.*") if path.is_file() and not path.name.endswith(".example"))
    for env_path in sorted(env_paths):
        instance_name = env_path.name.removeprefix(".env.")
        environment = env_path.relative_to(ENV_DIR).parts[0]
        display_name = f"{environment}/{instance_name}"
        # Find matching instance manifest
        manifest_path = INSTANCES_DIR / environment / f"{instance_name}.yaml"
        base_type = resolve_base_type(manifest_path)

        if base_type is None:
            # Try to infer from filename patterns
            if "-odoo-" in instance_name:
                base_type = "odoo"
            elif "-react-" in instance_name:
                base_type = "react-pwa"
            elif "-nextjs-" in instance_name:
                base_type = "nextjs"
            elif "-fastapi-" in instance_name:
                base_type = "fastapi"
            elif "-infra-" in instance_name:
                base_type = "infrastructure"
            else:
                base_type = "unknown"

        groups[base_type].append((display_name, env_path))

    return dict(groups)


def analyze_group(
    instances: list[tuple[str, Path]],
) -> tuple[set[str], list[dict], list[dict]]:
    """Analyze a group of env files for parity.

    Returns:
        - shared_keys: keys present in ALL instances with identical values
        - drift: list of {key, values: {instance: value}} where values differ
        - missing: list of {key, present_in: [...], missing_from: [...]}
    """
    # Parse all env files
    envs: dict[str, dict[str, str]] = {}
    for name, path in instances:
        envs[name] = parse_env_file(path)

    if len(envs) < 2:
        all_keys = set()
        for e in envs.values():
            all_keys.update(e.keys())
        return all_keys, [], []

    # Collect all keys across instances
    all_keys: set[str] = set()
    for e in envs.values():
        all_keys.update(e.keys())

    instance_names = list(envs.keys())
    shared_keys: set[str] = set()
    drift: list[dict] = []
    missing: list[dict] = []

    for key in sorted(all_keys):
        present_in = [name for name in instance_names if key in envs[name]]
        missing_from = [name for name in instance_names if key not in envs[name]]

        if missing_from:
            missing.append(
                {
                    "key": key,
                    "present_in": present_in,
                    "missing_from": missing_from,
                }
            )
            continue

        # Key exists in all instances -- check values
        values = {name: envs[name][key] for name in instance_names}
        unique_values = set(values.values())

        if len(unique_values) == 1:
            shared_keys.add(key)
        else:
            drift.append(
                {
                    "key": key,
                    "values": values,
                }
            )

    return shared_keys, drift, missing


def print_text_report(
    groups: dict[str, list[tuple[str, Path]]],
) -> tuple[int, int]:
    """Print a human-readable drift report. Returns (drift_count, missing_count)."""
    total_drift = 0
    total_missing = 0

    for base_type in sorted(groups.keys()):
        instances = groups[base_type]
        print(f"\n{'=' * 60}")
        print(f"  {base_type} instances ({len(instances)})")
        print(f"{'=' * 60}")

        if len(instances) < 2:
            name, path = instances[0]
            env = parse_env_file(path)
            print(f"  Only one instance: {name} ({len(env)} vars)")
            print("  (no parity check possible)")
            continue

        shared, drift, missing = analyze_group(instances)

        # Shared keys
        if shared:
            shared_display = ", ".join(sorted(shared)[:10])
            extra = len(shared) - 10
            if extra > 0:
                shared_display += f", ... (+{extra} more)"
            print(f"\n  All share ({len(shared)} vars): {shared_display}")

        # Drift
        if drift:
            print(f"\n  DRIFT ({len(drift)} vars):")
            for d in drift:
                key = d["key"]
                values = d["values"]
                print(f"\n    {key}:")

                # Group instances by value for compact display
                value_groups: dict[str, list[str]] = defaultdict(list)
                for inst, val in values.items():
                    masked = mask_value(key, val)
                    value_groups[masked].append(inst)

                for val, insts in value_groups.items():
                    if len(insts) <= 3:
                        inst_str = ", ".join(insts)
                    else:
                        inst_str = f"{insts[0]}, {insts[1]}, ... (+{len(insts) - 2} others)"
                    print(f"      {inst_str}: {val}")

            total_drift += len(drift)

        # Missing
        if missing:
            print(f"\n  MISSING ({len(missing)} vars not in all instances):")
            for m in missing:
                key = m["key"]
                missing_from = m["missing_from"]
                if len(missing_from) <= 3:
                    missing_str = ", ".join(missing_from)
                else:
                    missing_str = f"{missing_from[0]}, {missing_from[1]}, ... (+{len(missing_from) - 2} others)"
                print(f"    {key}")
                print(f"      missing from: {missing_str}")

            total_missing += len(missing)

        if not drift and not missing:
            print("\n  All instances are in perfect parity.")

    return total_drift, total_missing


def to_json_report(
    groups: dict[str, list[tuple[str, Path]]],
) -> str:
    """Generate a JSON drift report."""
    report: dict = {"groups": {}}
    total_drift = 0
    total_missing = 0

    for base_type in sorted(groups.keys()):
        instances = groups[base_type]
        instance_names = [name for name, _ in instances]

        if len(instances) < 2:
            name, path = instances[0]
            env = parse_env_file(path)
            report["groups"][base_type] = {
                "instance_count": 1,
                "instances": instance_names,
                "shared_keys": sorted(env.keys()),
                "drift": [],
                "missing": [],
            }
            continue

        shared, drift, missing = analyze_group(instances)

        # Mask secret values in drift
        masked_drift = []
        for d in drift:
            masked_drift.append(
                {
                    "key": d["key"],
                    "values": {inst: mask_value(d["key"], val) for inst, val in d["values"].items()},
                }
            )

        report["groups"][base_type] = {
            "instance_count": len(instances),
            "instances": instance_names,
            "shared_keys": sorted(shared),
            "drift": masked_drift,
            "missing": missing,
        }

        total_drift += len(drift)
        total_missing += len(missing)

    report["summary"] = {
        "total_groups": len(groups),
        "total_instances": sum(len(v) for v in groups.values()),
        "total_drift_vars": total_drift,
        "total_missing_vars": total_missing,
        "clean": total_drift == 0 and total_missing == 0,
    }

    return json.dumps(report, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check environment variable parity across deploy instances.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON",
    )
    args = parser.parse_args()

    if not ENV_DIR.exists():
        print(f"ERROR: Env directory not found: {ENV_DIR}", file=sys.stderr)
        return 1

    groups = discover_env_groups()

    if not groups:
        print("No env files found.", file=sys.stderr)
        return 0

    if args.json_output:
        print(to_json_report(groups))
    else:
        total_drift, total_missing = print_text_report(groups)
        print()
        print(f"Summary: {sum(len(v) for v in groups.values())} instances across {len(groups)} types")
        print(f"  Drift vars: {total_drift}  |  Missing vars: {total_missing}")
        if total_drift == 0 and total_missing == 0:
            print("  All groups in perfect parity.")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
