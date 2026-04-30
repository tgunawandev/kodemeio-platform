"""kctl-accurate doctor — config + connectivity diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import typer
from kctl_lib.doctor_base import CheckResult, DoctorCheck, run_doctor

from kctl_accurate.core.callbacks import AppContext
from kctl_accurate.core.client import AccurateClientWrapper
from kctl_accurate.core.config import (
    get_service_config,
    resolve_active_profile_name,
    resolve_connection,
)


@dataclass
class ConfigCheck:
    profile: str | None = None
    name: str = "Configuration"

    def run(self) -> CheckResult:
        try:
            profile = resolve_active_profile_name(self.profile)
            cfg = get_service_config(profile)
            missing = [k for k in ("api_token", "signature_secret") if not getattr(cfg, k)]
            if not cfg.db_id:
                missing.append("db_id")
            if missing:
                return CheckResult(
                    name=self.name,
                    status="fail",
                    message=f"Missing fields in profile '{profile}': {', '.join(missing)}",
                    fix_command="kctl-accurate config init",
                )
            return CheckResult(
                name=self.name,
                status="ok",
                message=f"Profile: {profile} (db_id={cfg.db_id})",
            )
        except Exception as exc:
            return CheckResult(
                name=self.name,
                status="fail",
                message=str(exc),
                fix_command="kctl-accurate config init",
            )


@dataclass
class TokenCheck:
    profile: str | None = None
    name: str = "Token Info"

    def run(self) -> CheckResult:
        try:
            cfg = resolve_connection(profile_name=self.profile)
            client = AccurateClientWrapper(cfg)
            info = client.token_info()
            d = (info.get("d") or {}).get("database") or {}
            return CheckResult(
                name=self.name,
                status="ok",
                message=f"User OK; default db_id={d.get('id')} alias={d.get('alias')}",
            )
        except Exception as exc:
            return CheckResult(
                name=self.name,
                status="fail",
                message=str(exc),
                fix_command="kctl-accurate auth token-info",
            )


@dataclass
class DbListCheck:
    profile: str | None = None
    name: str = "DB List"

    def run(self) -> CheckResult:
        try:
            cfg = resolve_connection(profile_name=self.profile)
            client = AccurateClientWrapper(cfg)
            companies = client.db_list()
            ids = [c.get("id") for c in companies]
            if cfg.db_id not in ids:
                return CheckResult(
                    name=self.name,
                    status="warn",
                    message=(
                        f"Configured db_id={cfg.db_id} not in account's company list "
                        f"(visible: {ids}). Open the right one with: "
                        f"kctl-accurate db open <id>"
                    ),
                )
            return CheckResult(
                name=self.name,
                status="ok",
                message=f"db_id={cfg.db_id} present in account ({len(companies)} companies)",
            )
        except Exception as exc:
            return CheckResult(
                name=self.name,
                status="fail",
                message=str(exc),
            )


@dataclass
class _CachedCheck:
    """Wraps a pre-run CheckResult so run_doctor doesn't re-execute the check."""

    _result: CheckResult

    @property
    def name(self) -> str:
        return cast(str, self._result.name)

    def run(self) -> CheckResult:
        return self._result


app = typer.Typer(help="Diagnose config + connectivity.", invoke_without_command=True)


@app.callback(invoke_without_command=True)
def doctor(ctx: typer.Context) -> None:
    """Run all diagnostic checks. Exits 0 on all-ok, 1 otherwise."""
    if ctx.invoked_subcommand is not None:
        return
    actx: AppContext = ctx.obj
    profile = actx.profile
    checks: list[DoctorCheck] = [
        ConfigCheck(profile=profile),
        TokenCheck(profile=profile),
        DbListCheck(profile=profile),
    ]
    # Run checks once and cache results so we can inspect statuses without
    # making duplicate API calls.
    results = [c.run() for c in checks]
    cached = [_CachedCheck(r) for r in results]
    ok = run_doctor(cached, actx.output)
    # kctl-* convention: warn also exits non-zero
    has_warn = any(r.status == "warn" for r in results)
    if not ok or has_warn:
        raise typer.Exit(1)
