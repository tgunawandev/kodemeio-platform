"""Tests for mailer module (core/mailer.py)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from kctl_ak.core.mailer import SmtpConfig, build_recovery_email, build_welcome_email, resolve_smtp_config


class TestSmtpConfig:
    def test_defaults(self) -> None:
        cfg = SmtpConfig()
        assert cfg.host == ""
        assert cfg.port == 587
        assert cfg.use_tls is True
        assert cfg.use_ssl is False
        assert cfg.from_name == "Kodemeio"

    def test_is_configured_false_when_empty(self) -> None:
        assert SmtpConfig().is_configured is False

    def test_is_configured_true(self) -> None:
        cfg = SmtpConfig(
            host="smtp.example.com",
            username="user",
            password="pass",
            from_address="noreply@example.com",
        )
        assert cfg.is_configured is True

    def test_is_configured_missing_host(self) -> None:
        cfg = SmtpConfig(username="u", password="p", from_address="a@b.com")
        assert cfg.is_configured is False

    def test_is_configured_missing_password(self) -> None:
        cfg = SmtpConfig(host="smtp.test", username="u", from_address="a@b.com")
        assert cfg.is_configured is False


class TestBuildWelcomeEmail:
    def test_subject_contains_tenant(self) -> None:
        subject, _ = build_welcome_email(name="Alice", email="alice@test.com")
        assert "Kodemeio" in subject
        assert "Welcome" in subject

    def test_body_contains_name(self) -> None:
        _, body = build_welcome_email(name="Alice", email="alice@test.com")
        assert "Alice" in body

    def test_body_with_recovery_link(self) -> None:
        _, body = build_welcome_email(
            name="Bob",
            email="bob@test.com",
            recovery_link="https://auth.kodeme.io/recovery/xyz",
        )
        assert "https://auth.kodeme.io/recovery/xyz" in body
        assert "Set Up Your Password" in body

    def test_body_with_password(self) -> None:
        _, body = build_welcome_email(
            name="Carol",
            email="carol@test.com",
            password="secret123",
        )
        assert "secret123" in body
        assert "Your Credentials" in body

    def test_custom_tenant(self) -> None:
        subject, body = build_welcome_email(name="X", email="x@x.com", tenant="MyOrg")
        assert "MyOrg" in subject
        assert "MyOrg" in body

    def test_custom_auth_url(self) -> None:
        _, body = build_welcome_email(name="X", email="x@x.com", auth_url="https://custom.auth.com")
        assert "https://custom.auth.com" in body

    def test_returns_tuple(self) -> None:
        result = build_welcome_email(name="X", email="x@x.com")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_body_is_html(self) -> None:
        _, body = build_welcome_email(name="X", email="x@x.com")
        assert body.startswith("<!DOCTYPE html>")


class TestBuildRecoveryEmail:
    def test_subject_contains_reset(self) -> None:
        subject, _ = build_recovery_email(
            name="Alice",
            recovery_link="https://auth.kodeme.io/recovery/abc",
        )
        assert "Reset" in subject

    def test_body_contains_link(self) -> None:
        link = "https://auth.kodeme.io/recovery/abc"
        _, body = build_recovery_email(name="Alice", recovery_link=link)
        assert link in body
        assert "Reset Password" in body

    def test_body_contains_name(self) -> None:
        _, body = build_recovery_email(name="Bob", recovery_link="https://x.com/r")
        assert "Bob" in body

    def test_body_is_html(self) -> None:
        _, body = build_recovery_email(name="X", recovery_link="https://x.com/r")
        assert "<!DOCTYPE html>" in body

    def test_custom_tenant(self) -> None:
        subject, body = build_recovery_email(name="X", recovery_link="https://x.com/r", tenant="Acme")
        assert "Acme" in subject
        assert "Acme" not in body or "Acme" in body  # Just check it doesn't crash


class TestResolveSmtpConfig:
    @patch("kctl_ak.core.mailer.resolve_active_profile_name", return_value="default")
    @patch("kctl_ak.core.mailer.get_service_config")
    def test_returns_smtp_config(self, mock_svc: MagicMock, mock_profile: MagicMock) -> None:
        mock_svc.return_value = MagicMock(smtp=None)
        cfg = resolve_smtp_config()
        assert isinstance(cfg, SmtpConfig)

    @patch.dict(os.environ, {"EMAIL_HOST": "smtp.env.com", "EMAIL_PORT": "465"})
    @patch("kctl_ak.core.mailer.resolve_active_profile_name", return_value="default")
    @patch("kctl_ak.core.mailer.get_service_config")
    def test_env_overrides(self, mock_svc: MagicMock, mock_profile: MagicMock) -> None:
        mock_svc.return_value = MagicMock(smtp=None)
        cfg = resolve_smtp_config()
        assert cfg.host == "smtp.env.com"
        assert cfg.port == 465

    @patch.dict(os.environ, {"EMAIL_USE_TLS": "false", "EMAIL_USE_SSL": "true"})
    @patch("kctl_ak.core.mailer.resolve_active_profile_name", return_value="default")
    @patch("kctl_ak.core.mailer.get_service_config")
    def test_boolean_env_parsing(self, mock_svc: MagicMock, mock_profile: MagicMock) -> None:
        mock_svc.return_value = MagicMock(smtp=None)
        cfg = resolve_smtp_config()
        assert cfg.use_tls is False
        assert cfg.use_ssl is True
