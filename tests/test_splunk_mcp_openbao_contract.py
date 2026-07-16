"""Static contract checks for the shared Splunk MCP OpenBao path."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DATA_PATH = 'path "{{ openbao_kv_mount }}/data/ai/mcp/splunk"'


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_hermes_can_read_own_bundle_and_shared_splunk_secret():
    policy = _read("roles/openbao/templates/hermes-policy.hcl.j2")

    assert 'path "{{ openbao_kv_mount }}/data/ai/hermes"' in policy
    assert CANONICAL_DATA_PATH in policy
    assert 'capabilities = ["read"]' in policy
    assert "/data/ai/*" not in policy


def test_default_ai_policies_can_read_shared_splunk_secret():
    # ai-readonly is now a composed actor role (#931): it attaches the read-ai
    # capability leaf, which the kv-capability template renders as read on
    # secret/data/ai/* — covering ai/mcp/splunk.
    defaults = yaml.safe_load(_read("roles/openbao/defaults/main.yml"))
    leaf = _read("roles/openbao/templates/kv-capability-policy.hcl.j2")
    local_llm = _read("roles/openbao/templates/local-llm-policy.hcl.j2")

    assert "ai" in defaults["openbao_ai_domains"]
    assert 'path "{{ openbao_kv_mount }}/data/{{ item.subtree }}/*"' in leaf
    assert 'capabilities = ["read"]' in leaf
    assert 'path "{{ openbao_kv_mount }}/data/ai/*"' in local_llm
    assert 'capabilities = ["read"]' in local_llm


def test_unrelated_domain_identity_cannot_read_shared_splunk_secret():
    policy = _read("roles/openbao/templates/observability-policy.hcl.j2")

    assert "ai/mcp/splunk" not in policy
    assert "/data/ai/" not in policy


def test_splunk_publisher_has_only_exact_transitional_write_paths():
    policy = _read("roles/openbao/templates/hermes-write-policy.hcl.j2")

    assert CANONICAL_DATA_PATH in policy
    assert 'path "{{ openbao_kv_mount }}/data/ai/hermes"' in policy
    assert 'capabilities = ["create", "update", "read"]' in policy
    assert "/data/ai/*" not in policy


def test_local_llm_fetch_contract_merges_canonical_splunk_fields():
    defaults = yaml.safe_load(
        _read("roles/openbao_secrets/defaults/main.yml")
    )
    local_llm = next(
        domain
        for domain in defaults["openbao_secrets_domains"]
        if domain["name"] == "local-llm"
    )

    assert "ai/hermes" in local_llm["paths"]
    assert "ai/mcp/splunk" in local_llm["paths"]


def test_hermes_inventory_keeps_rendered_environment_interface():
    inventory = yaml.safe_load(_read("inventory/group_vars/hermes_agent_group.yml"))

    assert "bao_local_llm_secrets.SPLUNK_MCP_URL" in inventory.get(
        "hermes_agent_splunk_mcp_url", ""
    )
    assert "bao_local_llm_secrets.SPLUNK_MCP_TOKEN" in inventory.get(
        "hermes_agent_splunk_mcp_token", ""
    )
