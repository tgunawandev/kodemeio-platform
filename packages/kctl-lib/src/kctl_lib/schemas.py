"""Service-schema registry for kctl-* profile validation.

Each kctl-* CLI may expose a `pydantic.BaseModel` describing the shape of its
service section within a profile. Schemas are registered at import time and
looked up by `kctl-profiles validate` to produce structured warnings and errors.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar

from pydantic import BaseModel

_T = TypeVar("_T", bound=BaseModel)

_REGISTRY: dict[str, type[BaseModel]] = {}


def register_service_schema(service_key: str, schema: type[_T]) -> type[_T]:
    """Register a pydantic schema for `service_key`. Returns the schema unchanged."""
    _REGISTRY[service_key] = schema
    return schema


def get_schema(service_key: str) -> type[BaseModel] | None:
    """Look up the registered schema for a service, or None if unregistered."""
    return _REGISTRY.get(service_key)


def all_registered_schemas() -> Iterable[tuple[str, type[BaseModel]]]:
    """Iterate (service_key, schema) pairs in insertion order."""
    return tuple(_REGISTRY.items())
