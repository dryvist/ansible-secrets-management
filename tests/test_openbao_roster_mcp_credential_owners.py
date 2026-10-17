"""Roster-owned MCP credential access is enforced across attached policies."""

from pathlib import Path
import re
import subprocess

import jinja2
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles/openbao/defaults/main"
TEMPLATES = ROOT / "roles/openbao/templates"
KV_MOUNTS = [
    {"path": "secret"},
    {"path": "secrets-external"},
    {"path": "config", "max_versions": 30},
]
FIXTURE_ROSTER = {
    "splunk-heimdall": {"container": "example", "hostname": "example.com", "display": "Splunk", "purpose": "fixture", "owns": ["splunk"]},
    "cribl-bifrost": {"container": "example", "hostname": "example.com", "display": "Cribl", "purpose": "fixture", "owns": ["cribl"]},
    "fixture-observer": {"container": "example", "hostname": "example.com", "display": "Observer", "purpose": "fixture", "owns": []},
}
SHARED_POLICY_TEMPLATES = (
    "local-llm-policy.hcl.j2",
    "openbao-reconcile-policy.hcl.j2",
)
OWNER_CONSUMER_TEMPLATES = (
    "hermes-policy.hcl.j2",
    "hermes-private-agent-policy.hcl.j2",
    "observability-policy.hcl.j2",
)
LEGACY_SHARED_TEMPLATES = OWNER_CONSUMER_TEMPLATES + SHARED_POLICY_TEMPLATES
# These live-only policies have no local templates. OpenBao's built-in
# `default` policy is also attached unless token_no_default_policy is true.
# Treat these policies as granting nothing on ai/mcp in this local audit.
RENDERLESS_POLICY_NAMES = {"vikunja", "terraform", "media-rotate"}
POLICY_STANZA = re.compile(
    r'path\s+"([^"]+)"\s*\{\s*capabilities\s*=\s*\[([^]]*)\]', re.DOTALL
)


@pytest.fixture(autouse=True)
def _render_only_inputs(monkeypatch):
    # Non-secret placeholders satisfy required defaults while keeping these
    # offline policy renders independent of the operator's environment.
    monkeypatch.setenv("OPENBAO_TERRAKUBE_NETWORK_WORKSPACE", "fixture-network")
    monkeypatch.setenv("OPENBAO_TERRAKUBE_AWS_WORKSPACE", "fixture-aws")
    monkeypatch.setenv("OPENBAO_AI_API_KEY_MOUNT", "secret")
    monkeypatch.setenv("OPENBAO_AI_API_KEY_PATH_PREFIX", "fixture-provider-keys")
    monkeypatch.setenv("PROXMOX_SUBDOMAIN", "example.com")


