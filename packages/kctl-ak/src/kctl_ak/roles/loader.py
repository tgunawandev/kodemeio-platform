"""Load role definitions from YAML files."""

from __future__ import annotations

from pathlib import Path

import yaml

from kctl_ak.core.config import resolve_roles_paths
from kctl_ak.models.role import RoleDefinition


class RoleLoader:
    """Loads role definitions from YAML files across multiple search paths."""

    def __init__(self, search_paths: list[Path] | None = None):
        self._paths = search_paths or resolve_roles_paths()

    def list_roles(self) -> list[RoleDefinition]:
        roles: dict[str, RoleDefinition] = {}
        for path in self._paths:
            if not path.is_dir():
                continue
            for f in sorted(path.glob("*.yaml")):
                role_name = f.stem
                if role_name in roles:
                    continue
                try:
                    with open(f) as fh:
                        data = yaml.safe_load(fh) or {}
                    roles[role_name] = RoleDefinition(
                        name=data.get("name", role_name),
                        description=data.get("description", ""),
                        groups=data.get("groups", []),
                        file_path=str(f),
                    )
                except Exception:
                    continue
        return sorted(roles.values(), key=lambda r: r.name)

    def get_role(self, name: str) -> RoleDefinition | None:
        for role in self.list_roles():
            if role.file_path and Path(role.file_path).stem == name:
                return role
            if role.name == name:
                return role
        return None

    def resolve_groups(self, role_names: list[str]) -> list[str]:
        """Collect unique groups from multiple roles."""
        groups: set[str] = set()
        for name in role_names:
            role = self.get_role(name)
            if role is None:
                raise ValueError(f"Role not found: {name}. Run 'kctl-ak users roles' to see available roles.")
            groups.update(role.groups)
        return sorted(groups)
