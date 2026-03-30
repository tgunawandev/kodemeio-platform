"""Security auditing commands for kctl-api.

Vulnerability scan, secret detection, CORS audit, headers check.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.utils import find_project_root

app = typer.Typer(name="security", help="Security — audit, secrets, CORS, headers, deps.", no_args_is_help=True)

# Patterns for secret detection
_SECRET_PATTERNS: list[tuple[str, str]] = [
    (r"(?i)(password|passwd|pwd)\s*=\s*['\"][^'\"]{6,}", "password assignment"),
    (r"(?i)(secret|token|api[_-]?key|apikey)\s*=\s*['\"][^'\"]{8,}", "secret/token assignment"),
    (r"(?i)authorization:\s*bearer\s+[a-zA-Z0-9._-]{20,}", "bearer token in code"),
    (r"sk-[a-zA-Z0-9]{20,}", "OpenAI API key"),
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub personal token"),
    (r"(?i)aws_secret_access_key\s*=\s*[a-zA-Z0-9/+]{40}", "AWS secret key"),
    (r"-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----", "private key"),
]


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------
@app.command()
def audit(ctx: typer.Context) -> None:
    """Run a combined security report: deps, secrets, and CORS."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    out.header("Security Audit Report")
    out.text("")

    issues: list[dict] = []

    # 1. Dependency vulnerabilities
    import shutil

    out.info("[1/3] Checking dependency vulnerabilities ...")
    if shutil.which("pip-audit"):
        result = subprocess.run(["pip-audit", "--format", "json"], capture_output=True, text=True, cwd=str(root))
        import json

        try:
            data = json.loads(result.stdout)
            vulns = data.get("vulnerabilities", [])
            for v in vulns:
                issues.append(
                    {
                        "category": "dependency",
                        "severity": "HIGH",
                        "detail": f"{v.get('name')} {v.get('version')}: {v.get('id')}",
                    }
                )
            if not vulns:
                out.success("  No dependency vulnerabilities.")
            else:
                out.warn(f"  {len(vulns)} vulnerabilities found.")
        except Exception:
            out.info("  pip-audit output could not be parsed.")
    else:
        out.info("  pip-audit not installed — skipping. Run: uv add --dev pip-audit")

    # 2. Secret detection (simplified scan)
    out.info("[2/3] Scanning for secrets in source ...")
    secret_issues = _scan_secrets(root)
    issues.extend(secret_issues)
    if not secret_issues:
        out.success("  No secrets detected in source code.")
    else:
        out.warn(f"  {len(secret_issues)} potential secrets detected.")

    # 3. CORS config
    out.info("[3/3] Checking CORS configuration ...")
    cors_issues = _check_cors_config(root)
    issues.extend(cors_issues)
    if not cors_issues:
        out.success("  CORS configuration looks safe.")
    else:
        out.warn(f"  {len(cors_issues)} CORS concern(s).")

    out.text("")
    if not issues:
        out.success("Security audit complete — no issues found.")
        return

    rows = [[i["category"], i["severity"], i["detail"][:80]] for i in issues]
    out.table(
        title=f"Security Issues ({len(issues)})",
        columns=[("Category", "bold"), ("Severity", "red"), ("Detail", "")],
        rows=rows,
        data_for_json=issues,
    )
    raise typer.Exit(1)


def _scan_secrets(root: pathlib.Path) -> list[dict]:
    """Scan Python source files for secret patterns."""

    issues: list[dict] = []
    skip_dirs = {".venv", "__pycache__", ".git", "node_modules", "dist", ".mypy_cache"}

    for py_file in root.rglob("*.py"):
        if any(part in skip_dirs for part in py_file.parts):
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pattern, label in _SECRET_PATTERNS:
            if re.search(pattern, content):
                issues.append(
                    {
                        "category": "secret",
                        "severity": "CRITICAL",
                        "detail": f"{py_file.relative_to(root)}: possible {label}",
                    }
                )
                break  # One issue per file

    return issues


def _check_cors_config(root: pathlib.Path) -> list[dict]:
    """Check for overly permissive CORS settings."""

    issues: list[dict] = []
    skip_dirs = {".venv", "__pycache__", ".git", "node_modules"}

    wildcard_patterns = [
        (r'allow_origins\s*=\s*\[.*["\']?\*["\']?.*\]', "allow_origins = ['*']"),
        (r"CORSMiddleware.*origins.*\*", "CORS wildcard origin"),
    ]

    for py_file in root.rglob("*.py"):
        if any(part in skip_dirs for part in py_file.parts):
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pattern, label in wildcard_patterns:
            if re.search(pattern, content):
                issues.append(
                    {
                        "category": "cors",
                        "severity": "MEDIUM",
                        "detail": f"{py_file.relative_to(root)}: {label}",
                    }
                )

    return issues


