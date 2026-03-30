"""Tests for kctl-gatus config module."""

import pytest
from kctl_gatus.core.config import ServiceConfig


class TestServiceConfig:
    def test_default_values(self):
        cfg = ServiceConfig()
        assert cfg.url == ""
        assert cfg.api_key == ""

    def test_custom_values(self):
        cfg = ServiceConfig(url="https://status.example.com", api_key="gatus-key")
        assert cfg.url == "https://status.example.com"
        assert cfg.api_key == "gatus-key"

    def test_model_fields_list(self):
        expected = {"url", "api_key"}
        assert set(ServiceConfig.model_fields.keys()) == expected

    def test_model_dump(self):
        cfg = ServiceConfig(url="https://example.com", api_key="k")
        data = cfg.model_dump()
        assert data == {"url": "https://example.com", "api_key": "k"}
