"""Sanity tests for MODULE_REGISTRY in kctl_accurate.core.columns."""

from __future__ import annotations

from pydantic import BaseModel

from accurate_sdk.client import AccurateClient
from kctl_accurate.core.columns import MODULE_REGISTRY, ModuleSpec


def test_registry_has_23_entries() -> None:
    assert len(MODULE_REGISTRY) >= 23, f"Expected >= 23 entries, got {len(MODULE_REGISTRY)}"


def test_all_entries_are_module_specs() -> None:
    for name, spec in MODULE_REGISTRY.items():
        assert isinstance(spec, ModuleSpec), f"{name!r} is not a ModuleSpec"


def test_all_models_are_pydantic_base_models() -> None:
    for name, spec in MODULE_REGISTRY.items():
        assert issubclass(spec.model, BaseModel), f"{name!r}: model {spec.model} is not a BaseModel subclass"


def test_all_columns_have_at_least_four_items() -> None:
    for name, spec in MODULE_REGISTRY.items():
        assert len(spec.columns) >= 4, f"{name!r}: only {len(spec.columns)} columns; need >= 4"


def test_all_sdk_accessors_exist_on_accurate_client() -> None:
    """Verify every sdk_accessor is a real attribute on AccurateClient.

    Note: journal-vouchers uses 'journal_vouchers' which IS an accessor,
    but the underlying client.py does a lazy import from models.accounting
    (a stale reference — the class actually lives in models.finance).
    The accessor property itself is present; it'll fail at call-time unless
    the SDK's client.py is updated. We only check ``hasattr`` here.
    """
    for name, spec in MODULE_REGISTRY.items():
        assert hasattr(AccurateClient, spec.sdk_accessor), (
            f"{name!r}: AccurateClient has no attribute {spec.sdk_accessor!r}"
        )


def test_cli_name_matches_registry_key() -> None:
    for key, spec in MODULE_REGISTRY.items():
        assert spec.cli_name == key, f"Registry key {key!r} != spec.cli_name {spec.cli_name!r}"
