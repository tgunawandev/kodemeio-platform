"""Tests for the `tokens` command group.

Uses pytest-httpx to mock Cloudflare API responses directly at the HTTP layer,
so we exercise the real CloudflareClient envelope-unwrapping and error mapping
in addition to the command logic.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import click
import pytest
from pytest_httpx import HTTPXMock

from kctl_cf.core.client import CloudflareClient
from tests.conftest import _make_actx, _make_ctx


def _cf_envelope(result: Any, *, success: bool = True, errors: list[dict] | None = None) -> dict:
    """Wrap a result in Cloudflare's standard API v4 envelope."""
    payload: dict = {
        "success": success,
        "errors": errors or [],
        "messages": [],
        "result": result,
    }
    return payload


@pytest.fixture
def cf_client() -> CloudflareClient:
    """Real CloudflareClient pointed at the Cloudflare base URL (httpx_mock intercepts)."""
    return CloudflareClient(api_token="test-token")


# ---------------------------------------------------------------------------
# tokens list
# ---------------------------------------------------------------------------


class TestTokensList:
    def test_tokens_list_shows_table(
        self,
        httpx_mock: HTTPXMock,
        cf_client: CloudflareClient,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            url="https://api.cloudflare.com/client/v4/user/tokens",
            json=_cf_envelope(
                [
                    {"id": "tok_1", "name": "dokploy-cert", "status": "active"},
                    {"id": "tok_2", "name": "ci-dns", "status": "disabled"},
                ]
            ),
        )
        actx = _make_actx(json_mode=True, client=cf_client)
        ctx = _make_ctx(actx)

        from kctl_cf.commands.tokens import list_

        list_(ctx)

        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 2
        assert {row["id"] for row in data} == {"tok_1", "tok_2"}

    def test_tokens_list_handles_9109_with_guidance(
        self,
        httpx_mock: HTTPXMock,
        cf_client: CloudflareClient,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            url="https://api.cloudflare.com/client/v4/user/tokens",
            status_code=403,
            json={
                "success": False,
                "errors": [{"code": 9109, "message": "Unauthorized to access requested resource"}],
                "messages": [],
                "result": None,
            },
        )
        actx = _make_actx(client=cf_client)
        ctx = _make_ctx(actx)

        from kctl_cf.commands.tokens import list_

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            list_(ctx)

        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "User.API Tokens.Edit" in combined
        assert "dash.cloudflare.com/profile/api-tokens" in combined


# ---------------------------------------------------------------------------
# tokens create
# ---------------------------------------------------------------------------


