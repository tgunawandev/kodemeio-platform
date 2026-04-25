"""Tests for SupabaseClient."""

import pytest
from kctl_supa.core.client import SupabaseClient
from kctl_supa.core.exceptions import AuthError


def test_client_requires_url():
    with pytest.raises(AuthError, match="No Supabase URL"):
        SupabaseClient(base_url="", service_role_key="key")


def test_client_requires_key():
    with pytest.raises(AuthError, match="No service role key"):
        SupabaseClient(base_url="https://supa.terakidz.com", service_role_key="")


def test_client_builds_headers():
    client = SupabaseClient(
        base_url="https://supa.terakidz.com",
        service_role_key="test-key",
    )
    assert client._base_url == "https://supa.terakidz.com"
    assert "apikey" in client._headers
    assert client._headers["apikey"] == "test-key"
    assert client._headers["Authorization"] == "Bearer test-key"
