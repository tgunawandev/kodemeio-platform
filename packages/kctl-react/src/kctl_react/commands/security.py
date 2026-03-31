"""Security scanning commands."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated

import typer

from kctl_react.core.callbacks import AppContext
from kctl_react.core.discovery import get_app_dir
from kctl_react.core.exceptions import CommandError
from kctl_react.core.runner import run, run_pnpm

app = typer.Typer(help="Security scanning and compliance checks.")

# Patterns for hardcoded secrets detection
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("AWS Secret Key", re.compile(r"""(?:aws_secret|secret_key)\s*[=:]\s*['"][A-Za-z0-9/+=]{40}['"]""", re.I)),
    ("Generic API Key", re.compile(r"""(?:api_key|apikey|api-key)\s*[=:]\s*['"][A-Za-z0-9_\-]{20,}['"]""", re.I)),
    (
        "Generic Secret",
        re.compile(r"""(?:secret|token|password|passwd)\s*[=:]\s*['"][A-Za-z0-9_\-/+=]{8,}['"]""", re.I),
    ),
    ("Private Key", re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----")),
    ("Bearer Token", re.compile(r"""['"]Bearer\s+[A-Za-z0-9\-._~+/]+=*['"]""")),
    ("Basic Auth", re.compile(r"""['"]Basic\s+[A-Za-z0-9+/]+=*['"]""")),
    ("GitHub Token", re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}")),
    ("Slack Token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]+")),
    ("JWT", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+")),
]

# Files to skip during secret scanning
_SKIP_DIRS = {
    "node_modules",
    "dist",
    ".next",
    ".git",
    "coverage",
    "generated",
    "__pycache__",
    ".turbo",
    ".kctl-react",
}
_SCAN_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".json", ".env", ".yaml", ".yml", ".toml"}

# Known security headers
_SECURITY_HEADERS = [
    "content-security-policy",
    "strict-transport-security",
    "x-frame-options",
    "x-content-type-options",
    "x-xss-protection",
    "referrer-policy",
    "permissions-policy",
]


def _scan_file_for_secrets(file_path: Path) -> list[dict]:
    """Scan a single file for hardcoded secrets."""
    findings: list[dict] = []
    try:
        content = file_path.read_text(errors="ignore")
    except Exception:
        return findings

    for line_num, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        # Skip comments and imports
        if stripped.startswith(("//", "#", "*", "/*", "import ", "from ")) or "VITE_" in stripped:
            continue
        for name, pattern in _SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(
                    {
                        "file": str(file_path),
                        "line": line_num,
                        "type": name,
                        "snippet": stripped[:120],
                    }
                )
    return findings


def _parse_audit_json(raw: str) -> dict:
    """Parse pnpm audit --json output into severity counts."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"critical": 0, "high": 0, "moderate": 0, "low": 0, "info": 0, "total": 0}

    # pnpm audit JSON uses "advisories" dict
    advisories = data.get("advisories", {})
    counts: dict[str, int] = {"critical": 0, "high": 0, "moderate": 0, "low": 0, "info": 0}
    for advisory in advisories.values():
        severity = advisory.get("severity", "info").lower()
        if severity in counts:
            counts[severity] += 1
        else:
            counts["info"] += 1

    counts["total"] = sum(counts.values())
    return counts


def _parse_audit_advisories(raw: str) -> list[dict]:
    """Parse pnpm audit --json output into detailed advisory list."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    advisories = data.get("advisories", {})
    results: list[dict] = []
    for _id, advisory in advisories.items():
        results.append(
            {
                "id": advisory.get("id", _id),
                "title": advisory.get("title", "Unknown"),
                "severity": advisory.get("severity", "info"),
                "module": advisory.get("module_name", "?"),
                "url": advisory.get("url", ""),
                "cves": advisory.get("cves", []),
                "recommendation": advisory.get("recommendation", "Update to latest"),
                "vulnerable_versions": advisory.get("vulnerable_versions", ""),
                "patched_versions": advisory.get("patched_versions", ""),
                "findings": [
                    {"version": f.get("version", "?"), "paths": f.get("paths", [])}
                    for f in advisory.get("findings", [])
                ],
            }
        )
    return sorted(results, key=lambda x: {"critical": 0, "high": 1, "moderate": 2, "low": 3}.get(x["severity"], 4))


