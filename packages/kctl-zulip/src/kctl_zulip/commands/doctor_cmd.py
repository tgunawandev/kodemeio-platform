"""Doctor diagnostic checks for kctl-zulip."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import typer

from kctl_zulip.core.callbacks import AppContext
from kctl_lib.doctor_base import CheckResult, DoctorCheck, run_doctor


@dataclass
class ConfigCheck:
    """Check that the active profile has a URL configured."""

    name: str = "Configuration"

    def run(self) -> CheckResult:
        try:
            from kctl_zulip.core.config import get_service_config, resolve_active_profile_name

            profile = resolve_active_profile_name()
            cfg = get_service_config(profile)
            url = cfg.url or ""
            if not url:
                return CheckResult(
                    name=self.name,
                    status="fail",
                    message="No URL configured",
                    fix_command="kctl-zulip config init",
                )
            return CheckResult(name=self.name, status="ok", message=f"Profile '{profile}' -> {url}")
        except Exception as e:
            return CheckResult(name=self.name, status="warn", message=str(e))


@dataclass
class APIConnectivityCheck:
    """Check that the Zulip API endpoint is reachable (no auth needed)."""

    name: str = "API Connectivity"

    def run(self) -> CheckResult:
        try:
            from kctl_zulip.core.config import get_service_config, resolve_active_profile_name

            profile = resolve_active_profile_name()
            cfg = get_service_config(profile)
            url = cfg.url or ""
            if not url:
                return CheckResult(
                    name=self.name,
                    status="fail",
                    message="No URL configured",
                    fix_command="kctl-zulip config init",
                )
            resp = httpx.get(f"{url.rstrip('/')}/api/v1/server_settings", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                version = data.get("zulip_version", "unknown")
                return CheckResult(name=self.name, status="ok", message=f"Zulip {version} at {url}")
            return CheckResult(
                name=self.name,
                status="fail",
                message=f"HTTP {resp.status_code} from {url}",
            )
        except httpx.HTTPError as e:
            return CheckResult(name=self.name, status="fail", message=f"Connection failed: {e}")
        except Exception as e:
            return CheckResult(name=self.name, status="warn", message=str(e))


@dataclass
class AuthCheck:
    """Check authentication by hitting /api/v1/users/me."""

    name: str = "Authentication"

    def run(self) -> CheckResult:
        try:
            from kctl_zulip.core.config import resolve_active_profile_name, resolve_connection

            profile = resolve_active_profile_name()
            url, email, api_key = resolve_connection(profile_name=profile)
            if not url or not email or not api_key:
                return CheckResult(
                    name=self.name,
                    status="fail",
                    message="Missing url, email, or api_key",
                    fix_command="kctl-zulip config init",
                )

            from kctl_zulip.core.client import ZulipClient

            client = ZulipClient(base_url=url, email=email, api_key=api_key)
            me = client.get("users/me")
            client.close()
            user_email = me.get("email", "unknown")
            role = me.get("role", "unknown")
            role_map = {100: "owner", 200: "admin", 300: "moderator", 400: "member", 600: "guest"}
            role_name = role_map.get(role, str(role))
            return CheckResult(name=self.name, status="ok", message=f"{user_email} (role: {role_name})")
        except Exception as e:
            return CheckResult(name=self.name, status="fail", message=str(e))


app = typer.Typer(help="Run diagnostic checks.", no_args_is_help=False, invoke_without_command=True)


@app.callback(invoke_without_command=True)
def doctor(ctx: typer.Context) -> None:
    """Run all diagnostic checks."""
    if ctx.invoked_subcommand is not None:
        return
    actx: AppContext = ctx.obj
    out = actx.output

    checks: list[DoctorCheck] = [
        ConfigCheck(),
        APIConnectivityCheck(),
        AuthCheck(),
    ]

    all_passed = run_doctor(checks, out)  # type: ignore[arg-type]
    if not all_passed:
        raise typer.Exit(code=1)
