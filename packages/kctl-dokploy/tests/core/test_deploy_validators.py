"""Tests for deploy_validators — type-aware pre/post deploy checks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from kctl_dokploy.core.deploy_validators import (
    KNOWN_TYPES,
    DeployValidator,
)
from kctl_dokploy.core.manifest import (
    DeployManifest,
    DomainConfig,
    InstanceConfig,
    SourceConfig,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manifest(**kwargs) -> DeployManifest:
    """Return a minimal DeployManifest with sensible defaults."""
    defaults = dict(
        server="srv-001",
        project="my-project",
        type="compose",
        source=SourceConfig(owner="acme", repo="app", branch="main"),
        instance=InstanceConfig(name="app-prod"),
        domain=DomainConfig(host="app.example.com", port=80, service="web"),
    )
    defaults.update(kwargs)
    return DeployManifest(**defaults)


def _mock_response(
    status_code: int = 200,
    json_data: dict | None = None,
    headers: dict[str, str] | None = None,
) -> MagicMock:
    """Build a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.headers = httpx.Headers(headers or {})
    return resp


# ---------------------------------------------------------------------------
# Type detection
# ---------------------------------------------------------------------------


class TestTypeDetection:
    @pytest.mark.parametrize("mtype", sorted(KNOWN_TYPES))
    def test_known_types(self, mtype: str) -> None:
        manifest = _make_manifest(type=mtype)
        v = DeployValidator(manifest)
        assert v.deploy_type == mtype

    def test_unknown_type_fallback(self) -> None:
        manifest = _make_manifest(type="custom-thing")
        v = DeployValidator(manifest)
        assert v.deploy_type == "unknown"

    def test_default_compose_is_unknown(self) -> None:
        manifest = _make_manifest(type="compose")
        v = DeployValidator(manifest)
        assert v.deploy_type == "unknown"


# ---------------------------------------------------------------------------
# Pre-validate — common checks
# ---------------------------------------------------------------------------


class TestPreValidateCommon:
    def test_valid_domain(self) -> None:
        manifest = _make_manifest(
            type="fastapi",
            domain=DomainConfig(host="api.example.com", service="web"),
        )
        warnings, errors = DeployValidator(manifest).pre_validate()
        assert not errors

    def test_invalid_domain_fqdn(self) -> None:
        manifest = _make_manifest(
            type="fastapi",
            domain=DomainConfig(host="NOT_VALID!", service="web"),
        )
        warnings, errors = DeployValidator(manifest).pre_validate()
        assert any("not a valid FQDN" in e for e in errors)

    def test_empty_service_with_host(self) -> None:
        manifest = _make_manifest(
            type="fastapi",
            domain=DomainConfig(host="api.example.com", service=""),
        )
        warnings, errors = DeployValidator(manifest).pre_validate()
        assert any("domain.service must not be empty" in e for e in errors)

    def test_no_domain_no_errors(self) -> None:
        """When domain.host is empty, domain checks are skipped."""
        manifest = _make_manifest(
            type="fastapi",
            domain=DomainConfig(host="", service=""),
        )
        warnings, errors = DeployValidator(manifest).pre_validate()
        assert not errors


# ---------------------------------------------------------------------------
# Pre-validate — react-pwa
# ---------------------------------------------------------------------------


class TestPreValidateReactPwa:
    def test_good_api_url(self) -> None:
        manifest = _make_manifest(
            type="react-pwa",
            env_overrides={
                "VITE_SFA_API_BASE_URL": "https://api.example.com/sfa/api",
                "VITE_AUTH_MODE": "native",
            },
        )
        warnings, errors = DeployValidator(manifest).pre_validate()
        assert not errors

    def test_bad_api_url(self) -> None:
        manifest = _make_manifest(
            type="react-pwa",
            env_overrides={
                "VITE_SFA_API_BASE_URL": "https://api.example.com/v1/bad",
                "VITE_AUTH_MODE": "native",
            },
        )
        warnings, errors = DeployValidator(manifest).pre_validate()
        assert any("must end with /{app}/api" in e for e in errors)

    def test_missing_auth_mode(self) -> None:
        manifest = _make_manifest(
            type="react-pwa",
            env_overrides={},
        )
        warnings, errors = DeployValidator(manifest).pre_validate()
        assert any("VITE_AUTH_MODE is not set" in w for w in warnings)

    def test_invalid_auth_mode(self) -> None:
        manifest = _make_manifest(
            type="react-pwa",
            env_overrides={"VITE_AUTH_MODE": "saml"},
        )
        warnings, errors = DeployValidator(manifest).pre_validate()
        assert any("VITE_AUTH_MODE='saml' is invalid" in e for e in errors)

    def test_oidc_missing_authority(self) -> None:
        manifest = _make_manifest(
            type="react-pwa",
            env_overrides={"VITE_AUTH_MODE": "oidc"},
        )
        warnings, errors = DeployValidator(manifest).pre_validate()
        assert any("VITE_OIDC_AUTHORITY must be set" in w for w in warnings)

    def test_oidc_with_authority_no_warning(self) -> None:
        manifest = _make_manifest(
            type="react-pwa",
            env_overrides={
                "VITE_AUTH_MODE": "oidc",
                "VITE_OIDC_AUTHORITY": "https://auth.example.com",
            },
        )
        warnings, errors = DeployValidator(manifest).pre_validate()
        assert not any("VITE_OIDC_AUTHORITY" in w for w in warnings)


