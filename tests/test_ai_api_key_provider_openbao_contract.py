"""Static contracts for provider-level API credentials in OpenBao."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = [
    "openrouter",
    "gemini",
    "alibaba",
    "openai",
    "anthropic",
    "grok",
    "deepseek",
    "zai",
    "nvidia",
    "moonshotai",
]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _read_defaults(filename: str) -> dict:
    return yaml.safe_load(_read(f"roles/openbao/defaults/main/{filename}"))


def test_provider_inventory_is_complete_and_single_sourced():
    names = _read_defaults("05c-terrakube-and-remaining-domain-names.yml")

    assert names["openbao_ai_api_key_providers"] == PROVIDERS

    derived = _read("roles/openbao/defaults/main/07a-derived-rollups-and-ttls.yml")
    assert "openbao_ai_api_key_policy_names" in derived
    assert "openbao_ai_api_key_policies" in derived
    assert "ai-api-key-\\1" in derived
    assert '"provider": "\\1"' in derived

    defaults_source = _read(
        "roles/openbao/defaults/main/05c-terrakube-and-remaining-domain-names.yml"
    )
    assert "OPENBAO_AI_API_KEY_MOUNT" in defaults_source
    assert "OPENBAO_AI_API_KEY_PATH_PREFIX" in defaults_source


def test_provider_policy_is_external_exact_and_read_only():
    template = _read("roles/openbao/templates/ai-api-key-provider-policy.hcl.j2")
    declarations = [
        line for line in template.splitlines() if line.startswith('path "')
    ]

    assert declarations == [
        'path "{{ openbao_ai_api_key_mount }}/data/{{ openbao_ai_api_key_path_prefix }}/{{ item.provider }}" {',
        'path "{{ openbao_ai_api_key_mount }}/metadata/{{ openbao_ai_api_key_path_prefix }}/{{ item.provider }}" {',
    ]
    assert 'capabilities = ["read"]' in template
    assert 'capabilities = ["read", "list"]' in template
    assert "create" not in template
    assert "update" not in template
    assert "ai/saas" not in template
    assert "openbao_kv_mount" not in template


def test_local_llm_attaches_the_derived_provider_policy_set():
    approles = _read("roles/openbao/defaults/main/07b-base-approles.yml")
    policies = _read("roles/openbao/defaults/main/07c-base-policies.yml")

    assert "[openbao_local_llm_policy_name] + openbao_ai_api_key_policy_names" in approles
    assert "+ openbao_ai_api_key_policies" in policies
    assert "ai_saas" not in approles
    assert "ai_saas" not in policies


def test_legacy_internal_provider_area_remains_denied():
    local_policy = _read("roles/openbao/templates/local-llm-policy.hcl.j2")

    assert 'path "{{ openbao_kv_mount }}/data/ai/saas/*"' in local_policy
    assert 'path "{{ openbao_kv_mount }}/metadata/ai/saas/*"' in local_policy
    assert local_policy.count('capabilities = ["deny"]') == 2
    assert "externally configured leaves" in local_policy


def test_ai_runner_uses_external_provider_leaves():
    runner_policy = _read("roles/openbao/templates/ai-runner-policy.hcl.j2")
    fetch_defaults = _read("roles/openbao_secrets/defaults/main.yml")

    assert "{{ openbao_ai_api_key_mount }}/data/{{ openbao_ai_api_key_path_prefix }}/{{ provider }}" in runner_policy
    assert "{{ openbao_ai_api_key_mount }}/metadata/{{ openbao_ai_api_key_path_prefix }}/{{ provider }}" in runner_policy
    assert "['anthropic', 'openai']" in runner_policy
    assert "ai/saas" not in runner_policy
    assert "ai/saas" not in fetch_defaults
