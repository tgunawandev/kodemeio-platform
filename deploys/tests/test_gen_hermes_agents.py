"""Multiple Hermes agents per tenant.

FRIDAY (superuser/engineering) and JARVIS (business/helpdesk) both serve tenant
`tpp`, but gen_hermes hardcoded `{code}-infra-hermes` everywhere, so a second
agent could not even be expressed — there was no manifest to deploy.
"""

from __future__ import annotations

import pytest
from generate import gen_hermes_agents

TENANT = {"code": "tpp", "name": "Pakerti", "short_name": "TPP", "domain": "idtpp.com"}
INBOUND = {
    "telegram": {"enabled": False},
    "mattermost": {"enabled": True, "url": "https://mm.idtpp.com"},
}


def test_a_tenant_without_an_agents_list_still_yields_one_agent():
    """Backwards compatibility: every existing tenant file must keep working."""
    hermes = {"enabled": True, "server": "tpp-prod-04", "inbound": INBOUND}
    out = gen_hermes_agents(TENANT, hermes, "production")
    assert len(out) == 1
    assert out[0][0] == "tpp-infra-hermes.yaml"


def test_two_agents_produce_two_distinct_manifests():
    hermes = {
        "enabled": True,
        "server": "tpp-prod-04",
        "inbound": INBOUND,
        "agents": [
            {"edition": "superuser"},
            {"name": "jarvis", "edition": "business"},
        ],
    }
    out = gen_hermes_agents(TENANT, hermes, "production")
    assert [o[0] for o in out] == ["tpp-infra-hermes.yaml", "tpp-infra-hermes-jarvis.yaml"]


def test_each_agent_gets_its_own_container_prefix():
    hermes = {
        "enabled": True, "server": "tpp-prod-04", "inbound": INBOUND,
        "agents": [{"edition": "superuser"}, {"name": "jarvis", "edition": "business"}],
    }
    out = gen_hermes_agents(TENANT, hermes, "production")
    assert "HERMES_CONTAINER_PREFIX: tpp-infra-hermes\n" in out[0][1]
    assert "HERMES_CONTAINER_PREFIX: tpp-infra-hermes-jarvis" in out[1][1]


def test_an_agent_inherits_shared_config_and_overrides_its_own():
    hermes = {
        "enabled": True, "server": "tpp-prod-04", "inbound": INBOUND,
        "edition": "superuser",
        "agents": [{}, {"name": "jarvis", "edition": "business"}],
    }
    out = gen_hermes_agents(TENANT, hermes, "production")
    assert "HERMES_EDITION: superuser" in out[0][1]
    assert "HERMES_EDITION: business" in out[1][1]
    # server was declared once, at the parent level, and both inherit it
    assert "server: tpp-prod-04" in out[0][1]
    assert "server: tpp-prod-04" in out[1][1]


def test_env_example_filenames_are_distinct_per_agent():
    hermes = {
        "enabled": True, "server": "tpp-prod-04", "inbound": INBOUND,
        "agents": [{}, {"name": "jarvis", "edition": "business"}],
    }
    out = gen_hermes_agents(TENANT, hermes, "production")
    names = [o[2] for o in out]
    assert names == [".env.tpp-infra-hermes.example", ".env.tpp-infra-hermes-jarvis.example"]
    assert len(set(names)) == 2, "agents must not share an env file"


def test_two_unnamed_agents_are_refused_rather_than_silently_colliding():
    hermes = {
        "enabled": True, "server": "tpp-prod-04", "inbound": INBOUND,
        "agents": [{}, {}],
    }
    with pytest.raises(ValueError, match="unique"):
        gen_hermes_agents(TENANT, hermes, "production")