# ---------------------------------------------------------------------------
# Pre-validate — odoo
# ---------------------------------------------------------------------------


class TestPreValidateOdoo:
    def test_db_name_too_long(self) -> None:
        manifest = _make_manifest(
            type="odoo",
            env_overrides={"PGDATABASE": "x" * 64},
        )
        warnings, errors = DeployValidator(manifest).pre_validate()
        assert any("exceeds PostgreSQL limit" in e for e in errors)

    def test_missing_admin_passwd(self) -> None:
        manifest = _make_manifest(
            type="odoo",
            env_overrides={"PGDATABASE": "mydb"},
        )
        warnings, errors = DeployValidator(manifest).pre_validate()
        assert any("ODOO_ADMIN_PASSWD is not set" in w for w in warnings)

    def test_valid_odoo_config(self) -> None:
        manifest = _make_manifest(
            type="odoo",
            env_overrides={
                "PGDATABASE": "kodemeio_prod",
                "ODOO_ADMIN_PASSWD": "supersecret",
            },
        )
        warnings, errors = DeployValidator(manifest).pre_validate()
        assert not errors
        assert not any("ODOO_ADMIN_PASSWD" in w for w in warnings)

    def test_odoo_db_name_uses_fallback(self) -> None:
        """ODOO_DB_NAME is checked when PGDATABASE is absent."""
        manifest = _make_manifest(
            type="odoo",
            env_overrides={
                "ODOO_DB_NAME": "y" * 64,
                "ODOO_ADMIN_PASSWD": "s",
            },
        )
        warnings, errors = DeployValidator(manifest).pre_validate()
        assert any("exceeds PostgreSQL limit" in e for e in errors)

    def test_db_name_at_limit_passes(self) -> None:
        manifest = _make_manifest(
            type="odoo",
            env_overrides={
                "PGDATABASE": "a" * 63,
                "ODOO_ADMIN_PASSWD": "s",
            },
        )
        warnings, errors = DeployValidator(manifest).pre_validate()
        assert not any("exceeds" in e for e in errors)


# ---------------------------------------------------------------------------
# Post-verify — react-pwa (mocked HTTP)
# ---------------------------------------------------------------------------


class TestPostVerifyReactPwa:
    def test_cors_pass(self) -> None:
        manifest = _make_manifest(
            type="react-pwa",
            env_overrides={
                "VITE_SFA_API_BASE_URL": "https://api.example.com/sfa/api",
            },
        )
        v = DeployValidator(manifest)

        cors_resp = _mock_response(
            200,
            headers={"Access-Control-Allow-Origin": "*"},
        )
        login_resp = _mock_response(401)

        with (
            patch("kctl_dokploy.core.deploy_validators.httpx.options", return_value=cors_resp),
            patch("kctl_dokploy.core.deploy_validators.httpx.post", return_value=login_resp),
        ):
            results = v.post_verify()

        cors = next(r for r in results if r.name == "cors_preflight")
        assert cors.status == "pass"

        login = next(r for r in results if r.name == "login_endpoint")
        assert login.status == "pass"

    def test_cors_405_warns(self) -> None:
        manifest = _make_manifest(
            type="react-pwa",
            env_overrides={
                "VITE_SFA_API_BASE_URL": "https://api.example.com/sfa/api",
            },
        )
        v = DeployValidator(manifest)

        cors_resp = _mock_response(405)
        login_resp = _mock_response(200)

        with (
            patch("kctl_dokploy.core.deploy_validators.httpx.options", return_value=cors_resp),
            patch("kctl_dokploy.core.deploy_validators.httpx.post", return_value=login_resp),
        ):
            results = v.post_verify()

        cors = next(r for r in results if r.name == "cors_preflight")
        assert cors.status == "warn"

    def test_login_404_warns(self) -> None:
        manifest = _make_manifest(
            type="react-pwa",
            env_overrides={
                "VITE_SFA_API_BASE_URL": "https://api.example.com/sfa/api",
            },
        )
        v = DeployValidator(manifest)

        cors_resp = _mock_response(
            200,
            headers={"Access-Control-Allow-Origin": "*"},
        )
        login_resp = _mock_response(404)

        with (
            patch("kctl_dokploy.core.deploy_validators.httpx.options", return_value=cors_resp),
            patch("kctl_dokploy.core.deploy_validators.httpx.post", return_value=login_resp),
        ):
            results = v.post_verify()

        login = next(r for r in results if r.name == "login_endpoint")
        assert login.status == "warn"

    def test_no_api_url_skips(self) -> None:
        manifest = _make_manifest(type="react-pwa", env_overrides={})
        v = DeployValidator(manifest)
        results = v.post_verify()
        assert all(r.status == "skip" for r in results)

    def test_http_error_fails(self) -> None:
        manifest = _make_manifest(
            type="react-pwa",
            env_overrides={
                "VITE_SFA_API_BASE_URL": "https://api.example.com/sfa/api",
            },
        )
        v = DeployValidator(manifest)

        with (
            patch(
                "kctl_dokploy.core.deploy_validators.httpx.options",
                side_effect=httpx.ConnectError("refused"),
            ),
            patch(
                "kctl_dokploy.core.deploy_validators.httpx.post",
                side_effect=httpx.ConnectError("refused"),
            ),
        ):
            results = v.post_verify()

        assert all(r.status == "fail" for r in results)