@app.command()
def audit(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (omit for monorepo root)")] = None,
    detail: Annotated[
        bool, typer.Option("--detail", "-d", help="Show CVE IDs, fix commands, and advisory URLs")
    ] = False,
) -> None:
    """Run pnpm audit — show vulnerabilities with severity, CVEs, and fix commands."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if app_name:
        actx.validate_app(app_name)
        cwd = get_app_dir(root, app_name)
        target = app_name
    else:
        cwd = root
        target = "monorepo root"

    out.info(f"Running dependency audit for {target}...")

    try:
        result = run_pnpm(["audit", "--json"], cwd=cwd, capture=True, timeout=120)
        raw = result.stdout
    except CommandError as e:
        raw = e.stderr or ""

    # Summary counts
    counts = _parse_audit_json(raw)

    severity_colors = {
        "critical": "red",
        "high": "red",
        "moderate": "yellow",
        "low": "dim",
        "info": "dim",
    }

    # Summary table
    summary_rows: list[list[str]] = [
        [sev, f"[{severity_colors.get(sev, 'white')}]{counts[sev]}[/{severity_colors.get(sev, 'white')}]"]
        for sev in ("critical", "high", "moderate", "low", "info")
    ]
    summary_rows.append(["total", str(counts["total"])])
    out.table(
        f"Vulnerability Summary — {target}",
        [("Severity", "cyan"), ("Count", "")],
        summary_rows,
    )

    if counts["total"] == 0:
        out.success("No known vulnerabilities found")
        if out.json_mode:
            out.raw_json({"target": target, "counts": counts, "advisories": []})
        return

    # Detailed advisory table
    advisories = _parse_audit_advisories(raw)

    if out.json_mode:
        out.raw_json({"target": target, "counts": counts, "advisories": advisories})
        return

    if advisories and detail:
        detail_rows: list[list[str]] = []
        for adv in advisories:
            sev = adv["severity"]
            color = severity_colors.get(sev, "white")
            cve_str = ", ".join(adv["cves"]) if adv["cves"] else "—"
            fix = adv["patched_versions"] or adv["recommendation"]
            detail_rows.append(
                [
                    f"[{color}]{sev.upper()}[/{color}]",
                    adv["module"],
                    adv["title"][:50],
                    cve_str,
                    fix[:40],
                ]
            )
        out.table(
            f"Advisory Details ({len(advisories)} found)",
            [("Severity", ""), ("Package", "cyan"), ("Title", ""), ("CVEs", "yellow"), ("Fix", "green")],
            detail_rows,
        )

        # Show fix commands
        fix_packages = sorted({adv["module"] for adv in advisories if adv["patched_versions"]})
        if fix_packages:
            out.info("Fix commands:")
            for pkg in fix_packages:
                out.text(f"  pnpm update {pkg}")
    elif advisories and not detail:
        out.info("Use --detail to see CVE IDs, advisory titles, and fix commands")

    critical_high = counts["critical"] + counts["high"]
    if critical_high > 0:
        out.error(f"{counts['total']} vulnerability(s) found — {critical_high} critical/high")
    else:
        out.warn(f"{counts['total']} vulnerability(s) found (no critical/high)")


@app.command()
def scan(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (omit for all)")] = None,
) -> None:
    """Combined security scan: dependency audit + secret detection."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("[bold]--- Dependency Audit ---[/bold]")
    ctx.invoke(audit, app_name=app_name)

    out.info("")
    out.info("[bold]--- Secret Scanning ---[/bold]")
    ctx.invoke(secrets, app_name=app_name)


