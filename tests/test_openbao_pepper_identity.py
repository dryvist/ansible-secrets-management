"""Pepper receives one guest-bound reader and a routinely seeded router key."""

import pytest
import yaml

from openbao_reconcile_bounds_helpers import (
    DEFAULTS,
    TEMPLATES,
    _capabilities,
    _render,
    _render_value,
    _stanzas,
)


@pytest.fixture
def pepper_defaults(monkeypatch):
    monkeypatch.setenv("OPENBAO_TERRAKUBE_NETWORK_WORKSPACE", "fixture-network")
    monkeypatch.setenv("OPENBAO_TERRAKUBE_AWS_WORKSPACE", "fixture-aws")
    values = {}
    for path in sorted(DEFAULTS.glob("*.yml")):
        values.update(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    values.update(
        ansible_managed="test fixture",
        openbao_platform_env={"OPENBAO_PEPPER_SECRET_ID_CIDR": "pepper-fixture-cidr"},
        llm_router_key_catalog_facts={"openbao_router_key_catalog": {}},
    )
    return values


def test_pepper_has_one_registered_read_only_policy(pepper_defaults):
    policies = _render_value(pepper_defaults, "{{ openbao_policies }}")
    pepper = [policy for policy in policies if policy["name"] == "pepper"]
    assert len(pepper) == 1
    stanzas = dict(_stanzas(_render(TEMPLATES / pepper[0]["template"], pepper_defaults)))
    assert list(stanzas) == ["secret/data/ai/pepper/*"]
    assert _capabilities(stanzas["secret/data/ai/pepper/*"]) == ["read"]


def test_pepper_approle_uses_only_its_guest_and_scheduled_rotation(pepper_defaults):
    roles = _render_value(pepper_defaults, "{{ openbao_approles }}")
    pepper = [role for role in roles if role["name"] == "pepper"]
    assert len(pepper) == 1
    assert pepper[0]["policy"] == "pepper"
    assert pepper[0]["manage_secret_id"] is False
    assert pepper[0]["secret_id_num_uses"] > 0
    parameters = _render_value(pepper_defaults, "{{ openbao_approle_cli_parameters }}")
    assert parameters["pepper"]["token_policies"] == "pepper"
    assert parameters["pepper"]["secret_id_bound_cidrs"] == "pepper-fixture-cidr"
    assert parameters["pepper"]["token_bound_cidrs"] == "pepper-fixture-cidr"
    ttls = _render_value(pepper_defaults, "{{ openbao_approle_secret_id_ttl_overrides }}")
    assert parameters["pepper"]["secret_id_ttl"] == ttls["hermes-private-agent"]
    assert ttls["pepper"] == pepper_defaults["openbao_rotated_domain_secret_id_ttl"]
    classes = _render_value(pepper_defaults, "{{ openbao_approle_class_map }}")
    assert classes["pepper"] == "trusted-agent-read"
    leaves = _render_value(pepper_defaults, "{{ openbao_roster_agent_ai_leaf_names }}")
    assert "pepper" in leaves


def test_pepper_approle_stays_dormant_without_its_cidr(pepper_defaults, monkeypatch):
    monkeypatch.delenv("OPENBAO_PEPPER_SECRET_ID_CIDR", raising=False)
    pepper_defaults["openbao_platform_env"] = {}
    roles = _render_value(pepper_defaults, "{{ openbao_approles }}")
    assert "pepper" not in [role["name"] for role in roles]


def test_shared_guest_defaults_preserve_the_private_hermes_bounds(pepper_defaults):
    pepper_defaults["openbao_platform_env"]["OPENBAO_HERMES_PRIVATE_AGENT_SECRET_ID_CIDR"] = "private-fixture-cidr"
    roles = _render_value(pepper_defaults, "{{ openbao_approles }}")
    hermes = next(role for role in roles if role["name"] == "hermes-private-agent")
    pepper = next(role for role in roles if role["name"] == "pepper")
    for field in ("secret_id_num_uses", "token_ttl", "token_max_ttl", "manage_secret_id"):
        assert hermes[field] == pepper[field]
    assert hermes["secret_id_bound_cidrs"] == "private-fixture-cidr"
    assert pepper["secret_id_bound_cidrs"] == "pepper-fixture-cidr"


def test_pepper_cidr_can_arrive_from_the_environment(pepper_defaults, monkeypatch):
    pepper_defaults["openbao_platform_env"] = {}
    monkeypatch.setenv("OPENBAO_PEPPER_SECRET_ID_CIDR", "fallback-fixture-cidr")
    roles = _render_value(pepper_defaults, "{{ openbao_pepper_approles }}")
    assert roles[0]["secret_id_bound_cidrs"] == "fallback-fixture-cidr"
