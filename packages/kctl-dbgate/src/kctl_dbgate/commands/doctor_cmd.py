"""Doctor diagnostic checks for kctl-dbgate."""

from __future__ import annotations

from dataclasses import dataclass

import typer
from kctl_lib.doctor_base import CheckResult, DoctorCheck, run_doctor

from kctl_dbgate.core.callbacks import AppContext

app = typer.Typer(help="Run diagnostic health checks.")


@dataclass
class URLConfigCheck:
    name: str = "URL configured"

    def run(self) -> CheckResult:
        try:
            from kctl_dbgate.core.config import get_service_config, resolve_active_profile_name

            profile = resolve_active_profile_name()
            cfg = get_service_config(profile)
            if not cfg.url:
                return CheckResult(
                    name=self.name,
                    status="fail",
                    message="No URL configured",
                    fix_command="kctl-dbgate config init",
                )
            return CheckResult(name=self.name, status="ok", message=f"URL: {cfg.url}")
        except Exception as e:
            return CheckResult(name=self.name, status="warn", message=str(e))


@dataclass
class AuthConfigCheck:
    name: str = "Credentials configured"

    def run(self) -> CheckResult:
        try:
            from kctl_dbgate.core.config import get_service_config, resolve_active_profile_name

            profile = resolve_active_profile_name()
            cfg = get_service_config(profile)
            if not cfg.password:
                return CheckResult(
                    name=self.name,
                    status="fail",
                    message="No password configured",
                    fix_command="kctl-dbgate config init",
                )
            return CheckResult(name=self.name, status="ok", message=f"Login: {cfg.login}")
        except Exception as e:
            return CheckResult(name=self.name, status="warn", message=str(e))


@dataclass
class ConnectivityCheck:
    name: str = "DBGate reachable"

    def run(self) -> CheckResult:
        try:
            from kctl_dbgate.core.callbacks import AppContext as _Ctx  # noqa: F401
            from kctl_dbgate.core.client import DBGateClient
            from kctl_dbgate.core.config import get_service_config, resolve_active_profile_name

            profile = resolve_active_profile_name()
            cfg = get_service_config(profile)
            if not cfg.url:
                return CheckResult(name=self.name, status="skip", message="No URL configured")
            client = DBGateClient(base_url=cfg.url, login=cfg.login, password=cfg.password)
            status = client.ping()
            client.close()
            if status < 400:
                return CheckResult(name=self.name, status="ok", message=f"HTTP {status}")
            return CheckResult(name=self.name, status="fail", message=f"HTTP {status}")
        except Exception as e:
            return CheckResult(name=self.name, status="fail", message=str(e))


@dataclass
class AuthCheck:
    name: str = "Login succeeds"

    def run(self) -> CheckResult:
        try:
            from kctl_dbgate.core.client import DBGateClient
            from kctl_dbgate.core.config import get_service_config, resolve_active_profile_name

            profile = resolve_active_profile_name()
            cfg = get_service_config(profile)
            if not cfg.url or not cfg.password:
                return CheckResult(name=self.name, status="skip", message="Missing URL or password")
            client = DBGateClient(base_url=cfg.url, login=cfg.login, password=cfg.password)
            client.login()
            client.close()
            return CheckResult(name=self.name, status="ok", message=f"Authenticated as {cfg.login}")
        except Exception as e:
            return CheckResult(name=self.name, status="fail", message=str(e))


@dataclass
class ConfigReadCheck:
    name: str = "Config readable"

    def run(self) -> CheckResult:
        try:
            from kctl_dbgate.core.client import DBGateClient
            from kctl_dbgate.core.config import get_service_config, resolve_active_profile_name

            profile = resolve_active_profile_name()
            cfg = get_service_config(profile)
            if not cfg.url or not cfg.password:
                return CheckResult(name=self.name, status="skip", message="Missing URL or password")
            client = DBGateClient(base_url=cfg.url, login=cfg.login, password=cfg.password)
            result = client.call("/config/get")
            client.close()
            if isinstance(result, dict) and result:
                version = result.get("version", "?")
                return CheckResult(name=self.name, status="ok", message=f"DBGate {version}")
            return CheckResult(name=self.name, status="warn", message="Empty /config/get response")
        except Exception as e:
            return CheckResult(name=self.name, status="fail", message=str(e))


@dataclass
class ServerSummaryCheck:
    name: str = "Server summary reachable"

    def run(self) -> CheckResult:
        try:
            from kctl_dbgate.core.client import DBGateClient
            from kctl_dbgate.core.config import get_service_config, resolve_active_profile_name

            profile = resolve_active_profile_name()
            cfg = get_service_config(profile)
            if not cfg.url or not cfg.password:
                return CheckResult(name=self.name, status="skip", message="Missing URL or password")
            client = DBGateClient(base_url=cfg.url, login=cfg.login, password=cfg.password)
            connections = client.list_connections()
            if not connections:
                client.close()
                return CheckResult(name=self.name, status="skip", message="No connections configured")
            first_id = connections[0].get("_id", "")
            if not first_id:
                client.close()
                return CheckResult(name=self.name, status="warn", message="Connection has no ID")
            result = client.call("/server-connections/server-summary", {"conid": first_id})
            client.close()
            if result is not None:
                return CheckResult(name=self.name, status="ok", message=f"Summary OK ({first_id})")
            return CheckResult(name=self.name, status="warn", message="Empty summary response")
        except Exception as e:
            return CheckResult(name=self.name, status="warn", message=str(e))


@app.callback(invoke_without_command=True)
def doctor(ctx: typer.Context) -> None:
    """Run all diagnostic checks."""
    actx: AppContext = ctx.obj
    checks: list[DoctorCheck] = [
        URLConfigCheck(),
        AuthConfigCheck(),
        ConnectivityCheck(),
        AuthCheck(),
        ConfigReadCheck(),
        ServerSummaryCheck(),
    ]
    run_doctor(checks, actx.output)  # type: ignore[arg-type]
