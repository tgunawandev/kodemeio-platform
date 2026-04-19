"""Role catalog — YAML schema, extend-chain resolver, DB planner.

Source-of-truth YAML shape:

    version: 1
    roles:
      <role_id>:
        name: "Human Name"
        category: "User roles / Foo"   # optional
        extends: "<other_role_id>"     # optional
        groups:
          - module.group_xmlid
          - ...

`role_id` is the YAML key — stable, snake_case. `name` is user-visible.
Use `extends` for inheritance (single-parent chain). Groups are deduped
across the chain preserving first-occurrence order.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class RoleSpec(BaseModel):
    name: str
    category: str | None = None
    extends: str | None = None
    groups: list[str] = Field(default_factory=list)


class RolesFile(BaseModel):
    version: int = 1
    roles: dict[str, RoleSpec] = Field(default_factory=dict)


class IgnoredFile(BaseModel):
    version: int = 1
    ignored: list[str] = Field(default_factory=list)


class CircularExtendError(ValueError):
    """Raised when role A extends role B which extends A (directly or indirectly)."""


class UnknownExtendError(ValueError):
    """Raised when a role's `extends` points to a role id not defined in the file."""


def load_roles_file(path: Path) -> RolesFile:
    data = yaml.safe_load(path.read_text()) or {}
    return RolesFile.model_validate(data)


def load_ignored_file(path: Path) -> IgnoredFile:
    if not path.exists():
        return IgnoredFile()
    data = yaml.safe_load(path.read_text()) or {}
    return IgnoredFile.model_validate(data)


def resolve_role_groups(rf: RolesFile, role_id: str) -> list[str]:
    """Return the full flat group list for a role, walking `extends` chain.

    Order: parent groups first, then child groups. Duplicates removed,
    first occurrence wins.
    """
    if role_id not in rf.roles:
        raise UnknownExtendError(f"Role '{role_id}' not defined")

    chain: list[str] = []
    current: str | None = role_id
    while current is not None:
        if current in chain:
            cycle = " -> ".join([*chain, current])
            raise CircularExtendError(f"Circular extends chain: {cycle}")
        if current not in rf.roles:
            # We only reach here via an `extends` pointer from the previous link.
            parent_of = chain[-1]
            raise UnknownExtendError(f"Role '{current}' referenced by 'extends' in '{parent_of}' is not defined")
        chain.append(current)
        current = rf.roles[current].extends

    # Parent first → reverse the chain
    chain.reverse()

    # Flatten groups with order-preserving dedup
    out: list[str] = []
    seen_groups: set[str] = set()
    for rid in chain:
        for g in rf.roles[rid].groups:
            if g not in seen_groups:
                seen_groups.add(g)
                out.append(g)
    return out
