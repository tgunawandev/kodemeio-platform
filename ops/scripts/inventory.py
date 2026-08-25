#!/usr/bin/env python3
"""Generate a resource inventory report from deploy manifests.

Scans deploys/instances/*.yaml, resolves base inheritance, and produces
a markdown, JSON, or CSV report of all services grouped by project.

Usage:
    uv run python ops/scripts/inventory.py
    uv run python ops/scripts/inventory.py --json
    uv run python ops/scripts/inventory.py --format csv --output inventory.csv
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ServiceInstance:
    """Parsed service instance from a deploy manifest."""

    name: str
    description: str
    type: str
    project: str
    server: str
    domain: str
    ssl: str
    backup_enabled: bool
    backup_schedule: str
    backup_retention: str
    manifest_file: str


@dataclass
class Inventory:
    """Complete resource inventory."""

    generated: str
    instances: list[ServiceInstance] = field(default_factory=list)

    # -- Derived summaries --

    @property
    def total(self) -> int:
        return len(self.instances)

    def count_by_type(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for inst in self.instances:
            counts[inst.type] += 1
        return dict(sorted(counts.items()))

    def group_by_project(self) -> dict[str, list[ServiceInstance]]:
        groups: dict[str, list[ServiceInstance]] = defaultdict(list)
        for inst in self.instances:
            groups[inst.project].append(inst)
        return dict(sorted(groups.items()))


# ---------------------------------------------------------------------------
# Manifest parsing
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTANCES_DIR = REPO_ROOT / "deploys" / "instances"
BASES_DIR = REPO_ROOT / "deploys" / "bases"

# Friendly labels for the type field
TYPE_LABELS: dict[str, str] = {
    "odoo": "Odoo instances",
    "nextjs": "Next.js websites",
    "react-pwa": "React PWA apps",
    "fastapi": "FastAPI services",
    "infrastructure": "Infrastructure services",
}


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path) as fh:
        return yaml.safe_load(fh) or {}


def _resolve_base(instance_path: Path, data: dict[str, Any]) -> dict[str, Any]:
    """Resolve 'extends' field by merging the base manifest into the instance."""
    extends = data.get("extends")
    if not extends:
        return data

    base_path = (instance_path.parent / extends).resolve()
    if not base_path.exists():
        return data

    base = _load_yaml(base_path)
    merged = _deep_merge(base, data)
    return merged


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override into base, preferring override values."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def parse_manifest(path: Path) -> ServiceInstance:
    """Parse a single instance manifest into a ServiceInstance."""
    raw = _load_yaml(path)
    data = _resolve_base(path, raw)

    instance_block = data.get("instance", {})
    domain_block = data.get("domain", {})
    backup_block = data.get("backup", {})

    name = instance_block.get("name", path.stem)
    description = instance_block.get("description", "")
    service_type = data.get("type", "unknown")
    project = data.get("project", "kodeme.io")
    server = data.get("server", "kodeme-service")
    domain_host = domain_block.get("host", "")
    https = domain_block.get("https", False)
    cert = domain_block.get("cert", "")

    if https and cert:
        ssl_label = cert.replace("letsencrypt", "Let's Encrypt")
    elif https:
        ssl_label = "Yes"
    else:
        ssl_label = "No"

    has_backup = bool(backup_block)
    backup_schedule = backup_block.get("schedule", "")
    keep_latest = backup_block.get("keep_latest")
    retention = f"{keep_latest} days" if keep_latest else ""

    return ServiceInstance(
        name=name,
        description=description,
        type=service_type,
        project=project,
        server=server,
        domain=domain_host,
        ssl=ssl_label,
        backup_enabled=has_backup,
        backup_schedule=_human_cron(backup_schedule) if backup_schedule else "",
        backup_retention=retention,
        manifest_file=path.name,
    )


def _human_cron(cron: str) -> str:
    """Convert a simple cron expression to a human-readable label."""
    parts = cron.strip().split()
    if len(parts) != 5:
        return cron

    minute, hour, dom, month, dow = parts

    # Daily pattern: 0 H * * *
    if dom == "*" and month == "*" and dow == "*":
        return f"Daily {hour}:{minute.zfill(2)}"

    # Weekly pattern: 0 H * * D
    if dom == "*" and month == "*" and dow != "*":
        day_names = {
            "0": "Sun",
            "1": "Mon",
            "2": "Tue",
            "3": "Wed",
            "4": "Thu",
            "5": "Fri",
            "6": "Sat",
            "7": "Sun",
        }
        day = day_names.get(dow, dow)
        return f"Weekly {day} {hour}:{minute.zfill(2)}"

    return cron


def scan_manifests(instances_dir: Path | None = None) -> Inventory:
    """Scan all instance manifests and build an Inventory."""
    directory = instances_dir or INSTANCES_DIR
    if not directory.exists():
        print(f"Error: instances directory not found: {directory}", file=sys.stderr)
        sys.exit(1)

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    inventory = Inventory(generated=now)

    for manifest_path in sorted(directory.glob("*.yaml")):
        try:
            instance = parse_manifest(manifest_path)
            inventory.instances.append(instance)
        except Exception as exc:
            print(
                f"Warning: failed to parse {manifest_path.name}: {exc}",
                file=sys.stderr,
            )

    return inventory


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    """Build a markdown table string."""
    lines: list[str] = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


def format_markdown(inv: Inventory) -> str:
    """Render inventory as a markdown report."""
    lines: list[str] = []

    lines.append("# Kodemeio Resource Inventory")
    lines.append(f"> Generated: {inv.generated}")
    lines.append("")

    # -- Service Summary --
    lines.append("## Service Summary")
    lines.append("")
    type_counts = inv.count_by_type()
    summary_rows: list[list[str]] = [["Total instances", str(inv.total)]]
    for stype, count in type_counts.items():
        label = TYPE_LABELS.get(stype, f"{stype} services")
        summary_rows.append([label, str(count)])

    lines.append(_md_table(["Metric", "Count"], summary_rows))
    lines.append("")

    # -- By Project --
    lines.append("## By Project")
    lines.append("")
    for project, instances in inv.group_by_project().items():
        lines.append(f"### {project} ({len(instances)} services)")
        lines.append("")
        rows = [[i.name, i.type, i.domain or "(no domain)", i.server] for i in instances]
        lines.append(_md_table(["Instance", "Type", "Domain", "Server"], rows))
        lines.append("")

    # -- Domain Registry --
    lines.append("## Domain Registry")
    lines.append("")
    domain_rows = [[i.domain, i.name, i.ssl, i.type] for i in inv.instances if i.domain]
    domain_rows.sort(key=lambda r: r[0])
    lines.append(_md_table(["Domain", "Service", "SSL", "Type"], domain_rows))
    lines.append("")

    # -- Backup Coverage --
    lines.append("## Backup Coverage")
    lines.append("")
    backup_rows = [
        [
            i.name,
            "Yes" if i.backup_enabled else "No",
            i.backup_schedule or "\u2014",
            i.backup_retention or "\u2014",
        ]
        for i in inv.instances
    ]
    lines.append(_md_table(["Instance", "Has Backup", "Schedule", "Retention"], backup_rows))
    lines.append("")

    return "\n".join(lines)


def format_json(inv: Inventory) -> str:
    """Render inventory as JSON."""
    payload = {
        "generated": inv.generated,
        "summary": {
            "total": inv.total,
            "by_type": inv.count_by_type(),
        },
        "instances": [asdict(i) for i in inv.instances],
        "by_project": {
            project: [asdict(i) for i in instances] for project, instances in inv.group_by_project().items()
        },
    }
    return json.dumps(payload, indent=2)


def format_csv(inv: Inventory) -> str:
    """Render inventory as CSV."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "name",
            "description",
            "type",
            "project",
            "server",
            "domain",
            "ssl",
            "backup_enabled",
            "backup_schedule",
            "backup_retention",
            "manifest_file",
        ]
    )
    for i in inv.instances:
        writer.writerow(
            [
                i.name,
                i.description,
                i.type,
                i.project,
                i.server,
                i.domain,
                i.ssl,
                i.backup_enabled,
                i.backup_schedule,
                i.backup_retention,
                i.manifest_file,
            ]
        )
    return buf.getvalue()


FORMATTERS: dict[str, Any] = {
    "markdown": format_markdown,
    "json": format_json,
    "csv": format_csv,
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a resource inventory from deploy manifests.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_shortcut",
        help="Output JSON instead of markdown (shortcut for --format json)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["markdown", "json", "csv"],
        default="markdown",
        dest="fmt",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Write output to FILE instead of stdout",
    )
    parser.add_argument(
        "--instances-dir",
        type=str,
        default=None,
        help="Path to instances directory (default: deploys/instances/)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    fmt = "json" if args.json_shortcut else args.fmt
    instances_dir = Path(args.instances_dir) if args.instances_dir else None

    inventory = scan_manifests(instances_dir)

    if not inventory.instances:
        print("No deploy manifests found.", file=sys.stderr)
        sys.exit(1)

    formatter = FORMATTERS[fmt]
    output = formatter(inventory)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output)
        print(f"Inventory written to {out_path}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
