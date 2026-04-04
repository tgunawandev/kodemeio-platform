"""Tests for kctl-ak config module."""

from kctl_ak.core.config import ServiceConfig, SmtpProfile


class TestServiceConfig:
    def test_default_values(self):
        cfg = ServiceConfig()
        assert cfg.url == ""
        assert cfg.token == ""
        assert cfg.container_name == ""
        assert cfg.roles_dir == ""
        assert cfg.group_structure == ""
        assert cfg.smtp is None

    def test_custom_values(self):
        cfg = ServiceConfig(url="https://auth.example.com", token="test-token")
        assert cfg.url == "https://auth.example.com"
        assert cfg.token == "test-token"

    def test_with_smtp_profile(self):
        smtp = SmtpProfile(host="smtp.example.com", port=465, use_ssl=True)
        cfg = ServiceConfig(url="https://auth.example.com", token="tk", smtp=smtp)
        assert cfg.smtp is not None
        assert cfg.smtp.host == "smtp.example.com"
        assert cfg.smtp.port == 465
        assert cfg.smtp.use_ssl is True

    def test_smtp_defaults(self):
        smtp = SmtpProfile()
        assert smtp.host == ""
        assert smtp.port == 587
        assert smtp.use_tls is True
        assert smtp.use_ssl is False
        assert smtp.from_name == "Kodemeio"

    def test_model_fields_list(self):
        """ServiceConfig should expose the expected fields for validation."""
        expected = {"url", "token", "container_name", "roles_dir", "group_structure", "app_registry", "smtp"}
        assert set(ServiceConfig.model_fields.keys()) == expected
