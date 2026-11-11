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
POLICY_NAME_VARIABLE = "{{ openbao_seed_writer_dify_secret_id_issuer_policy_name }}"
WRITER_NAME_VARIABLE = "{{ openbao_ansible_converge_writer_approle_name }}"
ISSUER_NAME_VARIABLE = "{{ openbao_dify_secret_id_issuer_approle_name }}"
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
    templar.available_variables = {"ansible_managed": "Ansible managed"}
    item = {"targets": list(role_names)}
    expression = "{{ lookup('template', '%s', template_vars={'item': %s}) }}" % (
        TEMPLATE_NAME,
        json.dumps(item),
    )
    return templar.template(trust_as_template(expression))


def _stanzas(policy: str) -> list[tuple[str, list[str]]]:
    return [(path, json.loads(caps)) for path, caps in STANZA.findall(policy)]


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
    values, _approles, _policies = rendered_defaults
    synthetic = {
        "name": "synthetic-issuer-b",
        "token_policies": ["{{ openbao_ansible_converge_policy_name }}"],
        "token_type": "batch",
        "token_ttl": "{{ openbao_approle_token_ttl }}",
        "token_max_ttl": "{{ openbao_approle_token_ttl }}",
        "secret_id_num_uses": 0,
    }
    extended = dict(values)
    extended["openbao_seed_writer_approles"] = values["openbao_seed_writer_approles"] + [synthetic]
    names = _expand(extended, "{{ openbao_base_approles | map(attribute='name') | list }}")
    assert names.count("dify-agent-secret-id-issuer") == 1
    assert names.count("synthetic-issuer-b") == 1


def test_policy_is_registered_and_attached_only_to_the_issuer_approle():
    static_rows = _yaml("07c-base-policies.yml")["openbao_base_policies_static"]
    rows = [row for row in static_rows if row["name"] == POLICY_NAME_VARIABLE]
    assert len(rows) == 1
    assert rows[0]["template"] == TEMPLATE_NAME

    seed_rows = _yaml("07i-seed-writer-approles.yml")["openbao_seed_writer_approles"]
    writers = [row for row in seed_rows if row["name"] == WRITER_NAME_VARIABLE]
    assert len(writers) == 1
    assert POLICY_NAME_VARIABLE not in writers[0]["token_policies"]
    issuers = [row for row in seed_rows if row["name"] == ISSUER_NAME_VARIABLE]
    assert len(issuers) == 1
    assert issuers[0]["token_policies"] == [POLICY_NAME_VARIABLE]
    for row in seed_rows:
        if row is not issuers[0]:
            assert POLICY_NAME_VARIABLE not in row.get("token_policies", [])

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


def test_issuer_approle_is_a_single_policy_batch_login_on_the_machine_class(rendered_defaults):
    values, approles, _policies = rendered_defaults
    name = values["openbao_dify_secret_id_issuer_approle_name"]
    writer = values["openbao_ansible_converge_writer_approle_name"]
    assert name == "dify-agent-secret-id-issuer"
    assert [role["name"] for role in approles].count(name) == 1

    parameters = values["openbao_approle_cli_parameters"][name]
    assert parameters["token_policies"] == "seed-writer-dify-secret-id-issuer"
    assert parameters["token_type"] == "batch"
    assert parameters["token_ttl"] == values["openbao_approle_token_ttl"]
    assert parameters["token_max_ttl"] == values["openbao_approle_token_ttl"]
    assert parameters["secret_id_num_uses"] == "0"
    assert parameters["secret_id_ttl"] == values["openbao_rotated_domain_secret_id_ttl"]

    classes = values["openbao_approle_cidr_class_map"]
    assert classes[name] == classes[writer] == "machine"
    assert parameters["secret_id_bound_cidrs"] == values["openbao_management_cidrs"]
    assert parameters["token_bound_cidrs"] == values["openbao_management_cidrs"]


def test_issuer_approle_is_on_the_rotation_ttl_map_and_domain_list(rendered_defaults):
    values, _approles, _policies = rendered_defaults
    name = values["openbao_dify_secret_id_issuer_approle_name"]
    overrides = _expand(values, "{{ openbao_approle_secret_id_ttl_overrides }}")
    assert overrides[name] == values["openbao_rotated_domain_secret_id_ttl"]
    assert name in _expand(values, "{{ openbao_secrets_domain_approle_names }}")


def test_no_other_approle_carries_the_issuer_policy(rendered_defaults):
    values, _approles, _policies = rendered_defaults
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
