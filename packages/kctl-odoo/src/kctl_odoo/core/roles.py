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

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

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


class OdooClientLike(Protocol):
    """Minimal interface for the Odoo JSON-RPC client used by this module."""

    def execute(self, model: str, method: str, *args: Any, **kwargs: Any) -> Any: ...


@dataclass
class RoleDbState:
    """Snapshot of the role-related state of a target DB."""

    roles_by_name: dict[str, dict[str, Any]]
    """name → {id, implied_ids: list[int]}"""

    xmlid_to_group_id: dict[str, int]
    """"module.xmlid" → res.groups.id"""


@dataclass
class SyncAction:
    action: Literal["create", "update", "delete"]
    role_id: str | None = None
    role_name: str | None = None
    category: str | None = None
    existing_role_id: int | None = None
    desired_group_ids: list[int] = field(default_factory=list)
    missing_xmlids: list[str] = field(default_factory=list)


def resolve_xmlids(
    client: OdooClientLike,
    xmlids: list[str],
) -> tuple[dict[str, int], list[str]]:
    """Resolve a list of `module.name` xml_ids to their `res.groups` ids.

    Returns (resolved, missing). Missing entries are NOT an error here —
    upstream code decides whether to warn or fail.
    """
    if not xmlids:
        return {}, []
    pairs: list[tuple[str, str]] = []
    for xid in xmlids:
        if "." not in xid:
            continue
        module, name = xid.split(".", 1)
        pairs.append((module, name))

    if not pairs:
        return {}, list(xmlids)

    # Build an OR chain over (module, name) pairs, ANDed with model = res.groups.
    or_clauses: list[Any] = []
    for module, name in pairs:
        or_clauses.append("&")
        or_clauses.append(("module", "=", module))
        or_clauses.append(("name", "=", name))
    domain = [("model", "=", "res.groups"), *(["|"] * (len(pairs) - 1)), *or_clauses]

    records = client.execute("ir.model.data", "search_read", domain, ["module", "name", "res_id"])

    resolved: dict[str, int] = {}
    for rec in records:
        key = f"{rec['module']}.{rec['name']}"
        resolved[key] = rec["res_id"]

    missing = [x for x in xmlids if x not in resolved]
    return resolved, missing


def plan_sync(
    rf: RolesFile,
    db_state: RoleDbState,
    prune: bool = False,
) -> list[SyncAction]:
    """Compute the minimal set of DB actions to make the DB match the YAML.

    Returns actions in order: creates + updates first (in YAML iteration order),
    then deletes (only under --prune).
    """
    actions: list[SyncAction] = []

    for role_id, spec in rf.roles.items():
        xmlids = resolve_role_groups(rf, role_id)

        desired_ids: list[int] = []
        missing: list[str] = []
        for xid in xmlids:
            if xid in db_state.xmlid_to_group_id:
                desired_ids.append(db_state.xmlid_to_group_id[xid])
            else:
                missing.append(xid)

        existing = db_state.roles_by_name.get(spec.name)
        if existing is None:
            actions.append(
                SyncAction(
                    action="create",
                    role_id=role_id,
                    role_name=spec.name,
                    category=spec.category,
                    desired_group_ids=sorted(set(desired_ids)),
                    missing_xmlids=missing,
                )
            )
        else:
            if set(existing["implied_ids"]) != set(desired_ids):
                actions.append(
                    SyncAction(
                        action="update",
                        role_id=role_id,
                        role_name=spec.name,
                        category=spec.category,
                        existing_role_id=existing["id"],
                        desired_group_ids=sorted(set(desired_ids)),
                        missing_xmlids=missing,
                    )
                )

    if prune:
        desired_names = {spec.name for spec in rf.roles.values()}
        for db_name, db_role in db_state.roles_by_name.items():
            if db_name not in desired_names:
                actions.append(
                    SyncAction(
                        action="delete",
                        role_name=db_name,
                        existing_role_id=db_role["id"],
                    )
                )

    return actions
