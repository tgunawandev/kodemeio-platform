"""Doctor diagnostic checks for kctl-cf."""

from __future__ import annotations

from dataclasses import dataclass

import typer

from kctl_cf.core.callbacks import AppContext
from kctl_lib.doctor_base import CheckResult, DoctorCheck, run_doctor


@dataclass
class APIConnectivityCheck:
    """Check that the configured API endpoint is reachable."""

    name: str = "API Connectivity"

    def run(self) -> CheckResult:
        try:
            from kctl_cf.core.config import get_service_config, resolve_active_profile_name

            profile = resolve_active_profile_name()
            cfg = get_service_config(profile)
            account_id = cfg.account_id or ""
            if not account_id:
                return CheckResult(
                    name=self.name,
                    status="fail",
                    message="No account_id configured",
                    fix_command="kctl-cf config init",
                )
            return CheckResult(name=self.name, status="ok", message=f"Account ID: {account_id}")
        except Exception as e:
            return CheckResult(name=self.name, status="warn", message=str(e))


@dataclass
class AuthCheck:
    """Check that authentication credentials are configured."""

    name: str = "Authentication"

    def run(self) -> CheckResult:
        try:
            from kctl_cf.core.config import get_service_config, resolve_active_profile_name

            profile = resolve_active_profile_name()
            cfg = get_service_config(profile)
            token = cfg.api_token or ""
            if not token:
                return CheckResult(
                    name=self.name,
                    status="fail",
                    message="No API token configured",
                    fix_command="kctl-cf config init",
                )
            masked = token[:4] + "****" + token[-4:] if len(token) > 8 else "****"
            return CheckResult(name=self.name, status="ok", message=f"API token configured ({masked})")
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
