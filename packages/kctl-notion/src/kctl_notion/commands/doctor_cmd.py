"""Doctor diagnostic checks for kctl-notion."""

from __future__ import annotations

from dataclasses import dataclass

import typer

from kctl_lib.doctor_base import CheckResult, DoctorCheck, run_doctor

from kctl_notion.core.callbacks import AppContext


@dataclass
class ConfigCheck:
    """Check that configuration is present."""

    name: str = "Configuration"

    def run(self) -> CheckResult:
        try:
            from kctl_notion.core.config import get_service_config, resolve_active_profile_name

            profile = resolve_active_profile_name()
            cfg = get_service_config(profile)
            if not cfg.token:
                return CheckResult(
                    name=self.name,
                    status="fail",
                    message="No integration token configured",
                    fix_command="kctl-notion config init",
                )
            return CheckResult(name=self.name, status="ok", message=f"Profile: {profile}")
        except Exception as e:
            return CheckResult(
                name=self.name,
                status="fail",
                message=str(e),
                fix_command="kctl-notion config init",
            )


app = typer.Typer(help="Run diagnostic checks.", invoke_without_command=True)


@app.callback(invoke_without_command=True)
def doctor(ctx: typer.Context) -> None:
    """Run all diagnostic checks."""
    if ctx.invoked_subcommand is not None:
        return
    actx: AppContext = ctx.obj
    out = actx.output

    checks: list[DoctorCheck] = [ConfigCheck()]
    all_passed = run_doctor(checks, out)  # type: ignore[arg-type]
    if not all_passed:
        raise typer.Exit(code=1)