@app.command()
def secrets(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (omit for all)")] = None,
) -> None:
    """Scan source code for hardcoded API keys, tokens, and passwords."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if app_name:
        actx.validate_app(app_name)
        scan_dirs = [get_app_dir(root, app_name) / "src"]
    else:
        scan_dirs = [get_app_dir(root, name) / "src" for name in actx.app_names]
        # Also scan packages
        packages_dir = root / "packages"
        if packages_dir.is_dir():
            for pkg_dir in sorted(packages_dir.iterdir()):
                src = pkg_dir / "src"
                if src.is_dir():
                    scan_dirs.append(src)

    out.info("Scanning for hardcoded secrets...")

    all_findings: list[dict] = []
    for scan_dir in scan_dirs:
        if not scan_dir.is_dir():
            continue
        for file_path in scan_dir.rglob("*"):
            if not file_path.is_file():
                continue
            if any(skip in file_path.parts for skip in _SKIP_DIRS):
                continue
            if file_path.suffix not in _SCAN_EXTENSIONS:
                continue
            all_findings.extend(_scan_file_for_secrets(file_path))

    if not all_findings:
        out.success("No hardcoded secrets detected")
        if out.json_mode:
            out.raw_json({"findings": [], "total": 0})
        return

    rows: list[list[str]] = []
    for f in all_findings:
        rel_path = str(Path(f["file"]).relative_to(root)) if root in Path(f["file"]).parents else f["file"]
        rows.append([rel_path, str(f["line"]), f["type"], f["snippet"][:60]])

    out.table(
        "Secret Scan Results",
        [("File", "cyan"), ("Line", "green"), ("Type", "yellow"), ("Snippet", "dim")],
        rows,
        data_for_json=all_findings,
    )
    out.warn(f"{len(all_findings)} potential secret(s) found — review and rotate if real")


@app.command()
def headers(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name to check")],
    url: Annotated[str | None, typer.Option("--url", help="Override URL (default: localhost:<port>)")] = None,
) -> None:
    """Check security headers on a running app."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_info = actx.apps[app_name]
    target_url = url or f"http://localhost:{app_info['port']}"

    out.info(f"Checking security headers on {target_url}...")

    try:
        result = run(
            ["curl", "-sI", "--max-time", "5", target_url],
            cwd=root,
            capture=True,
            timeout=10,
        )
        response_headers = result.stdout.lower()
    except Exception as e:
        out.error(f"Cannot reach {target_url}: {e}")
        if out.json_mode:
            out.raw_json({"url": target_url, "error": str(e), "headers": {}})
        raise typer.Exit(1) from None

    rows: list[list[str]] = []
    json_data: dict[str, dict] = {}

    for header in _SECURITY_HEADERS:
        present = header in response_headers
        status = "[green]present[/green]" if present else "[red]missing[/red]"
        rows.append([header, status])
        json_data[header] = {"present": present}

    present_count = sum(1 for h in _SECURITY_HEADERS if h in response_headers)
    total = len(_SECURITY_HEADERS)
    score = f"{present_count}/{total}"

    out.table(
        f"Security Headers — {app_name} ({target_url})",
        [("Header", "cyan"), ("Status", "")],
        rows,
        data_for_json=[{"url": target_url, "score": score, "headers": json_data}],
    )

    if present_count < total:
        out.warn(f"Score: {score} — missing {total - present_count} header(s)")
    else:
        out.success(f"Score: {score} — all security headers present")


