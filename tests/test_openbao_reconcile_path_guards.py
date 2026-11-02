"""KV path validation and template guards reject unsafe inputs."""

from openbao_reconcile_bounds_helpers import (
    ROOT,
    _templar,
    _trust,
)
import pytest
import yaml

from ansible.template import trust_as_template

POLICY_SYNC = ROOT / "roles/openbao/tasks/init/02b-policy-sync.yml"

@pytest.mark.parametrize(
    ("key", "valid"),
    [
        ("apps/open-llm/nested_key.v1", True),
        ("apps/bad*key", False),
        ("apps/bad+key", False),
        ('apps/bad"key', False),
        ("apps/foo..bar", False),
        ("/apps/open-llm", False),
        ("apps/open-llm/", False),
        ("apps/bad key", False),
    ],
)
def test_kv_path_assert_accepts_only_literal_nested_components(key, valid):
    tasks = yaml.safe_load(POLICY_SYNC.read_text(encoding="utf-8"))
    guard = next(
        task for task in tasks
        if task.get("name") == "Assert reconcile KV grant keys are literal path components"
    )
    conditions = guard["ansible.builtin.assert"]["that"]
    templar = _templar(_trust({"item": key}))

    results = [
        templar.template(trust_as_template("{{ " + condition + " }}"))
        for condition in conditions
    ]
    assert all(result is True or result == "True" for result in results) is valid

def test_path_guard_covers_template_sources_and_precedes_policy_write():
    tasks = yaml.safe_load(POLICY_SYNC.read_text(encoding="utf-8"))
    names = [task.get("name") for task in tasks]
    collect = next(
        task for task in tasks
        if task.get("name") == "Collect the KV keys used by the reconcile policy"
    )
    seed_paths = next(
        task for task in tasks
        if task.get("name") == "Add the generated seed paths used by the reconcile policy"
    )
    rotation_paths = next(
        task for task in tasks
        if task.get("name")
        == "Add the rotation-exempt mount and path components used by the reconcile policy"
    )
    guard_name = "Assert reconcile KV grant keys are literal path components"
    write_name = "Sync the reconcile policy from the declared set (policy-sync)"

    collection = collect["ansible.builtin.set_fact"]["openbao_reconcile_kv_policy_keys"]
    for variable in (
        "openbao_promoted_app_secrets",
        "openbao_promoted_external_secrets",
        "openbao_promoted_config_values",
        "openbao_seeded_generated_app_secrets",
        "openbao_roster_agent_generated_app_secrets",
        "openbao_caller_gateway_generated_app_secrets",
    ):
        assert variable in collection
    assert "openbao_generated_app_secret_paths" in str(
        seed_paths["ansible.builtin.set_fact"]
    )
    assert "openbao_rotation_exempt" in str(rotation_paths)
    assert names.index(guard_name) < names.index(write_name)
