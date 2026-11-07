"""Run the collection's selector with local, credential-free fixtures."""

import json
import os
import shutil
import subprocess

import pytest
import yaml

from test_openbao_select import ROOT

POLICY_TASKS = ROOT / "roles/openbao/tasks/init/08-rbac-policies.yml"


def _task(name):
    return next(
        task for task in yaml.safe_load(POLICY_TASKS.read_text(encoding="utf-8"))
        if task.get("name") == name
    )


def _run_policy_render(tmp_path, selection, candidates, expected_names):
    collection_root = tmp_path / "collections"
    namespace = collection_root / "ansible_collections/dryvist"
    namespace.mkdir(parents=True)
    (namespace / "secrets_management").symlink_to(ROOT, target_is_directory=True)

    select = _task("Select RBAC policy objects")
    select["ansible.builtin.import_tasks"] = str(
        ROOT / "roles/openbao/tasks/init/select-objects.yml"
    )
    tasks = [
        select,
        _task("Keep the selected RBAC policy objects"),
        _task("Render the RBAC policies on the controller"),
        _task("Assert no scheduled RBAC policy rendered empty"),
        {"name": "Assert only expected policy templates rendered", "ansible.builtin.assert": {
            "that": ["openbao_rendered_policy_map.keys() | list | sort == expected_names"]}},
        {"name": "Write marker after the empty-render guard", "ansible.builtin.debug": {
            "msg": "WRITE_PHASE_REACHED"}},
    ]
    playbook = tmp_path / "render.yml"
    playbook.write_text(yaml.safe_dump([{
        "name": "Verify selected RBAC policy rendering",
        "hosts": "localhost", "connection": "local", "gather_facts": False,
        "tasks": tasks,
    }]))
    variables = {
        "openbao_select": {"policies": [selection]} if selection else {},
        "openbao_select_max": 25,
        "openbao_bootstrap_token": "s.test",
        "openbao_policies": candidates,
        "openbao_reachable_policies": candidates,
        "expected_names": expected_names,
    }
    return subprocess.run(
        [shutil.which("ansible-playbook"), "-i", "localhost,", str(playbook),
         "-e", json.dumps(variables)],
        cwd=ROOT, env={**os.environ, "ANSIBLE_COLLECTIONS_PATH": str(collection_root)},
        text=True, capture_output=True, timeout=60, check=False,
    )


@pytest.mark.parametrize(("selection", "cap", "expected", "failure"), [
    ({"policies": ["apps"]}, 25, {"policies": [{"name": "apps"}], "approles": []}, ""),
    ({"policies": ["read-*"], "approles": ["backup"]}, 25,
     {"policies": [{"name": "read-apps"}], "approles": [{"name": "backup"}]}, ""),
    ({"policies": ["unknown-*"]}, 25, {}, "unknown-*"),
    ({"policies": ["*"], "approles": ["backup"]}, 2, {}, "exceeding openbao_select_max=2"),
    ({}, 1, {"policies": [{"name": "apps"}, {"name": "read-apps"}], "approles": [{"name": "backup"}]}, ""),
])
def test_native_collection_selection(tmp_path, selection, cap, expected, failure):
    output, returncode = _run_selection(tmp_path, {"openbao_select": selection}, cap, expected)
    if failure:
        assert returncode != 0 and failure in output, output
        assert "TASK [Assert the selected targets]" not in output
    else:
        assert returncode == 0, output


@pytest.mark.parametrize(("inputs", "expected"), [
    ({"openbao_rbac_policy_name": "apps"}, {"policies": [{"name": "apps"}], "approles": []}),
    ({"openbao_approle_config_name": "backup"}, {"policies": [], "approles": [{"name": "backup"}]}),
])
def test_retired_inputs_still_select_one_object(tmp_path, inputs, expected):
    output, returncode = _run_selection(tmp_path, inputs, 25, expected)
    assert returncode == 0, output


def test_retired_input_beside_the_selection_is_refused(tmp_path):
    inputs = {"openbao_rbac_policy_name": "apps", "openbao_select": {"approles": ["backup"]}}
    output, returncode = _run_selection(tmp_path, inputs, 25, {})
    assert returncode != 0 and "Use openbao_select alone" in output, output


def _run_selection(tmp_path, inputs, cap, expected):
    collection_root = tmp_path / "collections"
    namespace = collection_root / "ansible_collections/dryvist"
    namespace.mkdir(parents=True)
    (namespace / "secrets_management").symlink_to(ROOT, target_is_directory=True)
    playbook = tmp_path / "select.yml"
    playbook.write_text(yaml.safe_dump([{
        "name": "Verify object selection",
        "hosts": "localhost", "connection": "local", "gather_facts": False,
        "tasks": [
            # An absolute import keeps the file-relative nested includes the real play uses,
            # which tasks_from would not, and leaves out role dependencies selection never reads.
            {"name": "Resolve selection through the role's task files",
             "ansible.builtin.import_tasks": str(ROOT / "roles/openbao/tasks/init/selection-preflight.yml"),
             "tags": ["always"]},
            {"name": "Assert the selected targets", "ansible.builtin.assert": {
                "that": ["openbao_selected_objects == expected"]}, "tags": ["always"]},
        ],
    }]))
    variables = {
        **inputs, "openbao_select_max": cap, "expected": expected,
        "openbao_cli_host": "localhost",
        "openbao_select_profiles": {
            "policies": {"candidates": [{"name": "apps"}, {"name": "read-apps"}]},
            "approles": {"candidates": [{"name": "backup"}]},
        },
    }
    result = subprocess.run(
        [shutil.which("ansible-playbook"), "-i", "localhost,", str(playbook),
         "--tags", "openbao_rbac", "-e", json.dumps(variables)],
        cwd=ROOT, env={**os.environ, "ANSIBLE_COLLECTIONS_PATH": str(collection_root)},
        text=True, capture_output=True, timeout=60, check=False,
    )
    return result.stdout + result.stderr, result.returncode


def test_policy_render_is_scoped_before_templates_are_evaluated(tmp_path):
    selected_template = tmp_path / "selected.hcl.j2"
    selected_template.write_text('path "test/selected" { capabilities = ["read"] }\n')
    broken_template = tmp_path / "broken.hcl.j2"
    broken_template.write_text("{% if %}\n")
    empty_template = tmp_path / "empty.hcl.j2"
    empty_template.write_text("# no path stanza\n")
    second_template = tmp_path / "second.hcl.j2"
    second_template.write_text('path "test/second" { capabilities = ["read"] }\n')

    selective = _run_policy_render(tmp_path / "selective", "selected", [
        {"name": "selected", "template": str(selected_template)},
        {"name": "unselected", "template": str(broken_template)},
    ], ["selected"])
    assert selective.returncode == 0, selective.stdout + selective.stderr
    assert "WRITE_PHASE_REACHED" in selective.stdout

    empty = _run_policy_render(tmp_path / "empty", "empty", [
        {"name": "empty", "template": str(empty_template)},
        {"name": "other", "template": str(second_template)},
    ], ["empty"])
    empty_output = empty.stdout + empty.stderr
    assert empty.returncode != 0 and "rendered with no" in empty_output, empty_output
    assert "WRITE_PHASE_REACHED" not in empty_output

    full = _run_policy_render(tmp_path / "full", "", [
        {"name": "selected", "template": str(selected_template)},
        {"name": "second", "template": str(second_template)},
    ], ["second", "selected"])
    assert full.returncode == 0, full.stdout + full.stderr
    assert "WRITE_PHASE_REACHED" in full.stdout
