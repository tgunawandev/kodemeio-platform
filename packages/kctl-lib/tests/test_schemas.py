"""Service-schema registry tests."""

from __future__ import annotations

from pydantic import BaseModel


class TestSchemaRegistry:
    def test_register_and_lookup(self) -> None:
        from kctl_lib.schemas import get_schema, register_service_schema

        class OdooSchema(BaseModel):
            url: str
            database: str
            api_key: str

        register_service_schema("odoo", OdooSchema)
        assert get_schema("odoo") is OdooSchema

    def test_unknown_service_returns_none(self) -> None:
        from kctl_lib.schemas import get_schema

        assert get_schema("_nonexistent_service_") is None

    def test_all_registered_schemas_iter(self) -> None:
        from kctl_lib.schemas import all_registered_schemas, register_service_schema

        class FooSchema(BaseModel):
            bar: str

        register_service_schema("foo-test-iter", FooSchema)
        keys = {k for k, _ in all_registered_schemas()}
        assert "foo-test-iter" in keys
