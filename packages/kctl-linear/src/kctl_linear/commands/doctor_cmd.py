"""Doctor diagnostic checks for kctl-linear."""

from __future__ import annotations

from dataclasses import dataclass

import typer

from kctl_lib.doctor_base import CheckResult, DoctorCheck, run_doctor

from kctl_linear.core.callbacks import AppContext


@dataclass
class ConfigCheck:
    """Check that configuration is present."""

    name: str = "Configuration"
    profile: str | None = None

    def run(self) -> CheckResult:
        try:
            from kctl_linear.core.config import get_service_config, resolve_active_profile_name

            profile = resolve_active_profile_name(self.profile)
            cfg = get_service_config(profile)
            if not cfg.api_key:
                return CheckResult(
                    name=self.name,
                    status="fail",
                    message="No API key configured",
                    fix_command="kctl-linear config init",
                )
            return CheckResult(name=self.name, status="ok", message=f"Profile: {profile}")
        except Exception as e:
            return CheckResult(
                name=self.name,
                status="fail",
                message=str(e),
                fix_command="kctl-linear config init",
            )


app = typer.Typer(help="Run diagnostic checks.", invoke_without_command=True)


@app.callback(invoke_without_command=True)
def doctor(ctx: typer.Context) -> None:
    """Run all diagnostic checks."""
    if ctx.invoked_subcommand is not None:
        return
    actx: AppContext = ctx.obj
    out = actx.output

    checks: list[DoctorCheck] = [ConfigCheck(profile=actx.profile)]
    all_passed = run_doctor(checks, out)  # type: ignore[arg-type]
    if not all_passed:
        raise typer.Exit(code=1)