@app.command("deps-license")
@app.command("licenses")
def deps_license(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (omit for root)")] = None,
    check: Annotated[str | None, typer.Option("--check", help="Fail on disallowed licenses (comma-separated)")] = None,
) -> None:
    """Check license compliance across dependencies."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if app_name:
        actx.validate_app(app_name)

    cwd = get_app_dir(root, app_name) if app_name else root
    target = app_name or "monorepo root"
    out.info(f"Checking dependency licenses for {target}...")

    # Read node_modules for license info
    licenses: dict[str, int] = {}
    flagged: list[dict] = []
    disallowed = {lic.strip().upper() for lic in check.split(",")} if check else set()

    node_modules = cwd / "node_modules"
    if not node_modules.is_dir():
        # Fall back to root node_modules (pnpm hoists)
        node_modules = root / "node_modules"

    if not node_modules.is_dir():
        out.warn("node_modules not found — run `pnpm install` first")
        return

    scanned = 0
    for pkg_json in node_modules.rglob("package.json"):
        # Skip nested node_modules
        rel = pkg_json.relative_to(node_modules)
        parts = rel.parts
        if len(parts) > 2 and not parts[0].startswith("@"):
            continue
        if len(parts) > 3:
            continue

        try:
            pkg = json.loads(pkg_json.read_text())
        except Exception:
            continue

        pkg_name = pkg.get("name", "")
        if not pkg_name:
            continue

        license_val = pkg.get("license", "UNKNOWN")
        if isinstance(license_val, dict):
            license_val = license_val.get("type", "UNKNOWN")

        licenses[license_val] = licenses.get(license_val, 0) + 1
        scanned += 1

        if disallowed and license_val.upper() in disallowed:
            flagged.append({"package": pkg_name, "license": license_val})

    # Summary table
    rows: list[list[str]] = []
    json_data: list[dict] = []
    for lic, count in sorted(licenses.items(), key=lambda x: -x[1]):
        is_flagged = lic.upper() in disallowed if disallowed else False
        status = "[red]DISALLOWED[/red]" if is_flagged else "[green]OK[/green]"
        rows.append([lic, str(count), status])
        json_data.append({"license": lic, "count": count, "allowed": not is_flagged})

    out.table(
        f"License Summary — {target} ({scanned} packages)",
        [("License", "cyan"), ("Count", "green"), ("Status", "")],
        rows,
        data_for_json=json_data,
    )

    if flagged:
        out.warn(f"{len(flagged)} package(s) with disallowed licenses")
        flag_rows = [[f["package"], f["license"]] for f in flagged]
        out.table(
            "Disallowed Packages",
            [("Package", "cyan"), ("License", "red")],
            flag_rows,
            data_for_json=flagged,
        )
        raise typer.Exit(1) from None
    else:
        out.success(f"Scanned {scanned} packages — no license violations")


def _collect_secrets(root: Path, app_name: str | None, app_names: list[str], packages_dir: Path) -> list[dict]:
    """Collect secret scan findings without printing output."""
    if app_name:
        scan_dirs = [get_app_dir(root, app_name) / "src"]
    else:
        scan_dirs = [get_app_dir(root, name) / "src" for name in app_names]
        if packages_dir.is_dir():
            for pkg_dir in sorted(packages_dir.iterdir()):
                src = pkg_dir / "src"
                if src.is_dir():
                    scan_dirs.append(src)

    all_findings: list[dict] = []
    for scan_dir in scan_dirs:
        if not scan_dir.is_dir():
            continue
        for file_path in scan_dir.rglob("*"):
            if not file_path.is_file():
                continue
            if any(skip in file_path.parts for skip in _SKIP_DIRS):
                continue
            if file_path.suffix not in _SCAN_EXTENSIONS:
                continue
            all_findings.extend(_scan_file_for_secrets(file_path))
    return all_findings


def _collect_audit(root: Path, app_names: list[str]) -> dict:
    """Collect audit counts without printing output."""
    totals: dict[str, int] = {"critical": 0, "high": 0, "moderate": 0, "low": 0, "info": 0, "total": 0}
    for name in app_names:
        cwd = get_app_dir(root, name)
        try:
            result = run_pnpm(["audit", "--json"], cwd=cwd, capture=True, timeout=120)
            counts = _parse_audit_json(result.stdout)
        except CommandError as e:
            counts = _parse_audit_json(e.stderr or "")
        except Exception:
            counts = {"critical": 0, "high": 0, "moderate": 0, "low": 0, "info": 0, "total": 0}
        for key in totals:
            totals[key] += counts.get(key, 0)
    return totals


def _collect_license_flags(root: Path) -> list[dict]:
    """Collect license info without printing output. Returns flagged packages (GPL etc)."""
    node_modules = root / "node_modules"
    if not node_modules.is_dir():
        return []

    copyleft = {"GPL-2.0", "GPL-3.0", "AGPL-3.0", "LGPL-2.1", "LGPL-3.0"}
    flagged: list[dict] = []
    for pkg_json in node_modules.rglob("package.json"):
        rel = pkg_json.relative_to(node_modules)
        parts = rel.parts
        if len(parts) > 2 and not parts[0].startswith("@"):
            continue
        if len(parts) > 3:
            continue
        try:
            pkg = json.loads(pkg_json.read_text())
        except Exception:
            continue
        pkg_name = pkg.get("name", "")
        if not pkg_name:
            continue
        license_val = pkg.get("license", "UNKNOWN")
        if isinstance(license_val, dict):
            license_val = license_val.get("type", "UNKNOWN")
        if license_val.upper() in {c.upper() for c in copyleft}:
            flagged.append({"package": pkg_name, "license": license_val})
    return flagged


@app.command()
def report(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (omit for all)")] = None,
    strict: Annotated[bool, typer.Option("--strict", help="Exit 1 if any check has findings")] = False,
) -> None:
    """Run all security checks and produce an aggregated report."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if app_name:
        actx.validate_app(app_name)
        apps_to_check = [app_name]
    else:
        apps_to_check = actx.app_names

    target = app_name or "all apps"
    out.info(f"Running full security report for {target}...")

    has_issues = False

    # 1. Audit
    out.info("  [1/4] Dependency audit...")
    audit_counts = _collect_audit(root, apps_to_check)
    audit_critical = audit_counts["critical"] + audit_counts["high"]
    audit_ok = audit_counts["total"] == 0
    if not audit_ok:
        has_issues = True

    # 2. Secrets
    out.info("  [2/4] Secret scan...")
    findings = _collect_secrets(root, app_name, actx.app_names, root / "packages")
    secrets_count = len(findings)
    secrets_ok = secrets_count == 0
    if not secrets_ok:
        has_issues = True

    # 3. Headers (skip — requires running app, just report "skipped" unless single app)
    headers_missing = -1  # -1 means skipped
    headers_ok = True
    if app_name:
        app_info = actx.apps[app_name]
        target_url = f"http://localhost:{app_info['port']}"
        out.info(f"  [3/4] Security headers ({target_url})...")
        try:
            result = run(
                ["curl", "-sI", "--max-time", "5", target_url],
                cwd=root,
                capture=True,
                timeout=10,
            )
            response_headers = result.stdout.lower()
            headers_missing = sum(1 for h in _SECURITY_HEADERS if h not in response_headers)
            headers_ok = headers_missing == 0
            if not headers_ok:
                has_issues = True
        except Exception:
            headers_missing = -1  # Unreachable
    else:
        out.info("  [3/4] Security headers... skipped (specify APP to check)")

    # 4. Licenses
    out.info("  [4/4] License compliance...")
    license_flags = _collect_license_flags(root)
    license_count = len(license_flags)
    license_ok = license_count == 0
    if not license_ok:
        has_issues = True

    # Build summary
    checks: list[dict] = [
        {
            "check": "audit",
            "status": "pass" if audit_ok else "fail",
            "detail": f"{audit_counts['total']} vuln(s), {audit_critical} critical+high",
            "counts": audit_counts,
        },
        {
            "check": "secrets",
            "status": "pass" if secrets_ok else "fail",
            "detail": f"{secrets_count} finding(s)",
            "count": secrets_count,
        },
        {
            "check": "headers",
            "status": "skip" if headers_missing == -1 else ("pass" if headers_ok else "fail"),
            "detail": "skipped" if headers_missing == -1 else f"{headers_missing} missing",
            "missing": headers_missing,
        },
        {
            "check": "licenses",
            "status": "pass" if license_ok else "fail",
            "detail": f"{license_count} copyleft package(s)",
            "count": license_count,
        },
    ]

    rows: list[list[str]] = []
    for c in checks:
        status_map = {"pass": "[green]PASS[/green]", "fail": "[red]FAIL[/red]", "skip": "[dim]SKIP[/dim]"}
        rows.append([c["check"], status_map.get(c["status"], c["status"]), c["detail"]])

    out.table(
        f"Security Report — {target}",
        [("Check", "cyan"), ("Status", ""), ("Detail", "dim")],
        rows,
        data_for_json=checks,
    )

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    skipped = sum(1 for c in checks if c["status"] == "skip")

    if failed == 0:
        out.success(f"{passed} passed, {skipped} skipped — no issues found")
    else:
        out.warn(f"{passed} passed, {failed} failed, {skipped} skipped")

    if strict and has_issues:
        raise typer.Exit(1) from None
