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
CONSUMER_TEMPLATES = (
    "hermes-policy.hcl.j2",
    "hermes-private-agent-policy.hcl.j2",
    "observability-policy.hcl.j2",
    "local-llm-policy.hcl.j2",
)


def _render_policy(template, owned_slugs):
    environment = jinja2.Environment(undefined=jinja2.ChainableUndefined)
    environment.filters["comment"] = str
    environment.tests["match"] = lambda value, pattern: re.match(pattern, str(value)) is not None
    return environment.from_string(template).render(
        ansible_managed="",
        openbao_kv_mount="secret",
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


def _grants_slug(stanzas, slug):
    exact_data_path = f"secret/data/ai/mcp/{slug}"
    grant_paths = {
        exact_data_path,
        "secret/data/ai/mcp/*",
        "secret/data/ai/*",
    }
    has_deny = any(path == exact_data_path and "deny" in capabilities for path, capabilities in stanzas)
    return not has_deny and any(
        path in grant_paths and any(capability != "deny" for capability in capabilities)
        for path, capabilities in stanzas
    )


def test_mcp_credential_custodians_and_remaining_owners_match_rendered_grants():
    ownable_slugs = DEFAULTS_DATA["openbao_roster_agent_ownable_slugs"]
    custodians = DEFAULTS_DATA["openbao_mcp_credential_custodians"]
    declared_owners = DEFAULTS_DATA["openbao_mcp_credential_owners"]
    policy_templates = sorted(TEMPLATES.glob("*-policy.hcl.j2"))
    rendered = {
        template.name.removesuffix("-policy.hcl.j2"): _render_policy(
            template.read_bytes().decode("utf-8"), ownable_slugs
        )
        for template in policy_templates
    }

    assert set(declared_owners) == set(ownable_slugs)
    assert set(custodians) == set(ownable_slugs)
    for slug in ownable_slugs:
        granting_policies = {
            policy
            for policy, body in rendered.items()
            if _grants_slug(_path_stanzas(body), slug)
        }
        assert granting_policies == set(custodians[slug]) | set(declared_owners[slug])


def test_empty_roster_keeps_consumer_policy_renders_byte_identical_to_develop():
    for name in CONSUMER_TEMPLATES:
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
