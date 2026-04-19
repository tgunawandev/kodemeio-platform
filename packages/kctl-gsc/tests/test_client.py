"""GSCClient auth + discovery tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kctl_gsc.core.client import GSCClient, GSCCredentialsError


def _fake_sa_file(tmp_path: Path) -> Path:
    p = tmp_path / "sa.json"
    p.write_text(
        json.dumps(
            {
                "type": "service_account",
                "client_email": "gsc@proj.iam.gserviceaccount.com",
                "private_key": "-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----\n",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        )
    )
    return p


def test_missing_credentials_file_raises(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    with pytest.raises(GSCCredentialsError, match="not found"):
        GSCClient(credentials_file=str(missing))


def test_builds_service_with_expected_scopes(tmp_path: Path) -> None:
    sa = _fake_sa_file(tmp_path)
    with (
        patch("kctl_gsc.core.client.service_account.Credentials.from_service_account_file") as m_creds,
        patch("kctl_gsc.core.client.build") as m_build,
    ):
        m_creds.return_value = MagicMock()
        m_build.return_value = MagicMock()
        GSCClient(credentials_file=str(sa))
        args, kwargs = m_creds.call_args
        assert args[0] == str(sa)
        assert set(kwargs["scopes"]) == {
            "https://www.googleapis.com/auth/webmasters.readonly",
            "https://www.googleapis.com/auth/webmasters",
        }
        m_build.assert_called_once_with("searchconsole", "v1", credentials=m_creds.return_value, cache_discovery=False)


def test_check_auth_calls_sites_list(tmp_path: Path) -> None:
    sa = _fake_sa_file(tmp_path)
    with (
        patch("kctl_gsc.core.client.service_account.Credentials.from_service_account_file"),
        patch("kctl_gsc.core.client.build") as m_build,
    ):
        svc = MagicMock()
        svc.sites.return_value.list.return_value.execute.return_value = {"siteEntry": []}
        m_build.return_value = svc
        client = GSCClient(credentials_file=str(sa))
        assert client.check_auth() == {"siteEntry": []}
