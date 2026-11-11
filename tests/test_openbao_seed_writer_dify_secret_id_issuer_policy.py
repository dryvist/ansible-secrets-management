"""The Dify agent SecretID issuer policy grants exact paths on each Dify agent AppRole."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from ansible.errors import AnsibleError
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

from openbao_reconcile_bounds_helpers import _templar, _trust, rendered_defaults

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles/openbao/defaults/main"
TEMPLATE_NAME = "seed-writer-dify-secret-id-issuer-policy.hcl.j2"
DECLARED_ROLES = (
    "agent-code-simplifier",
    "agent-ci-fixer",
    "agent-vikunja-clerk",
    "agent-vikunja-triage",
    "agent-docs-updater",
)
CAPABILITIES = {
    "role-id": ["read"],
    "secret-id": ["create", "update", "list"],
    "secret-id-accessor/lookup": ["update"],
    "secret-id-accessor/destroy": ["update"],
}
STANZA = re.compile(r'(?ms)^path "([^"]+)" \{\s*capabilities = (\[[^\]]+\])\s*\}')


def _yaml(name: str) -> dict:
    return yaml.safe_load((DEFAULTS / name).read_text(encoding="utf-8"))


def _render(role_names) -> str:
    """Render the real template the way the policy row does: lookup() with item."""
    loader = DataLoader()
    loader.set_basedir(str(ROOT / "roles" / "openbao"))
    templar = Templar(loader=loader)
    templar.available_variables = {
        "ansible_managed": "Ansible managed",
        "openbao_roster_agent_slug_pattern": _yaml("05k-roster-agents.yml")[
            "openbao_roster_agent_slug_pattern"
        ],
    }
    item = {"targets": list(role_names)}
    expression = "{{ lookup('template', '%s', template_vars={'item': %s}) }}" % (
        TEMPLATE_NAME,
        json.dumps(item),
    )
    return templar.template(trust_as_template(expression))


def _stanzas(policy: str) -> list[tuple[str, list[str]]]:
    return [(path, json.loads(caps)) for path, caps in STANZA.findall(policy)]


def _catalogs(rendered_defaults, dify_cidr: str, issuer_cidr: str):
    rendered_values, _, _ = rendered_defaults
    values = {}
    for path in sorted(DEFAULTS.glob("*.yml")):
        values.update(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    values.update(
        tofu_data={"agents": {}},
        ansible_managed="Ansible managed",
        llm_router_key_catalog_facts={"openbao_router_key_catalog": {}},
        openbao_management_cidrs=rendered_values["openbao_management_cidrs"],
        openbao_workstation_cidrs=rendered_values["openbao_workstation_cidrs"],
        openbao_ci_cidrs=rendered_values["openbao_ci_cidrs"],
        openbao_ssh_source_cidrs=rendered_values["openbao_ssh_source_cidrs"],
        openbao_sandbox_agent_cidrs=rendered_values["openbao_sandbox_agent_cidrs"],
        openbao_dify_agent_cidrs=dify_cidr,
        openbao_dify_secret_id_issuer_secret_id_cidr=issuer_cidr,
    )
    templar = _templar(_trust(values))
    approles = templar.template(_trust(values["openbao_approles"]))
    policies = templar.template(_trust(values["openbao_policies"]))
    values.update(openbao_approles=approles, openbao_policies=policies)
    templar = _templar(_trust(values))
    for name in (
        "openbao_approle_cidr_classes",
        "openbao_approle_cidr_class_map",
        "openbao_approle_secret_id_ttl_overrides",
        "openbao_secrets_domain_approle_names",
    ):
        values[name] = templar.template(_trust(values[name]))
    values["openbao_approle_cli_parameters"] = templar.template(
        _trust(values["openbao_approle_cli_parameters"])
    )
    return values, approles, policies


def test_declared_role_names_are_exactly_the_five_dify_agent_roles():
    names = _yaml("05l-dify-agent-identities.yml")
    declared = [
        value
        for key, value in names.items()
        if key.startswith("openbao_dify_agent_") and key.endswith("_approle_name")
    ]
    assert sorted(declared) == sorted(DECLARED_ROLES)


def test_rendered_policy_has_exactly_four_paths_per_declared_role():
    paths = [path for path, _ in _stanzas(_render(DECLARED_ROLES))]
    expected = {
        f"auth/approle/role/{role}/{kind}"
        for role in DECLARED_ROLES
        for kind in CAPABILITIES
    }
    assert len(paths) == 20
    assert len(set(paths)) == 20
    assert set(paths) == expected


def test_capabilities_per_path_kind_are_exact():
    for path, caps in _stanzas(_render(DECLARED_ROLES)):
        parts = path.split("/")
        assert parts[:3] == ["auth", "approle", "role"], path
        kind = "/".join(parts[4:])
        assert caps == CAPABILITIES[kind], path


def test_rendered_policy_has_no_wildcard_characters():
    for line in _render(DECLARED_ROLES).splitlines():
        assert "*" not in line and "+" not in line, line


def test_role_names_come_from_the_list_not_the_template():
    base = {path for path, _ in _stanzas(_render(DECLARED_ROLES))}
    extended = {
        path for path, _ in _stanzas(_render(DECLARED_ROLES + ("agent-extra-role",)))
    }
    added = extended - base
    assert added == {
        f"auth/approle/role/agent-extra-role/{kind}" for kind in CAPABILITIES
    }
    assert base <= extended


def test_empty_target_list_fails_validation():
    with pytest.raises(AnsibleError, match="must name at least one AppRole"):
        _render(())


@pytest.mark.parametrize(
    "name", ["agent+grant", "agent/grant", "agent*grant", "", "Agent-grant"]
)
def test_target_names_reject_values_outside_the_agent_slug_pattern(name):
    with pytest.raises(
        AnsibleError, match=r"item\.targets\[0\]"
    ) as error:
        _render((name,))
    if name:
        assert name not in str(error.value)


def test_target_name_matching_the_agent_slug_pattern_renders():
    assert {path for path, _ in _stanzas(_render(("agent-valid-2",)))} == {
        f"auth/approle/role/agent-valid-2/{kind}" for kind in CAPABILITIES
    }


def test_second_target_list_renders_disjoint_policy_paths():
    first = {path for path, _ in _stanzas(_render(("synthetic-target-a",)))}
    second = {path for path, _ in _stanzas(_render(("synthetic-target-b",)))}
    assert first == {f"auth/approle/role/synthetic-target-a/{kind}" for kind in CAPABILITIES}
    assert second == {f"auth/approle/role/synthetic-target-b/{kind}" for kind in CAPABILITIES}
    assert first.isdisjoint(second)


def test_issuer_policy_body_is_generated_from_targets_with_one_source():
    body = (ROOT / "roles/openbao/templates" / TEMPLATE_NAME).read_text(encoding="utf-8")
    assert "{% for name in item.targets %}" in body
    assert not [role for role in DECLARED_ROLES if role in body]
    literal_copies = [
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "roles").rglob("*")
        if path.is_file()
        and path.name != TEMPLATE_NAME
        and "/defaults/" not in path.as_posix()
        and "seed-writer-dify-secret-id-issuer" in path.read_text(encoding="utf-8", errors="ignore")
    ]
    assert literal_copies == []


def test_second_entry_in_the_seed_writer_list_becomes_a_second_approle(rendered_defaults):
    values, _approles, _policies = _catalogs(
        rendered_defaults, "192.0.2.10/32", "198.51.100.10/32"
    )
    synthetic = {
        "name": "synthetic-issuer-b",
        "token_policies": ["{{ openbao_ansible_converge_policy_name }}"],
        "token_type": "batch",
        "token_ttl": "{{ openbao_approle_token_ttl }}",
        "token_max_ttl": "{{ openbao_approle_token_ttl }}",
        "secret_id_num_uses": 0,
    }
    extended = dict(values)
    seed_writer_approles = _expand(values, "{{ openbao_seed_writer_approles }}")
    extended["openbao_seed_writer_approles"] = seed_writer_approles + [synthetic]
    names = _expand(extended, "{{ openbao_base_approles | map(attribute='name') | list }}")
    assert names.count("dify-agent-secret-id-issuer") == 1
    assert names.count("synthetic-issuer-b") == 1


def test_policy_is_registered_and_attached_only_to_the_issuer_approle(rendered_defaults):
    values, approles, policies = _catalogs(
        rendered_defaults, "192.0.2.10/32", "198.51.100.10/32"
    )
    policy_name = values["openbao_seed_writer_dify_secret_id_issuer_policy_name"]
    rows = [row for row in policies if row["name"] == policy_name]
    assert len(rows) == 1
    assert rows[0]["template"] == TEMPLATE_NAME

    seed_rows = approles
    writer_name = values["openbao_ansible_converge_writer_approle_name"]
    issuer_name = values["openbao_dify_secret_id_issuer_approle_name"]
    writers = [row for row in seed_rows if row["name"] == writer_name]
    assert len(writers) == 1
    assert policy_name not in writers[0]["token_policies"]
    issuers = [row for row in seed_rows if row["name"] == issuer_name]
    assert len(issuers) == 1
    assert issuers[0]["token_policies"] == [policy_name]
    for row in seed_rows:
        if row is not issuers[0]:
            assert policy_name not in row.get("token_policies", [])

    owners = {
        path.name
        for path in DEFAULTS.iterdir()
        if path.is_file()
        and "openbao_seed_writer_dify_secret_id_issuer_policy_name"
        in path.read_text(encoding="utf-8")
    }
    assert owners == {
        "05l-dify-agent-identities.yml",
        "07c-base-policies.yml",
        "07i-seed-writer-approles.yml",
    }


def test_dify_agent_approle_rows_stay_inert():
    text = (DEFAULTS / "07j-dify-agent-approles.yml").read_text(encoding="utf-8")
    inert = text.count("'manage_secret_id': false")
    entries = len(re.findall(r"'name':", text))
    assert inert == entries == len(DECLARED_ROLES)


def _expand(values, expression):
    return _templar(_trust(values)).template(trust_as_template(expression))


def test_issuer_approle_uses_its_dedicated_bound_cidr(rendered_defaults):
    issuer_cidr = "198.51.100.10/32"
    values, approles, _policies = _catalogs(
        rendered_defaults, "192.0.2.10/32", issuer_cidr
    )
    name = values["openbao_dify_secret_id_issuer_approle_name"]
    assert name == "dify-agent-secret-id-issuer"
    issuer_rows = [role for role in approles if role["name"] == name]
    assert len(issuer_rows) == 1
    assert issuer_rows[0]["secret_id_bound_cidrs"] == issuer_cidr

    parameters = values["openbao_approle_cli_parameters"][name]
    assert parameters["token_policies"] == "seed-writer-dify-secret-id-issuer"
    assert parameters["token_type"] == "batch"
    assert parameters["token_ttl"] == values["openbao_approle_token_ttl"]
    assert parameters["token_max_ttl"] == values["openbao_approle_token_ttl"]
    assert parameters["secret_id_num_uses"] == "0"
    assert parameters["secret_id_ttl"] == values["openbao_rotated_domain_secret_id_ttl"]

    assert parameters["secret_id_bound_cidrs"] == issuer_cidr
    assert parameters["token_bound_cidrs"] == issuer_cidr


def test_empty_issuer_bound_cidr_fails_with_dify_targets(rendered_defaults):
    with pytest.raises(
        AnsibleError,
        match="OPENBAO_DIFY_SECRET_ID_ISSUER_SECRET_ID_CIDR is empty",
    ):
        _catalogs(rendered_defaults, "192.0.2.10/32", "")


def test_issuer_bound_cidr_does_not_change_other_approle_bounds(rendered_defaults):
    values, approles, _policies = _catalogs(
        rendered_defaults, "192.0.2.10/32", "198.51.100.10/32"
    )
    issuer = values["openbao_dify_secret_id_issuer_approle_name"]
    previous_approles = [role for role in approles if role["name"] != issuer]
    previous_values = dict(values, openbao_approles=previous_approles)
    previous_parameters = _expand(
        previous_values,
        _yaml("08b-cidr-and-unlock.yml")["openbao_approle_cli_parameters"],
    )
    current_parameters = values["openbao_approle_cli_parameters"]
    bound_parameters = ("secret_id_bound_cidrs", "token_bound_cidrs")
    assert {
        name: {key: current_parameters[name][key] for key in bound_parameters}
        for name in current_parameters
        if name != issuer
    } == {
        name: {key: previous_parameters[name][key] for key in bound_parameters}
        for name in previous_parameters
    }


def test_issuer_approle_is_on_the_rotation_ttl_map_and_domain_list(rendered_defaults):
    values, _approles, _policies = _catalogs(
        rendered_defaults, "192.0.2.10/32", "198.51.100.10/32"
    )
    name = values["openbao_dify_secret_id_issuer_approle_name"]
    overrides = _expand(values, "{{ openbao_approle_secret_id_ttl_overrides }}")
    assert overrides[name] == values["openbao_rotated_domain_secret_id_ttl"]
    assert name in _expand(values, "{{ openbao_secrets_domain_approle_names }}")


def test_no_other_approle_carries_the_issuer_policy(rendered_defaults):
    values, _approles, _policies = _catalogs(
        rendered_defaults, "192.0.2.10/32", "198.51.100.10/32"
    )
    policy = values["openbao_seed_writer_dify_secret_id_issuer_policy_name"]
    name = values["openbao_dify_secret_id_issuer_approle_name"]
    carriers = sorted(
        role
        for role, parameters in values["openbao_approle_cli_parameters"].items()
        if policy in parameters["token_policies"].split(",")
    )
    assert carriers == [name]


def test_shared_writer_keeps_its_pre_issuer_policies(rendered_defaults):
    values, _approles, _policies = rendered_defaults
    writer = values["openbao_ansible_converge_writer_approle_name"]
    policies = values["openbao_approle_cli_parameters"][writer]["token_policies"].split(",")
    assert policies == [
        values["openbao_ansible_converge_policy_name"],
        values["openbao_authelia_signing_writer_policy_name"],
    ]
    assert values["openbao_seed_writer_dify_secret_id_issuer_policy_name"] not in policies


def test_issuer_catalog_entries_follow_dify_targets(rendered_defaults):
    issuer = "dify-agent-secret-id-issuer"
    policy_name = "seed-writer-dify-secret-id-issuer"
    values, approles, policies = _catalogs(rendered_defaults, "", "")
    assert issuer not in {role["name"] for role in approles}
    assert policy_name not in {policy["name"] for policy in policies}
    assert issuer not in values["openbao_secrets_domain_approle_names"]
    assert issuer not in values["openbao_approle_secret_id_ttl_overrides"]

    values, approles, policies = _catalogs(
        rendered_defaults, "192.0.2.10/32", "198.51.100.10/32"
    )
    assert issuer in {role["name"] for role in approles}
    assert policy_name in {policy["name"] for policy in policies}
    assert issuer in values["openbao_secrets_domain_approle_names"]
    assert issuer in values["openbao_approle_secret_id_ttl_overrides"]