class TestTokensCreate:
    def _register_perm_groups(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            method="GET",
            url="https://api.cloudflare.com/client/v4/user/tokens/permission_groups",
            json=_cf_envelope(
                [
                    {"id": "pg-dns", "name": "DNS Write", "scopes": ["com.cloudflare.api.account.zone"]},
                    {"id": "pg-zone", "name": "Zone Read", "scopes": ["com.cloudflare.api.account.zone"]},
                    {"id": "pg-other", "name": "Workers Scripts:Edit", "scopes": ["com.cloudflare.api.account"]},
                ]
            ),
        )

    def test_tokens_create_with_preset_dns_edit(
        self,
        httpx_mock: HTTPXMock,
        cf_client: CloudflareClient,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Zone lookup
        httpx_mock.add_response(
            method="GET",
            url="https://api.cloudflare.com/client/v4/zones?name=example.com",
            json=_cf_envelope([{"id": "zone123", "name": "example.com"}]),
        )
        # Permission groups lookup
        self._register_perm_groups(httpx_mock)
        # Token create
        httpx_mock.add_response(
            method="POST",
            url="https://api.cloudflare.com/client/v4/user/tokens",
            json=_cf_envelope({"id": "tok1", "name": "my-token", "value": "secret-token-value"}),
        )

        actx = _make_actx(client=cf_client)
        ctx = _make_ctx(actx)

        from kctl_cf.commands.tokens import create

        create(
            ctx,
            name="my-token",
            preset="dns-edit",
            zone="example.com",
            ttl_days=None,
            permission_group=None,
        )

        # Inspect the POST body that was sent
        requests = httpx_mock.get_requests(method="POST")
        assert len(requests) == 1
        body = json.loads(requests[0].content)
        assert body["name"] == "my-token"
        assert len(body["policies"]) == 1
        policy = body["policies"][0]
        assert policy["effect"] == "allow"
        assert policy["resources"] == {"com.cloudflare.api.account.zone.zone123": "*"}
        assert policy["permission_groups"] == [{"id": "pg-dns"}, {"id": "pg-zone"}]
        assert "expires_on" not in body

        out = capsys.readouterr().out
        assert "secret-token-value" in out
        assert "IMPORTANT: save this value now" in out

    def test_tokens_create_with_explicit_permission_groups(
        self,
        httpx_mock: HTTPXMock,
        cf_client: CloudflareClient,
    ) -> None:
        # Zone lookup still needed
        httpx_mock.add_response(
            method="GET",
            url="https://api.cloudflare.com/client/v4/zones?name=example.com",
            json=_cf_envelope([{"id": "zone123", "name": "example.com"}]),
        )
        # Token create (no permission_groups lookup expected)
        httpx_mock.add_response(
            method="POST",
            url="https://api.cloudflare.com/client/v4/user/tokens",
            json=_cf_envelope({"id": "tok2", "name": "custom", "value": "another-secret"}),
        )

        actx = _make_actx(client=cf_client, quiet=True)
        ctx = _make_ctx(actx)

        from kctl_cf.commands.tokens import create

        create(
            ctx,
            name="custom",
            preset=None,
            zone="example.com",
            ttl_days=None,
            permission_group=["pg1", "pg2"],
        )

        # The permission_groups endpoint MUST NOT have been called
        all_requests = httpx_mock.get_requests()
        pg_calls = [r for r in all_requests if r.url.path.endswith("/user/tokens/permission_groups")]
        assert pg_calls == []

        post_requests = httpx_mock.get_requests(method="POST")
        assert len(post_requests) == 1
        body = json.loads(post_requests[0].content)
        assert body["policies"][0]["permission_groups"] == [{"id": "pg1"}, {"id": "pg2"}]

    def test_tokens_create_with_ttl_days(
        self,
        httpx_mock: HTTPXMock,
        cf_client: CloudflareClient,
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            url="https://api.cloudflare.com/client/v4/zones?name=example.com",
            json=_cf_envelope([{"id": "zone123", "name": "example.com"}]),
        )
        self._register_perm_groups(httpx_mock)
        httpx_mock.add_response(
            method="POST",
            url="https://api.cloudflare.com/client/v4/user/tokens",
            json=_cf_envelope({"id": "tok3", "name": "ttl-token", "value": "ttl-secret"}),
        )

        actx = _make_actx(client=cf_client, quiet=True)
        ctx = _make_ctx(actx)

        from kctl_cf.commands.tokens import create

        before = datetime.now(timezone.utc)
        create(
            ctx,
            name="ttl-token",
            preset="dns-edit",
            zone="example.com",
            ttl_days=365,
            permission_group=None,
        )
        after = datetime.now(timezone.utc)

        post_requests = httpx_mock.get_requests(method="POST")
        assert len(post_requests) == 1
        body = json.loads(post_requests[0].content)
        assert "expires_on" in body
        # RFC3339 — parse and check it's ~365 days out
        expires_on = datetime.fromisoformat(body["expires_on"].replace("Z", "+00:00"))
        expected_low = before + timedelta(days=365) - timedelta(seconds=5)
        expected_high = after + timedelta(days=365) + timedelta(seconds=5)
        assert expected_low <= expires_on <= expected_high


# ---------------------------------------------------------------------------
# tokens delete
# ---------------------------------------------------------------------------


class TestTokensDelete:
    def test_tokens_delete_requires_confirmation(
        self,
        httpx_mock: HTTPXMock,
        cf_client: CloudflareClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # User refuses confirmation
        monkeypatch.setattr("typer.confirm", lambda *a, **kw: False)

        actx = _make_actx(client=cf_client)
        ctx = _make_ctx(actx)

        from kctl_cf.commands.tokens import delete_

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            delete_(ctx, token_id="tok_1", force=False)

        # No API call made — httpx_mock will fail at teardown if any unmatched mock
        # was registered, but we registered none — so we just assert no calls happened.
        assert httpx_mock.get_requests() == []

    def test_tokens_delete_with_force(
        self,
        httpx_mock: HTTPXMock,
        cf_client: CloudflareClient,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        httpx_mock.add_response(
            method="DELETE",
            url="https://api.cloudflare.com/client/v4/user/tokens/tok_1",
            json=_cf_envelope({"id": "tok_1"}),
        )

        actx = _make_actx(client=cf_client)
        ctx = _make_ctx(actx)

        from kctl_cf.commands.tokens import delete_

        delete_(ctx, token_id="tok_1", force=True)

        requests = httpx_mock.get_requests(method="DELETE")
        assert len(requests) == 1

        out = capsys.readouterr().out
        assert "deleted" in out.lower()


# ---------------------------------------------------------------------------
# tokens permission-groups
# ---------------------------------------------------------------------------


class TestTokensPermissionGroups:
    def test_tokens_permission_groups_filters(
        self,
        httpx_mock: HTTPXMock,
        cf_client: CloudflareClient,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            url="https://api.cloudflare.com/client/v4/user/tokens/permission_groups",
            json=_cf_envelope(
                [
                    {"id": "pg-dns", "name": "DNS Write"},
                    {"id": "pg-zone", "name": "Zone Read"},
                    {"id": "pg-dns-read", "name": "DNS Read"},
                    {"id": "pg-workers", "name": "Workers Scripts:Edit"},
                    {"id": "pg-pages", "name": "Pages:Edit"},
                ]
            ),
        )
        actx = _make_actx(json_mode=True, client=cf_client)
        ctx = _make_ctx(actx)

        from kctl_cf.commands.tokens import permission_groups

        permission_groups(ctx, filter_="dns")

        data = json.loads(capsys.readouterr().out)
        names = {row["name"] for row in data}
        # Case-insensitive substring match on "dns" → DNS Write + DNS Read only
        assert names == {"DNS Write", "DNS Read"}
