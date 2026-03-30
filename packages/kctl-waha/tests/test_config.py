"""Tests for kctl-waha config module."""

import pytest
from kctl_waha.core.config import ServiceConfig


class TestServiceConfig:
    def test_default_values(self):
        cfg = ServiceConfig()
        assert cfg.url == ""
        assert cfg.api_key == ""
        assert cfg.bridge_url == ""
        assert cfg.container_name == ""

    def test_custom_values(self):
        cfg = ServiceConfig(url="https://waha.example.com", api_key="waha-key")
        assert cfg.url == "https://waha.example.com"
        assert cfg.api_key == "waha-key"

    def test_with_bridge_url(self):
        cfg = ServiceConfig(
            url="https://waha.example.com",
            api_key="k",
            bridge_url="http://localhost:3050",
        )
        assert cfg.bridge_url == "http://localhost:3050"

    def test_model_fields_list(self):
        expected = {"url", "api_key", "bridge_url", "container_name"}
        assert set(ServiceConfig.model_fields.keys()) == expected

    def test_model_dump(self):
        cfg = ServiceConfig(url="https://waha.example.com", api_key="k")
        data = cfg.model_dump()
        assert data["url"] == "https://waha.example.com"
        assert data["api_key"] == "k"
        assert data["bridge_url"] == ""
        assert data["container_name"] == ""
