"""Tests for provision config loading."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from kctl_ak.provision.config import load_provision_config
from kctl_ak.models.provision import ProvisionConfig


def test_load_provision_config(tmp_path: Path) -> None:
    config_file = tmp_path / "provision-config.yaml"
    config_file.write_text(
        textwrap.dedent("""\
        mailcow:
          api_url: https://mail.kodeme.io

        defaults:
          mailbox_quota: 1073741824

        companies:
          mac:
            domain: mandiriagro.com
            hrms: mac-odoo-hrms.mandiriagro.com
            odoo_targets:
              - mac-odoo-dist.mandiriagro.com
    """)
    )

    config = load_provision_config(config_file)

    assert config.mailcow.api_url == "https://mail.kodeme.io"
    assert config.defaults.mailbox_quota == 1073741824
    assert "mac" in config.companies
    assert config.companies["mac"].domain == "mandiriagro.com"
    assert config.companies["mac"].hrms == "mac-odoo-hrms.mandiriagro.com"
    assert config.companies["mac"].odoo_targets == ["mac-odoo-dist.mandiriagro.com"]


def test_load_provision_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_provision_config(tmp_path / "nonexistent.yaml")


def test_company_without_hrms(tmp_path: Path) -> None:
    config_file = tmp_path / "provision-config.yaml"
    config_file.write_text(
        textwrap.dedent("""\
        mailcow:
          api_url: https://mail.kodeme.io
        defaults:
          mailbox_quota: 1073741824
        companies:
          tkz:
            domain: terakidz.com
            hrms: null
            odoo_targets: []
    """)
    )

    config = load_provision_config(config_file)
    assert config.companies["tkz"].hrms is None
    assert config.companies["tkz"].odoo_targets == []
