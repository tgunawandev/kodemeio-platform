"""Type-aware pre-deploy validation and post-deploy smoke tests.

Reads ``manifest.type`` to select domain-specific checks for
``react-pwa``, ``odoo``, ``nextjs``, ``fastapi``, and ``infrastructure``
deploy types.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import httpx

from kctl_dokploy.core.manifest import DeployManifest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KNOWN_TYPES: frozenset[str] = frozenset({"react-pwa", "odoo", "nextjs", "infrastructure", "fastapi"})

FQDN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")

VALID_APPS = frozenset(
    {
        "sfa",
        "lfa",
        "shop",
        "wms",
        "bia",
        "hrm",
        "mrp",
        "eam",
        "asset",
        "dms",
        "tpm",
        "recruitment",
        "saas",
    }
)

VALID_AUTH_MODES = frozenset({"native", "oidc", "development"})

# All 13 apps that require JWT secrets in Odoo config parameters
ODOO_JWT_APPS = (
    "sfa",
    "lfa",
    "shop",
    "wms",
    "bia",
    "hrm",
    "mrp",
    "eam",
    "asset",
    "dms",
    "tpm",
    "recruitment",
    "saas",
)

# API URL must match /{app}/api at the end
_API_URL_SUFFIX_RE = re.compile(r"/(" + "|".join(VALID_APPS) + r")/api$")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    """Result of a single post-deploy smoke check."""

    name: str
    status: str  # pass, warn, fail, skip
    detail: str = ""


# ---------------------------------------------------------------------------
# DeployValidator
# ---------------------------------------------------------------------------


class DeployValidator:
    """Type-aware deploy validator.

    Args:
        manifest: A resolved :class:`DeployManifest`.
    """

    def __init__(self, manifest: DeployManifest) -> None:
        self.manifest = manifest
        self.deploy_type = self._detect_type()

    # -- Type detection -----------------------------------------------------

    def _detect_type(self) -> str:
        """Return the manifest type if known, otherwise ``"unknown"``."""
        mtype = self.manifest.type
        return mtype if mtype in KNOWN_TYPES else "unknown"

    # -- Pre-validate -------------------------------------------------------

    def pre_validate(self) -> tuple[list[str], list[str]]:
        """Run pre-deploy validation checks.

        Returns:
            A ``(warnings, errors)`` tuple of human-readable messages.
        """
        warnings: list[str] = []
        errors: list[str] = []

        self._check_common(warnings, errors)

        if self.deploy_type == "react-pwa":
            self._check_react_pwa(warnings, errors)
        elif self.deploy_type == "odoo":
            self._check_odoo(warnings, errors)

        return warnings, errors

    def _check_common(self, warnings: list[str], errors: list[str]) -> None:
        """Checks that apply to all deploy types."""
        domain = self.manifest.domain

        if domain.host and not FQDN_RE.match(domain.host):
            errors.append(f"domain.host '{domain.host}' is not a valid FQDN")

        if domain.host and not domain.service:
            errors.append("domain.service must not be empty when domain.host is set")

    def _check_react_pwa(self, warnings: list[str], errors: list[str]) -> None:
        """React PWA-specific pre-deploy checks."""
        env = {**self.manifest.env_defaults, **self.manifest.env_overrides}

        # Check VITE_*_API_BASE_URL vars
        for key, value in env.items():
            if key.startswith("VITE_") and key.endswith("_API_BASE_URL"):
                if not _API_URL_SUFFIX_RE.search(value):
                    errors.append(
                        f"{key}='{value}' must end with /{{app}}/api "
                        f"where app is one of: {', '.join(sorted(VALID_APPS))}"
                    )

        # Check VITE_AUTH_MODE
        auth_mode = env.get("VITE_AUTH_MODE")
        if auth_mode is None:
            warnings.append("VITE_AUTH_MODE is not set")
        elif auth_mode not in VALID_AUTH_MODES:
            errors.append(
                f"VITE_AUTH_MODE='{auth_mode}' is invalid; must be one of: {', '.join(sorted(VALID_AUTH_MODES))}"
            )

        # If OIDC, check authority
        if auth_mode == "oidc" and not env.get("VITE_OIDC_AUTHORITY"):
            warnings.append("VITE_OIDC_AUTHORITY must be set when VITE_AUTH_MODE=oidc")

    def _check_odoo(self, warnings: list[str], errors: list[str]) -> None:
        """Odoo-specific pre-deploy checks."""
        env = {**self.manifest.env_defaults, **self.manifest.env_overrides}

        db_name = env.get("PGDATABASE") or env.get("ODOO_DB_NAME") or ""
        if len(db_name) > 63:
            errors.append(f"Database name length ({len(db_name)}) exceeds PostgreSQL limit of 63 characters")

        if not env.get("ODOO_ADMIN_PASSWD"):
            warnings.append("ODOO_ADMIN_PASSWD is not set")

    # -- Post-verify --------------------------------------------------------

    def post_verify(self, timeout: float = 10.0) -> list[CheckResult]:
        """Run post-deploy smoke tests.

        Args:
            timeout: HTTP request timeout in seconds.

        Returns:
            A list of :class:`CheckResult` entries.
        """
        results: list[CheckResult] = []

        if self.deploy_type == "react-pwa":
            self._verify_react_pwa(results, timeout)
        elif self.deploy_type == "odoo":
            self._verify_odoo(results, timeout)
        elif self.deploy_type == "nextjs":
            self._verify_nextjs(results, timeout)

        return results

    def _verify_react_pwa(self, results: list[CheckResult], timeout: float) -> None:
        """React PWA post-deploy: CORS preflight and login endpoint."""
        env = {**self.manifest.env_defaults, **self.manifest.env_overrides}
        domain_host = self.manifest.domain.host

        # Find an API URL to probe
        api_url: str | None = None
        for key, value in env.items():
            if key.startswith("VITE_") and key.endswith("_API_BASE_URL"):
                api_url = value
                break

        if not api_url:
            results.append(
                CheckResult(
                    name="cors_preflight",
                    status="skip",
                    detail="No VITE_*_API_BASE_URL found",
                )
            )
            results.append(
                CheckResult(
                    name="login_endpoint",
                    status="skip",
                    detail="No VITE_*_API_BASE_URL found",
                )
            )
            return

        # CORS preflight
        try:
            resp = httpx.options(
                f"{api_url}/auth/login",
                headers={"Origin": f"https://{domain_host}"},
                timeout=timeout,
            )
            has_cors = "access-control-allow-origin" in {k.lower() for k in resp.headers.keys()}
            if resp.status_code == 200 and has_cors:
                results.append(
                    CheckResult(
                        name="cors_preflight",
                        status="pass",
                        detail="200 with CORS headers",
                    )
                )
            elif resp.status_code == 405:
                results.append(
                    CheckResult(
                        name="cors_preflight",
                        status="warn",
                        detail="405 Method Not Allowed",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        name="cors_preflight",
                        status="fail",
                        detail=f"HTTP {resp.status_code}, CORS={has_cors}",
                    )
                )
        except httpx.HTTPError as exc:
            results.append(
                CheckResult(
                    name="cors_preflight",
                    status="fail",
                    detail=str(exc),
                )
            )

        # Login endpoint probe
        try:
            resp = httpx.post(
                f"{api_url}/auth/login",
                json={"username": "probe", "password": "probe"},
                timeout=timeout,
            )
            if resp.status_code == 404:
                results.append(
                    CheckResult(
                        name="login_endpoint",
                        status="warn",
                        detail="404 Not Found",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        name="login_endpoint",
                        status="pass",
                        detail=f"HTTP {resp.status_code}",
                    )
                )
        except httpx.HTTPError as exc:
            results.append(
                CheckResult(
                    name="login_endpoint",
                    status="fail",
                    detail=str(exc),
                )
            )

    def _verify_odoo(self, results: list[CheckResult], timeout: float) -> None:
        """Odoo post-deploy: JWT secrets and stuck modules."""
        env = {**self.manifest.env_defaults, **self.manifest.env_overrides}
        domain_host = self.manifest.domain.host
        base_url = f"https://{domain_host}"

        odoo_db = env.get("PGDATABASE") or env.get("ODOO_DB_NAME") or ""
        odoo_password = env.get("ODOO_ADMIN_PASSWD") or ""

        # JWT secrets check
        try:
            missing_or_weak: list[str] = []
            for app in ODOO_JWT_APPS:
                payload = {
                    "jsonrpc": "2.0",
                    "method": "call",
                    "params": {
                        "model": "ir.config_parameter",
                        "method": "get_param",
                        "args": [f"{app}.jwt_secret"],
                        "kwargs": {},
                    },
                }
                resp = httpx.post(
                    f"{base_url}/jsonrpc",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    cookies={"session_id": "probe"},
                    timeout=timeout,
                )
                data = resp.json()
                secret = data.get("result")
                if not secret or (isinstance(secret, str) and len(secret) < 32):
                    missing_or_weak.append(app)

            if missing_or_weak:
                results.append(
                    CheckResult(
                        name="jwt_secrets",
                        status="warn",
                        detail=f"Missing/weak JWT secrets: {', '.join(missing_or_weak)}",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        name="jwt_secrets",
                        status="pass",
                        detail="All 13 JWT secrets present and strong",
                    )
                )
        except httpx.HTTPError as exc:
            results.append(
                CheckResult(
                    name="jwt_secrets",
                    status="fail",
                    detail=str(exc),
                )
            )

        # Stuck modules check
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "model": "ir.module.module",
                    "method": "search_count",
                    "args": [[["state", "in", ["to upgrade", "to install", "to remove"]]]],
                    "kwargs": {},
                },
            }
            resp = httpx.post(
                f"{base_url}/jsonrpc",
                json=payload,
                headers={"Content-Type": "application/json"},
                cookies={"session_id": "probe"},
                timeout=timeout,
            )
            data = resp.json()
            count = data.get("result", 0)
            if count > 0:
                results.append(
                    CheckResult(
                        name="stuck_modules",
                        status="warn",
                        detail=f"{count} module(s) in pending state",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        name="stuck_modules",
                        status="pass",
                        detail="No stuck modules",
                    )
                )
        except httpx.HTTPError as exc:
            results.append(
                CheckResult(
                    name="stuck_modules",
                    status="fail",
                    detail=str(exc),
                )
            )

    def _verify_nextjs(self, results: list[CheckResult], timeout: float) -> None:
        """Next.js post-deploy: root path check."""
        domain_host = self.manifest.domain.host
        url = f"https://{domain_host}/"

        try:
            resp = httpx.get(
                url,
                follow_redirects=False,
                timeout=timeout,
            )
            if resp.status_code == 404:
                results.append(
                    CheckResult(
                        name="root_path",
                        status="warn",
                        detail="404 Not Found",
                    )
                )
            elif 200 <= resp.status_code < 400:
                results.append(
                    CheckResult(
                        name="root_path",
                        status="pass",
                        detail=f"HTTP {resp.status_code}",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        name="root_path",
                        status="fail",
                        detail=f"HTTP {resp.status_code}",
                    )
                )
        except httpx.HTTPError as exc:
            results.append(
                CheckResult(
                    name="root_path",
                    status="fail",
                    detail=str(exc),
                )
            )
