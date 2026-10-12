"""The MCP credential owner catalog matches rendered policy grants."""

from pathlib import Path
import re
import subprocess

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles/openbao/defaults/main/05k-roster-agents.yml"
TEMPLATES = ROOT / "roles/openbao/templates"
DEFAULTS_DATA = yaml.safe_load(DEFAULTS.read_text(encoding="utf-8"))
OWNER_GATED_TEMPLATES = (
    "hermes-policy.hcl.j2",
    "hermes-private-agent-policy.hcl.j2",
    "observability-policy.hcl.j2",
    "local-llm-policy.hcl.j2",
    "openbao-reconcile-policy.hcl.j2",
)
KV_MOUNTS = [
    {"path": "secret"},
    {"path": "secrets-external"},
    {"path": "config", "max_versions": 30},
]


def _render_policy(template, owned_slugs):
    environment = jinja2.Environment(undefined=jinja2.ChainableUndefined)
    environment.filters["comment"] = str
    environment.tests["match"] = lambda value, pattern: re.match(pattern, str(value)) is not None
    return environment.from_string(template).render(
        ansible_managed="",
        openbao_kv_mount="secret",
        openbao_kv_mounts=KV_MOUNTS,
        openbao_roster_owned_slug_names=owned_slugs,
        openbao_secrets_domain_approle_names=[],
        openbao_host_secret_zero_approle_names=[],
        openbao_ai_agents={"fixture-agent": {"owns": []}},
        openbao_roster_agent_policy_marker="# managed-by: openbao roster-agent ",
        item={"agent": "fixture-agent"},
    )


def _path_stanzas(rendered):
    return [
        (path, set(re.findall(r'"([^\"]+)"', capabilities)))
        for path, capabilities in re.findall(
            r'path\s+"([^"]+)"\s*\{\s*capabilities\s*=\s*\[([^]]*)\]',
            rendered,
            re.DOTALL,
        )
    ]


def _path_glob_covers(path_glob, path):
    pattern = re.escape(path_glob).replace(r"\*", ".*").replace(r"\+", "[^/]+")
    return re.fullmatch(pattern, path) is not None


def _grants_path(stanzas, target, ignored_capabilities):
    if any(path == target and "deny" in capabilities for path, capabilities in stanzas):
        return False
    return any(
        _path_glob_covers(path, target) and capabilities - ignored_capabilities
        for path, capabilities in stanzas
    )


def _grants_slug(stanzas, slug):
    exact_data_path = f"secret/data/ai/mcp/{slug}"
    exact_metadata_path = f"secret/metadata/ai/mcp/{slug}"
    return _grants_path(stanzas, exact_data_path, {"deny"}) or _grants_path(
        stanzas, exact_metadata_path, {"deny", "read", "list"}
    )


def test_mcp_credential_custodians_and_remaining_owners_match_rendered_grants():
    ownable_slugs = DEFAULTS_DATA["openbao_roster_agent_ownable_slugs"]
    custodians = DEFAULTS_DATA["openbao_mcp_credential_custodians"]
    declared_owners = DEFAULTS_DATA["openbao_mcp_credential_owners"]
    expected_grantors = {
        "splunk": {"ai-admin", "ai-rotate", "ansible-converge", "splunk-mcp-rotate"},
        "cribl": {"ai-admin", "ai-rotate"},
    }
    policy_templates = sorted(TEMPLATES.glob("*-policy.hcl.j2"))
    rendered = {
        template.name.removesuffix("-policy.hcl.j2"): _render_policy(
            template.read_bytes().decode("utf-8"), ownable_slugs
        )
        for template in policy_templates
    }

    assert set(declared_owners) == set(ownable_slugs)
    assert set(custodians) == set(ownable_slugs)
    grantors_by_slug = {}
    for slug in ownable_slugs:
        granting_policies = {
            policy
            for policy, body in rendered.items()
            if _grants_slug(_path_stanzas(body), slug)
        }
        grantors_by_slug[slug] = granting_policies
        assert granting_policies == set(custodians[slug]) | set(declared_owners[slug])
        assert granting_policies == expected_grantors[slug]
    assert grantors_by_slug == expected_grantors


def test_mcp_credential_audit_matches_wildcards_and_metadata_capability_tiers():
    # Rule (b): metadata read/list observers are allowed without credential access.
    assert _grants_slug([("secret/metadata/*", {"delete"})], "splunk")
    assert not _grants_slug([("secret/metadata/*", {"read", "list"})], "splunk")
    assert _grants_slug([("secret/data/ai/mcp/+", {"read"})], "splunk")
    assert _grants_slug([("secret/*", {"read"})], "splunk")


def test_empty_roster_keeps_owner_gated_policy_renders_byte_identical_to_develop():
    for name in OWNER_GATED_TEMPLATES:
        current = (TEMPLATES / name).read_bytes().decode("utf-8")
        original = subprocess.run(
            ["git", "show", f"origin/develop:roles/openbao/templates/{name}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout.decode("utf-8")

        assert _render_policy(current, []).encode("utf-8") == _render_policy(original, []).encode(
            "utf-8"
        ), name


def test_owned_consumer_policy_renders_do_not_leave_blank_lines_from_removed_grants():
    hermes = _render_policy((TEMPLATES / "hermes-policy.hcl.j2").read_text(), ["splunk"])
    hermes_private = _render_policy(
        (TEMPLATES / "hermes-private-agent-policy.hcl.j2").read_text(), ["splunk"]
    )
    observability = _render_policy(
        (TEMPLATES / "observability-policy.hcl.j2").read_text(), ["splunk"]
    )

    assert (
        'path "secret/metadata/ai/hermes" {\n  capabilities = ["read", "list"]\n}\n\n'
        'path "secret/data/ai/mcp/zammad"' in hermes
    )
    assert hermes_private.endswith(
        'path "secret/metadata/ai/hermes-private" {\n  capabilities = ["read", "list"]\n}'
    )
    assert (
        "# cross-domain grant to its canonical KV-v2 data leaf; no metadata or siblings.\n\n"
        "# OpenRouter usage/management key" in observability
    )
