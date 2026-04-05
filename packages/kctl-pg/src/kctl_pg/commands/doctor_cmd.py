"""Doctor diagnostic checks for kctl-pg."""

from __future__ import annotations

from dataclasses import dataclass

import typer

from kctl_lib.doctor_base import CheckResult, DoctorCheck, run_doctor

from kctl_pg.core.callbacks import AppContext


@dataclass
class SSHCheck:
    """Check that SSH host is configured."""

    name: str = "SSH Configuration"

    def run(self) -> CheckResult:
        try:
            from kctl_pg.core.config import get_service_config, resolve_active_profile_name

            profile = resolve_active_profile_name()
            cfg = get_service_config(profile)
            host = cfg.ssh_host or cfg.host or ""
            if not host:
                return CheckResult(
                    name=self.name,
                    status="fail",
                    message="No SSH host configured",
                    fix_command="kctl-pg config init",
                )
            return CheckResult(name=self.name, status="ok", message=f"Host: {host}")
        except Exception as e:
            return CheckResult(
                name=self.name,
                status="fail",
                message=str(e),
                fix_command="kctl-pg config init",
            )


@dataclass
class ConfigCheck:
    """Check that configuration is present."""

    name: str = "Configuration"

    def run(self) -> CheckResult:
        try:
            from kctl_pg.core.config import get_service_config, resolve_active_profile_name

            profile = resolve_active_profile_name()
            cfg = get_service_config(profile)
            if not cfg.host:
                return CheckResult(
                    name=self.name,
                    status="warn",
                    message="No database host configured",
                    fix_command="kctl-pg config init",
                )
            return CheckResult(name=self.name, status="ok", message=f"Profile: {profile}")
        except Exception as e:
            return CheckResult(
                name=self.name,
                status="fail",
                message=str(e),
                fix_command="kctl-pg config init",
            )


app = typer.Typer(help="Run diagnostic checks.", invoke_without_command=True)


@app.callback(invoke_without_command=True)
def doctor(ctx: typer.Context) -> None:
    """Run all diagnostic checks."""
    if ctx.invoked_subcommand is not None:
        return
    actx: AppContext = ctx.obj
    out = actx.output

    checks: list[DoctorCheck] = [ConfigCheck(), SSHCheck()]
    all_passed = run_doctor(checks, out)  # type: ignore[arg-type]
    if not all_passed:
        raise typer.Exit(code=1)