# ---------------------------------------------------------------------------
# Post-verify — odoo (mocked HTTP)
# ---------------------------------------------------------------------------


class TestPostVerifyOdoo:
    def test_jwt_secrets_all_present(self) -> None:
        manifest = _make_manifest(
            type="odoo",
            env_overrides={"PGDATABASE": "mydb"},
        )
        v = DeployValidator(manifest)

        jwt_resp = _mock_response(200, json_data={"result": "a" * 64})
        stuck_resp = _mock_response(200, json_data={"result": 0})

        with patch(
            "kctl_dokploy.core.deploy_validators.httpx.post",
            side_effect=[jwt_resp] * 14 + [stuck_resp],
        ):
            results = v.post_verify()

        jwt = next(r for r in results if r.name == "jwt_secrets")
        assert jwt.status == "pass"

    def test_jwt_secrets_missing_warns(self) -> None:
        manifest = _make_manifest(
            type="odoo",
            env_overrides={"PGDATABASE": "mydb"},
        )
        v = DeployValidator(manifest)

        # First call returns empty secret, rest return valid
        weak_resp = _mock_response(200, json_data={"result": ""})
        good_resp = _mock_response(200, json_data={"result": "b" * 64})
        stuck_resp = _mock_response(200, json_data={"result": 0})

        with patch(
            "kctl_dokploy.core.deploy_validators.httpx.post",
            side_effect=[weak_resp] + [good_resp] * 13 + [stuck_resp],
        ):
            results = v.post_verify()

        jwt = next(r for r in results if r.name == "jwt_secrets")
        assert jwt.status == "warn"
        assert "sfa" in jwt.detail  # first app is sfa

    def test_stuck_modules_warns(self) -> None:
        manifest = _make_manifest(
            type="odoo",
            env_overrides={"PGDATABASE": "mydb"},
        )
        v = DeployValidator(manifest)

        jwt_resp = _mock_response(200, json_data={"result": "c" * 64})
        stuck_resp = _mock_response(200, json_data={"result": 3})

        with patch(
            "kctl_dokploy.core.deploy_validators.httpx.post",
            side_effect=[jwt_resp] * 14 + [stuck_resp],
        ):
            results = v.post_verify()

        stuck = next(r for r in results if r.name == "stuck_modules")
        assert stuck.status == "warn"
        assert "3" in stuck.detail


# ---------------------------------------------------------------------------
# Post-verify — nextjs (mocked HTTP)
# ---------------------------------------------------------------------------


class TestPostVerifyNextjs:
    def test_root_200_passes(self) -> None:
        manifest = _make_manifest(type="nextjs")
        v = DeployValidator(manifest)

        with patch(
            "kctl_dokploy.core.deploy_validators.httpx.get",
            return_value=_mock_response(200),
        ):
            results = v.post_verify()

        root = next(r for r in results if r.name == "root_path")
        assert root.status == "pass"

    def test_root_301_passes(self) -> None:
        manifest = _make_manifest(type="nextjs")
        v = DeployValidator(manifest)

        with patch(
            "kctl_dokploy.core.deploy_validators.httpx.get",
            return_value=_mock_response(301),
        ):
            results = v.post_verify()

        root = next(r for r in results if r.name == "root_path")
        assert root.status == "pass"

    def test_root_404_warns(self) -> None:
        manifest = _make_manifest(type="nextjs")
        v = DeployValidator(manifest)

        with patch(
            "kctl_dokploy.core.deploy_validators.httpx.get",
            return_value=_mock_response(404),
        ):
            results = v.post_verify()

        root = next(r for r in results if r.name == "root_path")
        assert root.status == "warn"

    def test_connection_error_fails(self) -> None:
        manifest = _make_manifest(type="nextjs")
        v = DeployValidator(manifest)

        with patch(
            "kctl_dokploy.core.deploy_validators.httpx.get",
            side_effect=httpx.ConnectError("refused"),
        ):
            results = v.post_verify()

        root = next(r for r in results if r.name == "root_path")
        assert root.status == "fail"


# ---------------------------------------------------------------------------
# Post-verify — unknown type returns empty
# ---------------------------------------------------------------------------


class TestPostVerifyUnknown:
    def test_unknown_returns_empty(self) -> None:
        manifest = _make_manifest(type="compose")
        v = DeployValidator(manifest)
        results = v.post_verify()
        assert results == []
