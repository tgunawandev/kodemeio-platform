"""Doctor diagnostic checks for kctl-rmm."""

from __future__ import annotations

from dataclasses import dataclass

import typer
from kctl_lib.doctor_base import CheckResult, DoctorCheck, run_doctor

from kctl_rmm.core.callbacks import AppContext
from kctl_rmm.core.config import get_service_config, resolve_active_profile_name


@dataclass
class APIConnectivityCheck:
    """Check that the configured Tactical RMM URL is set."""

    name: str = "API Connectivity"

    def run(self) -> CheckResult:
        profile = resolve_active_profile_name()
        cfg = get_service_config(profile)
        url = cfg.url or ""
        if not url:
            return CheckResult(
                name=self.name,
                status="fail",
                message="No URL configured",
                fix_command="kctl-rmm config init",
            )
        return CheckResult(name=self.name, status="ok", message=f"URL: {url}")


@dataclass
class AuthCheck:
    """Check that the API key is configured."""

    name: str = "Authentication"

    def run(self) -> CheckResult:
        profile = resolve_active_profile_name()
        cfg = get_service_config(profile)
        api_key = cfg.api_key or ""
        if not api_key:
            return CheckResult(
                name=self.name,
                status="fail",
                message="No API key configured",
                fix_command="kctl-rmm config init",
            )
        masked = api_key[:4] + "****" + api_key[-4:] if len(api_key) > 8 else "****"
        return CheckResult(name=self.name, status="ok", message=f"API key configured ({masked})")


app = typer.Typer(help="Run diagnostic checks.", no_args_is_help=False)


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
