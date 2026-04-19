"""Tests for mask_secret_fields() helper in kctl_lib.output."""

from __future__ import annotations


class TestMaskSecretFields:
    def test_masks_known_secret_keys(self) -> None:
        from kctl_lib.output import mask_secret_fields

        out = mask_secret_fields(
            {
                "url": "https://x.com",
                "api_key": "supersecretvalue",
                "username": "admin",
                "token": "abcd",
            }
        )
        assert out["url"] == "https://x.com"
        assert out["username"] == "admin"
        assert "supersecretvalue" not in out["api_key"]
        assert "****" in out["api_key"]
        # Short secret still masked, just without leak of prefix/suffix.
        assert out["token"] == "****"

    def test_non_string_secrets_passed_through(self) -> None:
        from kctl_lib.output import mask_secret_fields

        out = mask_secret_fields({"api_key": None, "password": 42})
        # Non-strings aren't masked (nothing to mask); they pass through unchanged.
        assert out["api_key"] is None
        assert out["password"] == 42

    def test_empty_input(self) -> None:
        from kctl_lib.output import mask_secret_fields

        assert mask_secret_fields({}) == {}

    def test_long_secret_shows_prefix_and_suffix(self) -> None:
        from kctl_lib.output import mask_secret_fields

        out = mask_secret_fields({"api_key": "abcdefghijklmnop"})
        assert out["api_key"] == "abcd****mnop"

    def test_exactly_8_chars_collapses(self) -> None:
        from kctl_lib.output import mask_secret_fields

        out = mask_secret_fields({"password": "12345678"})
        assert out["password"] == "****"

    def test_all_secret_field_names_are_masked(self) -> None:
        from kctl_lib.output import mask_secret_fields

        secret_fields = [
            "token",
            "api_key",
            "password",
            "service_account_token",
            "auth_token",
            "signature_secret",
            "dns_token",
            "s3_secret_key",
        ]
        data = {field: "averylongsecretvalue123" for field in secret_fields}
        out = mask_secret_fields(data)
        for field in secret_fields:
            assert "averylongsecretvalue123" not in out[field]
            assert "****" in str(out[field])

    def test_non_secret_fields_pass_through(self) -> None:
        from kctl_lib.output import mask_secret_fields

        out = mask_secret_fields({"url": "https://example.com", "username": "admin", "database": "mydb"})
        assert out["url"] == "https://example.com"
        assert out["username"] == "admin"
        assert out["database"] == "mydb"
