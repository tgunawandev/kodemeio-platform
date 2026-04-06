"""Diagnostic checks for kctl-opencloud."""

from __future__ import annotations

from dataclasses import dataclass

import typer

from kctl_opencloud.core.callbacks import AppContext


@dataclass
class CheckResult:
    name: str
    status: str  # ok, fail, warn
    message: str
    fix_command: str = ""


def _check_connectivity(ctx: AppContext) -> CheckResult:
    """Check API connectivity."""
    from kctl_opencloud.core.config import get_service_config, resolve_active_profile_name

    try:
        pname = resolve_active_profile_name(ctx.profile)
        cfg = get_service_config(pname)
        if not cfg.url:
            return CheckResult(
                "API Connectivity",
                "fail",
                "No URL configured",
                fix_command="kctl-opencloud config init",
            )
        # Now try connecting
        from kctl_opencloud.core.client import OpenCloudClient

        client = OpenCloudClient(base_url=cfg.url, credential=cfg.token)
        status = client.check_health()
        if status == 200:
            return CheckResult("API Connectivity", "ok", f"Connected to {cfg.url}")
        return CheckResult(
            "API Connectivity",
            "warn",
            f"HTTP {status} from {cfg.url}",
        )
    except Exception as e:
        return CheckResult(
            "API Connectivity",
            "fail",
            str(e),
            fix_command="kctl-opencloud config init",
        )


def _check_auth(ctx: AppContext) -> CheckResult:
    """Check authentication."""
    from kctl_opencloud.core.config import get_service_config, resolve_active_profile_name

    try:
        pname = resolve_active_profile_name(ctx.profile)
        cfg = get_service_config(pname)
        if not cfg.url or not cfg.token:
            return CheckResult(
                "Authentication",
                "fail",
                "No URL or token configured",
                fix_command="kctl-opencloud config init",
            )
        from kctl_opencloud.core.client import OpenCloudClient

        client = OpenCloudClient(base_url=cfg.url, credential=cfg.token)
        client.get("me")
        return CheckResult("Authentication", "ok", "Authenticated")
    except Exception:
        return CheckResult(
            "Authentication",
            "fail",
            "Authentication failed",
            fix_command="kctl-opencloud config set token <your-token>",
        )


app = typer.Typer(help="Diagnostic checks.")


@app.callback(invoke_without_command=True)
def doctor(ctx: typer.Context) -> None:
    """Run all diagnostic checks."""
    c: AppContext = ctx.obj
    out = c.output

    checks = [
        _check_connectivity(c),
        _check_auth(c),
    ]

    all_ok = True
    for check in checks:
        if check.status == "ok":
            out.success(f"{check.name}: {check.message}")
        elif check.status == "warn":
            out.warn(f"{check.name}: {check.message}")
        else:
            out.error(f"{check.name}: {check.message}")
            if check.fix_command:
                out.info(f"  Fix: {check.fix_command}")
            all_ok = False

    if not all_ok:
        raise typer.Exit(code=1)
