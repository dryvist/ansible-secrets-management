"""The router-key catalog drives both generated secrets and their read paths."""

from pathlib import Path
import re

import jinja2
import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles/openbao/defaults/main/01c-app-secrets-generated.yml"
READ_DEFAULTS = ROOT / "roles/openbao/defaults/main/05c-terrakube-and-remaining-domain-names.yml"
EXCLUDED_DEFAULTS = ROOT / "roles/openbao/defaults/main/05h-cribl-edge-readers.yml"
GENERATION = ROOT / "roles/openbao/tasks/init/03-kv-mounts-and-seed-secrets.yml"
OPEN_LLM_POLICY = ROOT / "roles/openbao/templates/open-llm-policy.hcl.j2"
APPS_POLICY = ROOT / "roles/openbao/templates/apps-policy.hcl.j2"

DEFAULTS_DATA = yaml.safe_load(DEFAULTS.read_text(encoding="utf-8"))
READ_DATA = yaml.safe_load(READ_DEFAULTS.read_text(encoding="utf-8"))
EXCLUDED_DATA = yaml.safe_load(EXCLUDED_DEFAULTS.read_text(encoding="utf-8"))


def _render(value, variables):
    templar = Templar(loader=DataLoader())
    templar.available_variables = variables
    return templar.template(trust_as_template(value))


def _read_apps(router_catalog):
    return _render(
        READ_DATA["openbao_apps_read_apps"],
        {
            "openbao_generated_app_secrets": DEFAULTS_DATA["openbao_generated_app_secrets"],
            "openbao_promoted_app_secrets": {},
            "openbao_router_key_catalog": router_catalog,
            "openbao_apps_read_published_apps": READ_DATA["openbao_apps_read_published_apps"],
            "openbao_apps_read_excluded_generated_apps": EXCLUDED_DATA[
                "openbao_apps_read_excluded_generated_apps"
            ],
        },
    )


def _find_task(tasks, name):
    for task in tasks:
        if not isinstance(task, dict):
            continue
        if task.get("name") == name:
            return task
        for section in ("block", "rescue", "always"):
            if section in task:
                found = _find_task(task[section], name)
                if found is not None:
                    return found
    raise AssertionError(f"task {name!r} not found")


def _generation_loop():
    tasks = yaml.safe_load(GENERATION.read_text(encoding="utf-8"))
    task = _find_task(
        tasks,
        "Generate + seed per-app service secrets in OpenBao (generate-if-absent)",
    )
    return task["loop"]


def _render_apps_policy(router_catalog):
    environment = jinja2.Environment()
    environment.filters["comment"] = str
    return environment.from_string(APPS_POLICY.read_text(encoding="utf-8")).render(
        ansible_managed="",
        openbao_kv_mount="secret",
        openbao_apps_read_apps=_read_apps(router_catalog),
    )


def test_public_router_key_entries_remain_literal_and_allowlisted():
    assert DEFAULTS_DATA["openbao_router_key_catalog"] == {}
    generated = DEFAULTS_DATA["openbao_generated_app_secrets"]
    assert generated["agy"] == ["agy_llm_router_key"]
    assert generated["hermes-private"] == ["hermes_private_llm_router_key"]
    assert generated["zcode"] == ["zcode_llm_router_key"]
    assert generated["opencode"] == ["opencode_llm_router_key"]
    assert {"agy", "hermes-private", "zcode", "opencode"}.issubset(
        _read_apps({})
    )


def test_router_catalog_entries_feed_generation_and_the_apps_read_paths():
    catalog = {"contract-fixture": ["contract_fixture_llm_router_key"]}
    generated = _render(
        _generation_loop(),
        {
            "openbao_generated_app_secrets": DEFAULTS_DATA["openbao_generated_app_secrets"],
            "openbao_router_key_catalog": catalog,
        },
    )
    assert {entry["key"]: entry["value"] for entry in generated}["contract-fixture"] == catalog[
        "contract-fixture"
    ]
    assert set(_read_apps(catalog)) - set(_read_apps({})) == set(catalog)

    policy = _render_apps_policy(catalog)
    assert 'path "secret/data/apps/contract-fixture"' in policy
    assert 'path "secret/metadata/apps/contract-fixture"' in policy
    assert 'path "secret/data/apps/*"' not in policy
    assert 'path "secret/metadata/apps/*"' not in policy


def test_open_llm_fields_mirror_the_generated_router_fields():
    tasks = yaml.safe_load(GENERATION.read_text(encoding="utf-8"))
    source = _find_task(tasks, "Read generated router keys for the open-llm mirror")
    assert source["loop"] == [
        {"app": "zcode", "field": "zcode_llm_router_key"},
        {"app": "opencode", "field": "opencode_llm_router_key"},
    ]
    assert source["no_log"] is True

    capture = _find_task(tasks, "Capture generated router keys for the open-llm merge")
    assert capture["no_log"] is True
    assert capture["ansible.builtin.set_fact"] == {
        "openbao_zcode_router_key_source": "{{ openbao_open_llm_router_key_sources.results[0].stdout }}",
        "openbao_opencode_router_key_source": "{{ openbao_open_llm_router_key_sources.results[1].stdout }}",
    }
    merge = _find_task(tasks, "Merge generated router keys into open-llm")
    assert merge["vars"]["openbao_promote_fields"] == {
        "ZCODE_ROUTER_KEY": "openbao_zcode_router_key_source",
        "OPENCODE_ROUTER_KEY": "openbao_opencode_router_key_source",
    }


def test_open_llm_policy_reads_only_its_own_bucket():
    environment = jinja2.Environment()
    environment.filters["comment"] = str
    rendered = environment.from_string(OPEN_LLM_POLICY.read_text(encoding="utf-8")).render(
        ansible_managed="",
        openbao_kv_mount="secret",
        openbao_github_agents_mount="github",
        openbao_github_agents_installation_id="",
    )
    app_paths = [
        path
        for path in re.findall(r'^path "([^"]+)"', rendered, re.MULTILINE)
        if re.match(r"secret/(?:data|metadata)/apps/", path)
    ]
    assert sorted(app_paths) == [
        "secret/data/apps/open-llm",
        "secret/metadata/apps/open-llm",
    ]
