"""Tests for Odoo webhook setup logic."""

from __future__ import annotations

import pytest

from kctl_ak.provision.webhook_setup import (
    AUTOMATION_NAME,
    generate_webhook_code,
    build_automation_vals,
)


def test_generate_webhook_code() -> None:
    code = generate_webhook_code(
        webhook_url="https://ak-sync.kodeme.io/webhook/odoo-hrms",
        webhook_secret="my-secret",
        hmac_key="my-hmac-key",
        company_code="mac",
        hrms_domain="mac-odoo-hrms.mandiriagro.com",
    )
    assert "https://ak-sync.kodeme.io/webhook/odoo-hrms" in code
    assert "my-secret" in code
    assert "my-hmac-key" in code
    assert '"mac"' in code
    assert "mac-odoo-hrms.mandiriagro.com" in code
    assert "urllib.request" in code
    assert "hmac.new" in code
    assert "employee.create" in code
    assert "employee.archive" in code


def test_generate_webhook_code_no_double_braces() -> None:
    """Ensure the generated code has no unresolved template braces."""
    code = generate_webhook_code(
        webhook_url="https://example.com",
        webhook_secret="secret",
        hmac_key="key",
        company_code="tpp",
        hrms_domain="tpp-odoo-hrms.pakerti.com",
    )
    assert "{{" not in code
    assert "}}" not in code


def test_build_automation_vals() -> None:
    vals = build_automation_vals(
        model_id=42,
        active_field_id=99,
        code="# test code",
    )
    assert vals["name"] == AUTOMATION_NAME
    assert vals["model_id"] == 42
    assert vals["trigger"] == "on_create_or_write"
    assert vals["trigger_field_ids"] == [[6, 0, [99]]]
    assert vals["state"] == "code"
    assert vals["active"] is True
    assert vals["code"] == "# test code"


def test_automation_name_is_consistent() -> None:
    assert AUTOMATION_NAME == "AK Sync: Employee Provisioning"
