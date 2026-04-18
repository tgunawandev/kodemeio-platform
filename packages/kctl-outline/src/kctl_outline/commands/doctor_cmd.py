"""Doctor diagnostic checks for kctl-outline."""

from __future__ import annotations

from dataclasses import dataclass

import typer
from kctl_lib.doctor_base import CheckResult, DoctorCheck, run_doctor

from kctl_outline.core.callbacks import AppContext


@dataclass
class APIConnectivityCheck:
    """Check that the configured Outline URL is reachable."""

    name: str = "API Connectivity"

    def run(self) -> CheckResult:
        try:
            from kctl_outline.core.config import get_service_config, resolve_active_profile_name

            profile = resolve_active_profile_name()
            cfg = get_service_config(profile)
            url = cfg.url or ""
            if not url:
                return CheckResult(
                    name=self.name,
                    status="fail",
                    message="No URL configured",
                    fix_command="kctl-outline config init",
                )
            return CheckResult(name=self.name, status="ok", message=f"URL: {url}")
        except Exception as e:
            return CheckResult(name=self.name, status="warn", message=str(e))


@dataclass
class AuthCheck:
    """Check that the API token is configured."""

    name: str = "Authentication"

    def run(self) -> CheckResult:
        try:
            from kctl_outline.core.config import get_service_config, resolve_active_profile_name

            profile = resolve_active_profile_name()
            cfg = get_service_config(profile)
            token = cfg.token or ""
            if not token:
                return CheckResult(
                    name=self.name,
                    status="fail",
                    message="No API token configured",
                    fix_command="kctl-outline config init",
                )
            masked = token[:4] + "****" + token[-4:] if len(token) > 8 else "****"
            return CheckResult(name=self.name, status="ok", message=f"Token configured ({masked})")
        except Exception as e:
            return CheckResult(name=self.name, status="warn", message=str(e))


app = typer.Typer(help="Run diagnostic checks.", no_args_is_help=False, invoke_without_command=True)


@app.callback(invoke_without_command=True)
def doctor(ctx: typer.Context) -> None:
    """Run all diagnostic checks."""
    if ctx.invoked_subcommand is not None:
        return
    actx: AppContext = ctx.obj
    out = actx.output

    checks: list[DoctorCheck] = [
        APIConnectivityCheck(),
        AuthCheck(),
    ]
    all_passed = run_doctor(checks, out)  # type: ignore[arg-type]
    if not all_passed:
        raise typer.Exit(code=1)
