"""The Dify agent SecretID issuer policy grants exact paths on each Dify agent AppRole."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles/openbao/defaults/main"
TEMPLATE_NAME = "seed-writer-dify-secret-id-issuer-policy.hcl.j2"
POLICY_NAME_VARIABLE = "{{ openbao_seed_writer_dify_secret_id_issuer_policy_name }}"
WRITER_NAME_VARIABLE = "{{ openbao_ansible_converge_writer_approle_name }}"
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
    """Render the real template through lookup(), as the role's own render does."""
    loader = DataLoader()
    loader.set_basedir(str(ROOT / "roles" / "openbao"))
    templar = Templar(loader=loader)
    templar.available_variables = {
        "openbao_dify_agent_approles": [{"name": name} for name in role_names],
        "ansible_managed": "Ansible managed",
    }
    expression = "{{ lookup('template', '%s') }}" % TEMPLATE_NAME
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


def test_empty_role_list_renders_no_path_stanza():
    policy = _render(())
    assert not re.search(r"(?m)^path ", policy)
    assert _stanzas(policy) == []


def test_policy_is_registered_and_attached_only_to_the_seed_writer():
    static_rows = _yaml("07c-base-policies.yml")["openbao_base_policies_static"]
    rows = [row for row in static_rows if row["name"] == POLICY_NAME_VARIABLE]
    assert len(rows) == 1
    assert rows[0]["template"] == TEMPLATE_NAME

    seed_rows = _yaml("07i-seed-writer-approles.yml")["openbao_seed_writer_approles"]
    writers = [row for row in seed_rows if row["name"] == WRITER_NAME_VARIABLE]
    assert len(writers) == 1
    assert POLICY_NAME_VARIABLE in writers[0]["token_policies"]
    for row in seed_rows:
        if row is not writers[0]:
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