def _git_text(ref, path):
    return subprocess.run(
        ["git", "show", f"{ref}:{path.relative_to(ROOT).as_posix()}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _default_paths(ref=None):
    if ref is None:
        return sorted(DEFAULTS.glob("*.yml"))
    names = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", ref, "roles/openbao/defaults/main"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return [ROOT / name for name in names if name.endswith(".yml")]


def _defaults_context(roster, ref=None):
    values = {}
    for path in _default_paths(ref):
        source = _git_text(ref, path) if ref is not None else path.read_text(encoding="utf-8")
        values.update(yaml.safe_load(source) or {})
    values["tofu_data"] = {"agents": roster}
    values["ansible_managed"] = "Ansible managed"
    values["llm_router_key_catalog_facts"] = {"openbao_router_key_catalog": {}}
    return {name: _trust_values(value) for name, value in values.items()}


def _trust_values(value):
    if isinstance(value, str):
        return trust_as_template(value)
    if isinstance(value, list):
        return [_trust_values(item) for item in value]
    if isinstance(value, dict):
        return {name: _trust_values(item) for name, item in value.items()}
    return value


def _templar(values):
    loader = DataLoader()
    loader.set_basedir(str(ROOT / "roles/openbao"))
    templar = Templar(loader=loader)
    templar.available_variables = values
    return templar


def _resolve_lists(roster, ref=None):
    values = _defaults_context(roster, ref)
    templar = _templar(values)
    approles = templar.template(trust_as_template(values["openbao_approles"]))
    policies = templar.template(trust_as_template(values["openbao_policies"]))
    for name in (
        "openbao_roster_owned_slug_names",
        "openbao_roster_owned_mcp_deny_policies",
        "openbao_roster_owned_mcp_deny_retired_names",
        "openbao_policies_without_inputs",
    ):
        if name in values:
            values[name] = templar.template(trust_as_template(values[name]))
    return values, approles, policies


def _render_declared_policies(values, approles, policies):
    # Match the role's Templar render with the per-policy `item` context.
    rendered = {}
    for item in policies:
        source = (TEMPLATES / item["template"]).read_text(encoding="utf-8")
        context = {
            **values,
            "openbao_approles": approles,
            "openbao_policies": policies,
            "openbao_ai_api_key_mount": "secret",
            "openbao_ai_api_key_path_prefix": "fixture-provider-keys",
            "item": item,
        }
        try:
            rendered[item["name"]] = _templar(context).template(
                trust_as_template(source)
            ).strip()
        except Exception as exc:
            raise AssertionError(
                f"failed rendering {item['name']} from {item['template']}"
            ) from exc
    return rendered


def _render_template(source, values, extra=None):
    return _templar({**values, **(extra or {})}).template(trust_as_template(source))


def _render_owner_wrapper(source, owned_slugs):
    environment = jinja2.Environment(undefined=jinja2.ChainableUndefined)
    environment.filters["comment"] = str
    environment.tests["match"] = lambda value, pattern: re.match(pattern, str(value)) is not None
    return environment.from_string(source).render(
        ansible_managed="",
        openbao_kv_mount="secret",
        openbao_kv_mounts=KV_MOUNTS,
        openbao_transit_mount="transit",
        openbao_tofu_state_transit_key="tofu-state",
        openbao_roster_owned_slug_names=owned_slugs,
        openbao_secrets_domain_approle_names=[],
        openbao_host_secret_zero_approle_names=[],
        openbao_ai_agents=FIXTURE_ROSTER,
        openbao_roster_agent_policy_marker="# managed-by: openbao roster-agent ",
        item={"agent": "fixture-observer"},
    )


def _without_reconcile_transit_grants(name, source):
    if name != "openbao-reconcile-policy.hcl.j2":
        return source
    # The transit grants are asserted separately (tests/test_openbao_transit_state_key.py);
    # parity ignores them, comments and blank lines, and compares every other stanza.
    source = re.sub(r"(?m)^\s*#.*\n", "", source)
    source = re.sub(r'path\s+"[^"]*transit[^"]*"\s*\{[^}]*\}\s*', "", source)
    return re.sub(r"\n\s*\n", "\n", source)

def _stanzas(source):
    return [
        (match.group(1), set(re.findall(r'"([^\"]+)"', match.group(2))))
        for match in POLICY_STANZA.finditer(source)
    ]


def _path_glob_covers(path_glob, path):
    pattern = re.escape(path_glob).replace(r"\*", ".*").replace(r"\+", "[^/]+")
    return re.fullmatch(pattern, path) is not None


def _matching_capabilities(policy_stanzas, target):
    return [
        capabilities
        for path, capabilities in policy_stanzas
        if _path_glob_covers(path, target)
    ]


def _is_access_grant(target, capabilities):
    grants = capabilities - {"deny"}
    if "/metadata/" in target:
        grants -= {"read", "list"}
    return bool(grants)


def _effective_path_access(attached_stanzas, target):
    capabilities = [
        item
        for stanzas in attached_stanzas.values()
        for item in _matching_capabilities(stanzas, target)
    ]
    denied = any("deny" in item for item in capabilities)
    granted = any(_is_access_grant(target, item) for item in capabilities)
    return granted and not denied


def _policy_names(role):
    names = role.get("token_policies")
    if names is None:
        names = [role["policy"]] if "policy" in role else []
    else:
        names = list(names)
    if not role.get("token_no_default_policy", False):
        names.append("default")
    return names


def _role_access_audit(roster=FIXTURE_ROSTER):
    values, approles, policies = _resolve_lists(roster)
    rendered = _render_declared_policies(values, approles, policies)
    stanzas_by_policy = {name: _stanzas(body) for name, body in rendered.items()}
    attached_by_role = {role["name"]: _policy_names(role) for role in approles}
    attached_stanzas_by_role = {
        role_name: {
            policy_name: stanzas_by_policy.get(policy_name, [])
            for policy_name in policy_names
        }
        for role_name, policy_names in attached_by_role.items()
    }
    return values, approles, policies, rendered, attached_by_role, attached_stanzas_by_role


def _slug_targets(slug):
    return (
        f"secret/data/ai/mcp/{slug}",
        f"secret/metadata/ai/mcp/{slug}",
    )


def _effective_holders(attached_stanzas_by_role, slug):
    data_path, metadata_path = _slug_targets(slug)
    return {
        role_name
        for role_name, policies in attached_stanzas_by_role.items()
        if _effective_path_access(policies, data_path)
        or _effective_path_access(policies, metadata_path)
    }


def _effective_grant_in_policy(stanzas, target):
    return any(
        _is_access_grant(target, capabilities)
        for capabilities in _matching_capabilities(stanzas, target)
    )


def _shadow_rows(attached_stanzas_by_role, custodians, slugs):
    custodian_shadows = []
    allowed_non_custodian_shadows = set()
    for slug in slugs:
        custodian_policies = set(custodians[slug])
        targets = _slug_targets(slug)
        for role_name, policies in attached_stanzas_by_role.items():
            all_caps = {
                target: [
                    (policy_name, capabilities)
                    for policy_name, stanzas in policies.items()
                    for capabilities in _matching_capabilities(stanzas, target)
                ]
                for target in targets
            }
            for target, entries in all_caps.items():
                denies = [policy for policy, caps in entries if "deny" in caps]
                if not denies:
                    continue
                custodian_grants = [
                    policy
                    for policy, caps in entries
                    if policy in custodian_policies and _is_access_grant(target, caps)
                ]
                for deny_policy in denies:
                    for grant_policy in custodian_grants:
                        custodian_shadows.append(
                            (role_name, target, deny_policy, grant_policy)
                        )
                for grant_policy, caps in entries:
                    if (
                        grant_policy not in custodian_policies
                        and _is_access_grant(target, caps)
                    ):
                        allowed_non_custodian_shadows.add(
                            (role_name, target, grant_policy)
                        )
    return custodian_shadows, sorted(allowed_non_custodian_shadows)


def test_mcp_credential_effective_holders_match_approle_grants():
    values, approles, policies, rendered, attached, attached_stanzas = _role_access_audit()
    ownable_slugs = values["openbao_roster_agent_ownable_slugs"]
    custodians = values["openbao_mcp_credential_custodians"]
    session_holders = values["openbao_mcp_credential_session_holders"]
    assert len(approles) == len({role["name"] for role in approles})
    assert len(policies) == len({policy["name"] for policy in policies})
    assert set(custodians) == set(ownable_slugs)
    assert set(session_holders) == set(ownable_slugs)

    fixture_owners = {
        slug: {
            name
            for name, definition in FIXTURE_ROSTER.items()
            if slug in definition["owns"]
        }
        for slug in ownable_slugs
    }
    effective = {}
    for slug in ownable_slugs:
        custodian_policies = set(custodians[slug])
        custodian_carriers = {
            role_name
            for role_name, policy_names in attached.items()
            if custodian_policies.intersection(policy_names)
        }
        expected = custodian_carriers | fixture_owners[slug] | set(session_holders[slug])
        actual = _effective_holders(attached_stanzas, slug)
        effective[slug] = actual
        unexpected = {
            role_name: sorted(attached[role_name])
            for role_name in actual - expected
        }
        missing = sorted(expected - actual)
        assert actual == expected, (
            f"{slug}: unexpected holders with attached policies={unexpected}; "
            f"expected holders missing effective grants={missing}; "
            f"custodian carriers={sorted(custodian_carriers)}"
        )

    for slug, owner_agent in (("splunk", "splunk-heimdall"), ("cribl", "cribl-bifrost")):
        assert fixture_owners[slug] == {owner_agent}
        assert owner_agent in effective[slug]

    explicitly_denied = {
        values["openbao_hermes_approle_name"],
        values["openbao_hermes_private_agent_approle_name"],
        values["openbao_ai_donna_approle_name"],
        values["openbao_local_llm_approle_name"],
        values["openbao_observability_approle_name"],
        "fixture-observer",
    }
    for slug in ownable_slugs:
        assert explicitly_denied.isdisjoint(effective[slug])

    local_llm = values["openbao_local_llm_approle_name"]
    all_custodian_policies = set().union(*(set(items) for items in custodians.values()))
    assert not all_custodian_policies.intersection(attached[local_llm])
    deny_policy = values["openbao_roster_owned_mcp_deny_policy_name"]
    deny_policy_carriers = [
        name for name, names in attached.items() if deny_policy in names
    ]
    assert deny_policy_carriers == [local_llm]
    assert all(
        not all_custodian_policies.intersection(attached[name])
        for name in deny_policy_carriers
    )

    custodian_shadows, allowed_non_custodian_shadows = _shadow_rows(
        attached_stanzas, custodians, ownable_slugs
    )
    assert not custodian_shadows, custodian_shadows
    assert allowed_non_custodian_shadows == [
        (local_llm, "secret/data/ai/mcp/cribl", "local-llm"),
        (local_llm, "secret/data/ai/mcp/splunk", "local-llm"),
    ]

    template_less = {
        policy_name
        for policy_names in attached.values()
        for policy_name in policy_names
        if policy_name != "default" and policy_name not in rendered
    }
    # Policies whose inputs are unset are undeclared, so they have no render here.
    assert template_less == RENDERLESS_POLICY_NAMES | set(
        values["openbao_policies_without_inputs"]
    )
    assert {
        (path, frozenset(capabilities)) for path, capabilities in _stanzas(rendered[deny_policy])
    } == {
        (f"secret/data/ai/mcp/{slug}", frozenset({"deny"})) for slug in ownable_slugs
    } | {
        (f"secret/metadata/ai/mcp/{slug}", frozenset({"deny"})) for slug in ownable_slugs
    }


def test_empty_roster_keeps_shared_policy_and_declared_lists_identical_to_develop():
    values, approles, policies = _resolve_lists({})
    _, develop_approles, develop_policies = _resolve_lists({}, ref="origin/develop")
    assert approles == develop_approles
    assert policies == develop_policies

    for name in LEGACY_SHARED_TEMPLATES:
        current = _render_owner_wrapper(
            (TEMPLATES / name).read_text(encoding="utf-8"), []
        )
        original = _render_owner_wrapper(_git_text("origin/develop", TEMPLATES / name), [])
        current = _without_reconcile_transit_grants(name, current)
        original = _without_reconcile_transit_grants(name, original)
        assert current.encode("utf-8") == original.encode("utf-8"), name

    assert values["openbao_roster_owned_mcp_deny_policies"] == []
    assert values["openbao_roster_owned_mcp_deny_retired_names"] == [
        values["openbao_roster_owned_mcp_deny_policy_name"]
    ]
    assert values["openbao_roster_owned_mcp_deny_policy_name"] not in {
        policy["name"] for policy in policies
    }
    local_llm = values["openbao_local_llm_approle_name"]
    local_llm_role = next(role for role in approles if role["name"] == local_llm)
    assert values["openbao_roster_owned_mcp_deny_policy_name"] not in _policy_names(
        local_llm_role
    )
    empty_deny = _render_template(
        (TEMPLATES / "roster-owned-mcp-deny-policy.hcl.j2").read_text(encoding="utf-8"),
        values,
        {"openbao_roster_owned_slug_names": []},
    )
    assert not _stanzas(empty_deny)


def test_shared_policies_remain_develop_identical_for_owned_roster():
    values, _, _ = _resolve_lists(FIXTURE_ROSTER)
    for name in SHARED_POLICY_TEMPLATES:
        current = _render_template((TEMPLATES / name).read_text(encoding="utf-8"), values)
        original = _render_template(_git_text("origin/develop", TEMPLATES / name), values)
        current = _without_reconcile_transit_grants(name, current)
        original = _without_reconcile_transit_grants(name, original)
        assert current.encode("utf-8") == original.encode("utf-8"), name


def test_owned_consumer_policy_renders_do_not_leave_blank_lines_from_removed_grants():
    hermes = _render_owner_wrapper(
        (TEMPLATES / "hermes-policy.hcl.j2").read_text(), ["splunk"]
    )
    hermes_private = _render_owner_wrapper(
        (TEMPLATES / "hermes-private-agent-policy.hcl.j2").read_text(), ["splunk"]
    )
    observability = _render_owner_wrapper(
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


def test_observability_policy_grants_start_their_own_line_for_every_owner_set():
    values, _, _ = _resolve_lists(FIXTURE_ROSTER)
    source = (TEMPLATES / "observability-policy.hcl.j2").read_text(encoding="utf-8")

    for owned in ([], ["splunk"]):
        rendered = _render_template(source, values, {"openbao_roster_owned_slug_names": owned})
        swallowed = [
            line for line in rendered.splitlines() if line.startswith("#") and 'path "' in line
        ]
        assert not swallowed, owned
        assert ('\npath "secret/data/ai/mcp/splunk" {' in rendered) == (not owned)
