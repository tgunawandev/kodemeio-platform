"""Tests for provision chain orchestrator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kctl_ak.models.provision import (
    ChainResult,
    CompanyConfig,
    MailcowConfig,
    ProvisionConfig,
    ProvisionDefaults,
    StepStatus,
)
from kctl_ak.provision.chain import ProvisionChain


@pytest.fixture
def mock_ak_client() -> MagicMock:
    client = MagicMock()
    # user does not exist
    client.get.return_value = {"results": [], "pagination": {"count": 0}}
    # create user returns pk=42
    client.post.return_value = {"pk": 42}
    return client


@pytest.fixture
def config() -> ProvisionConfig:
    return ProvisionConfig(
        mailcow=MailcowConfig(api_url="https://mail.kodeme.io"),
        defaults=ProvisionDefaults(mailbox_quota=1073741824),
        companies={
            "mac": CompanyConfig(
                domain="mandiriagro.com",
                hrms="mac-odoo-hrms.mandiriagro.com",
                odoo_targets=["mac-odoo-dist.mandiriagro.com"],
            ),
        },
    )


@pytest.fixture
def mock_output() -> MagicMock:
    return MagicMock()


def test_onboard_new_user(mock_ak_client: MagicMock, config: ProvisionConfig, mock_output: MagicMock) -> None:
    chain = ProvisionChain(
        ak_client=mock_ak_client,
        config=config,
        output=mock_output,
        mailcow_api_key="test-key",
        odoo_credentials={},
        dry_run=False,
    )

    with patch.object(chain, "_step_mailcow_create") as mock_mc, patch.object(chain, "_step_odoo_sync") as mock_odoo:
        mock_mc.return_value = None
        mock_odoo.return_value = None

        result = chain.onboard(
            email="john.doe@mandiriagro.com",
            name="John Doe",
            company="mac",
        )

    assert result.success
    assert result.action == "onboard"
    assert result.email == "john.doe@mandiriagro.com"
    # Authentik user creation was called
    mock_ak_client.post.assert_called()


def test_onboard_dry_run(mock_ak_client: MagicMock, config: ProvisionConfig, mock_output: MagicMock) -> None:
    chain = ProvisionChain(
        ak_client=mock_ak_client,
        config=config,
        output=mock_output,
        mailcow_api_key="test-key",
        odoo_credentials={},
        dry_run=True,
    )

    result = chain.onboard(
        email="john.doe@mandiriagro.com",
        name="John Doe",
        company="mac",
    )

    assert result.success
    # No API calls in dry run
    mock_ak_client.post.assert_not_called()
    mock_ak_client.patch.assert_not_called()


def test_offboard_user(mock_ak_client: MagicMock, config: ProvisionConfig, mock_output: MagicMock) -> None:
    # User exists and is active
    mock_ak_client.get.side_effect = [
        {"results": [{"pk": 42, "is_active": True, "username": "john.doe"}], "pagination": {"count": 1}},
        {"results": [], "pagination": {"count": 0}},  # sessions
    ]
    mock_ak_client.patch.return_value = {"pk": 42, "is_active": False}

    chain = ProvisionChain(
        ak_client=mock_ak_client,
        config=config,
        output=mock_output,
        mailcow_api_key="test-key",
        odoo_credentials={},
        dry_run=False,
    )

    with (
        patch.object(chain, "_step_mailcow_disable") as mock_mc,
        patch.object(chain, "_step_odoo_deactivate") as mock_odoo,
    ):
        mock_mc.return_value = None
        mock_odoo.return_value = None

        result = chain.offboard(email="john.doe@mandiriagro.com")

    assert result.success
    assert result.action == "offboard"


def test_offboard_unknown_user(mock_ak_client: MagicMock, config: ProvisionConfig, mock_output: MagicMock) -> None:
    mock_ak_client.get.return_value = {"results": [], "pagination": {"count": 0}}

    chain = ProvisionChain(
        ak_client=mock_ak_client,
        config=config,
        output=mock_output,
        mailcow_api_key="test-key",
        odoo_credentials={},
        dry_run=False,
    )

    result = chain.offboard(email="unknown@mandiriagro.com")
    assert not result.success
    assert any(s.status == StepStatus.FAILED for s in result.steps)