# ---------------------------------------------------------------------------
# secrets
# ---------------------------------------------------------------------------
@app.command()
def secrets(
    ctx: typer.Context,
    path: Annotated[str | None, typer.Argument(help="Path to scan (default: project root).")] = None,
) -> None:
    """Scan source code for potential secrets and credentials."""
    actx: AppContext = ctx.obj
    out = actx.output

    import pathlib

    root = pathlib.Path(path) if path else find_project_root()
    out.info(f"Scanning {root} for secrets ...")

    # Try gitleaks if available
    import shutil

    if shutil.which("gitleaks"):
        result = subprocess.run(
            ["gitleaks", "detect", "--source", str(root), "--report-format", "json"], capture_output=True, text=True
        )
        if result.returncode == 0:
            out.success("No secrets detected (gitleaks).")
            return
        import json

        try:
            findings = json.loads(result.stdout)
            rows = [[f.get("RuleID", ""), f.get("File", ""), str(f.get("StartLine", ""))] for f in findings]
            out.table(
                title=f"Secret Findings ({len(findings)})",
                columns=[("Rule", "bold"), ("File", ""), ("Line", "")],
                rows=rows,
                data_for_json=findings,
            )
            raise typer.Exit(1)
        except Exception:
            out.text(result.stdout[:2000])
            raise typer.Exit(1) from None

    # Fall back to regex scan
    issues = _scan_secrets(root)
    if not issues:
        out.success("No secrets detected in Python source files.")
        return

    rows = [[i["severity"], i["detail"]] for i in issues]
    out.table(
        title=f"Potential Secrets ({len(issues)})",
        columns=[("Severity", "bold"), ("Detail", "")],
        rows=rows,
        data_for_json=issues,
    )
    out.info("Install gitleaks for comprehensive scanning: https://github.com/gitleaks/gitleaks")
    raise typer.Exit(1)


# ---------------------------------------------------------------------------
# cors
# ---------------------------------------------------------------------------
@app.command()
def cors(ctx: typer.Context) -> None:
    """Audit CORS configuration in the codebase."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    out.info("Auditing CORS configuration ...")

    issues = _check_cors_config(root)

    # Also check env files for CORS_ORIGINS

    env_file = root / ".env"
    if env_file.exists():
        content = env_file.read_text()
        if "CORS_ORIGINS=*" in content or 'CORS_ORIGINS="*"' in content:
            issues.append(
                {
                    "category": "cors",
                    "severity": "HIGH",
                    "detail": ".env: CORS_ORIGINS=* (wildcard in env var)",
                }
            )

    if not issues:
        out.success("CORS configuration looks safe — no wildcard origins found.")
        return

    rows = [[i["severity"], i["detail"]] for i in issues]
    out.table(
        title=f"CORS Issues ({len(issues)})",
        columns=[("Severity", "bold"), ("Detail", "red")],
        rows=rows,
        data_for_json=issues,
    )
    out.warn("Review CORS config. Wildcard origins allow any site to call your API.")
    raise typer.Exit(1)


# ---------------------------------------------------------------------------
# headers
# ---------------------------------------------------------------------------
@app.command()
def headers(
    ctx: typer.Context,
    url: Annotated[str | None, typer.Argument(help="URL to check (default: configured API URL).")] = None,
) -> None:
    """Check security headers on a URL."""
    actx: AppContext = ctx.obj
    out = actx.output

    import httpx

    target_url = url or f"{actx.client.base_url.rstrip('/')}/api/v1/health"
    out.info(f"Checking security headers: {target_url}")

    try:
        response = httpx.get(target_url, timeout=10, follow_redirects=True)
    except Exception as e:
        out.error(f"Request failed: {e}")
        raise typer.Exit(1) from None

    security_headers = {
        "Strict-Transport-Security": {"required": True, "note": "HSTS — forces HTTPS"},
        "X-Content-Type-Options": {"required": True, "note": "Prevents MIME sniffing"},
        "X-Frame-Options": {"required": False, "note": "Clickjacking protection"},
        "Content-Security-Policy": {"required": False, "note": "XSS protection"},
        "X-XSS-Protection": {"required": False, "note": "Browser XSS filter"},
        "Referrer-Policy": {"required": False, "note": "Controls referrer info"},
        "Permissions-Policy": {"required": False, "note": "Controls browser features"},
    }

    results: list[dict] = []
    for header, meta in security_headers.items():
        value = response.headers.get(header, "")
        present = bool(value)
        results.append(
            {
                "header": header,
                "present": present,
                "value": value[:60] if value else "",
                "required": meta["required"],
                "note": meta["note"],
            }
        )

    rows = [
        [
            r["header"],
            "[green]yes[/green]" if r["present"] else ("[red]NO[/red]" if r["required"] else "[yellow]no[/yellow]"),
            r["value"] or r["note"],
        ]
        for r in results
    ]
    out.table(
        title=f"Security Headers: {target_url}",
        columns=[("Header", "bold"), ("Present", ""), ("Value / Note", "")],
        rows=rows,
        data_for_json={"url": target_url, "status_code": response.status_code, "headers": results},
    )

    missing_required = [r for r in results if r["required"] and not r["present"]]
    if missing_required:
        out.warn(f"{len(missing_required)} required security header(s) missing.")
        raise typer.Exit(1)
    else:
        out.success("All required security headers present.")


# ---------------------------------------------------------------------------
# deps
# ---------------------------------------------------------------------------
@app.command()
def deps(ctx: typer.Context) -> None:
    """Scan dependencies for known vulnerabilities (alias for: kctl-api deps audit)."""
    _actx: AppContext = ctx.obj

    # Delegate to deps audit
    from kctl_api.commands.deps import audit as deps_audit

    deps_audit(ctx)
