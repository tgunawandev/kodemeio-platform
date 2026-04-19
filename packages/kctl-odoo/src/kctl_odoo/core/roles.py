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
    hide_menus: list[str] = Field(default_factory=list)
    """Top-level menu NAMES to hide from this role via
    base_menu_visibility_restriction. Does NOT inherit via `extends` —
    each role must list its own hides explicitly."""


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

    def search_read(
        self,
        model: str,
        domain: list | None = None,
        fields: list[str] | None = None,
        limit: int = 0,
        offset: int = 0,
        order: str = "",
    ) -> list[dict]: ...

    def read(self, model: str, ids: list[int], fields: list[str] | None = None) -> list[dict]: ...

    def create(self, model: str, vals: dict) -> int: ...

    def write(self, model: str, ids: list[int], vals: dict) -> bool: ...

    def unlink(self, model: str, ids: list[int]) -> bool: ...


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

    records = client.search_read(
        "ir.model.data",
        domain,
        fields=["module", "name", "res_id"],
    )

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


@dataclass
class MenuVisibilityAction:
    """One write against ir.ui.menu.excluded_group_ids.

    `action="add"` appends `group_id` to the menu's excluded_group_ids
    (hides the menu from users in that group). `action="remove"` does
    the opposite. `role_id` is the YAML key (for logging).
    """

    action: Literal["add", "remove"]
    menu_id: int
    menu_name: str
    group_id: int
    role_id: str


def plan_menu_visibility(
    rf: RolesFile,
    role_backing_groups: dict[str, int],
    menu_ids_by_name: dict[str, int],
    current_exclusions: dict[int, set[int]],
    prune: bool = False,
) -> list[MenuVisibilityAction]:
    """Plan menu-visibility updates via ir.ui.menu.excluded_group_ids.

    For each role with `hide_menus`: for each menu NAME the role wants
    hidden, emit an `add` action if the role's backing group isn't
    already in that menu's excluded_group_ids. With `prune=True`,
    also emit `remove` actions for role/menu pairs the YAML no longer
    requests.

    Unknown menu names (not in `menu_ids_by_name`) are silently skipped —
    the caller is expected to log a warning.

    Prune scope: only touches exclusions whose group id is a tracked
    role-backing group. Any other group a human may have manually added
    (e.g., a one-off Settings group) is left alone.

    `hide_menus` does NOT inherit via `extends`; each role lists its
    own hides explicitly.
    """
    # Desired: {menu_id: {group_ids}} from YAML
    desired: dict[int, set[int]] = {}
    for role_id, spec in rf.roles.items():
        if not spec.hide_menus:
            continue
        gid = role_backing_groups.get(role_id)
        if gid is None:
            # Role not synced yet — caller should warn.
            continue
        for menu_name in spec.hide_menus:
            mid = menu_ids_by_name.get(menu_name)
            if mid is None:
                # Unknown menu — caller warns.
                continue
            desired.setdefault(mid, set()).add(gid)

    actions: list[MenuVisibilityAction] = []
    relevant_groups = set(role_backing_groups.values())
    menu_names_by_id = {mid: name for name, mid in menu_ids_by_name.items()}

    # Adds — deterministic order (menu_id asc, then group_id asc).
    for mid in sorted(desired):
        want = desired[mid]
        current = current_exclusions.get(mid, set())
        missing = want - current
        for gid in sorted(missing):
            role_id = next((rid for rid, v in role_backing_groups.items() if v == gid), "")
            actions.append(
                MenuVisibilityAction(
                    action="add",
                    menu_id=mid,
                    menu_name=menu_names_by_id.get(mid, ""),
                    group_id=gid,
                    role_id=role_id,
                )
            )

    # Prunes — only on exclusions we would track (role backing groups).
    if prune:
        for mid in sorted(current_exclusions):
            current = current_exclusions[mid]
            want = desired.get(mid, set())
            stale = (current & relevant_groups) - want
            for gid in sorted(stale):
                role_id = next((rid for rid, v in role_backing_groups.items() if v == gid), "")
                actions.append(
                    MenuVisibilityAction(
                        action="remove",
                        menu_id=mid,
                        menu_name=menu_names_by_id.get(mid, ""),
                        group_id=gid,
                        role_id=role_id,
                    )
                )

    return actions
