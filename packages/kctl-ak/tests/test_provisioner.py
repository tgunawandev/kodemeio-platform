"""Tests for user provisioner (roles/provisioner.py)."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock

import pytest

from kctl_ak.roles.loader import RoleLoader
from kctl_ak.roles.provisioner import Provisioner, ProvisionResult


@pytest.fixture()
def roles_dir(tmp_path: Path) -> Path:
    d = tmp_path / "roles"
    d.mkdir()
    (d / "basic-user.yaml").write_text(
        dedent("""\
        name: Basic User
        description: Basic access
        groups:
          - ak-role-basic
          - ak-app-mattermost-all
    """)
    )
    (d / "admin.yaml").write_text(
        dedent("""\
        name: IT Administrator
        description: Admin access
        groups:
          - ak-admin-super
    """)
    )
    return d


@pytest.fixture()
def mock_client() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def mock_output() -> MagicMock:
    return MagicMock()


class TestProvisionResult:
    def test_defaults(self) -> None:
        r = ProvisionResult()
        assert r.operation == ""
        assert r.user_id == 0
        assert r.groups_added == []
        assert r.groups_existed == []
        assert r.groups_failed == []
        assert r.recovery_link == ""

    def test_fields_populated(self) -> None:
        r = ProvisionResult(
            operation="create",
            user_id=42,
            email="a@b.com",
            username="a",
            roles=["admin"],
            groups_added=["g1"],
        )
        assert r.user_id == 42
        assert r.roles == ["admin"]


class TestProvisioner:
    def test_create_new_user(self, mock_client: MagicMock, mock_output: MagicMock, roles_dir: Path) -> None:
        mock_client.get.side_effect = [
            # Check user exists → no
            {"results": []},
            # Resolve group ak-app-mattermost-all
            {"results": [{"pk": "g1-uuid"}]},
            # Resolve group ak-role-basic
            {"results": [{"pk": "g2-uuid"}]},
        ]
        mock_client.post.side_effect = [
            # Create user
            {"pk": 100},
            # Add to group 1
            {},
            # Add to group 2
            {},
            # Recovery link
            {"link": "https://auth.kodeme.io/recovery/xyz"},
        ]

        loader = RoleLoader(search_paths=[roles_dir])
        prov = Provisioner(client=mock_client, role_loader=loader, output=mock_output)
        result = prov.provision(email="test@example.com", role_names=["basic-user"])

        assert result.operation == "create"
        assert result.user_id == 100
        assert result.email == "test@example.com"
        assert len(result.groups_added) == 2

    def test_update_existing_user(self, mock_client: MagicMock, mock_output: MagicMock, roles_dir: Path) -> None:
        mock_client.get.side_effect = [
            # Check user exists → yes
            {"results": [{"pk": 50}]},
            # Resolve group
            {"results": [{"pk": "g1-uuid"}]},
        ]
        mock_client.post.side_effect = [
            # Add to group
            {},
            # Recovery link
            {"link": "https://auth.kodeme.io/recovery/abc"},
        ]

        loader = RoleLoader(search_paths=[roles_dir])
        prov = Provisioner(client=mock_client, role_loader=loader, output=mock_output)
        result = prov.provision(email="existing@example.com", role_names=["admin"])

        assert result.operation == "update"
        assert result.user_id == 50

    def test_missing_group_tracked(self, mock_client: MagicMock, mock_output: MagicMock, roles_dir: Path) -> None:
        mock_client.get.side_effect = [
            {"results": []},  # user doesn't exist
            {"results": []},  # group not found
            {"results": []},  # group not found
        ]
        mock_client.post.side_effect = [
            {"pk": 200},  # create user
            {"link": ""},  # recovery
        ]

        loader = RoleLoader(search_paths=[roles_dir])
        prov = Provisioner(client=mock_client, role_loader=loader, output=mock_output)
        result = prov.provision(email="new@example.com", role_names=["basic-user"])

        assert result.groups_failed == ["ak-app-mattermost-all", "ak-role-basic"]
        assert result.groups_added == []

    def test_invalid_role_raises(self, mock_client: MagicMock, mock_output: MagicMock, roles_dir: Path) -> None:
        loader = RoleLoader(search_paths=[roles_dir])
        prov = Provisioner(client=mock_client, role_loader=loader, output=mock_output)

        with pytest.raises(ValueError, match="Role not found"):
            prov.provision(email="x@x.com", role_names=["nonexistent-role"])

    def test_username_from_email(self, mock_client: MagicMock, mock_output: MagicMock, roles_dir: Path) -> None:
        mock_client.get.side_effect = [
            {"results": []},
            {"results": []},
            {"results": []},
        ]
        mock_client.post.side_effect = [{"pk": 1}, {"link": ""}]

        loader = RoleLoader(search_paths=[roles_dir])
        prov = Provisioner(client=mock_client, role_loader=loader, output=mock_output)
        result = prov.provision(email="alice@example.com", role_names=["basic-user"])

        assert result.username == "alice"

    def test_explicit_username(self, mock_client: MagicMock, mock_output: MagicMock, roles_dir: Path) -> None:
        mock_client.get.side_effect = [
            {"results": []},
            {"results": []},
        ]
        mock_client.post.side_effect = [{"pk": 1}, {}, {"link": ""}]

        loader = RoleLoader(search_paths=[roles_dir])
        prov = Provisioner(client=mock_client, role_loader=loader, output=mock_output)
        result = prov.provision(email="a@b.com", role_names=["admin"], username="custom")

        assert result.username == "custom"

    def test_recovery_link_failure(self, mock_client: MagicMock, mock_output: MagicMock, roles_dir: Path) -> None:
        mock_client.get.side_effect = [
            {"results": []},
            {"results": []},
        ]
        mock_client.post.side_effect = [
            {"pk": 1},
            Exception("recovery flow not configured"),
        ]

        loader = RoleLoader(search_paths=[roles_dir])
        prov = Provisioner(client=mock_client, role_loader=loader, output=mock_output)
        result = prov.provision(email="a@b.com", role_names=["admin"])

        assert "not configured" in result.recovery_link
