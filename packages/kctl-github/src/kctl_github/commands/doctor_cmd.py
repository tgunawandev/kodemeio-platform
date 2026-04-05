"""Doctor diagnostic checks for kctl-github."""

from __future__ import annotations

from dataclasses import dataclass

import typer

from kctl_github.core.callbacks import AppContext
from kctl_lib.doctor_base import CheckResult, DoctorCheck, run_doctor


@dataclass
class APIConnectivityCheck:
    """Check that the configured GitHub organization is set."""

    name: str = "API Connectivity"

    def run(self) -> CheckResult:
        try:
            from kctl_github.core.config import get_service_config, resolve_active_profile_name

            profile = resolve_active_profile_name()
            cfg = get_service_config(profile)
            org = cfg.organization or ""
            if not org:
                return CheckResult(
                    name=self.name,
                    status="fail",
                    message="No organization configured",
                    fix_command="kctl-github config init",
                )
            return CheckResult(name=self.name, status="ok", message=f"Organization: {org}")
        except Exception as e:
            return CheckResult(name=self.name, status="warn", message=str(e))


@dataclass
class AuthCheck:
    """Check that authentication credentials are configured."""

    name: str = "Authentication"

    def run(self) -> CheckResult:
        try:
            from kctl_github.core.config import get_service_config, resolve_active_profile_name

            profile = resolve_active_profile_name()
            cfg = get_service_config(profile)
            token = cfg.token or ""
            if not token:
                return CheckResult(
                    name=self.name,
                    status="fail",
                    message="No GitHub token configured",
                    fix_command="kctl-github config init",
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
