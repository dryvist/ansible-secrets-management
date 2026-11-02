"""Agent-tier reader and reconcile grants stay on their declared leaves."""

import ast
from pathlib import Path
import re

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles/openbao/defaults/main"
TEMPLATES = ROOT / "roles/openbao/templates"


def _defaults():
    values = {}
    for path in sorted(DEFAULTS.glob("*.yml")):
        values.update(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    return values


def _render(expression, values):
    templar = jinja2.Environment(undefined=jinja2.StrictUndefined)
    return templar.from_string(expression).render(**values)


def _grants(rendered):
    return {
        (path, tuple(re.findall(r'"([^"]+)"', capabilities)))
        for path, capabilities in re.findall(
            r'path "([^"]+)"\s*\{\s*capabilities\s*=\s*\[([^]]+)\]\s*\}',
            rendered,
        )
    }


def test_generated_credentials_are_declared_only_on_agent_tier_leaves():
    values = _defaults()
    generated = _render(values["openbao_app_agent_tier_generated_app_secrets"], values)
    generated = yaml.safe_load(generated)
    base = values["openbao_generated_app_secrets"]
    for reader in values["openbao_app_agent_tier_readers"]:
        if reader.get("generated_fields"):
            assert generated[f"agent-tier-{reader['tier']}"] == reader["generated_fields"]
        if reader.get("login_fields"):
            assert generated[f"agent-tier-login-{reader['tier']}"] == reader["login_fields"]
        for field in reader.get("generated_fields", []) + reader.get("login_fields", []):
            assert sum(field in fields for fields in generated.values()) == 1
            assert field not in base.get("vikunja", [])
            assert field not in base.get("zammad", [])


def test_agent_tier_mount_is_provisioned_outside_shared_wildcard_mounts():
    values = _defaults()
    assert values["openbao_agent_tier_mount"] not in {
        mount["path"] for mount in values["openbao_kv_mounts"]
    }
    task = (ROOT / "roles/openbao/tasks/init/03-kv-mounts-and-seed-secrets.yml").read_text(
        encoding="utf-8"
    )
    assert "Enable the dedicated agent-tier KV v2 mount (add-if-missing)" in task
    assert "bao secrets enable -path={{ openbao_agent_tier_mount }} -version=2 kv" in task


def test_reader_policy_grants_only_its_exact_data_and_metadata_leaf():
    values = _defaults()
    login_paths = ast.literal_eval(
        _render(values["openbao_app_agent_tier_login_paths"], values).strip()
    )
    assert login_paths == [
        reader["login_path"]
        for reader in values["openbao_app_agent_tier_readers"]
        if reader.get("login_path")
    ]
    source = (TEMPLATES / "app-agent-tier-reader-policy.hcl.j2").read_text(
        encoding="utf-8"
    )
    environment = jinja2.Environment()
    environment.filters["comment"] = str
    for reader in values["openbao_app_agent_tier_readers"]:
        rendered = environment.from_string(source).render(
            ansible_managed="", openbao_agent_tier_mount="agent-tier", item=reader
        )
        assert _grants(rendered) == {
            (f"agent-tier/data/{reader['tier']}", ("read",)),
            (f"agent-tier/metadata/{reader['tier']}", ("read",)),
        }
        if reader.get("login_path"):
            assert reader["login_path"] not in rendered
            assert not any(reader["login_path"] in path for path, _caps in _grants(rendered))
        assert not any("list" in capabilities for _path, capabilities in _grants(rendered))
        for other in values["openbao_app_agent_tier_readers"]:
            if other["tier"] != reader["tier"]:
                assert other["tier"] not in rendered


def test_reconcile_grant_has_no_list_or_other_agent_tier_path():
    values = _defaults()
    source = (TEMPLATES / "openbao-reconcile-policy.hcl.j2").read_text(
        encoding="utf-8"
    )
    loop = re.search(
        r"{% for reader in openbao_app_agent_tier_readers %}.*?{% endfor %}",
        source,
        re.DOTALL,
    )
    assert loop
    rendered = jinja2.Environment().from_string(loop.group(0)).render(
        openbao_agent_tier_mount="agent-tier",
        openbao_app_agent_tier_readers=values["openbao_app_agent_tier_readers"],
    )
    expected = set()
    for reader in values["openbao_app_agent_tier_readers"]:
        expected.add(
            (f"agent-tier/data/{reader['tier']}", ("create", "read", "update"))
        )
        expected.add((f"agent-tier/metadata/{reader['tier']}", ("read",)))
        if reader.get("login_path"):
            expected.add(
                (f"agent-tier/data/{reader['login_path']}", ("create", "read", "update"))
            )
            expected.add((f"agent-tier/metadata/{reader['login_path']}", ("read",)))
    assert _grants(rendered) == expected
    assert "list" not in rendered
    assert "*" not in rendered
    assert "+" not in rendered
    assert source.count("openbao_agent_tier_mount") == 4


def test_legacy_removal_is_field_scoped_and_uses_kv_check_and_set():
    task = (ROOT / "roles/openbao/tasks/remove_app_agent_legacy_fields.yml").read_text(
        encoding="utf-8"
    )
    declarations = _defaults()["openbao_app_agent_tier_readers"]
    fields = [
        field
        for row in declarations
        for field in row.get("generated_fields", []) + row.get("login_fields", [])
    ]
    assert "status_code: [200, 403, 404]" in task
    assert "rejectattr('key', 'in', openbao_agent_tier_legacy_remove_fields)" in task
    assert "cas:" in task
    assert "changed_when: true" in task
    assert "no_log: true" in task
    assert fields == [
        "vikunja_agent_read_password",
        "vikunja_agent_write_password",
        "zammad_agent_write_api_token",
    ]
    assert "login_path | default(openbao_agent_tier_reader.tier)" in task
    assert "Remove the migrated password from the token leaf" in task
    assert "_login.get(_field, '') | string == _token.get(_field, '') | string" in task
    assert "openbao_agent_tier_reader.generated_fields" in task
    assert "openbao_agent_tier_reader.login_fields" in task
